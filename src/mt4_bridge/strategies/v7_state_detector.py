# src\mt4_bridge\strategies\v7_state_detector.py
from __future__ import annotations

from mt4_bridge.models import Bar, MarketSnapshot
from mt4_bridge.signal_exceptions import SignalEngineError
from mt4_bridge.strategies.v7_features import (
    build_v7_feature_snapshot,
    build_v7_feature_snapshot_from_bars,
    required_bars_for_v7_features,
)
from mt4_bridge.strategies.v7_state_models import (
    V7_DEFAULT_PARAMS,
    V7DetectorParams,
    V7FeatureSnapshot,
    V7MarketState,
    V7ScoreSnapshot,
    V7StateContext,
    V7StateDecision,
    V7TransitionEvent,
)


def build_initial_state_context() -> V7StateContext:
    return V7StateContext()


def score_range(features: V7FeatureSnapshot, params: V7DetectorParams) -> int:
    range_params = params.range
    score = 0
    if abs(features.range_slope) <= range_params.max_abs_range_slope:
        score += 1
    if features.normalized_band_width <= range_params.max_normalized_band_width:
        score += 1
    if features.distance_from_middle <= range_params.max_distance_from_middle:
        score += 1
    if features.recent_high_break_count <= range_params.max_recent_high_break_count:
        score += 1
    if features.recent_low_break_count <= range_params.max_recent_low_break_count:
        score += 1
    if features.price_above_ma_streak <= range_params.max_price_above_ma_streak:
        score += 1
    if features.price_below_ma_streak <= range_params.max_price_below_ma_streak:
        score += 1
    if abs(features.band_width_slope) <= range_params.max_band_width_slope:
        score += 1
    return score


def score_transition_to_trend_up(
    features: V7FeatureSnapshot,
    params: V7DetectorParams,
) -> int:
    transition = params.transition
    score = 0
    if features.trend_slope >= transition.min_transition_trend_slope:
        score += 1
    if features.recent_high_break_count >= transition.min_recent_high_break_count:
        score += 1
    if features.higher_lows_count >= transition.min_higher_lows_count:
        score += 1
    if features.price_above_ma_streak >= transition.min_price_above_ma_streak:
        score += 1
    if features.band_width_slope >= transition.min_band_width_slope:
        score += 1
    return score


def score_transition_to_trend_down(
    features: V7FeatureSnapshot,
    params: V7DetectorParams,
) -> int:
    transition = params.transition
    score = 0
    if features.trend_slope <= -transition.min_transition_trend_slope:
        score += 1
    if features.recent_low_break_count >= transition.min_recent_low_break_count:
        score += 1
    if features.lower_highs_count >= transition.min_lower_highs_count:
        score += 1
    if features.price_below_ma_streak >= transition.min_price_below_ma_streak:
        score += 1
    if features.band_width_slope >= transition.min_band_width_slope:
        score += 1
    return score


def score_trend_up(features: V7FeatureSnapshot, params: V7DetectorParams) -> int:
    trend = params.trend
    score = 0
    if features.trend_slope >= trend.min_abs_trend_slope:
        score += 1
    if features.recent_high_break_count >= trend.min_recent_high_break_count:
        score += 1
    if features.higher_lows_count >= trend.min_higher_lows_count:
        score += 1
    if features.price_above_ma_streak >= trend.min_price_above_ma_streak:
        score += 1
    if features.band_width_slope >= trend.min_band_width_slope:
        score += 1
    return score


def score_trend_down(features: V7FeatureSnapshot, params: V7DetectorParams) -> int:
    trend = params.trend
    score = 0
    if features.trend_slope <= -trend.min_abs_trend_slope:
        score += 1
    if features.recent_low_break_count >= trend.min_recent_low_break_count:
        score += 1
    if features.lower_highs_count >= trend.min_lower_highs_count:
        score += 1
    if features.price_below_ma_streak >= trend.min_price_below_ma_streak:
        score += 1
    if features.band_width_slope >= trend.min_band_width_slope:
        score += 1
    return score


def build_score_snapshot(
    features: V7FeatureSnapshot,
    params: V7DetectorParams,
) -> V7ScoreSnapshot:
    return V7ScoreSnapshot(
        range_score=score_range(features, params),
        transition_to_trend_up_score=score_transition_to_trend_up(features, params),
        transition_to_trend_down_score=score_transition_to_trend_down(features, params),
        trend_up_score=score_trend_up(features, params),
        trend_down_score=score_trend_down(features, params),
    )


def _pick_initial_confirmed_state(
    scores: V7ScoreSnapshot,
    params: V7DetectorParams,
) -> V7MarketState:
    if scores.trend_up_score >= params.trend.min_trend_score_to_confirm:
        return V7MarketState.TREND_UP
    if scores.trend_down_score >= params.trend.min_trend_score_to_confirm:
        return V7MarketState.TREND_DOWN
    if (
        scores.transition_to_trend_up_score
        >= params.transition.min_transition_score_to_confirm
    ):
        return V7MarketState.TRANSITION_TO_TREND_UP
    if (
        scores.transition_to_trend_down_score
        >= params.transition.min_transition_score_to_confirm
    ):
        return V7MarketState.TRANSITION_TO_TREND_DOWN
    if scores.range_score >= params.range.min_range_score_to_confirm:
        return V7MarketState.RANGE
    return V7MarketState.UNKNOWN


def _candidate_started_event(candidate_state: V7MarketState) -> V7TransitionEvent:
    if candidate_state == V7MarketState.TRANSITION_TO_TREND_UP:
        return V7TransitionEvent.TRANSITION_TO_TREND_UP_STARTED
    if candidate_state == V7MarketState.TRANSITION_TO_TREND_DOWN:
        return V7TransitionEvent.TRANSITION_TO_TREND_DOWN_STARTED
    return V7TransitionEvent.STATE_UNCHANGED


def _confirmed_started_event(state: V7MarketState) -> V7TransitionEvent:
    if state == V7MarketState.RANGE:
        return V7TransitionEvent.RANGE_STARTED
    if state == V7MarketState.TREND_UP:
        return V7TransitionEvent.TREND_UP_STARTED
    if state == V7MarketState.TREND_DOWN:
        return V7TransitionEvent.TREND_DOWN_STARTED
    return V7TransitionEvent.STATE_UNCHANGED


def _candidate_cancelled_event(
    candidate_state: V7MarketState | None,
) -> V7TransitionEvent:
    if candidate_state == V7MarketState.TRANSITION_TO_TREND_UP:
        return V7TransitionEvent.TRANSITION_TO_TREND_UP_CANCELLED
    if candidate_state == V7MarketState.TRANSITION_TO_TREND_DOWN:
        return V7TransitionEvent.TRANSITION_TO_TREND_DOWN_CANCELLED
    return V7TransitionEvent.STATE_UNCHANGED


def _build_reason(
    *,
    decision_state: V7MarketState,
    candidate_state: V7MarketState | None,
    transition_event: V7TransitionEvent,
    scores: V7ScoreSnapshot,
) -> str:
    return (
        f"confirmed_state={decision_state.value}, "
        f"candidate_state={candidate_state.value if candidate_state else 'none'}, "
        f"event={transition_event.value}, "
        f"range_score={scores.range_score}, "
        f"transition_up_score={scores.transition_to_trend_up_score}, "
        f"transition_down_score={scores.transition_to_trend_down_score}, "
        f"trend_up_score={scores.trend_up_score}, "
        f"trend_down_score={scores.trend_down_score}"
    )


def detect_v7_market_state_from_snapshot(
    features: V7FeatureSnapshot,
    previous_context: V7StateContext,
    params: V7DetectorParams,
) -> V7StateDecision:
    scores = build_score_snapshot(features, params)

    if previous_context.confirmed_state == V7MarketState.UNKNOWN:
        initial_state = _pick_initial_confirmed_state(scores, params)
        transition_event = (
            V7TransitionEvent.INITIALIZED
            if initial_state == V7MarketState.UNKNOWN
            else _confirmed_started_event(initial_state)
        )
        reason = _build_reason(
            decision_state=initial_state,
            candidate_state=None,
            transition_event=transition_event,
            scores=scores,
        )
        return V7StateDecision(
            confirmed_state=initial_state,
            candidate_state=None,
            transition_event=transition_event,
            confirmed_state_age=1 if initial_state != V7MarketState.UNKNOWN else 0,
            candidate_state_age=0,
            detector_reason=reason,
            feature_snapshot=features,
            score_snapshot=scores,
        )

    confirmed_state = previous_context.confirmed_state
    confirmed_age = previous_context.confirmed_state_age + 1
    candidate_state = previous_context.candidate_state
    candidate_age = previous_context.candidate_state_age
    transition_event = V7TransitionEvent.STATE_UNCHANGED

    if scores.trend_up_score >= params.trend.min_trend_score_to_confirm:
        desired_candidate = V7MarketState.TREND_UP
    elif scores.trend_down_score >= params.trend.min_trend_score_to_confirm:
        desired_candidate = V7MarketState.TREND_DOWN
    elif (
        scores.transition_to_trend_up_score
        >= params.transition.min_transition_score_to_confirm
    ):
        desired_candidate = V7MarketState.TRANSITION_TO_TREND_UP
    elif (
        scores.transition_to_trend_down_score
        >= params.transition.min_transition_score_to_confirm
    ):
        desired_candidate = V7MarketState.TRANSITION_TO_TREND_DOWN
    elif scores.range_score >= params.range.min_range_score_to_confirm:
        desired_candidate = V7MarketState.RANGE
    else:
        desired_candidate = None

    if desired_candidate is None:
        if candidate_state is not None:
            transition_event = _candidate_cancelled_event(candidate_state)
        candidate_state = None
        candidate_age = 0
        reason = _build_reason(
            decision_state=confirmed_state,
            candidate_state=candidate_state,
            transition_event=transition_event,
            scores=scores,
        )
        return V7StateDecision(
            confirmed_state=confirmed_state,
            candidate_state=candidate_state,
            transition_event=transition_event,
            confirmed_state_age=confirmed_age,
            candidate_state_age=candidate_age,
            detector_reason=reason,
            feature_snapshot=features,
            score_snapshot=scores,
        )

    if desired_candidate == confirmed_state:
        if candidate_state is not None:
            transition_event = _candidate_cancelled_event(candidate_state)
        candidate_state = None
        candidate_age = 0
        reason = _build_reason(
            decision_state=confirmed_state,
            candidate_state=candidate_state,
            transition_event=transition_event,
            scores=scores,
        )
        return V7StateDecision(
            confirmed_state=confirmed_state,
            candidate_state=candidate_state,
            transition_event=transition_event,
            confirmed_state_age=confirmed_age,
            candidate_state_age=candidate_age,
            detector_reason=reason,
            feature_snapshot=features,
            score_snapshot=scores,
        )

    if candidate_state == desired_candidate:
        candidate_age += 1
    else:
        if candidate_state is not None:
            transition_event = _candidate_cancelled_event(candidate_state)
        candidate_state = desired_candidate
        candidate_age = 1
        started_event = _candidate_started_event(candidate_state)
        if started_event != V7TransitionEvent.STATE_UNCHANGED:
            transition_event = started_event

    confirm_bars = (
        params.timing.trend_confirm_bars
        if candidate_state in {V7MarketState.TREND_UP, V7MarketState.TREND_DOWN}
        else params.timing.transition_confirm_bars
        if candidate_state
        in {
            V7MarketState.TRANSITION_TO_TREND_UP,
            V7MarketState.TRANSITION_TO_TREND_DOWN,
        }
        else params.timing.range_confirm_bars
    )

    if candidate_age >= confirm_bars:
        confirmed_state = candidate_state
        confirmed_age = 1
        candidate_state = None
        candidate_age = 0

        if confirmed_state == V7MarketState.RANGE:
            transition_event = V7TransitionEvent.RANGE_STARTED
        elif confirmed_state == V7MarketState.TREND_UP:
            transition_event = V7TransitionEvent.TREND_UP_STARTED
        elif confirmed_state == V7MarketState.TREND_DOWN:
            transition_event = V7TransitionEvent.TREND_DOWN_STARTED
        elif confirmed_state == V7MarketState.TRANSITION_TO_TREND_UP:
            transition_event = V7TransitionEvent.TRANSITION_TO_TREND_UP_STARTED
        elif confirmed_state == V7MarketState.TRANSITION_TO_TREND_DOWN:
            transition_event = V7TransitionEvent.TRANSITION_TO_TREND_DOWN_STARTED

    reason = _build_reason(
        decision_state=confirmed_state,
        candidate_state=candidate_state,
        transition_event=transition_event,
        scores=scores,
    )
    return V7StateDecision(
        confirmed_state=confirmed_state,
        candidate_state=candidate_state,
        transition_event=transition_event,
        confirmed_state_age=confirmed_age,
        candidate_state_age=candidate_age,
        detector_reason=reason,
        feature_snapshot=features,
        score_snapshot=scores,
    )


def initialize_v7_state_context_from_bars(
    bars: list[Bar],
    params: V7DetectorParams = V7_DEFAULT_PARAMS,
) -> V7StateDecision:
    required_bars = required_bars_for_v7_features(params)
    if len(bars) < required_bars:
        raise SignalEngineError(
            f"At least {required_bars} bars are required to initialize v7 state context"
        )

    context = build_initial_state_context()
    latest_decision: V7StateDecision | None = None

    for index in range(required_bars, len(bars) + 1):
        features = build_v7_feature_snapshot_from_bars(bars[:index], params)
        latest_decision = detect_v7_market_state_from_snapshot(features, context, params)
        context = V7StateContext(
            confirmed_state=latest_decision.confirmed_state,
            candidate_state=latest_decision.candidate_state,
            confirmed_state_age=latest_decision.confirmed_state_age,
            candidate_state_age=latest_decision.candidate_state_age,
            last_range_score=latest_decision.score_snapshot.range_score,
            last_transition_up_score=latest_decision.score_snapshot.transition_to_trend_up_score,
            last_transition_down_score=latest_decision.score_snapshot.transition_to_trend_down_score,
            last_trend_up_score=latest_decision.score_snapshot.trend_up_score,
            last_trend_down_score=latest_decision.score_snapshot.trend_down_score,
        )

    if latest_decision is None:
        raise SignalEngineError("Failed to initialize v7 state context")

    return latest_decision


def advance_v7_state_context_from_bars(
    bars: list[Bar],
    previous_context: V7StateContext,
    params: V7DetectorParams = V7_DEFAULT_PARAMS,
) -> V7StateDecision:
    required_bars = required_bars_for_v7_features(params)
    if len(bars) < required_bars:
        raise SignalEngineError(
            f"At least {required_bars} bars are required to advance v7 state context"
        )

    features = build_v7_feature_snapshot_from_bars(bars, params)
    return detect_v7_market_state_from_snapshot(features, previous_context, params)


def detect_v7_market_state(
    market_snapshot: MarketSnapshot,
    params: V7DetectorParams = V7_DEFAULT_PARAMS,
) -> V7StateDecision:
    required_bars = required_bars_for_v7_features(params)
    bars = market_snapshot.bars
    if len(bars) < required_bars:
        raise SignalEngineError(
            f"At least {required_bars} bars are required to detect v7 market state"
        )

    return initialize_v7_state_context_from_bars(bars, params)