# src/backtest/simulator/generic_runner.py
from __future__ import annotations

from dataclasses import replace

from backtest.csv_loader import HistoricalBarDataset
from backtest.simulator.models import (
    BacktestResult,
    BacktestSimulationError,
    ExecutedTrade,
    SimulatedPosition,
)
from mt4_bridge.models import Bar, SignalAction, SignalDecision
from mt4_bridge.signal_engine import (
    SignalEngineError,
    evaluate_signals,
    get_required_bars,
)


class GenericRunnerMixin:
    def _run_generic_path(
        self,
        dataset: HistoricalBarDataset,
        close_open_position_at_end: bool,
    ) -> BacktestResult:
        required_bars = get_required_bars(self._strategy_name)
        if len(dataset.rows) < required_bars:
            raise BacktestSimulationError(
                f"Dataset has {len(dataset.rows)} bars but strategy "
                f"{self._strategy_name} requires at least {required_bars} bars"
            )

        range_position: SimulatedPosition | None = None
        trend_position: SimulatedPosition | None = None
        legacy_position: SimulatedPosition | None = None

        executed_trades: list[ExecutedTrade] = []
        decision_logs = []
        processed_bars = 0
        next_ticket = 1
        bars_buffer: list[Bar] = []

        range_reentry_blocks = self._create_range_reentry_blocks()

        for current_bar_index, current_row in enumerate(dataset.rows):
            bars_buffer.append(self._build_bar(current_row))

            if len(bars_buffer) < required_bars:
                continue

            if self._is_multi_lane_strategy():
                range_position = self._advance_position_bar_index(range_position)
                trend_position = self._advance_position_bar_index(trend_position)

                if range_position is not None:
                    range_position = self._update_position_excursion(
                        range_position, current_row.high, current_row.low,
                    )
                    intrabar_trade = self._check_intrabar_exit(
                        simulated_position=range_position,
                        current_row=current_row,
                        current_bar_index=current_bar_index,
                    )
                    if intrabar_trade is not None:
                        executed_trades.append(intrabar_trade)
                        self._update_range_sl_streak_from_trade(
                            range_reentry_blocks=range_reentry_blocks,
                            trade=intrabar_trade,
                        )
                        range_position = None

                if trend_position is not None:
                    trend_position = self._update_position_excursion(
                        trend_position, current_row.high, current_row.low,
                    )
                    intrabar_trade = self._check_intrabar_exit(
                        simulated_position=trend_position,
                        current_row=current_row,
                        current_bar_index=current_bar_index,
                    )
                    if intrabar_trade is not None:
                        executed_trades.append(intrabar_trade)
                        trend_position = None
            else:
                legacy_position = self._advance_position_bar_index(legacy_position)

                if legacy_position is not None:
                    legacy_position = self._update_position_excursion(
                        legacy_position, current_row.high, current_row.low,
                    )
                    intrabar_trade = self._check_intrabar_exit(
                        simulated_position=legacy_position,
                        current_row=current_row,
                        current_bar_index=current_bar_index,
                    )
                    if intrabar_trade is not None:
                        executed_trades.append(intrabar_trade)
                        legacy_position = None
                        processed_bars += 1
                        continue

            market_snapshot = self._build_market_snapshot_from_bars(
                bars=bars_buffer,
                latest_row=current_row,
                digits=dataset.digits,
                point=dataset.point,
            )
            position_snapshot = self._build_position_snapshot(
                range_position=range_position,
                trend_position=trend_position,
                legacy_position=legacy_position,
            )

            try:
                raw_decisions = evaluate_signals(
                    market_snapshot=market_snapshot,
                    position_snapshot=position_snapshot,
                    strategy_name=self._strategy_name,
                )

                if self._is_multi_lane_strategy():
                    self._release_range_reentry_blocks_by_middle_cross(
                        range_reentry_blocks=range_reentry_blocks,
                        decisions=raw_decisions,
                    )
                    decisions = self._select_lane_decisions(raw_decisions)
                    decisions = [
                        self._apply_range_reentry_block_to_decision(
                            decision=decision,
                            range_reentry_blocks=range_reentry_blocks,
                        )
                        for decision in decisions
                    ]
                else:
                    decisions = raw_decisions
            except SignalEngineError as exc:
                raise BacktestSimulationError(
                    f"Signal evaluation failed at {current_row.time}: {exc}"
                ) from exc

            for decision in decisions:
                decision_logs.append(
                    self._build_decision_log(
                        current_row=current_row,
                        decision=decision,
                        range_position=range_position,
                        trend_position=trend_position,
                        legacy_position=legacy_position,
                    )
                )

                # accumulate unsuitable-bar counters on held positions
                range_position = self._update_unsuitable_bars(range_position, decision)
                trend_position = self._update_unsuitable_bars(trend_position, decision)
                legacy_position = self._update_unsuitable_bars(legacy_position, decision)

                if self._is_multi_lane_strategy():
                    (
                        range_position,
                        trend_position,
                        new_trade,
                        next_ticket,
                    ) = self._apply_multi_lane_decision(
                        current_row=current_row,
                        decision=decision,
                        range_position=range_position,
                        trend_position=trend_position,
                        next_ticket=next_ticket,
                        point=dataset.point,
                        current_bar_index=current_bar_index,
                    )
                else:
                    (
                        legacy_position,
                        new_trade,
                        next_ticket,
                    ) = self._apply_single_position_decision(
                        current_row=current_row,
                        decision=decision,
                        simulated_position=legacy_position,
                        next_ticket=next_ticket,
                        point=dataset.point,
                        current_bar_index=current_bar_index,
                    )

                if new_trade is not None:
                    executed_trades.append(new_trade)
                    if self._is_multi_lane_strategy():
                        self._update_range_sl_streak_from_trade(
                            range_reentry_blocks=range_reentry_blocks,
                            trade=new_trade,
                        )

            processed_bars += 1

        if close_open_position_at_end:
            final_row = dataset.rows[-1]
            final_bar_index = len(dataset.rows) - 1

            if self._is_multi_lane_strategy():
                if range_position is not None:
                    forced_trade = self._close_position(
                        simulated_position=range_position,
                        exit_time=final_row.time,
                        exit_price=final_row.close,
                        exit_reason="forced_end_of_data",
                        exit_decision=None,
                        exit_absolute_bar_index=final_bar_index,
                    )
                    executed_trades.append(forced_trade)
                    range_position = None

                if trend_position is not None:
                    forced_trade = self._close_position(
                        simulated_position=trend_position,
                        exit_time=final_row.time,
                        exit_price=final_row.close,
                        exit_reason="forced_end_of_data",
                        exit_decision=None,
                        exit_absolute_bar_index=final_bar_index,
                    )
                    executed_trades.append(forced_trade)
                    trend_position = None
            else:
                if legacy_position is not None:
                    forced_trade = self._close_position(
                        simulated_position=legacy_position,
                        exit_time=final_row.time,
                        exit_price=final_row.close,
                        exit_reason="forced_end_of_data",
                        exit_decision=None,
                        exit_absolute_bar_index=final_bar_index,
                    )
                    executed_trades.append(forced_trade)
                    legacy_position = None

        final_open_position_label = self._build_final_open_position_label(
            range_position=range_position,
            trend_position=trend_position,
            legacy_position=legacy_position,
        )

        stats = self._build_stats(
            total_bars=len(dataset.rows),
            processed_bars=processed_bars,
            executed_trades=executed_trades,
            final_open_position_type=final_open_position_label,
        )
        return BacktestResult(
            stats=stats,
            trades=executed_trades,
            state_segments=[],
            decision_logs=decision_logs,
        )

    def _advance_position_bar_index(
        self,
        simulated_position: SimulatedPosition | None,
    ) -> SimulatedPosition | None:
        if simulated_position is None:
            return None
        return replace(
            simulated_position,
            entry_bar_index=simulated_position.entry_bar_index + 1,
        )

    def _update_unsuitable_bars(
        self,
        simulated_position: SimulatedPosition | None,
        decision: SignalDecision,
    ) -> SimulatedPosition | None:
        if simulated_position is None:
            return None
        obs = decision.debug_metrics
        if not isinstance(obs, dict):
            return simulated_position
        band_walk = bool(obs.get("range_unsuitable_flag_band_walk"))
        one_side = bool(obs.get("range_unsuitable_flag_one_side_stay"))
        bandwidth = bool(obs.get("range_unsuitable_flag_bandwidth_expansion"))
        slope_accel = bool(obs.get("range_unsuitable_flag_slope_acceleration"))
        if not (band_walk or one_side or bandwidth or slope_accel):
            return simulated_position
        return replace(
            simulated_position,
            unsuitable_bars_band_walk=(
                simulated_position.unsuitable_bars_band_walk + (1 if band_walk else 0)
            ),
            unsuitable_bars_one_side_stay=(
                simulated_position.unsuitable_bars_one_side_stay + (1 if one_side else 0)
            ),
            unsuitable_bars_bandwidth_expansion=(
                simulated_position.unsuitable_bars_bandwidth_expansion
                + (1 if bandwidth else 0)
            ),
            unsuitable_bars_slope_acceleration=(
                simulated_position.unsuitable_bars_slope_acceleration
                + (1 if slope_accel else 0)
            ),
            unsuitable_bars_total=simulated_position.unsuitable_bars_total + 1,
        )

    def _normalize_decisions(
        self,
        result: SignalDecision | list[SignalDecision],
    ) -> list[SignalDecision]:
        if isinstance(result, list):
            return result
        return [result]

    def _select_lane_decisions(
        self,
        decisions: list[SignalDecision],
    ) -> list[SignalDecision]:
        range_decision: SignalDecision | None = None
        trend_decision: SignalDecision | None = None
        legacy_decision: SignalDecision | None = None

        for decision in decisions:
            lane = (decision.entry_lane or "legacy").strip().lower()

            if lane == "range" and range_decision is None:
                range_decision = decision
            elif lane == "trend" and trend_decision is None:
                trend_decision = decision
            elif lane == "legacy" and legacy_decision is None:
                legacy_decision = decision

        selected: list[SignalDecision] = []
        if range_decision is not None:
            selected.append(range_decision)
        if trend_decision is not None:
            selected.append(trend_decision)
        if legacy_decision is not None:
            selected.append(legacy_decision)
        return selected

    def _create_range_reentry_blocks(
        self,
    ) -> dict[str, dict[str, int | bool | str | None]]:
        return {
            "buy": {
                "sl_streak": 0,
                "active": False,
                "trigger_exit_reason": None,
            },
            "sell": {
                "sl_streak": 0,
                "active": False,
                "trigger_exit_reason": None,
            },
        }

    def _update_range_sl_streak_from_trade(
        self,
        *,
        range_reentry_blocks: dict[str, dict[str, int | bool | str | None]],
        trade: ExecutedTrade,
    ) -> None:
        if trade.lane != "range":
            return
        if trade.position_type not in {"buy", "sell"}:
            return

        side = trade.position_type
        block = range_reentry_blocks[side]

        if trade.exit_reason.startswith("sl"):
            next_streak = int(block["sl_streak"]) + 1
            block["sl_streak"] = next_streak
            block["trigger_exit_reason"] = trade.exit_reason
            block["active"] = next_streak >= 2
            return

        block["sl_streak"] = 0
        block["active"] = False
        block["trigger_exit_reason"] = trade.exit_reason

    def _release_range_reentry_blocks_by_middle_cross(
        self,
        *,
        range_reentry_blocks: dict[str, dict[str, int | bool | str | None]],
        decisions: list[SignalDecision],
    ) -> None:
        range_decision = self._extract_range_decision(decisions)
        if range_decision is None:
            return

        middle_band = range_decision.middle_band
        previous_close = range_decision.previous_close
        latest_close = range_decision.latest_close

        if middle_band is None:
            return

        if self._is_middle_cross_up(
            previous_close=previous_close,
            latest_close=latest_close,
            middle_band=middle_band,
        ):
            self._clear_range_reentry_block(
                range_reentry_blocks=range_reentry_blocks,
                side="buy",
            )

        if self._is_middle_cross_down(
            previous_close=previous_close,
            latest_close=latest_close,
            middle_band=middle_band,
        ):
            self._clear_range_reentry_block(
                range_reentry_blocks=range_reentry_blocks,
                side="sell",
            )

    def _extract_range_decision(
        self,
        decisions: list[SignalDecision],
    ) -> SignalDecision | None:
        for decision in decisions:
            lane = (decision.entry_lane or "").strip().lower()
            if lane == "range":
                return decision
        return None

    @staticmethod
    def _is_middle_cross_up(
        *,
        previous_close: float,
        latest_close: float,
        middle_band: float,
    ) -> bool:
        return previous_close < middle_band and latest_close >= middle_band

    @staticmethod
    def _is_middle_cross_down(
        *,
        previous_close: float,
        latest_close: float,
        middle_band: float,
    ) -> bool:
        return previous_close > middle_band and latest_close <= middle_band

    def _clear_range_reentry_block(
        self,
        *,
        range_reentry_blocks: dict[str, dict[str, int | bool | str | None]],
        side: str,
    ) -> None:
        range_reentry_blocks[side]["sl_streak"] = 0
        range_reentry_blocks[side]["active"] = False
        range_reentry_blocks[side]["trigger_exit_reason"] = None

    def _apply_range_reentry_block_to_decision(
        self,
        *,
        decision: SignalDecision,
        range_reentry_blocks: dict[str, dict[str, int | bool | str | None]],
    ) -> SignalDecision:
        lane = (decision.entry_lane or "").strip().lower()
        if lane != "range":
            return decision

        if decision.action == SignalAction.BUY:
            side = "buy"
        elif decision.action == SignalAction.SELL:
            side = "sell"
        else:
            return decision

        block = range_reentry_blocks[side]
        if not bool(block["active"]):
            return decision

        sl_streak = int(block["sl_streak"])
        trigger_exit_reason = block["trigger_exit_reason"]

        return replace(
            decision,
            action=SignalAction.HOLD,
            reason=(
                "range reentry blocked after consecutive SL"
                f" (blocked_side={side}, sl_streak={sl_streak},"
                f" unblock_condition=middle_band_cross,"
                f" trigger_exit_reason={trigger_exit_reason})"
                f" | original_reason={decision.reason}"
            ),
        )