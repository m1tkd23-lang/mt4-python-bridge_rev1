# src/mt4_bridge/strategies/bollinger_range_A_guarded.py
from __future__ import annotations

from mt4_bridge.models import MarketSnapshot, PositionSnapshot, SignalDecision
from mt4_bridge.strategies.bollinger_range_v4_4_guarded import (
    evaluate_bollinger_range_v4_4_guarded,
    required_bars as required_bars_v4_4_guarded,
)


def required_bars() -> int:
    return required_bars_v4_4_guarded()


def evaluate_bollinger_range_A_guarded(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_range_A_guarded",
) -> SignalDecision:
    decision = evaluate_bollinger_range_v4_4_guarded(
        market_snapshot=market_snapshot,
        position_snapshot=position_snapshot,
        strategy_name=strategy_name,
    )
    return SignalDecision(
        strategy_name=strategy_name,
        action=decision.action,
        reason=decision.reason,
        previous_bar_time=decision.previous_bar_time,
        latest_bar_time=decision.latest_bar_time,
        previous_close=decision.previous_close,
        latest_close=decision.latest_close,
        current_position_ticket=decision.current_position_ticket,
        current_position_type=decision.current_position_type,
        sl_price=decision.sl_price,
        tp_price=decision.tp_price,
        entry_lane="range",
        entry_subtype="v4_4_guarded",
        market_state=decision.market_state,
        middle_band=decision.middle_band,
        upper_band=decision.upper_band,
        lower_band=decision.lower_band,
        normalized_band_width=decision.normalized_band_width,
        range_slope=decision.range_slope,
        trend_slope=decision.trend_slope,
        trend_current_ma=decision.trend_current_ma,
        distance_from_middle=decision.distance_from_middle,
        detected_market_state=decision.detected_market_state,
        candidate_market_state=decision.candidate_market_state,
        state_transition_event=decision.state_transition_event,
        state_age=decision.state_age,
        candidate_age=decision.candidate_age,
        detector_reason=decision.detector_reason,
        range_score=decision.range_score,
        transition_up_score=decision.transition_up_score,
        transition_down_score=decision.transition_down_score,
        trend_up_score=decision.trend_up_score,
        trend_down_score=decision.trend_down_score,
    )