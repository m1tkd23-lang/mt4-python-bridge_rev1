# src/mt4_bridge/strategies/bollinger_range_v4_4_rules.py
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

from mt4_bridge.strategies.bollinger_range_v4_4_params import (
    BAND_WALK_MIN_HITS,
    BAND_WIDTH_EXPANSION_THRESHOLD,
    RANGE_BAND_WIDTH_THRESHOLD,
    RANGE_FAILURE_ADVERSE_MOVE_RATIO,
    RANGE_MIDDLE_DISTANCE_THRESHOLD,
    RANGE_REQUIRE_REENTRY_CONFIRMATION,
    RANGE_SLOPE_THRESHOLD,
    TREND_PRICE_POSITION_FILTER_ENABLED,
    TREND_REQUIRE_BREAK_CONFIRMATION,
    TREND_SLOPE_ACCEL_THRESHOLD,
    TREND_SLOPE_THRESHOLD,
)
from mt4_bridge.strategies.bollinger_range_v4_4_indicators import (
    _distance_from_middle,
)


def _is_trend_up(
    latest_close: float,
    trend_current_ma: float,
    trend_slope: float,
) -> bool:
    if trend_slope <= TREND_SLOPE_THRESHOLD:
        return False
    if TREND_PRICE_POSITION_FILTER_ENABLED and latest_close < trend_current_ma:
        return False
    return True


def _is_trend_down(
    latest_close: float,
    trend_current_ma: float,
    trend_slope: float,
) -> bool:
    if trend_slope >= -TREND_SLOPE_THRESHOLD:
        return False
    if TREND_PRICE_POSITION_FILTER_ENABLED and latest_close > trend_current_ma:
        return False
    return True


def _is_range(
    latest_close: float,
    middle_band: float,
    range_slope: float,
    normalized_band_width: float,
) -> bool:
    distance_from_middle = _distance_from_middle(latest_close, middle_band)
    return (
        abs(range_slope) <= RANGE_SLOPE_THRESHOLD
        and normalized_band_width <= RANGE_BAND_WIDTH_THRESHOLD
        and distance_from_middle <= RANGE_MIDDLE_DISTANCE_THRESHOLD
    )


def _determine_market_state(
    latest_close: float,
    middle_band: float,
    trend_current_ma: float,
    range_slope: float,
    trend_slope: float,
    normalized_band_width: float,
) -> tuple[str, str, float]:
    distance_from_middle = _distance_from_middle(latest_close, middle_band)

    if _is_trend_up(latest_close, trend_current_ma, trend_slope):
        return (
            "trend_up",
            (
                f"trend_up because trend_slope={trend_slope:.6f}"
                f" > threshold={TREND_SLOPE_THRESHOLD:.6f}"
                f" and latest_close={latest_close} >= trend_ma={trend_current_ma}"
            ),
            distance_from_middle,
        )

    if _is_trend_down(latest_close, trend_current_ma, trend_slope):
        return (
            "trend_down",
            (
                f"trend_down because trend_slope={trend_slope:.6f}"
                f" < -threshold={TREND_SLOPE_THRESHOLD:.6f}"
                f" and latest_close={latest_close} <= trend_ma={trend_current_ma}"
            ),
            distance_from_middle,
        )

    if _is_range(
        latest_close=latest_close,
        middle_band=middle_band,
        range_slope=range_slope,
        normalized_band_width=normalized_band_width,
    ):
        return (
            "range",
            (
                f"range because abs(range_slope)={abs(range_slope):.6f}"
                f" <= threshold={RANGE_SLOPE_THRESHOLD:.6f}"
                f" and normalized_band_width={normalized_band_width:.6f}"
                f" <= threshold={RANGE_BAND_WIDTH_THRESHOLD:.6f}"
                f" and distance_from_middle={distance_from_middle:.6f}"
                f" <= threshold={RANGE_MIDDLE_DISTANCE_THRESHOLD:.6f}"
            ),
            distance_from_middle,
        )

    return (
        "neutral",
        (
            f"neutral because no strong trend or range was confirmed"
            f" (range_slope={range_slope:.6f}, trend_slope={trend_slope:.6f},"
            f" normalized_band_width={normalized_band_width:.6f},"
            f" distance_from_middle={distance_from_middle:.6f})"
        ),
        distance_from_middle,
    )


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


def _range_extreme_buy_touch_confirmed(
    latest_low: float,
    latest_lower_extreme_band: float,
) -> bool:
    return latest_low <= latest_lower_extreme_band


def _range_extreme_sell_touch_confirmed(
    latest_high: float,
    latest_upper_extreme_band: float,
) -> bool:
    return latest_high >= latest_upper_extreme_band


def _range_buy_failure_exit(
    latest_close: float,
    previous_close: float,
    entry_price: float,
    middle_band: float,
    band_width: float,
) -> bool:
    adverse_threshold = band_width * RANGE_FAILURE_ADVERSE_MOVE_RATIO
    adverse_move = max(0.0, entry_price - latest_close)
    return (
        latest_close < entry_price
        and latest_close <= previous_close
        and latest_close < middle_band
        and adverse_move >= adverse_threshold
    )


def _range_sell_failure_exit(
    latest_close: float,
    previous_close: float,
    entry_price: float,
    middle_band: float,
    band_width: float,
) -> bool:
    adverse_threshold = band_width * RANGE_FAILURE_ADVERSE_MOVE_RATIO
    adverse_move = max(0.0, latest_close - entry_price)
    return (
        latest_close > entry_price
        and latest_close >= previous_close
        and latest_close > middle_band
        and adverse_move >= adverse_threshold
    )


# =============================================================================
# RangeObservation: 現在バー時点の観測値を構造化して保持する dataclass
# (TASK-0109)
# 売買ロジックには接続しない。後続の decision log / 中央回帰分析で利用する。
# =============================================================================


@dataclass(frozen=True)
class RangeObservation:
    market_state: str
    entry_setup_type: Optional[str]
    middle_band: float
    upper_band: float
    lower_band: float
    upper_extreme_band_3sigma: float
    lower_extreme_band_3sigma: float
    band_width: float
    normalized_band_width: float
    distance_from_middle: float
    range_slope: float
    trend_slope: float
    trend_current_ma: float
    band_walk_upper_hits: int
    band_walk_lower_hits: int
    middle_cross_count: int
    stay_above_middle_ratio: float
    stay_below_middle_ratio: float
    band_width_change_ratio: float
    trend_slope_acceleration_ratio: float
    range_unsuitable_flag_band_walk: bool
    range_unsuitable_flag_one_side_stay: bool
    range_unsuitable_flag_bandwidth_expansion: bool
    range_unsuitable_flag_slope_acceleration: bool


def build_range_observation(
    *,
    market_state: str,
    entry_setup_type: Optional[str],
    middle_band: float,
    upper_band: float,
    lower_band: float,
    upper_extreme_band_3sigma: float,
    lower_extreme_band_3sigma: float,
    band_width: float,
    normalized_band_width: float,
    distance_from_middle: float,
    range_slope: float,
    trend_slope: float,
    trend_current_ma: float,
    band_walk_stats: dict,
    middle_cross_stats: dict,
    one_side_stay_stats: dict,
    band_width_expansion_stats: dict,
    trend_slope_accel_stats: dict,
) -> RangeObservation:
    band_walk_upper_hits = band_walk_stats.get("upper_hits_count", 0)
    band_walk_lower_hits = band_walk_stats.get("lower_hits_count", 0)
    middle_cross_count = middle_cross_stats.get("cross_count", 0)
    stay_above_middle_ratio = one_side_stay_stats.get("above_ratio", 0.0)
    stay_below_middle_ratio = one_side_stay_stats.get("below_ratio", 0.0)
    band_width_change_ratio = band_width_expansion_stats.get("expansion_ratio", 0.0)
    trend_slope_acceleration_ratio = trend_slope_accel_stats.get(
        "acceleration_ratio", 0.0
    )

    range_unsuitable_flag_band_walk = (
        band_walk_upper_hits >= BAND_WALK_MIN_HITS
        or band_walk_lower_hits >= BAND_WALK_MIN_HITS
    )
    range_unsuitable_flag_one_side_stay = one_side_stay_stats.get("is_one_side", False)
    range_unsuitable_flag_bandwidth_expansion = (
        band_width_change_ratio >= BAND_WIDTH_EXPANSION_THRESHOLD
    )
    range_unsuitable_flag_slope_acceleration = (
        abs(trend_slope_accel_stats.get("current_slope", 0.0))
        >= TREND_SLOPE_ACCEL_THRESHOLD
        and abs(trend_slope_acceleration_ratio) > 1.0
    )

    return RangeObservation(
        market_state=market_state,
        entry_setup_type=entry_setup_type,
        middle_band=middle_band,
        upper_band=upper_band,
        lower_band=lower_band,
        upper_extreme_band_3sigma=upper_extreme_band_3sigma,
        lower_extreme_band_3sigma=lower_extreme_band_3sigma,
        band_width=band_width,
        normalized_band_width=normalized_band_width,
        distance_from_middle=distance_from_middle,
        range_slope=range_slope,
        trend_slope=trend_slope,
        trend_current_ma=trend_current_ma,
        band_walk_upper_hits=band_walk_upper_hits,
        band_walk_lower_hits=band_walk_lower_hits,
        middle_cross_count=middle_cross_count,
        stay_above_middle_ratio=stay_above_middle_ratio,
        stay_below_middle_ratio=stay_below_middle_ratio,
        band_width_change_ratio=band_width_change_ratio,
        trend_slope_acceleration_ratio=trend_slope_acceleration_ratio,
        range_unsuitable_flag_band_walk=range_unsuitable_flag_band_walk,
        range_unsuitable_flag_one_side_stay=range_unsuitable_flag_one_side_stay,
        range_unsuitable_flag_bandwidth_expansion=range_unsuitable_flag_bandwidth_expansion,
        range_unsuitable_flag_slope_acceleration=range_unsuitable_flag_slope_acceleration,
    )


def range_observation_to_dict(obs: RangeObservation) -> dict:
    return asdict(obs)
