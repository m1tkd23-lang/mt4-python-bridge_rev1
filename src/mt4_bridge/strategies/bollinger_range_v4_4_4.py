# src/mt4_bridge/strategies/bollinger_range_v4_4_4.py
from __future__ import annotations

from math import sqrt

from mt4_bridge.models import (
    MarketSnapshot,
    PositionSnapshot,
    SignalAction,
    SignalDecision,
)
from mt4_bridge.signal_exceptions import SignalEngineError


# =========================
# 調整パラメータ
# =========================
# ボリンジャーバンド
BOLLINGER_PERIOD = 20
BOLLINGER_SIGMA = 2.0
BOLLINGER_EXTREME_SIGMA = 3.0

# レンジ判定用 MA
RANGE_MA_PERIOD = 10
RANGE_SLOPE_LOOKBACK = 5
RANGE_SLOPE_THRESHOLD = 0.0002

# レンジ判定用のバンド幅しきい値
RANGE_BAND_WIDTH_THRESHOLD = 0.0025

# レンジ判定用のミドル距離しきい値
RANGE_MIDDLE_DISTANCE_THRESHOLD = 0.0012

# =========================
# v4.4.1 由来: range強化ガード
# =========================
RANGE_MAX_TREND_SLOPE_FOR_RANGE = 0.00012

RANGE_RECENT_CLOSE_LOOKBACK = 6
RANGE_RECENT_MIDDLE_PROXIMITY_THRESHOLD = 0.0009
RANGE_RECENT_MIDDLE_PROXIMITY_RATIO = 0.67
RANGE_SIDE_DOMINANCE_MAX_RATIO = 0.80
RANGE_REQUIRE_BOTH_SIDES_OF_MIDDLE = True

# =========================
# トレンド判定用 MA
# =========================
TREND_MA_PERIOD = 30
TREND_SLOPE_LOOKBACK = 2

# strong trend 判定
TREND_SLOPE_THRESHOLD = 0.00022

# weak trend 判定
WEAK_TREND_SLOPE_THRESHOLD = 0.00005

# トレンド判定時に価格位置も見る
TREND_PRICE_POSITION_FILTER_ENABLED = True

# weak trend 補助条件
WEAK_TREND_REQUIRE_MIDDLE_SIDE = True
WEAK_TREND_ALLOW_IF_PRICE_ON_TREND_MA_SIDE = True

# =========================
# エントリー確認
# =========================
RANGE_REQUIRE_REENTRY_CONFIRMATION = True
TREND_REQUIRE_BREAK_CONFIRMATION = True

# strong / weak trend continuation
ENABLE_TREND_CONTINUATION_ENTRY = True
TREND_CONTINUATION_MIN_SLOPE = 0.00016
TREND_CONTINUATION_PULLBACK_DISTANCE_THRESHOLD = 0.00075

# =========================
# v4.4.4 追加:
# weak trend continuation をかなり単純化
# =========================
ENABLE_WEAK_TREND_CONTINUATION_ENTRY = True
WEAK_TREND_CONTINUATION_MIN_SLOPE = 0.00005
WEAK_TREND_CONTINUATION_MAX_DISTANCE_FROM_MIDDLE = 0.00110
WEAK_TREND_CONTINUATION_REQUIRE_SAME_DIRECTION_CLOSE = True
WEAK_TREND_CONTINUATION_REQUIRE_TREND_MA_SIDE = True

# 決済ルール
EXIT_ON_RANGE_MIDDLE_BAND = True
CLOSE_ON_OPPOSITE_TREND_STATE = True

# =========================
# range failure exit
# =========================
ENABLE_RANGE_FAILURE_EXIT = True
RANGE_FAILURE_ADVERSE_MOVE_RATIO = 0.28

# =========================
# 3σタッチ即時エントリー
# =========================
ENABLE_RANGE_EXTREME_TOUCH_ENTRY = True


def required_bars() -> int:
    return max(
        BOLLINGER_PERIOD,
        RANGE_MA_PERIOD + RANGE_SLOPE_LOOKBACK,
        TREND_MA_PERIOD + TREND_SLOPE_LOOKBACK,
        RANGE_RECENT_CLOSE_LOOKBACK,
    )


def _simple_moving_average(values: list[float]) -> float:
    if not values:
        raise SignalEngineError("Moving average requires at least 1 value")
    return sum(values) / len(values)


def _standard_deviation(values: list[float], mean: float) -> float:
    if not values:
        raise SignalEngineError("Standard deviation requires at least 1 value")
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return sqrt(variance)


def _calculate_bollinger_bands_from_window(
    window: list[float],
    sigma: float,
) -> tuple[float, float, float, float]:
    if len(window) < BOLLINGER_PERIOD:
        raise SignalEngineError(
            f"At least {BOLLINGER_PERIOD} closes are required for Bollinger Bands"
        )

    middle = _simple_moving_average(window)
    stddev = _standard_deviation(window, middle)
    upper = middle + (sigma * stddev)
    lower = middle - (sigma * stddev)
    band_width = upper - lower
    return middle, upper, lower, band_width


def _calculate_latest_bollinger_bands(
    closes: list[float],
    sigma: float,
) -> tuple[float, float, float, float]:
    if len(closes) < BOLLINGER_PERIOD:
        raise SignalEngineError(
            f"At least {BOLLINGER_PERIOD} closes are required for Bollinger Bands"
        )
    return _calculate_bollinger_bands_from_window(closes[-BOLLINGER_PERIOD:], sigma)


def _calculate_previous_bollinger_bands(
    closes: list[float],
    sigma: float,
) -> tuple[float, float, float, float]:
    if len(closes) < BOLLINGER_PERIOD + 1:
        raise SignalEngineError(
            f"At least {BOLLINGER_PERIOD + 1} closes are required for previous Bollinger Bands"
        )
    return _calculate_bollinger_bands_from_window(
        closes[-(BOLLINGER_PERIOD + 1) : -1],
        sigma,
    )


def _normalized_band_width(middle: float, band_width: float) -> float:
    if middle == 0:
        raise SignalEngineError("Middle band is zero; normalized band width undefined")
    return band_width / middle


def _distance_from_middle(latest_close: float, middle: float) -> float:
    if middle == 0:
        raise SignalEngineError("Middle band is zero; distance from middle undefined")
    return abs(latest_close - middle) / middle


def _calculate_recent_ma(
    closes: list[float],
    period: int,
) -> float:
    if len(closes) < period:
        raise SignalEngineError(
            f"At least {period} closes are required to calculate MA"
        )
    return _simple_moving_average(closes[-period:])


def _calculate_past_ma(
    closes: list[float],
    period: int,
    lookback: int,
) -> float:
    if len(closes) < period + lookback:
        raise SignalEngineError(
            f"At least {period + lookback} closes are required to calculate past MA"
        )
    end_index = len(closes) - lookback
    start_index = end_index - period
    window = closes[start_index:end_index]
    return _simple_moving_average(window)


def _normalized_slope(
    closes: list[float],
    period: int,
    lookback: int,
) -> tuple[float, float, float]:
    current_ma = _calculate_recent_ma(closes, period)
    past_ma = _calculate_past_ma(closes, period, lookback)

    if current_ma == 0:
        raise SignalEngineError("Current MA is zero; normalized slope undefined")

    slope = current_ma - past_ma
    normalized = slope / current_ma
    return normalized, current_ma, past_ma


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


def _is_weak_trend_up(
    latest_close: float,
    middle_band: float,
    trend_current_ma: float,
    trend_slope: float,
) -> bool:
    if trend_slope < WEAK_TREND_SLOPE_THRESHOLD:
        return False
    if trend_slope >= TREND_SLOPE_THRESHOLD:
        return False

    if WEAK_TREND_REQUIRE_MIDDLE_SIDE and latest_close < middle_band:
        return False

    if WEAK_TREND_ALLOW_IF_PRICE_ON_TREND_MA_SIDE and latest_close < trend_current_ma:
        return False

    return True


def _is_weak_trend_down(
    latest_close: float,
    middle_band: float,
    trend_current_ma: float,
    trend_slope: float,
) -> bool:
    if trend_slope > -WEAK_TREND_SLOPE_THRESHOLD:
        return False
    if trend_slope <= -TREND_SLOPE_THRESHOLD:
        return False

    if WEAK_TREND_REQUIRE_MIDDLE_SIDE and latest_close > middle_band:
        return False

    if WEAK_TREND_ALLOW_IF_PRICE_ON_TREND_MA_SIDE and latest_close > trend_current_ma:
        return False

    return True


def _analyze_recent_middle_behavior(
    closes: list[float],
    middle_band: float,
) -> tuple[float, float, float, bool]:
    if len(closes) < RANGE_RECENT_CLOSE_LOOKBACK:
        raise SignalEngineError(
            f"At least {RANGE_RECENT_CLOSE_LOOKBACK} closes are required for recent middle behavior"
        )
    if middle_band == 0:
        raise SignalEngineError("Middle band is zero; recent middle behavior undefined")

    recent_closes = closes[-RANGE_RECENT_CLOSE_LOOKBACK:]

    proximity_count = 0
    above_count = 0
    below_count = 0

    for close in recent_closes:
        normalized_distance = abs(close - middle_band) / middle_band
        if normalized_distance <= RANGE_RECENT_MIDDLE_PROXIMITY_THRESHOLD:
            proximity_count += 1

        if close >= middle_band:
            above_count += 1
        else:
            below_count += 1

    total = len(recent_closes)
    proximity_ratio = proximity_count / total
    above_ratio = above_count / total
    below_ratio = below_count / total
    has_both_sides = above_count > 0 and below_count > 0

    return proximity_ratio, above_ratio, below_ratio, has_both_sides


def _is_range(
    *,
    closes: list[float],
    latest_close: float,
    middle_band: float,
    range_slope: float,
    trend_slope: float,
    normalized_band_width: float,
) -> tuple[bool, str, float]:
    distance_from_middle = _distance_from_middle(latest_close, middle_band)
    (
        recent_middle_proximity_ratio,
        recent_above_ratio,
        recent_below_ratio,
        recent_has_both_sides,
    ) = _analyze_recent_middle_behavior(closes, middle_band)

    side_dominance_ratio = max(recent_above_ratio, recent_below_ratio)

    base_range_ok = (
        abs(range_slope) <= RANGE_SLOPE_THRESHOLD
        and normalized_band_width <= RANGE_BAND_WIDTH_THRESHOLD
        and distance_from_middle <= RANGE_MIDDLE_DISTANCE_THRESHOLD
    )

    trend_guard_ok = abs(trend_slope) <= RANGE_MAX_TREND_SLOPE_FOR_RANGE
    proximity_guard_ok = (
        recent_middle_proximity_ratio >= RANGE_RECENT_MIDDLE_PROXIMITY_RATIO
    )
    side_balance_guard_ok = side_dominance_ratio <= RANGE_SIDE_DOMINANCE_MAX_RATIO
    both_sides_guard_ok = (
        recent_has_both_sides if RANGE_REQUIRE_BOTH_SIDES_OF_MIDDLE else True
    )

    is_range = (
        base_range_ok
        and trend_guard_ok
        and proximity_guard_ok
        and side_balance_guard_ok
        and both_sides_guard_ok
    )

    reason = (
        f"range_checks=("
        f"base_range_ok={base_range_ok}, "
        f"trend_guard_ok={trend_guard_ok}, "
        f"proximity_guard_ok={proximity_guard_ok}, "
        f"side_balance_guard_ok={side_balance_guard_ok}, "
        f"both_sides_guard_ok={both_sides_guard_ok}, "
        f"abs(range_slope)={abs(range_slope):.6f}, "
        f"range_slope_threshold={RANGE_SLOPE_THRESHOLD:.6f}, "
        f"abs(trend_slope)={abs(trend_slope):.6f}, "
        f"range_max_trend_slope_for_range={RANGE_MAX_TREND_SLOPE_FOR_RANGE:.6f}, "
        f"normalized_band_width={normalized_band_width:.6f}, "
        f"range_band_width_threshold={RANGE_BAND_WIDTH_THRESHOLD:.6f}, "
        f"distance_from_middle={distance_from_middle:.6f}, "
        f"range_middle_distance_threshold={RANGE_MIDDLE_DISTANCE_THRESHOLD:.6f}, "
        f"recent_middle_proximity_ratio={recent_middle_proximity_ratio:.3f}, "
        f"recent_middle_proximity_ratio_threshold={RANGE_RECENT_MIDDLE_PROXIMITY_RATIO:.3f}, "
        f"recent_above_ratio={recent_above_ratio:.3f}, "
        f"recent_below_ratio={recent_below_ratio:.3f}, "
        f"side_dominance_ratio={side_dominance_ratio:.3f}, "
        f"side_dominance_max_ratio={RANGE_SIDE_DOMINANCE_MAX_RATIO:.3f}, "
        f"recent_has_both_sides={recent_has_both_sides})"
    )

    return is_range, reason, distance_from_middle


def _determine_market_state(
    *,
    closes: list[float],
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

    if _is_weak_trend_up(
        latest_close=latest_close,
        middle_band=middle_band,
        trend_current_ma=trend_current_ma,
        trend_slope=trend_slope,
    ):
        return (
            "weak_trend_up",
            (
                f"weak_trend_up because trend_slope={trend_slope:.6f}"
                f" >= weak_threshold={WEAK_TREND_SLOPE_THRESHOLD:.6f}"
                f" and < strong_threshold={TREND_SLOPE_THRESHOLD:.6f}"
                f" and latest_close={latest_close} >= middle={middle_band}"
                f" and latest_close={latest_close} >= trend_ma={trend_current_ma}"
            ),
            distance_from_middle,
        )

    if _is_weak_trend_down(
        latest_close=latest_close,
        middle_band=middle_band,
        trend_current_ma=trend_current_ma,
        trend_slope=trend_slope,
    ):
        return (
            "weak_trend_down",
            (
                f"weak_trend_down because trend_slope={trend_slope:.6f}"
                f" <= -weak_threshold={WEAK_TREND_SLOPE_THRESHOLD:.6f}"
                f" and > -strong_threshold={TREND_SLOPE_THRESHOLD:.6f}"
                f" and latest_close={latest_close} <= middle={middle_band}"
                f" and latest_close={latest_close} <= trend_ma={trend_current_ma}"
            ),
            distance_from_middle,
        )

    range_ok, range_reason, distance_from_middle = _is_range(
        closes=closes,
        latest_close=latest_close,
        middle_band=middle_band,
        range_slope=range_slope,
        trend_slope=trend_slope,
        normalized_band_width=normalized_band_width,
    )

    if range_ok:
        return "range", f"range because {range_reason}", distance_from_middle

    return (
        "neutral",
        (
            f"neutral because no strong trend, weak trend, or range was confirmed"
            f" (range_slope={range_slope:.6f}, trend_slope={trend_slope:.6f},"
            f" normalized_band_width={normalized_band_width:.6f},"
            f" distance_from_middle={distance_from_middle:.6f},"
            f" {range_reason})"
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


def _trend_continuation_buy_confirmed(
    *,
    previous_close: float,
    latest_close: float,
    middle_band: float,
    trend_current_ma: float,
    trend_slope: float,
) -> bool:
    if not ENABLE_TREND_CONTINUATION_ENTRY:
        return False

    latest_distance = _distance_from_middle(latest_close, middle_band)
    previous_distance = _distance_from_middle(previous_close, middle_band)

    return (
        trend_slope >= TREND_CONTINUATION_MIN_SLOPE
        and previous_close >= middle_band
        and latest_close >= middle_band
        and latest_close >= trend_current_ma
        and latest_close > previous_close
        and latest_distance <= TREND_CONTINUATION_PULLBACK_DISTANCE_THRESHOLD
        and latest_distance >= previous_distance
    )


def _trend_continuation_sell_confirmed(
    *,
    previous_close: float,
    latest_close: float,
    middle_band: float,
    trend_current_ma: float,
    trend_slope: float,
) -> bool:
    if not ENABLE_TREND_CONTINUATION_ENTRY:
        return False

    latest_distance = _distance_from_middle(latest_close, middle_band)
    previous_distance = _distance_from_middle(previous_close, middle_band)

    return (
        trend_slope <= -TREND_CONTINUATION_MIN_SLOPE
        and previous_close <= middle_band
        and latest_close <= middle_band
        and latest_close <= trend_current_ma
        and latest_close < previous_close
        and latest_distance <= TREND_CONTINUATION_PULLBACK_DISTANCE_THRESHOLD
        and latest_distance >= previous_distance
    )


def _weak_trend_continuation_buy_confirmed(
    *,
    previous_close: float,
    latest_close: float,
    middle_band: float,
    trend_current_ma: float,
    trend_slope: float,
) -> bool:
    if not ENABLE_WEAK_TREND_CONTINUATION_ENTRY:
        return False

    latest_distance = _distance_from_middle(latest_close, middle_band)

    if trend_slope < WEAK_TREND_CONTINUATION_MIN_SLOPE:
        return False
    if trend_slope >= TREND_SLOPE_THRESHOLD:
        return False
    if latest_close < middle_band:
        return False
    if WEAK_TREND_CONTINUATION_REQUIRE_TREND_MA_SIDE and latest_close < trend_current_ma:
        return False
    if WEAK_TREND_CONTINUATION_REQUIRE_SAME_DIRECTION_CLOSE and latest_close <= previous_close:
        return False
    if latest_distance > WEAK_TREND_CONTINUATION_MAX_DISTANCE_FROM_MIDDLE:
        return False

    return True


def _weak_trend_continuation_sell_confirmed(
    *,
    previous_close: float,
    latest_close: float,
    middle_band: float,
    trend_current_ma: float,
    trend_slope: float,
) -> bool:
    if not ENABLE_WEAK_TREND_CONTINUATION_ENTRY:
        return False

    latest_distance = _distance_from_middle(latest_close, middle_band)

    if trend_slope > -WEAK_TREND_CONTINUATION_MIN_SLOPE:
        return False
    if trend_slope <= -TREND_SLOPE_THRESHOLD:
        return False
    if latest_close > middle_band:
        return False
    if WEAK_TREND_CONTINUATION_REQUIRE_TREND_MA_SIDE and latest_close > trend_current_ma:
        return False
    if WEAK_TREND_CONTINUATION_REQUIRE_SAME_DIRECTION_CLOSE and latest_close >= previous_close:
        return False
    if latest_distance > WEAK_TREND_CONTINUATION_MAX_DISTANCE_FROM_MIDDLE:
        return False

    return True


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


def _build_signal_decision(
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
    market_state: str,
    middle_band: float,
    upper_band: float,
    lower_band: float,
    normalized_width: float,
    range_slope: float,
    trend_slope: float,
    trend_current_ma: float,
    distance_from_middle: float,
) -> SignalDecision:
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
        market_state=market_state,
        middle_band=middle_band,
        upper_band=upper_band,
        lower_band=lower_band,
        normalized_band_width=normalized_width,
        range_slope=range_slope,
        trend_slope=trend_slope,
        trend_current_ma=trend_current_ma,
        distance_from_middle=distance_from_middle,
    )


def _base_signal(
    market_snapshot: MarketSnapshot,
) -> tuple[
    SignalAction,
    str,
    str,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
]:
    bars = market_snapshot.bars

    if len(bars) < required_bars():
        raise SignalEngineError(
            f"At least {required_bars()} bars are required to evaluate bollinger_range_v4_4_4"
        )

    closes = [bar.close for bar in bars]
    previous_bar = bars[-2]
    latest_bar = bars[-1]
    previous_close = previous_bar.close
    latest_close = latest_bar.close

    latest_middle, latest_upper, latest_lower, latest_band_width = (
        _calculate_latest_bollinger_bands(closes, BOLLINGER_SIGMA)
    )
    _, previous_upper, previous_lower, _ = _calculate_previous_bollinger_bands(
        closes,
        BOLLINGER_SIGMA,
    )

    (
        _,
        latest_upper_extreme,
        latest_lower_extreme,
        _,
    ) = _calculate_latest_bollinger_bands(closes, BOLLINGER_EXTREME_SIGMA)

    normalized_width = _normalized_band_width(latest_middle, latest_band_width)

    range_slope, _, _ = _normalized_slope(
        closes=closes,
        period=RANGE_MA_PERIOD,
        lookback=RANGE_SLOPE_LOOKBACK,
    )
    trend_slope, trend_current_ma, _ = _normalized_slope(
        closes=closes,
        period=TREND_MA_PERIOD,
        lookback=TREND_SLOPE_LOOKBACK,
    )

    market_state, state_reason, distance_from_middle = _determine_market_state(
        closes=closes,
        latest_close=latest_close,
        middle_band=latest_middle,
        trend_current_ma=trend_current_ma,
        range_slope=range_slope,
        trend_slope=trend_slope,
        normalized_band_width=normalized_width,
    )

    if market_state == "range":
        if ENABLE_RANGE_EXTREME_TOUCH_ENTRY:
            if _range_extreme_sell_touch_confirmed(
                latest_high=latest_bar.high,
                latest_upper_extreme_band=latest_upper_extreme,
            ):
                return (
                    SignalAction.SELL,
                    (
                        f"range extreme-touch sell confirmed by 3sigma upper band touch;"
                        f" latest_high={latest_bar.high}, latest_upper_3sigma={latest_upper_extreme};"
                        f" {state_reason}"
                    ),
                    market_state,
                    latest_middle,
                    latest_upper,
                    latest_lower,
                    normalized_width,
                    range_slope,
                    trend_slope,
                    trend_current_ma,
                    previous_upper,
                    previous_lower,
                    distance_from_middle,
                    latest_upper_extreme,
                    latest_lower_extreme,
                )

            if _range_extreme_buy_touch_confirmed(
                latest_low=latest_bar.low,
                latest_lower_extreme_band=latest_lower_extreme,
            ):
                return (
                    SignalAction.BUY,
                    (
                        f"range extreme-touch buy confirmed by 3sigma lower band touch;"
                        f" latest_low={latest_bar.low}, latest_lower_3sigma={latest_lower_extreme};"
                        f" {state_reason}"
                    ),
                    market_state,
                    latest_middle,
                    latest_upper,
                    latest_lower,
                    normalized_width,
                    range_slope,
                    trend_slope,
                    trend_current_ma,
                    previous_upper,
                    previous_lower,
                    distance_from_middle,
                    latest_upper_extreme,
                    latest_lower_extreme,
                )

        if _range_sell_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            previous_upper_band=previous_upper,
            latest_upper_band=latest_upper,
        ):
            return (
                SignalAction.SELL,
                (
                    f"range mean-reversion sell confirmed by reentry from outside upper band;"
                    f" previous_close={previous_close}, latest_close={latest_close},"
                    f" previous_upper={previous_upper}, latest_upper={latest_upper};"
                    f" {state_reason}"
                ),
                market_state,
                latest_middle,
                latest_upper,
                latest_lower,
                normalized_width,
                range_slope,
                trend_slope,
                trend_current_ma,
                previous_upper,
                previous_lower,
                distance_from_middle,
                latest_upper_extreme,
                latest_lower_extreme,
            )

        if _range_buy_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            previous_lower_band=previous_lower,
            latest_lower_band=latest_lower,
        ):
            return (
                SignalAction.BUY,
                (
                    f"range mean-reversion buy confirmed by reentry from outside lower band;"
                    f" previous_close={previous_close}, latest_close={latest_close},"
                    f" previous_lower={previous_lower}, latest_lower={latest_lower};"
                    f" {state_reason}"
                ),
                market_state,
                latest_middle,
                latest_upper,
                latest_lower,
                normalized_width,
                range_slope,
                trend_slope,
                trend_current_ma,
                previous_upper,
                previous_lower,
                distance_from_middle,
                latest_upper_extreme,
                latest_lower_extreme,
            )

        return (
            SignalAction.HOLD,
            (
                f"range state but no confirmed signal"
                f" (previous_close={previous_close}, latest_close={latest_close},"
                f" previous_upper={previous_upper}, latest_upper={latest_upper},"
                f" previous_lower={previous_lower}, latest_lower={latest_lower},"
                f" latest_upper_3sigma={latest_upper_extreme},"
                f" latest_lower_3sigma={latest_lower_extreme},"
                f" latest_high={latest_bar.high}, latest_low={latest_bar.low});"
                f" {state_reason}"
            ),
            market_state,
            latest_middle,
            latest_upper,
            latest_lower,
            normalized_width,
            range_slope,
            trend_slope,
            trend_current_ma,
            previous_upper,
            previous_lower,
            distance_from_middle,
            latest_upper_extreme,
            latest_lower_extreme,
        )

    if market_state == "trend_up":
        if _trend_buy_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            previous_upper_band=previous_upper,
            latest_upper_band=latest_upper,
        ):
            return (
                SignalAction.BUY,
                (
                    f"trend-follow buy confirmed by upper band breakout;"
                    f" previous_close={previous_close}, latest_close={latest_close},"
                    f" previous_upper={previous_upper}, latest_upper={latest_upper};"
                    f" {state_reason}"
                ),
                market_state,
                latest_middle,
                latest_upper,
                latest_lower,
                normalized_width,
                range_slope,
                trend_slope,
                trend_current_ma,
                previous_upper,
                previous_lower,
                distance_from_middle,
                latest_upper_extreme,
                latest_lower_extreme,
            )

        if _trend_continuation_buy_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            middle_band=latest_middle,
            trend_current_ma=trend_current_ma,
            trend_slope=trend_slope,
        ):
            return (
                SignalAction.BUY,
                (
                    f"trend-continuation buy confirmed without upper breakout;"
                    f" previous_close={previous_close}, latest_close={latest_close},"
                    f" middle={latest_middle}, trend_ma={trend_current_ma},"
                    f" trend_slope={trend_slope:.6f}; {state_reason}"
                ),
                market_state,
                latest_middle,
                latest_upper,
                latest_lower,
                normalized_width,
                range_slope,
                trend_slope,
                trend_current_ma,
                previous_upper,
                previous_lower,
                distance_from_middle,
                latest_upper_extreme,
                latest_lower_extreme,
            )

        return (
            SignalAction.HOLD,
            (
                f"trend_up state but no confirmed upper band breakout or continuation entry"
                f" (previous_close={previous_close}, latest_close={latest_close},"
                f" previous_upper={previous_upper}, latest_upper={latest_upper},"
                f" middle={latest_middle}, trend_ma={trend_current_ma});"
                f" {state_reason}"
            ),
            market_state,
            latest_middle,
            latest_upper,
            latest_lower,
            normalized_width,
            range_slope,
            trend_slope,
            trend_current_ma,
            previous_upper,
            previous_lower,
            distance_from_middle,
            latest_upper_extreme,
            latest_lower_extreme,
        )

    if market_state == "trend_down":
        if _trend_sell_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            previous_lower_band=previous_lower,
            latest_lower_band=latest_lower,
        ):
            return (
                SignalAction.SELL,
                (
                    f"trend-follow sell confirmed by lower band breakout;"
                    f" previous_close={previous_close}, latest_close={latest_close},"
                    f" previous_lower={previous_lower}, latest_lower={latest_lower};"
                    f" {state_reason}"
                ),
                market_state,
                latest_middle,
                latest_upper,
                latest_lower,
                normalized_width,
                range_slope,
                trend_slope,
                trend_current_ma,
                previous_upper,
                previous_lower,
                distance_from_middle,
                latest_upper_extreme,
                latest_lower_extreme,
            )

        if _trend_continuation_sell_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            middle_band=latest_middle,
            trend_current_ma=trend_current_ma,
            trend_slope=trend_slope,
        ):
            return (
                SignalAction.SELL,
                (
                    f"trend-continuation sell confirmed without lower breakout;"
                    f" previous_close={previous_close}, latest_close={latest_close},"
                    f" middle={latest_middle}, trend_ma={trend_current_ma},"
                    f" trend_slope={trend_slope:.6f}; {state_reason}"
                ),
                market_state,
                latest_middle,
                latest_upper,
                latest_lower,
                normalized_width,
                range_slope,
                trend_slope,
                trend_current_ma,
                previous_upper,
                previous_lower,
                distance_from_middle,
                latest_upper_extreme,
                latest_lower_extreme,
            )

        return (
            SignalAction.HOLD,
            (
                f"trend_down state but no confirmed lower band breakout or continuation entry"
                f" (previous_close={previous_close}, latest_close={latest_close},"
                f" previous_lower={previous_lower}, latest_lower={latest_lower},"
                f" middle={latest_middle}, trend_ma={trend_current_ma});"
                f" {state_reason}"
            ),
            market_state,
            latest_middle,
            latest_upper,
            latest_lower,
            normalized_width,
            range_slope,
            trend_slope,
            trend_current_ma,
            previous_upper,
            previous_lower,
            distance_from_middle,
            latest_upper_extreme,
            latest_lower_extreme,
        )

    if market_state == "weak_trend_up":
        if _weak_trend_continuation_buy_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            middle_band=latest_middle,
            trend_current_ma=trend_current_ma,
            trend_slope=trend_slope,
        ):
            return (
                SignalAction.BUY,
                (
                    f"weak-trend continuation buy confirmed;"
                    f" previous_close={previous_close}, latest_close={latest_close},"
                    f" middle={latest_middle}, trend_ma={trend_current_ma},"
                    f" trend_slope={trend_slope:.6f}; {state_reason}"
                ),
                market_state,
                latest_middle,
                latest_upper,
                latest_lower,
                normalized_width,
                range_slope,
                trend_slope,
                trend_current_ma,
                previous_upper,
                previous_lower,
                distance_from_middle,
                latest_upper_extreme,
                latest_lower_extreme,
            )

        return (
            SignalAction.HOLD,
            (
                f"weak_trend_up state so range entries are skipped"
                f" and no weak-trend continuation entry was confirmed"
                f" (previous_close={previous_close}, latest_close={latest_close},"
                f" middle={latest_middle}, trend_ma={trend_current_ma});"
                f" {state_reason}"
            ),
            market_state,
            latest_middle,
            latest_upper,
            latest_lower,
            normalized_width,
            range_slope,
            trend_slope,
            trend_current_ma,
            previous_upper,
            previous_lower,
            distance_from_middle,
            latest_upper_extreme,
            latest_lower_extreme,
        )

    if market_state == "weak_trend_down":
        if _weak_trend_continuation_sell_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            middle_band=latest_middle,
            trend_current_ma=trend_current_ma,
            trend_slope=trend_slope,
        ):
            return (
                SignalAction.SELL,
                (
                    f"weak-trend continuation sell confirmed;"
                    f" previous_close={previous_close}, latest_close={latest_close},"
                    f" middle={latest_middle}, trend_ma={trend_current_ma},"
                    f" trend_slope={trend_slope:.6f}; {state_reason}"
                ),
                market_state,
                latest_middle,
                latest_upper,
                latest_lower,
                normalized_width,
                range_slope,
                trend_slope,
                trend_current_ma,
                previous_upper,
                previous_lower,
                distance_from_middle,
                latest_upper_extreme,
                latest_lower_extreme,
            )

        return (
            SignalAction.HOLD,
            (
                f"weak_trend_down state so range entries are skipped"
                f" and no weak-trend continuation entry was confirmed"
                f" (previous_close={previous_close}, latest_close={latest_close},"
                f" middle={latest_middle}, trend_ma={trend_current_ma});"
                f" {state_reason}"
            ),
            market_state,
            latest_middle,
            latest_upper,
            latest_lower,
            normalized_width,
            range_slope,
            trend_slope,
            trend_current_ma,
            previous_upper,
            previous_lower,
            distance_from_middle,
            latest_upper_extreme,
            latest_lower_extreme,
        )

    return (
        SignalAction.HOLD,
        (
            f"neutral state so entry is skipped"
            f" (previous_close={previous_close}, latest_close={latest_close},"
            f" previous_upper={previous_upper}, latest_upper={latest_upper},"
            f" previous_lower={previous_lower}, latest_lower={latest_lower},"
            f" latest_upper_3sigma={latest_upper_extreme},"
            f" latest_lower_3sigma={latest_lower_extreme},"
            f" latest_high={latest_bar.high}, latest_low={latest_bar.low});"
            f" {state_reason}"
        ),
        market_state,
        latest_middle,
        latest_upper,
        latest_lower,
        normalized_width,
        range_slope,
        trend_slope,
        trend_current_ma,
        previous_upper,
        previous_lower,
        distance_from_middle,
        latest_upper_extreme,
        latest_lower_extreme,
    )


def evaluate_bollinger_range_v4_4_4(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_range_v4_4_4",
) -> SignalDecision:
    bars = market_snapshot.bars
    if len(bars) < required_bars():
        raise SignalEngineError(
            f"At least {required_bars()} bars are required to evaluate bollinger_range_v4_4_4"
        )

    previous_bar = bars[-2]
    latest_bar = bars[-1]

    (
        base_action,
        base_reason,
        market_state,
        middle_band,
        upper_band,
        lower_band,
        normalized_width,
        range_slope,
        trend_slope,
        trend_current_ma,
        previous_upper_band,
        previous_lower_band,
        distance_from_middle,
        latest_upper_extreme_band,
        latest_lower_extreme_band,
    ) = _base_signal(market_snapshot)

    current_position = (
        position_snapshot.positions[0] if position_snapshot.positions else None
    )
    latest_band_width = upper_band - lower_band

    reason_suffix = (
        f" (bollinger_period={BOLLINGER_PERIOD}, bollinger_sigma={BOLLINGER_SIGMA},"
        f" bollinger_extreme_sigma={BOLLINGER_EXTREME_SIGMA},"
        f" range_ma_period={RANGE_MA_PERIOD},"
        f" range_slope_lookback={RANGE_SLOPE_LOOKBACK},"
        f" range_slope_threshold={RANGE_SLOPE_THRESHOLD},"
        f" range_band_width_threshold={RANGE_BAND_WIDTH_THRESHOLD},"
        f" range_middle_distance_threshold={RANGE_MIDDLE_DISTANCE_THRESHOLD},"
        f" range_max_trend_slope_for_range={RANGE_MAX_TREND_SLOPE_FOR_RANGE},"
        f" range_recent_close_lookback={RANGE_RECENT_CLOSE_LOOKBACK},"
        f" range_recent_middle_proximity_threshold={RANGE_RECENT_MIDDLE_PROXIMITY_THRESHOLD},"
        f" range_recent_middle_proximity_ratio={RANGE_RECENT_MIDDLE_PROXIMITY_RATIO},"
        f" range_side_dominance_max_ratio={RANGE_SIDE_DOMINANCE_MAX_RATIO},"
        f" range_require_both_sides_of_middle={RANGE_REQUIRE_BOTH_SIDES_OF_MIDDLE},"
        f" trend_ma_period={TREND_MA_PERIOD},"
        f" trend_slope_lookback={TREND_SLOPE_LOOKBACK},"
        f" trend_slope_threshold={TREND_SLOPE_THRESHOLD},"
        f" weak_trend_slope_threshold={WEAK_TREND_SLOPE_THRESHOLD},"
        f" trend_price_position_filter_enabled={TREND_PRICE_POSITION_FILTER_ENABLED},"
        f" weak_trend_require_middle_side={WEAK_TREND_REQUIRE_MIDDLE_SIDE},"
        f" weak_trend_allow_if_price_on_trend_ma_side={WEAK_TREND_ALLOW_IF_PRICE_ON_TREND_MA_SIDE},"
        f" range_require_reentry_confirmation={RANGE_REQUIRE_REENTRY_CONFIRMATION},"
        f" trend_require_break_confirmation={TREND_REQUIRE_BREAK_CONFIRMATION},"
        f" enable_trend_continuation_entry={ENABLE_TREND_CONTINUATION_ENTRY},"
        f" trend_continuation_min_slope={TREND_CONTINUATION_MIN_SLOPE},"
        f" trend_continuation_pullback_distance_threshold={TREND_CONTINUATION_PULLBACK_DISTANCE_THRESHOLD},"
        f" enable_weak_trend_continuation_entry={ENABLE_WEAK_TREND_CONTINUATION_ENTRY},"
        f" weak_trend_continuation_min_slope={WEAK_TREND_CONTINUATION_MIN_SLOPE},"
        f" weak_trend_continuation_max_distance_from_middle={WEAK_TREND_CONTINUATION_MAX_DISTANCE_FROM_MIDDLE},"
        f" weak_trend_continuation_require_same_direction_close={WEAK_TREND_CONTINUATION_REQUIRE_SAME_DIRECTION_CLOSE},"
        f" weak_trend_continuation_require_trend_ma_side={WEAK_TREND_CONTINUATION_REQUIRE_TREND_MA_SIDE},"
        f" exit_on_range_middle_band={EXIT_ON_RANGE_MIDDLE_BAND},"
        f" close_on_opposite_trend_state={CLOSE_ON_OPPOSITE_TREND_STATE},"
        f" enable_range_failure_exit={ENABLE_RANGE_FAILURE_EXIT},"
        f" range_failure_adverse_move_ratio={RANGE_FAILURE_ADVERSE_MOVE_RATIO},"
        f" enable_range_extreme_touch_entry={ENABLE_RANGE_EXTREME_TOUCH_ENTRY},"
        f" state={market_state}, middle={middle_band}, upper={upper_band},"
        f" lower={lower_band}, upper_3sigma={latest_upper_extreme_band},"
        f" lower_3sigma={latest_lower_extreme_band},"
        f" previous_upper={previous_upper_band}, previous_lower={previous_lower_band},"
        f" normalized_band_width={normalized_width:.6f},"
        f" latest_band_width={latest_band_width:.6f},"
        f" distance_from_middle={distance_from_middle:.6f},"
        f" range_slope={range_slope:.6f}, trend_slope={trend_slope:.6f},"
        f" trend_current_ma={trend_current_ma},"
        f" latest_high={latest_bar.high}, latest_low={latest_bar.low})"
    )

    common_kwargs = {
        "strategy_name": strategy_name,
        "previous_bar_time": previous_bar.time,
        "latest_bar_time": latest_bar.time,
        "previous_close": previous_bar.close,
        "latest_close": latest_bar.close,
        "current_position_ticket": current_position.ticket if current_position else None,
        "current_position_type": current_position.position_type.lower()
        if current_position
        else None,
        "market_state": market_state,
        "middle_band": middle_band,
        "upper_band": upper_band,
        "lower_band": lower_band,
        "normalized_width": normalized_width,
        "range_slope": range_slope,
        "trend_slope": trend_slope,
        "trend_current_ma": trend_current_ma,
        "distance_from_middle": distance_from_middle,
    }

    if current_position is None:
        return _build_signal_decision(
            action=base_action,
            reason=base_reason + reason_suffix,
            **common_kwargs,
        )

    current_type = current_position.position_type.lower()
    entry_price = current_position.open_price

    if ENABLE_RANGE_FAILURE_EXIT and market_state == "range":
        if current_type == "buy" and _range_buy_failure_exit(
            latest_close=latest_bar.close,
            previous_close=previous_bar.close,
            entry_price=entry_price,
            middle_band=middle_band,
            band_width=latest_band_width,
        ):
            return _build_signal_decision(
                action=SignalAction.CLOSE,
                reason=(
                    "buy position closed because range recovery failed and adverse move resumed"
                    f" (entry_price={entry_price}, previous_close={previous_bar.close},"
                    f" latest_close={latest_bar.close}, middle={middle_band},"
                    f" band_width={latest_band_width})"
                    + reason_suffix
                ),
                **common_kwargs,
            )

        if current_type == "sell" and _range_sell_failure_exit(
            latest_close=latest_bar.close,
            previous_close=previous_bar.close,
            entry_price=entry_price,
            middle_band=middle_band,
            band_width=latest_band_width,
        ):
            return _build_signal_decision(
                action=SignalAction.CLOSE,
                reason=(
                    "sell position closed because range recovery failed and adverse move resumed"
                    f" (entry_price={entry_price}, previous_close={previous_bar.close},"
                    f" latest_close={latest_bar.close}, middle={middle_band},"
                    f" band_width={latest_band_width})"
                    + reason_suffix
                ),
                **common_kwargs,
            )

    if market_state == "range" and EXIT_ON_RANGE_MIDDLE_BAND:
        if current_type == "buy" and latest_bar.close >= middle_band:
            return _build_signal_decision(
                action=SignalAction.CLOSE,
                reason=(
                    f"buy position closed because range state returned to middle band:"
                    f" latest close {latest_bar.close} >= middle {middle_band}"
                    + reason_suffix
                ),
                **common_kwargs,
            )

        if current_type == "sell" and latest_bar.close <= middle_band:
            return _build_signal_decision(
                action=SignalAction.CLOSE,
                reason=(
                    f"sell position closed because range state returned to middle band:"
                    f" latest close {latest_bar.close} <= middle {middle_band}"
                    + reason_suffix
                ),
                **common_kwargs,
            )

    if CLOSE_ON_OPPOSITE_TREND_STATE:
        if current_type == "buy" and market_state in {"trend_down", "weak_trend_down"}:
            return _build_signal_decision(
                action=SignalAction.CLOSE,
                reason="buy position closed because state switched to down-trend side"
                + reason_suffix,
                **common_kwargs,
            )

        if current_type == "sell" and market_state in {"trend_up", "weak_trend_up"}:
            return _build_signal_decision(
                action=SignalAction.CLOSE,
                reason="sell position closed because state switched to up-trend side"
                + reason_suffix,
                **common_kwargs,
            )

    if base_action == SignalAction.HOLD:
        return _build_signal_decision(
            action=SignalAction.HOLD,
            reason=f"{base_reason}{reason_suffix}; existing {current_type} position kept",
            **common_kwargs,
        )

    if current_type == "buy":
        if base_action == SignalAction.BUY:
            return _build_signal_decision(
                action=SignalAction.HOLD,
                reason="buy signal but buy position already exists" + reason_suffix,
                **common_kwargs,
            )
        return _build_signal_decision(
            action=SignalAction.CLOSE,
            reason="sell signal detected while buy position exists" + reason_suffix,
            **common_kwargs,
        )

    if current_type == "sell":
        if base_action == SignalAction.SELL:
            return _build_signal_decision(
                action=SignalAction.HOLD,
                reason="sell signal but sell position already exists" + reason_suffix,
                **common_kwargs,
            )
        return _build_signal_decision(
            action=SignalAction.CLOSE,
            reason="buy signal detected while sell position exists" + reason_suffix,
            **common_kwargs,
        )

    raise SignalEngineError(f"Unsupported position type: {current_type}")