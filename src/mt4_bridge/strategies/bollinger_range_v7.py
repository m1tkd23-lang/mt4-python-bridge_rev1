# src\mt4_bridge\strategies\bollinger_range_v7.py
from __future__ import annotations

from mt4_bridge.models import (
    MarketSnapshot,
    PositionSnapshot,
    SignalAction,
    SignalDecision,
)
from mt4_bridge.signal_exceptions import SignalEngineError
from mt4_bridge.strategies.v7_features import required_bars_for_v7_features
from mt4_bridge.strategies.v7_state_detector import detect_v7_market_state
from mt4_bridge.strategies.v7_state_models import (
    V7_DEFAULT_PARAMS,
    V7DetectorParams,
    V7MarketState,
)


RANGE_REQUIRE_REENTRY_CONFIRMATION = True
TREND_REQUIRE_BREAK_CONFIRMATION = True
EXIT_ON_RANGE_MIDDLE_BAND = True


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


def evaluate_bollinger_range_v7(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_range_v7",
) -> SignalDecision:
    params = V7_DEFAULT_PARAMS
    bars = market_snapshot.bars
    if len(bars) < required_bars(params):
        raise SignalEngineError(
            f"At least {required_bars(params)} bars are required to evaluate bollinger_range_v7"
        )

    previous_bar = bars[-2]
    latest_bar = bars[-1]
    previous_close = previous_bar.close
    latest_close = latest_bar.close

    state_decision = detect_v7_market_state(market_snapshot, params)
    feature = state_decision.feature_snapshot
    confirmed_state = state_decision.confirmed_state
    candidate_state = state_decision.candidate_state

    previous_closes = [bar.close for bar in bars[:-1]]
    if len(previous_closes) < params.feature.bollinger_period:
        raise SignalEngineError(
            f"At least {params.feature.bollinger_period + 1} bars are required for previous bands"
        )
    previous_window = previous_closes[-params.feature.bollinger_period :]
    previous_middle = sum(previous_window) / len(previous_window)
    previous_std = (
        sum((value - previous_middle) ** 2 for value in previous_window)
        / len(previous_window)
    ) ** 0.5
    previous_upper = previous_middle + (params.feature.bollinger_sigma * previous_std)
    previous_lower = previous_middle - (params.feature.bollinger_sigma * previous_std)

    current_position = (
        position_snapshot.positions[0] if position_snapshot.positions else None
    )
    current_type = current_position.position_type.lower() if current_position else None

    common_reason_suffix = (
        f" | confirmed_state={confirmed_state.value}"
        f" candidate_state={candidate_state.value if candidate_state else 'none'}"
        f" event={state_decision.transition_event.value}"
        f" state_age={state_decision.confirmed_state_age}"
        f" candidate_age={state_decision.candidate_state_age}"
        f" range_score={state_decision.score_snapshot.range_score}"
        f" transition_up_score={state_decision.score_snapshot.transition_to_trend_up_score}"
        f" transition_down_score={state_decision.score_snapshot.transition_to_trend_down_score}"
        f" trend_up_score={state_decision.score_snapshot.trend_up_score}"
        f" trend_down_score={state_decision.score_snapshot.trend_down_score}"
    )

    if current_position is None:
        if confirmed_state == V7MarketState.RANGE:
            if _range_sell_confirmed(
                previous_close=previous_close,
                latest_close=latest_close,
                previous_upper_band=previous_upper,
                latest_upper_band=feature.upper_band,
            ):
                return _build_decision(
                    strategy_name=strategy_name,
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

            if _range_buy_confirmed(
                previous_close=previous_close,
                latest_close=latest_close,
                previous_lower_band=previous_lower,
                latest_lower_band=feature.lower_band,
            ):
                return _build_decision(
                    strategy_name=strategy_name,
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

        if confirmed_state == V7MarketState.TREND_UP and _trend_buy_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            previous_upper_band=previous_upper,
            latest_upper_band=feature.upper_band,
        ):
            return _build_decision(
                strategy_name=strategy_name,
                action=SignalAction.BUY,
                reason="trend_up buy confirmed by upper band breakout" + common_reason_suffix,
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=None,
                current_position_type=None,
                state_decision=state_decision,
            )

        if confirmed_state == V7MarketState.TREND_DOWN and _trend_sell_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            previous_lower_band=previous_lower,
            latest_lower_band=feature.lower_band,
        ):
            return _build_decision(
                strategy_name=strategy_name,
                action=SignalAction.SELL,
                reason="trend_down sell confirmed by lower band breakout" + common_reason_suffix,
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=None,
                current_position_type=None,
                state_decision=state_decision,
            )

        return _build_decision(
            strategy_name=strategy_name,
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

    # transition protection
    if current_type == "sell" and candidate_state == V7MarketState.TRANSITION_TO_TREND_UP:
        return _build_decision(
            strategy_name=strategy_name,
            action=SignalAction.CLOSE,
            reason="sell position closed because transition_to_trend_up candidate detected" + common_reason_suffix,
            previous_bar_time=previous_bar.time,
            latest_bar_time=latest_bar.time,
            previous_close=previous_close,
            latest_close=latest_close,
            current_position_ticket=current_position.ticket,
            current_position_type=current_type,
            state_decision=state_decision,
        )

    if current_type == "buy" and candidate_state == V7MarketState.TRANSITION_TO_TREND_DOWN:
        return _build_decision(
            strategy_name=strategy_name,
            action=SignalAction.CLOSE,
            reason="buy position closed because transition_to_trend_down candidate detected" + common_reason_suffix,
            previous_bar_time=previous_bar.time,
            latest_bar_time=latest_bar.time,
            previous_close=previous_close,
            latest_close=latest_close,
            current_position_ticket=current_position.ticket,
            current_position_type=current_type,
            state_decision=state_decision,
        )

    # confirmed trend protection
    if current_type == "sell" and confirmed_state == V7MarketState.TREND_UP:
        return _build_decision(
            strategy_name=strategy_name,
            action=SignalAction.CLOSE,
            reason="sell position closed because confirmed state is trend_up" + common_reason_suffix,
            previous_bar_time=previous_bar.time,
            latest_bar_time=latest_bar.time,
            previous_close=previous_close,
            latest_close=latest_close,
            current_position_ticket=current_position.ticket,
            current_position_type=current_type,
            state_decision=state_decision,
        )

    if current_type == "buy" and confirmed_state == V7MarketState.TREND_DOWN:
        return _build_decision(
            strategy_name=strategy_name,
            action=SignalAction.CLOSE,
            reason="buy position closed because confirmed state is trend_down" + common_reason_suffix,
            previous_bar_time=previous_bar.time,
            latest_bar_time=latest_bar.time,
            previous_close=previous_close,
            latest_close=latest_close,
            current_position_ticket=current_position.ticket,
            current_position_type=current_type,
            state_decision=state_decision,
        )

    # range mean reversion exit
    if (
        EXIT_ON_RANGE_MIDDLE_BAND
        and confirmed_state == V7MarketState.RANGE
        and current_type == "buy"
        and latest_close >= feature.middle_band
    ):
        return _build_decision(
            strategy_name=strategy_name,
            action=SignalAction.CLOSE,
            reason="buy position closed because range state returned to middle band" + common_reason_suffix,
            previous_bar_time=previous_bar.time,
            latest_bar_time=latest_bar.time,
            previous_close=previous_close,
            latest_close=latest_close,
            current_position_ticket=current_position.ticket,
            current_position_type=current_type,
            state_decision=state_decision,
        )

    if (
        EXIT_ON_RANGE_MIDDLE_BAND
        and confirmed_state == V7MarketState.RANGE
        and current_type == "sell"
        and latest_close <= feature.middle_band
    ):
        return _build_decision(
            strategy_name=strategy_name,
            action=SignalAction.CLOSE,
            reason="sell position closed because range state returned to middle band" + common_reason_suffix,
            previous_bar_time=previous_bar.time,
            latest_bar_time=latest_bar.time,
            previous_close=previous_close,
            latest_close=latest_close,
            current_position_ticket=current_position.ticket,
            current_position_type=current_type,
            state_decision=state_decision,
        )

    return _build_decision(
        strategy_name=strategy_name,
        action=SignalAction.HOLD,
        reason="existing position kept" + common_reason_suffix,
        previous_bar_time=previous_bar.time,
        latest_bar_time=latest_bar.time,
        previous_close=previous_close,
        latest_close=latest_close,
        current_position_ticket=current_position.ticket,
        current_position_type=current_type,
        state_decision=state_decision,
    )