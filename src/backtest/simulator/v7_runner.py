# src/backtest/simulator/v7_runner.py
from __future__ import annotations

from backtest.csv_loader import HistoricalBarDataset
from backtest.simulator.models import (
    BacktestResult,
    BacktestSimulationError,
    SimulatedPosition,
    StateSegment,
)
from mt4_bridge.models import Bar, SignalAction, SignalDecision
from mt4_bridge.signal_engine import SignalEngineError
from mt4_bridge.strategies.bollinger_range_v7 import (
    EXIT_ON_RANGE_MIDDLE_BAND,
    _build_decision as build_v7_decision,
    _range_buy_confirmed as range_buy_confirmed_v7,
    _range_sell_confirmed as range_sell_confirmed_v7,
    _trend_buy_confirmed as trend_buy_confirmed_v7,
    _trend_sell_confirmed as trend_sell_confirmed_v7,
)
from mt4_bridge.strategies.bollinger_range_v7_1 import (
    _build_decision as build_v7_1_decision,
    _is_entry_event_allowed as is_v7_1_entry_event_allowed,
    _range_buy_confirmed as range_buy_confirmed_v7_1,
    _range_sell_confirmed as range_sell_confirmed_v7_1,
    _trend_buy_confirmed as trend_buy_confirmed_v7_1,
    _trend_sell_confirmed as trend_sell_confirmed_v7_1,
)
from mt4_bridge.strategies.v7_features import required_bars_for_v7_features
from mt4_bridge.strategies.v7_state_detector import (
    advance_v7_state_context_from_bars,
    initialize_v7_state_context_from_bars,
)
from mt4_bridge.strategies.v7_state_models import (
    V7_DEFAULT_PARAMS,
    V7MarketState,
    V7StateContext,
)


class V7RunnerMixin:
    def _run_v7_fast_path(
        self,
        dataset: HistoricalBarDataset,
        close_open_position_at_end: bool,
    ) -> BacktestResult:
        params = V7_DEFAULT_PARAMS
        required_bars = required_bars_for_v7_features(params)
        if len(dataset.rows) < required_bars:
            raise BacktestSimulationError(
                f"Dataset has {len(dataset.rows)} bars but strategy "
                f"{self._strategy_name} requires at least {required_bars} bars"
            )

        bars_buffer: list[Bar] = []
        simulated_position: SimulatedPosition | None = None
        executed_trades = []
        decision_logs = []
        processed_bars = 0
        next_ticket = 1
        state_context: V7StateContext | None = None
        state_segments: list[StateSegment] = []
        current_segment_state: str | None = None
        current_segment_start_time = None

        for current_row in dataset.rows:
            bars_buffer.append(self._build_bar(current_row))

            if len(bars_buffer) < required_bars:
                continue

            if simulated_position is not None:
                simulated_position = self._update_position_excursion(
                    simulated_position, current_row.high, current_row.low,
                )
                intrabar_trade = self._check_intrabar_exit(
                    simulated_position=simulated_position,
                    current_row=current_row,
                )
                if intrabar_trade is not None:
                    executed_trades.append(intrabar_trade)
                    simulated_position = None
                    processed_bars += 1
                    continue

            try:
                if state_context is None:
                    state_decision = initialize_v7_state_context_from_bars(
                        bars_buffer,
                        params,
                    )
                else:
                    state_decision = advance_v7_state_context_from_bars(
                        bars_buffer,
                        state_context,
                        params,
                    )
            except SignalEngineError as exc:
                raise BacktestSimulationError(
                    f"V7 fast-path state evaluation failed at {current_row.time}: {exc}"
                ) from exc

            confirmed_state_value = state_decision.confirmed_state.value
            if current_segment_state is None:
                current_segment_state = confirmed_state_value
                current_segment_start_time = current_row.time
            elif confirmed_state_value != current_segment_state:
                state_segments.append(
                    StateSegment(
                        start_time=current_segment_start_time,
                        end_time=current_row.time,
                        state=current_segment_state,
                    )
                )
                current_segment_state = confirmed_state_value
                current_segment_start_time = current_row.time

            state_context = V7StateContext(
                confirmed_state=state_decision.confirmed_state,
                candidate_state=state_decision.candidate_state,
                confirmed_state_age=state_decision.confirmed_state_age,
                candidate_state_age=state_decision.candidate_state_age,
                last_range_score=state_decision.score_snapshot.range_score,
                last_transition_up_score=(
                    state_decision.score_snapshot.transition_to_trend_up_score
                ),
                last_transition_down_score=(
                    state_decision.score_snapshot.transition_to_trend_down_score
                ),
                last_trend_up_score=state_decision.score_snapshot.trend_up_score,
                last_trend_down_score=state_decision.score_snapshot.trend_down_score,
            )

            try:
                decision = self._evaluate_v7_fast_decision(
                    bars=bars_buffer,
                    state_decision=state_decision,
                    simulated_position=simulated_position,
                    point=dataset.point,
                )
            except SignalEngineError as exc:
                raise BacktestSimulationError(
                    f"V7 fast-path signal evaluation failed at {current_row.time}: {exc}"
                ) from exc

            decision_logs.append(
                self._build_decision_log(
                    current_row=current_row,
                    decision=decision,
                    range_position=None,
                    trend_position=None,
                    legacy_position=simulated_position,
                )
            )

            (
                simulated_position,
                new_trade,
                next_ticket,
            ) = self._apply_single_position_decision(
                current_row=current_row,
                decision=decision,
                simulated_position=simulated_position,
                next_ticket=next_ticket,
                point=dataset.point,
            )
            if new_trade is not None:
                executed_trades.append(new_trade)

            processed_bars += 1

        if (
            current_segment_state is not None
            and current_segment_start_time is not None
            and dataset.rows
        ):
            state_segments.append(
                StateSegment(
                    start_time=current_segment_start_time,
                    end_time=dataset.rows[-1].time,
                    state=current_segment_state,
                )
            )

        if close_open_position_at_end and simulated_position is not None:
            final_row = dataset.rows[-1]
            forced_trade = self._close_position(
                simulated_position=simulated_position,
                exit_time=final_row.time,
                exit_price=final_row.close,
                exit_reason="forced_end_of_data",
                exit_decision=None,
            )
            executed_trades.append(forced_trade)
            simulated_position = None

        stats = self._build_stats(
            total_bars=len(dataset.rows),
            processed_bars=processed_bars,
            executed_trades=executed_trades,
            final_open_position_type=(
                simulated_position.position_type
                if simulated_position is not None
                else None
            ),
        )
        return BacktestResult(
            stats=stats,
            trades=executed_trades,
            state_segments=state_segments,
            decision_logs=decision_logs,
        )

    def _compute_previous_bollinger_bands_from_bars(
        self,
        bars: list[Bar],
    ) -> tuple[float, float, float]:
        params = V7_DEFAULT_PARAMS
        period = params.feature.bollinger_period
        sigma = params.feature.bollinger_sigma

        if len(bars) < period + 1:
            raise SignalEngineError(
                f"At least {period + 1} bars are required for previous bands"
            )

        previous_closes = [bar.close for bar in bars[:-1]]
        previous_window = previous_closes[-period:]
        previous_middle = sum(previous_window) / len(previous_window)
        previous_std = (
            sum((value - previous_middle) ** 2 for value in previous_window)
            / len(previous_window)
        ) ** 0.5
        previous_upper = previous_middle + (sigma * previous_std)
        previous_lower = previous_middle - (sigma * previous_std)
        return previous_middle, previous_upper, previous_lower

    def _evaluate_v7_fast_decision(
        self,
        *,
        bars: list[Bar],
        state_decision,
        simulated_position: SimulatedPosition | None,
        point: float,
    ) -> SignalDecision:
        if self._strategy_name == "bollinger_range_v7":
            return self._evaluate_v7_fast_decision_v7(
                bars=bars,
                state_decision=state_decision,
                simulated_position=simulated_position,
                point=point,
            )

        if self._strategy_name == "bollinger_range_v7_1":
            return self._evaluate_v7_fast_decision_v7_1(
                bars=bars,
                state_decision=state_decision,
                simulated_position=simulated_position,
                point=point,
            )

        raise SignalEngineError(
            f"Unsupported V7 fast-path strategy: {self._strategy_name}"
        )

    def _evaluate_v7_fast_decision_v7(
        self,
        *,
        bars: list[Bar],
        state_decision,
        simulated_position: SimulatedPosition | None,
        point: float,
    ) -> SignalDecision:
        del point

        previous_bar = bars[-2]
        latest_bar = bars[-1]
        previous_close = previous_bar.close
        latest_close = latest_bar.close
        feature = state_decision.feature_snapshot
        confirmed_state = state_decision.confirmed_state
        candidate_state = state_decision.candidate_state

        _, previous_upper, previous_lower = (
            self._compute_previous_bollinger_bands_from_bars(bars)
        )

        current_ticket = simulated_position.ticket if simulated_position else None
        current_type = simulated_position.position_type if simulated_position else None

        common_reason_suffix = (
            f" | confirmed_state={confirmed_state.value}"
            f" candidate_state={candidate_state.value if candidate_state else 'none'}"
            f" event={state_decision.transition_event.value}"
            f" state_age={state_decision.confirmed_state_age}"
            f" candidate_age={state_decision.candidate_state_age}"
            f" range_score={state_decision.score_snapshot.range_score}"
            f" transition_up_score="
            f"{state_decision.score_snapshot.transition_to_trend_up_score}"
            f" transition_down_score="
            f"{state_decision.score_snapshot.transition_to_trend_down_score}"
            f" trend_up_score={state_decision.score_snapshot.trend_up_score}"
            f" trend_down_score={state_decision.score_snapshot.trend_down_score}"
        )

        if simulated_position is None:
            if confirmed_state == V7MarketState.RANGE:
                if range_sell_confirmed_v7(
                    previous_close=previous_close,
                    latest_close=latest_close,
                    previous_upper_band=previous_upper,
                    latest_upper_band=feature.upper_band,
                ):
                    return build_v7_decision(
                        strategy_name=self._strategy_name,
                        action=SignalAction.SELL,
                        reason=(
                            "range sell confirmed by reentry from outside upper band"
                            + common_reason_suffix
                        ),
                        previous_bar_time=previous_bar.time,
                        latest_bar_time=latest_bar.time,
                        previous_close=previous_close,
                        latest_close=latest_close,
                        current_position_ticket=None,
                        current_position_type=None,
                        state_decision=state_decision,
                    )

                if range_buy_confirmed_v7(
                    previous_close=previous_close,
                    latest_close=latest_close,
                    previous_lower_band=previous_lower,
                    latest_lower_band=feature.lower_band,
                ):
                    return build_v7_decision(
                        strategy_name=self._strategy_name,
                        action=SignalAction.BUY,
                        reason=(
                            "range buy confirmed by reentry from outside lower band"
                            + common_reason_suffix
                        ),
                        previous_bar_time=previous_bar.time,
                        latest_bar_time=latest_bar.time,
                        previous_close=previous_close,
                        latest_close=latest_close,
                        current_position_ticket=None,
                        current_position_type=None,
                        state_decision=state_decision,
                    )

            if confirmed_state == V7MarketState.TREND_UP and trend_buy_confirmed_v7(
                previous_close=previous_close,
                latest_close=latest_close,
                previous_upper_band=previous_upper,
                latest_upper_band=feature.upper_band,
            ):
                return build_v7_decision(
                    strategy_name=self._strategy_name,
                    action=SignalAction.BUY,
                    reason=(
                        "trend_up buy confirmed by upper band breakout"
                        + common_reason_suffix
                    ),
                    previous_bar_time=previous_bar.time,
                    latest_bar_time=latest_bar.time,
                    previous_close=previous_close,
                    latest_close=latest_close,
                    current_position_ticket=None,
                    current_position_type=None,
                    state_decision=state_decision,
                )

            if confirmed_state == V7MarketState.TREND_DOWN and trend_sell_confirmed_v7(
                previous_close=previous_close,
                latest_close=latest_close,
                previous_lower_band=previous_lower,
                latest_lower_band=feature.lower_band,
            ):
                return build_v7_decision(
                    strategy_name=self._strategy_name,
                    action=SignalAction.SELL,
                    reason=(
                        "trend_down sell confirmed by lower band breakout"
                        + common_reason_suffix
                    ),
                    previous_bar_time=previous_bar.time,
                    latest_bar_time=latest_bar.time,
                    previous_close=previous_close,
                    latest_close=latest_close,
                    current_position_ticket=None,
                    current_position_type=None,
                    state_decision=state_decision,
                )

            return build_v7_decision(
                strategy_name=self._strategy_name,
                action=SignalAction.HOLD,
                reason="no entry condition matched" + common_reason_suffix,
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=None,
                current_position_type=None,
                state_decision=state_decision,
            )

        if (
            current_type == "sell"
            and candidate_state == V7MarketState.TRANSITION_TO_TREND_UP
        ):
            return build_v7_decision(
                strategy_name=self._strategy_name,
                action=SignalAction.CLOSE,
                reason=(
                    "sell position closed because transition_to_trend_up candidate "
                    "detected" + common_reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=current_ticket,
                current_position_type=current_type,
                state_decision=state_decision,
            )

        if (
            current_type == "buy"
            and candidate_state == V7MarketState.TRANSITION_TO_TREND_DOWN
        ):
            return build_v7_decision(
                strategy_name=self._strategy_name,
                action=SignalAction.CLOSE,
                reason=(
                    "buy position closed because transition_to_trend_down candidate "
                    "detected" + common_reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=current_ticket,
                current_position_type=current_type,
                state_decision=state_decision,
            )

        if current_type == "sell" and confirmed_state == V7MarketState.TREND_UP:
            return build_v7_decision(
                strategy_name=self._strategy_name,
                action=SignalAction.CLOSE,
                reason=(
                    "sell position closed because confirmed state is trend_up"
                    + common_reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=current_ticket,
                current_position_type=current_type,
                state_decision=state_decision,
            )

        if current_type == "buy" and confirmed_state == V7MarketState.TREND_DOWN:
            return build_v7_decision(
                strategy_name=self._strategy_name,
                action=SignalAction.CLOSE,
                reason=(
                    "buy position closed because confirmed state is trend_down"
                    + common_reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=current_ticket,
                current_position_type=current_type,
                state_decision=state_decision,
            )

        if (
            EXIT_ON_RANGE_MIDDLE_BAND
            and confirmed_state == V7MarketState.RANGE
            and current_type == "buy"
            and latest_close >= feature.middle_band
        ):
            return build_v7_decision(
                strategy_name=self._strategy_name,
                action=SignalAction.CLOSE,
                reason=(
                    "buy position closed because range state returned to middle band"
                    + common_reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=current_ticket,
                current_position_type=current_type,
                state_decision=state_decision,
            )

        if (
            EXIT_ON_RANGE_MIDDLE_BAND
            and confirmed_state == V7MarketState.RANGE
            and current_type == "sell"
            and latest_close <= feature.middle_band
        ):
            return build_v7_decision(
                strategy_name=self._strategy_name,
                action=SignalAction.CLOSE,
                reason=(
                    "sell position closed because range state returned to middle band"
                    + common_reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=current_ticket,
                current_position_type=current_type,
                state_decision=state_decision,
            )

        return build_v7_decision(
            strategy_name=self._strategy_name,
            action=SignalAction.HOLD,
            reason="existing position kept" + common_reason_suffix,
            previous_bar_time=previous_bar.time,
            latest_bar_time=latest_bar.time,
            previous_close=previous_close,
            latest_close=latest_close,
            current_position_ticket=current_ticket,
            current_position_type=current_type,
            state_decision=state_decision,
        )

    def _evaluate_v7_fast_decision_v7_1(
        self,
        *,
        bars: list[Bar],
        state_decision,
        simulated_position: SimulatedPosition | None,
        point: float,
    ) -> SignalDecision:
        del point

        previous_bar = bars[-2]
        latest_bar = bars[-1]
        previous_close = previous_bar.close
        latest_close = latest_bar.close
        feature = state_decision.feature_snapshot
        confirmed_state = state_decision.confirmed_state
        candidate_state = state_decision.candidate_state

        _, previous_upper, previous_lower = (
            self._compute_previous_bollinger_bands_from_bars(bars)
        )

        current_ticket = simulated_position.ticket if simulated_position else None
        current_type = simulated_position.position_type if simulated_position else None

        common_reason_suffix = (
            f" | confirmed_state={confirmed_state.value}"
            f" candidate_state={candidate_state.value if candidate_state else 'none'}"
            f" event={state_decision.transition_event.value}"
            f" state_age={state_decision.confirmed_state_age}"
            f" candidate_age={state_decision.candidate_state_age}"
            f" range_score={state_decision.score_snapshot.range_score}"
            f" transition_up_score="
            f"{state_decision.score_snapshot.transition_to_trend_up_score}"
            f" transition_down_score="
            f"{state_decision.score_snapshot.transition_to_trend_down_score}"
            f" trend_up_score={state_decision.score_snapshot.trend_up_score}"
            f" trend_down_score={state_decision.score_snapshot.trend_down_score}"
        )

        if simulated_position is None:
            if not is_v7_1_entry_event_allowed(state_decision):
                return build_v7_1_decision(
                    strategy_name=self._strategy_name,
                    action=SignalAction.HOLD,
                    reason=(
                        "entry blocked because transition event is not an allowed "
                        "entry event" + common_reason_suffix
                    ),
                    previous_bar_time=previous_bar.time,
                    latest_bar_time=latest_bar.time,
                    previous_close=previous_close,
                    latest_close=latest_close,
                    current_position_ticket=None,
                    current_position_type=None,
                    state_decision=state_decision,
                )

            if confirmed_state == V7MarketState.RANGE:
                if range_sell_confirmed_v7_1(
                    previous_close=previous_close,
                    latest_close=latest_close,
                    previous_upper_band=previous_upper,
                    latest_upper_band=feature.upper_band,
                ):
                    return build_v7_1_decision(
                        strategy_name=self._strategy_name,
                        action=SignalAction.SELL,
                        reason=(
                            "range sell confirmed on range_started event by reentry "
                            "from outside upper band" + common_reason_suffix
                        ),
                        previous_bar_time=previous_bar.time,
                        latest_bar_time=latest_bar.time,
                        previous_close=previous_close,
                        latest_close=latest_close,
                        current_position_ticket=None,
                        current_position_type=None,
                        state_decision=state_decision,
                    )

                if range_buy_confirmed_v7_1(
                    previous_close=previous_close,
                    latest_close=latest_close,
                    previous_lower_band=previous_lower,
                    latest_lower_band=feature.lower_band,
                ):
                    return build_v7_1_decision(
                        strategy_name=self._strategy_name,
                        action=SignalAction.BUY,
                        reason=(
                            "range buy confirmed on range_started event by reentry "
                            "from outside lower band" + common_reason_suffix
                        ),
                        previous_bar_time=previous_bar.time,
                        latest_bar_time=latest_bar.time,
                        previous_close=previous_close,
                        latest_close=latest_close,
                        current_position_ticket=None,
                        current_position_type=None,
                        state_decision=state_decision,
                    )

            if confirmed_state == V7MarketState.TREND_UP and trend_buy_confirmed_v7_1(
                previous_close=previous_close,
                latest_close=latest_close,
                previous_upper_band=previous_upper,
                latest_upper_band=feature.upper_band,
            ):
                return build_v7_1_decision(
                    strategy_name=self._strategy_name,
                    action=SignalAction.BUY,
                    reason=(
                        "trend_up buy confirmed on trend_up_started event by upper "
                        "band breakout" + common_reason_suffix
                    ),
                    previous_bar_time=previous_bar.time,
                    latest_bar_time=latest_bar.time,
                    previous_close=previous_close,
                    latest_close=latest_close,
                    current_position_ticket=None,
                    current_position_type=None,
                    state_decision=state_decision,
                )

            if (
                confirmed_state == V7MarketState.TREND_DOWN
                and trend_sell_confirmed_v7_1(
                    previous_close=previous_close,
                    latest_close=latest_close,
                    previous_lower_band=previous_lower,
                    latest_lower_band=feature.lower_band,
                )
            ):
                return build_v7_1_decision(
                    strategy_name=self._strategy_name,
                    action=SignalAction.SELL,
                    reason=(
                        "trend_down sell confirmed on trend_down_started event by "
                        "lower band breakout" + common_reason_suffix
                    ),
                    previous_bar_time=previous_bar.time,
                    latest_bar_time=latest_bar.time,
                    previous_close=previous_close,
                    latest_close=latest_close,
                    current_position_ticket=None,
                    current_position_type=None,
                    state_decision=state_decision,
                )

            return build_v7_1_decision(
                strategy_name=self._strategy_name,
                action=SignalAction.HOLD,
                reason=(
                    "allowed entry event occurred but no entry condition matched"
                    + common_reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=None,
                current_position_type=None,
                state_decision=state_decision,
            )

        if (
            current_type == "sell"
            and candidate_state == V7MarketState.TRANSITION_TO_TREND_UP
        ):
            return build_v7_1_decision(
                strategy_name=self._strategy_name,
                action=SignalAction.CLOSE,
                reason=(
                    "sell position closed because transition_to_trend_up candidate "
                    "detected" + common_reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=current_ticket,
                current_position_type=current_type,
                state_decision=state_decision,
            )

        if (
            current_type == "buy"
            and candidate_state == V7MarketState.TRANSITION_TO_TREND_DOWN
        ):
            return build_v7_1_decision(
                strategy_name=self._strategy_name,
                action=SignalAction.CLOSE,
                reason=(
                    "buy position closed because transition_to_trend_down candidate "
                    "detected" + common_reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=current_ticket,
                current_position_type=current_type,
                state_decision=state_decision,
            )

        if current_type == "sell" and confirmed_state == V7MarketState.TREND_UP:
            return build_v7_1_decision(
                strategy_name=self._strategy_name,
                action=SignalAction.CLOSE,
                reason=(
                    "sell position closed because confirmed state is trend_up"
                    + common_reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=current_ticket,
                current_position_type=current_type,
                state_decision=state_decision,
            )

        if current_type == "buy" and confirmed_state == V7MarketState.TREND_DOWN:
            return build_v7_1_decision(
                strategy_name=self._strategy_name,
                action=SignalAction.CLOSE,
                reason=(
                    "buy position closed because confirmed state is trend_down"
                    + common_reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=current_ticket,
                current_position_type=current_type,
                state_decision=state_decision,
            )

        if (
            EXIT_ON_RANGE_MIDDLE_BAND
            and confirmed_state == V7MarketState.RANGE
            and current_type == "buy"
            and latest_close >= feature.middle_band
        ):
            return build_v7_1_decision(
                strategy_name=self._strategy_name,
                action=SignalAction.CLOSE,
                reason=(
                    "buy position closed because range state returned to middle band"
                    + common_reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=current_ticket,
                current_position_type=current_type,
                state_decision=state_decision,
            )

        if (
            EXIT_ON_RANGE_MIDDLE_BAND
            and confirmed_state == V7MarketState.RANGE
            and current_type == "sell"
            and latest_close <= feature.middle_band
        ):
            return build_v7_1_decision(
                strategy_name=self._strategy_name,
                action=SignalAction.CLOSE,
                reason=(
                    "sell position closed because range state returned to middle band"
                    + common_reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=current_ticket,
                current_position_type=current_type,
                state_decision=state_decision,
            )

        return build_v7_1_decision(
            strategy_name=self._strategy_name,
            action=SignalAction.HOLD,
            reason="existing position kept" + common_reason_suffix,
            previous_bar_time=previous_bar.time,
            latest_bar_time=latest_bar.time,
            previous_close=previous_close,
            latest_close=latest_close,
            current_position_ticket=current_ticket,
            current_position_type=current_type,
            state_decision=state_decision,
        )