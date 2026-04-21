# src/mt4_bridge/strategies/bollinger_trend_B_rules.py
from __future__ import annotations

from mt4_bridge.models import OpenPosition, PositionSnapshot

from mt4_bridge.strategies.bollinger_trend_B_params import (
    STRONG_TREND_SLOPE_THRESHOLD,
    TREND_MAGIC_NUMBER,
    TREND_PRICE_POSITION_FILTER_ENABLED,
    TREND_SLOPE_THRESHOLD,
)
from mt4_bridge.strategies.bollinger_trend_B_indicators import (
    _distance_from_middle,
)


def _analyze_trend_up(
    latest_close: float,
    trend_current_ma: float,
    trend_slope: float,
) -> tuple[bool, bool, bool]:
    slope_passed = trend_slope > TREND_SLOPE_THRESHOLD
    price_passed = (
        latest_close >= trend_current_ma
        if TREND_PRICE_POSITION_FILTER_ENABLED
        else True
    )
    return slope_passed and price_passed, slope_passed, price_passed


def _analyze_trend_down(
    latest_close: float,
    trend_current_ma: float,
    trend_slope: float,
) -> tuple[bool, bool, bool]:
    slope_passed = trend_slope < -TREND_SLOPE_THRESHOLD
    price_passed = (
        latest_close <= trend_current_ma
        if TREND_PRICE_POSITION_FILTER_ENABLED
        else True
    )
    return slope_passed and price_passed, slope_passed, price_passed


def _determine_market_state(
    latest_close: float,
    middle_band: float,
    trend_current_ma: float,
    trend_slope: float,
    normalized_band_width: float,
) -> tuple[str, str, float, bool, bool, bool, bool, str | None]:
    distance_from_middle = _distance_from_middle(latest_close, middle_band)

    is_trend_up, trend_up_slope_passed, trend_up_price_passed = _analyze_trend_up(
        latest_close=latest_close,
        trend_current_ma=trend_current_ma,
        trend_slope=trend_slope,
    )
    if is_trend_up:
        if trend_slope >= STRONG_TREND_SLOPE_THRESHOLD:
            return (
                "strong_trend_up",
                (
                    f"strong_trend_up because trend_slope={trend_slope:.6f}"
                    f" >= strong_threshold={STRONG_TREND_SLOPE_THRESHOLD:.6f}"
                    f" and latest_close={latest_close} >= trend_ma={trend_current_ma}"
                ),
                distance_from_middle,
                trend_up_slope_passed,
                trend_up_price_passed,
                False,
                False,
                "upper_1sigma_touch",
            )
        return (
            "trend_up",
            (
                f"trend_up because trend_slope={trend_slope:.6f}"
                f" > threshold={TREND_SLOPE_THRESHOLD:.6f}"
                f" and latest_close={latest_close} >= trend_ma={trend_current_ma}"
            ),
            distance_from_middle,
            trend_up_slope_passed,
            trend_up_price_passed,
            False,
            False,
            "middle_touch",
        )

    is_trend_down, trend_down_slope_passed, trend_down_price_passed = (
        _analyze_trend_down(
            latest_close=latest_close,
            trend_current_ma=trend_current_ma,
            trend_slope=trend_slope,
        )
    )
    if is_trend_down:
        if trend_slope <= -STRONG_TREND_SLOPE_THRESHOLD:
            return (
                "strong_trend_down",
                (
                    f"strong_trend_down because trend_slope={trend_slope:.6f}"
                    f" <= -strong_threshold={STRONG_TREND_SLOPE_THRESHOLD:.6f}"
                    f" and latest_close={latest_close} <= trend_ma={trend_current_ma}"
                ),
                distance_from_middle,
                trend_up_slope_passed,
                trend_up_price_passed,
                trend_down_slope_passed,
                trend_down_price_passed,
                "lower_1sigma_touch",
            )
        return (
            "trend_down",
            (
                f"trend_down because trend_slope={trend_slope:.6f}"
                f" < -threshold={TREND_SLOPE_THRESHOLD:.6f}"
                f" and latest_close={latest_close} <= trend_ma={trend_current_ma}"
            ),
            distance_from_middle,
            trend_up_slope_passed,
            trend_up_price_passed,
            trend_down_slope_passed,
            trend_down_price_passed,
            "middle_touch",
        )

    if trend_up_slope_passed and not trend_up_price_passed:
        state_reason = (
            "neutral because up-slope passed but up price-position filter failed"
            f" (latest_close={latest_close}, trend_ma={trend_current_ma},"
            f" trend_slope={trend_slope:.6f}, threshold={TREND_SLOPE_THRESHOLD:.6f})"
        )
    elif trend_down_slope_passed and not trend_down_price_passed:
        state_reason = (
            "neutral because down-slope passed but down price-position filter failed"
            f" (latest_close={latest_close}, trend_ma={trend_current_ma},"
            f" trend_slope={trend_slope:.6f}, threshold={TREND_SLOPE_THRESHOLD:.6f})"
        )
    else:
        state_reason = (
            "neutral because no strong trend was confirmed"
            f" (trend_slope={trend_slope:.6f},"
            f" normalized_band_width={normalized_band_width:.6f},"
            f" distance_from_middle={distance_from_middle:.6f})"
        )

    return (
        "neutral",
        state_reason,
        distance_from_middle,
        trend_up_slope_passed,
        trend_up_price_passed,
        trend_down_slope_passed,
        trend_down_price_passed,
        None,
    )


def _trend_buy_touch_confirmed(
    latest_low: float,
    entry_band: float,
) -> bool:
    return latest_low <= entry_band


def _trend_sell_touch_confirmed(
    latest_high: float,
    entry_band: float,
) -> bool:
    return latest_high >= entry_band


def _trend_buy_take_profit_confirmed(
    latest_high: float,
    latest_upper_band: float,
) -> bool:
    return latest_high >= latest_upper_band


def _trend_sell_take_profit_confirmed(
    latest_low: float,
    latest_lower_band: float,
) -> bool:
    return latest_low <= latest_lower_band


def _is_trend_lane_position(position: OpenPosition) -> bool:
    comment = (position.comment or "").lower()
    return (
        position.magic_number == TREND_MAGIC_NUMBER
        or "lane:trend" in comment
        or "entry_lane=trend" in comment
    )


def _get_trend_position(position_snapshot: PositionSnapshot) -> OpenPosition | None:
    for position in position_snapshot.positions:
        if _is_trend_lane_position(position):
            return position
    return None
