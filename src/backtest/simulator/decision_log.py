# src/backtest/simulator/decision_log.py
from __future__ import annotations

from backtest.csv_loader import HistoricalBarRow
from backtest.simulator.models import BacktestDecisionLog, SimulatedPosition
from mt4_bridge.models import SignalDecision


class DecisionLogMixin:
    def _build_decision_log(
        self,
        *,
        current_row: HistoricalBarRow,
        decision: SignalDecision,
        range_position: SimulatedPosition | None,
        trend_position: SimulatedPosition | None,
        legacy_position: SimulatedPosition | None,
    ) -> BacktestDecisionLog:
        return BacktestDecisionLog(
            bar_time=current_row.time,
            action=decision.action.value,
            reason=decision.reason,
            market_state=decision.market_state,
            entry_lane=decision.entry_lane,
            entry_subtype=decision.entry_subtype,
            previous_close=decision.previous_close,
            latest_close=decision.latest_close,
            middle_band=decision.middle_band,
            upper_band=decision.upper_band,
            lower_band=decision.lower_band,
            normalized_band_width=decision.normalized_band_width,
            range_slope=decision.range_slope,
            trend_slope=decision.trend_slope,
            trend_current_ma=decision.trend_current_ma,
            distance_from_middle=decision.distance_from_middle,
            current_position_ticket=decision.current_position_ticket,
            current_position_type=decision.current_position_type,
            has_range_position=range_position is not None,
            has_trend_position=trend_position is not None,
            has_legacy_position=legacy_position is not None,
            range_observation=decision.debug_metrics,
        )