# src\mt4_bridge\strategies\v7_state_models.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class V7MarketState(str, Enum):
    RANGE = "range"
    TRANSITION_TO_TREND_UP = "transition_to_trend_up"
    TREND_UP = "trend_up"
    TRANSITION_TO_TREND_DOWN = "transition_to_trend_down"
    TREND_DOWN = "trend_down"
    UNKNOWN = "unknown"


class V7TransitionEvent(str, Enum):
    STATE_UNCHANGED = "state_unchanged"
    RANGE_STARTED = "range_started"
    RANGE_ENDED = "range_ended"
    TRANSITION_TO_TREND_UP_STARTED = "transition_to_trend_up_started"
    TRANSITION_TO_TREND_UP_CANCELLED = "transition_to_trend_up_cancelled"
    TREND_UP_STARTED = "trend_up_started"
    TREND_UP_ENDED = "trend_up_ended"
    TRANSITION_TO_TREND_DOWN_STARTED = "transition_to_trend_down_started"
    TRANSITION_TO_TREND_DOWN_CANCELLED = "transition_to_trend_down_cancelled"
    TREND_DOWN_STARTED = "trend_down_started"
    TREND_DOWN_ENDED = "trend_down_ended"
    INITIALIZED = "initialized"


@dataclass(frozen=True)
class V7FeatureParams:
    bollinger_period: int = 20
    bollinger_sigma: float = 2.0
    range_ma_period: int = 10
    trend_ma_period: int = 30
    range_slope_lookback: int = 5
    trend_slope_lookback: int = 2
    band_width_slope_lookback: int = 3
    structure_lookback_bars: int = 5
    streak_lookback_bars: int = 6
    price_epsilon: float = 0.0


@dataclass(frozen=True)
class V7RangeParams:
    max_abs_range_slope: float = 0.00022
    max_normalized_band_width: float = 0.0028
    max_distance_from_middle: float = 0.0015
    max_recent_high_break_count: int = 2
    max_recent_low_break_count: int = 2
    max_price_above_ma_streak: int = 2
    max_price_below_ma_streak: int = 2
    max_band_width_slope: float = 0.00020
    min_range_score_to_confirm: int = 5


@dataclass(frozen=True)
class V7TransitionParams:
    min_transition_trend_slope: float = 0.00005
    min_recent_high_break_count: int = 2
    min_recent_low_break_count: int = 2
    min_higher_lows_count: int = 2
    min_lower_highs_count: int = 2
    min_price_above_ma_streak: int = 2
    min_price_below_ma_streak: int = 2
    min_band_width_slope: float = 0.00002
    min_transition_score_to_confirm: int = 3


@dataclass(frozen=True)
class V7TrendParams:
    min_abs_trend_slope: float = 0.00020
    min_recent_high_break_count: int = 2
    min_recent_low_break_count: int = 2
    min_higher_lows_count: int = 2
    min_lower_highs_count: int = 2
    min_price_above_ma_streak: int = 3
    min_price_below_ma_streak: int = 3
    min_band_width_slope: float = 0.00004
    min_trend_score_to_confirm: int = 4


@dataclass(frozen=True)
class V7TimingParams:
    range_confirm_bars: int = 3
    transition_confirm_bars: int = 2
    trend_confirm_bars: int = 3
    state_exit_confirm_bars: int = 2


@dataclass(frozen=True)
class V7DetectorParams:
    feature: V7FeatureParams = field(default_factory=V7FeatureParams)
    range: V7RangeParams = field(default_factory=V7RangeParams)
    transition: V7TransitionParams = field(default_factory=V7TransitionParams)
    trend: V7TrendParams = field(default_factory=V7TrendParams)
    timing: V7TimingParams = field(default_factory=V7TimingParams)


@dataclass(frozen=True)
class V7FeatureSnapshot:
    latest_close: float
    middle_band: float
    upper_band: float
    lower_band: float
    normalized_band_width: float
    band_width_slope: float
    distance_from_middle: float
    range_slope: float
    trend_slope: float
    trend_ma: float
    recent_high_break_count: int
    recent_low_break_count: int
    higher_lows_count: int
    lower_highs_count: int
    price_above_ma_streak: int
    price_below_ma_streak: int


@dataclass(frozen=True)
class V7ScoreSnapshot:
    range_score: int
    transition_to_trend_up_score: int
    transition_to_trend_down_score: int
    trend_up_score: int
    trend_down_score: int


@dataclass(frozen=True)
class V7StateContext:
    confirmed_state: V7MarketState = V7MarketState.UNKNOWN
    candidate_state: V7MarketState | None = None
    confirmed_state_age: int = 0
    candidate_state_age: int = 0
    last_range_score: int = 0
    last_transition_up_score: int = 0
    last_transition_down_score: int = 0
    last_trend_up_score: int = 0
    last_trend_down_score: int = 0


@dataclass(frozen=True)
class V7StateDecision:
    confirmed_state: V7MarketState
    candidate_state: V7MarketState | None
    transition_event: V7TransitionEvent
    confirmed_state_age: int
    candidate_state_age: int
    detector_reason: str
    feature_snapshot: V7FeatureSnapshot
    score_snapshot: V7ScoreSnapshot


V7_DEFAULT_PARAMS = V7DetectorParams()