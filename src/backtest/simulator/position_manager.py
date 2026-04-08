# src/backtest/simulator/position_manager.py
from __future__ import annotations

from backtest.csv_loader import HistoricalBarRow
from backtest.simulator.models import (
    BacktestSimulationError,
    ExecutedTrade,
    SimulatedPosition,
)
from mt4_bridge.models import SignalAction, SignalDecision
from mt4_bridge.risk_manager import calculate_sl_tp


class PositionManagerMixin:
    @staticmethod
    def _get_debug_bool(
        debug_metrics: dict[str, object] | None,
        key: str,
    ) -> bool | None:
        if not debug_metrics or key not in debug_metrics:
            return None
        value = debug_metrics[key]
        if isinstance(value, bool):
            return value
        return None

    @staticmethod
    def _get_debug_int(
        debug_metrics: dict[str, object] | None,
        key: str,
    ) -> int | None:
        if not debug_metrics or key not in debug_metrics:
            return None
        value = debug_metrics[key]
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        return None

    @staticmethod
    def _get_debug_float(
        debug_metrics: dict[str, object] | None,
        key: str,
    ) -> float | None:
        if not debug_metrics or key not in debug_metrics:
            return None
        value = debug_metrics[key]
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        return None

    def _create_position_from_decision(
        self,
        *,
        current_row: HistoricalBarRow,
        decision: SignalDecision,
        next_ticket: int,
        point: float,
    ) -> tuple[SimulatedPosition, int]:
        if decision.action not in (SignalAction.BUY, SignalAction.SELL):
            raise BacktestSimulationError(
                f"Unsupported entry action for position creation: {decision.action}"
            )

        sl_price, tp_price = calculate_sl_tp(
            action=decision.action,
            bid=current_row.close,
            ask=current_row.close,
            point=point,
            sl_pips=self._sl_pips,
            tp_pips=self._tp_pips,
        )

        debug_metrics = decision.debug_metrics
        position_type = "buy" if decision.action == SignalAction.BUY else "sell"

        position = SimulatedPosition(
            lane=decision.entry_lane or "legacy",
            entry_subtype=decision.entry_subtype,
            position_type=position_type,
            entry_price=current_row.close,
            entry_time=current_row.time,
            ticket=next_ticket,
            sl_price=sl_price,
            tp_price=tp_price,
            entry_signal_reason=decision.reason,
            entry_market_state=decision.market_state,
            entry_middle_band=decision.middle_band,
            entry_upper_band=decision.upper_band,
            entry_lower_band=decision.lower_band,
            entry_normalized_band_width=decision.normalized_band_width,
            entry_range_slope=decision.range_slope,
            entry_trend_slope=decision.trend_slope,
            entry_trend_current_ma=decision.trend_current_ma,
            entry_distance_from_middle=decision.distance_from_middle,
            entry_detected_market_state=decision.detected_market_state,
            entry_candidate_market_state=decision.candidate_market_state,
            entry_state_transition_event=decision.state_transition_event,
            entry_state_age=decision.state_age,
            entry_candidate_age=decision.candidate_age,
            entry_detector_reason=decision.detector_reason,
            entry_range_score=decision.range_score,
            entry_transition_up_score=decision.transition_up_score,
            entry_transition_down_score=decision.transition_down_score,
            entry_trend_up_score=decision.trend_up_score,
            entry_trend_down_score=decision.trend_down_score,
            entry_risk_score=self._get_debug_int(debug_metrics, "risk_score"),
            entry_upper_band_walk=self._get_debug_bool(debug_metrics, "upper_band_walk"),
            entry_lower_band_walk=self._get_debug_bool(debug_metrics, "lower_band_walk"),
            entry_upper_band_walk_hits=self._get_debug_int(
                debug_metrics,
                "upper_band_walk_hits",
            ),
            entry_lower_band_walk_hits=self._get_debug_int(
                debug_metrics,
                "lower_band_walk_hits",
            ),
            entry_dangerous_for_buy=self._get_debug_bool(
                debug_metrics,
                "dangerous_for_buy",
            ),
            entry_dangerous_for_sell=self._get_debug_bool(
                debug_metrics,
                "dangerous_for_sell",
            ),
            entry_strong_up_slope=self._get_debug_bool(
                debug_metrics,
                "strong_up_slope",
            ),
            entry_strong_down_slope=self._get_debug_bool(
                debug_metrics,
                "strong_down_slope",
            ),
            entry_latest_slope=self._get_debug_float(debug_metrics, "latest_slope"),
            entry_prev_slope=self._get_debug_float(debug_metrics, "prev_slope"),
            entry_latest_band_width=self._get_debug_float(
                debug_metrics,
                "latest_band_width",
            ),
            entry_prev_band_width=self._get_debug_float(
                debug_metrics,
                "prev_band_width",
            ),
            entry_latest_distance=self._get_debug_float(
                debug_metrics,
                "latest_distance",
            ),
            entry_prev_distance=self._get_debug_float(debug_metrics, "prev_distance"),
        )
        return position, next_ticket + 1

    def _apply_single_position_decision(
        self,
        current_row: HistoricalBarRow,
        decision: SignalDecision,
        simulated_position: SimulatedPosition | None,
        next_ticket: int,
        point: float,
    ) -> tuple[SimulatedPosition | None, ExecutedTrade | None, int]:
        if simulated_position is None:
            if decision.action in (SignalAction.BUY, SignalAction.SELL):
                new_position, next_ticket = self._create_position_from_decision(
                    current_row=current_row,
                    decision=decision,
                    next_ticket=next_ticket,
                    point=point,
                )
                return new_position, None, next_ticket

            return simulated_position, None, next_ticket

        if decision.action == SignalAction.CLOSE:
            closed_trade = self._close_position(
                simulated_position=simulated_position,
                exit_time=current_row.time,
                exit_price=current_row.close,
                exit_reason="signal_close",
                exit_decision=decision,
            )
            return None, closed_trade, next_ticket

        return simulated_position, None, next_ticket

    def _apply_multi_lane_decision(
        self,
        current_row: HistoricalBarRow,
        decision: SignalDecision,
        range_position: SimulatedPosition | None,
        trend_position: SimulatedPosition | None,
        next_ticket: int,
        point: float,
    ) -> tuple[
        SimulatedPosition | None,
        SimulatedPosition | None,
        ExecutedTrade | None,
        int,
    ]:
        lane = (decision.entry_lane or "").strip().lower()

        if lane == "range":
            if decision.action in (SignalAction.BUY, SignalAction.SELL):
                if range_position is not None:
                    return range_position, trend_position, None, next_ticket

                new_position, next_ticket = self._create_position_from_decision(
                    current_row=current_row,
                    decision=decision,
                    next_ticket=next_ticket,
                    point=point,
                )
                return new_position, trend_position, None, next_ticket

            if decision.action == SignalAction.CLOSE:
                if range_position is None:
                    return range_position, trend_position, None, next_ticket

                closed_trade = self._close_position(
                    simulated_position=range_position,
                    exit_time=current_row.time,
                    exit_price=current_row.close,
                    exit_reason="signal_close",
                    exit_decision=decision,
                )
                return None, trend_position, closed_trade, next_ticket

            return range_position, trend_position, None, next_ticket

        if lane == "trend":
            if decision.action in (SignalAction.BUY, SignalAction.SELL):
                if trend_position is not None:
                    return range_position, trend_position, None, next_ticket

                new_position, next_ticket = self._create_position_from_decision(
                    current_row=current_row,
                    decision=decision,
                    next_ticket=next_ticket,
                    point=point,
                )
                return range_position, new_position, None, next_ticket

            if decision.action == SignalAction.CLOSE:
                if trend_position is None:
                    return range_position, trend_position, None, next_ticket

                closed_trade = self._close_position(
                    simulated_position=trend_position,
                    exit_time=current_row.time,
                    exit_price=current_row.close,
                    exit_reason="signal_close",
                    exit_decision=decision,
                )
                return range_position, None, closed_trade, next_ticket

            return range_position, trend_position, None, next_ticket

        return range_position, trend_position, None, next_ticket

    def _close_position(
        self,
        simulated_position: SimulatedPosition,
        exit_time,
        exit_price: float,
        exit_reason: str,
        exit_decision: SignalDecision | None,
    ) -> ExecutedTrade:
        if simulated_position.position_type == "buy":
            pips = (exit_price - simulated_position.entry_price) / self._pip_size
        elif simulated_position.position_type == "sell":
            pips = (simulated_position.entry_price - exit_price) / self._pip_size
        else:
            raise BacktestSimulationError(
                f"Unsupported simulated position type: {simulated_position.position_type}"
            )

        return ExecutedTrade(
            lane=simulated_position.lane,
            entry_subtype=simulated_position.entry_subtype,
            entry_time=simulated_position.entry_time,
            exit_time=exit_time,
            position_type=simulated_position.position_type,
            entry_price=simulated_position.entry_price,
            exit_price=exit_price,
            pips=pips,
            exit_reason=exit_reason,
            entry_signal_reason=simulated_position.entry_signal_reason,
            entry_market_state=simulated_position.entry_market_state,
            entry_middle_band=simulated_position.entry_middle_band,
            entry_upper_band=simulated_position.entry_upper_band,
            entry_lower_band=simulated_position.entry_lower_band,
            entry_normalized_band_width=(
                simulated_position.entry_normalized_band_width
            ),
            entry_range_slope=simulated_position.entry_range_slope,
            entry_trend_slope=simulated_position.entry_trend_slope,
            entry_trend_current_ma=simulated_position.entry_trend_current_ma,
            entry_distance_from_middle=simulated_position.entry_distance_from_middle,
            exit_signal_reason=exit_decision.reason if exit_decision else None,
            exit_market_state=exit_decision.market_state if exit_decision else None,
            exit_middle_band=exit_decision.middle_band if exit_decision else None,
            exit_upper_band=exit_decision.upper_band if exit_decision else None,
            exit_lower_band=exit_decision.lower_band if exit_decision else None,
            exit_normalized_band_width=(
                exit_decision.normalized_band_width if exit_decision else None
            ),
            exit_range_slope=exit_decision.range_slope if exit_decision else None,
            exit_trend_slope=exit_decision.trend_slope if exit_decision else None,
            exit_trend_current_ma=(
                exit_decision.trend_current_ma if exit_decision else None
            ),
            exit_distance_from_middle=(
                exit_decision.distance_from_middle if exit_decision else None
            ),
            entry_detected_market_state=(
                simulated_position.entry_detected_market_state
            ),
            entry_candidate_market_state=(
                simulated_position.entry_candidate_market_state
            ),
            entry_state_transition_event=(
                simulated_position.entry_state_transition_event
            ),
            entry_state_age=simulated_position.entry_state_age,
            entry_candidate_age=simulated_position.entry_candidate_age,
            entry_detector_reason=simulated_position.entry_detector_reason,
            entry_range_score=simulated_position.entry_range_score,
            entry_transition_up_score=simulated_position.entry_transition_up_score,
            entry_transition_down_score=(
                simulated_position.entry_transition_down_score
            ),
            entry_trend_up_score=simulated_position.entry_trend_up_score,
            entry_trend_down_score=simulated_position.entry_trend_down_score,
            exit_detected_market_state=(
                exit_decision.detected_market_state if exit_decision else None
            ),
            exit_candidate_market_state=(
                exit_decision.candidate_market_state if exit_decision else None
            ),
            exit_state_transition_event=(
                exit_decision.state_transition_event if exit_decision else None
            ),
            exit_state_age=exit_decision.state_age if exit_decision else None,
            exit_candidate_age=(
                exit_decision.candidate_age if exit_decision else None
            ),
            exit_detector_reason=(
                exit_decision.detector_reason if exit_decision else None
            ),
            exit_range_score=exit_decision.range_score if exit_decision else None,
            exit_transition_up_score=(
                exit_decision.transition_up_score if exit_decision else None
            ),
            exit_transition_down_score=(
                exit_decision.transition_down_score if exit_decision else None
            ),
            exit_trend_up_score=(
                exit_decision.trend_up_score if exit_decision else None
            ),
            exit_trend_down_score=(
                exit_decision.trend_down_score if exit_decision else None
            ),
            entry_risk_score=simulated_position.entry_risk_score,
            entry_upper_band_walk=simulated_position.entry_upper_band_walk,
            entry_lower_band_walk=simulated_position.entry_lower_band_walk,
            entry_upper_band_walk_hits=simulated_position.entry_upper_band_walk_hits,
            entry_lower_band_walk_hits=simulated_position.entry_lower_band_walk_hits,
            entry_dangerous_for_buy=simulated_position.entry_dangerous_for_buy,
            entry_dangerous_for_sell=simulated_position.entry_dangerous_for_sell,
            entry_strong_up_slope=simulated_position.entry_strong_up_slope,
            entry_strong_down_slope=simulated_position.entry_strong_down_slope,
            entry_latest_slope=simulated_position.entry_latest_slope,
            entry_prev_slope=simulated_position.entry_prev_slope,
            entry_latest_band_width=simulated_position.entry_latest_band_width,
            entry_prev_band_width=simulated_position.entry_prev_band_width,
            entry_latest_distance=simulated_position.entry_latest_distance,
            entry_prev_distance=simulated_position.entry_prev_distance,
        )

    def _build_final_open_position_label(
        self,
        *,
        range_position: SimulatedPosition | None,
        trend_position: SimulatedPosition | None,
        legacy_position: SimulatedPosition | None,
    ) -> str | None:
        if legacy_position is not None:
            return legacy_position.position_type

        parts: list[str] = []
        if range_position is not None:
            parts.append(f"range:{range_position.position_type}")
        if trend_position is not None:
            parts.append(f"trend:{trend_position.position_type}")

        if not parts:
            return None
        return ", ".join(parts)