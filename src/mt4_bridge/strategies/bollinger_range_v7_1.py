# src\mt4_bridge\strategies\bollinger_range_v7_1.py
from __future__ import annotations

from mt4_bridge.models import (
    MarketSnapshot,
    PositionSnapshot,
    SignalAction,
    SignalDecision,
)
from mt4_bridge.signal_exceptions import SignalEngineError
from mt4_bridge.strategies.bollinger_range_v7 import (
    EXIT_ON_RANGE_MIDDLE_BAND,
    RANGE_REQUIRE_REENTRY_CONFIRMATION,
    TREND_REQUIRE_BREAK_CONFIRMATION,
)
from mt4_bridge.strategies.v7_features import required_bars_for_v7_features
from mt4_bridge.strategies.v7_state_detector import detect_v7_market_state
from mt4_bridge.strategies.v7_state_models import (
    V7_DEFAULT_PARAMS,
    V7DetectorParams,
    V7MarketState,
    V7TransitionEvent,
)


def required_bars(params: V7DetectorParams = V7_DEFAULT_PARAMS) -> int:
    return required_bars_for_v7_features(params)


def _range_buy_confirmed(
    previous_close: float,
    latest_close: float,
    previous_lower_band: float,
    latest_lower_band: float,
) -> bool:
    if not RANGE_REQUIRE_REENTRY_CONFIRMATION:
        return latest_close <= latest_lower_band
    return previous_close < previous_lower_band and latest_close >= latest_lower_band


def _range_sell_confirmed(
    previous_close: float,
    latest_close: float,
    previous_upper_band: float,
    latest_upper_band: float,
) -> bool:
    if not RANGE_REQUIRE_REENTRY_CONFIRMATION:
        return latest_close >= latest_upper_band
    return previous_close > previous_upper_band and latest_close <= latest_upper_band


def _trend_buy_confirmed(
    previous_close: float,
    latest_close: float,
    previous_upper_band: float,
    latest_upper_band: float,
) -> bool:
    if not TREND_REQUIRE_BREAK_CONFIRMATION:
        return latest_close >= latest_upper_band
    return previous_close <= previous_upper_band and latest_close > latest_upper_band


def _trend_sell_confirmed(
    previous_close: float,
    latest_close: float,
    previous_lower_band: float,
    latest_lower_band: float,
) -> bool:
    if not TREND_REQUIRE_BREAK_CONFIRMATION:
        return latest_close <= latest_lower_band
    return previous_close >= previous_lower_band and latest_close < latest_lower_band


def _build_decision(
    *,
    strategy_name: str,
    action: SignalAction,
    reason: str,
    previous_bar_time,
    latest_bar_time,
    previous_close: float,
    latest_close: float,
    current_position_ticket: int | None,
    current_position_type: str | None,
    state_decision,
) -> SignalDecision:
    feature = state_decision.feature_snapshot
    scores = state_decision.score_snapshot
    confirmed_state = state_decision.confirmed_state.value
    candidate_state = (
        state_decision.candidate_state.value
        if state_decision.candidate_state is not None
        else None
    )

    return SignalDecision(
        strategy_name=strategy_name,
        action=action,
        reason=reason,
        previous_bar_time=previous_bar_time,
        latest_bar_time=latest_bar_time,
        previous_close=previous_close,
        latest_close=latest_close,
        current_position_ticket=current_position_ticket,
        current_position_type=current_position_type,
        market_state=confirmed_state,
        middle_band=feature.middle_band,
        upper_band=feature.upper_band,
        lower_band=feature.lower_band,
        normalized_band_width=feature.normalized_band_width,
        range_slope=feature.range_slope,
        trend_slope=feature.trend_slope,
        trend_current_ma=feature.trend_ma,
        distance_from_middle=feature.distance_from_middle,
        detected_market_state=confirmed_state,
        candidate_market_state=candidate_state,
        state_transition_event=state_decision.transition_event.value,
        state_age=state_decision.confirmed_state_age,
        candidate_age=state_decision.candidate_state_age,
        detector_reason=state_decision.detector_reason,
        range_score=float(scores.range_score),
        transition_up_score=float(scores.transition_to_trend_up_score),
        transition_down_score=float(scores.transition_to_trend_down_score),
        trend_up_score=float(scores.trend_up_score),
        trend_down_score=float(scores.trend_down_score),
    )


def _is_entry_event_allowed(state_decision) -> bool:
    return state_decision.transition_event in {
        V7TransitionEvent.RANGE_STARTED,
        V7TransitionEvent.TREND_UP_STARTED,
        V7TransitionEvent.TREND_DOWN_STARTED,
    }


# ★ state保持用（簡易static）
_prev_confirmed_state: V7MarketState | None = None


def evaluate_bollinger_range_v7_1(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_range_v7_1",
) -> SignalDecision:
    global _prev_confirmed_state

    params = V7_DEFAULT_PARAMS
    bars = market_snapshot.bars
    if len(bars) < required_bars(params):
        raise SignalEngineError(
            f"At least {required_bars(params)} bars are required"
        )

    previous_bar = bars[-2]
    latest_bar = bars[-1]
    previous_close = previous_bar.close
    latest_close = latest_bar.close

    state_decision = detect_v7_market_state(market_snapshot, params)
    confirmed_state = state_decision.confirmed_state
    state_changed = state_decision.confirmed_state_age == 1

    current_position = (
        position_snapshot.positions[0] if position_snapshot.positions else None
    )
    current_type = current_position.position_type.lower() if current_position else None

    # =========================
    # ★ 検証モード：state切替トレード
    # =========================

    # --- クローズ優先 ---
    if current_position is not None and state_changed:
        _prev_confirmed_state = confirmed_state
        return _build_decision(
            strategy_name=strategy_name,
            action=SignalAction.CLOSE,
            reason="forced close on state change",
            previous_bar_time=previous_bar.time,
            latest_bar_time=latest_bar.time,
            previous_close=previous_close,
            latest_close=latest_close,
            current_position_ticket=current_position.ticket,
            current_position_type=current_type,
            state_decision=state_decision,
        )

    # --- エントリー ---
    if current_position is None and state_changed:

        if confirmed_state == V7MarketState.TREND_UP:
            action = SignalAction.BUY

        elif confirmed_state == V7MarketState.TREND_DOWN:
            action = SignalAction.SELL

        elif confirmed_state == V7MarketState.RANGE:
            if _prev_confirmed_state == V7MarketState.TREND_UP:
                action = SignalAction.SELL
            elif _prev_confirmed_state == V7MarketState.TREND_DOWN:
                action = SignalAction.BUY
            else:
                action = SignalAction.BUY

        else:
            action = SignalAction.HOLD

        _prev_confirmed_state = confirmed_state

        return _build_decision(
            strategy_name=strategy_name,
            action=action,
            reason="forced entry on state change",
            previous_bar_time=previous_bar.time,
            latest_bar_time=latest_bar.time,
            previous_close=previous_close,
            latest_close=latest_close,
            current_position_ticket=None,
            current_position_type=None,
            state_decision=state_decision,
        )

    # state保持更新
    _prev_confirmed_state = confirmed_state

    # =========================
    # 既存ロジック（検証後戻せるように残す）
    # =========================

    return _build_decision(
        strategy_name=strategy_name,
        action=SignalAction.HOLD,
        reason="existing position kept (verification mode)",
        previous_bar_time=previous_bar.time,
        latest_bar_time=latest_bar.time,
        previous_close=previous_close,
        latest_close=latest_close,
        current_position_ticket=current_position.ticket if current_position else None,
        current_position_type=current_type,
        state_decision=state_decision,
    )