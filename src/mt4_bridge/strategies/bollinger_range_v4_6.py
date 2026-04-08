# src/mt4_bridge/strategies/bollinger_range_v4_6.py
from __future__ import annotations

from math import sqrt

from mt4_bridge.models import (
    MarketSnapshot,
    OpenPosition,
    PositionSnapshot,
    SignalAction,
    SignalDecision,
)
from mt4_bridge.signal_exceptions import SignalEngineError

RANGE_MAGIC_NUMBER = 44001
TREND_MAGIC_NUMBER = 44002

# =========================
# 調整パラメータ
# =========================
BOLLINGER_PERIOD = 20
BOLLINGER_SIGMA = 2.0
BOLLINGER_EXTREME_SIGMA = 3.0

RANGE_MA_PERIOD = 10
RANGE_SLOPE_LOOKBACK = 5
RANGE_SLOPE_THRESHOLD = 0.0002

RANGE_BAND_WIDTH_THRESHOLD = 0.0025
RANGE_MIDDLE_DISTANCE_THRESHOLD = 0.0012

TREND_MA_PERIOD = 30
TREND_SLOPE_LOOKBACK = 2
TREND_SLOPE_THRESHOLD = 0.0003

TREND_PRICE_POSITION_FILTER_ENABLED = True

RANGE_REQUIRE_REENTRY_CONFIRMATION = True
TREND_REQUIRE_BREAK_CONFIRMATION = True

EXIT_ON_RANGE_MIDDLE_BAND = True
CLOSE_ON_OPPOSITE_TREND_STATE = True

ENABLE_RANGE_FAILURE_EXIT = True
RANGE_FAILURE_ADVERSE_MOVE_RATIO = 0.28

ENABLE_RANGE_EXTREME_TOUCH_ENTRY = True
DISABLE_EXTREME_TOUCH_ENTRY_IN_TREND = True


def required_bars() -> int:
    return max(
        BOLLINGER_PERIOD,
        RANGE_MA_PERIOD + RANGE_SLOPE_LOOKBACK,
        TREND_MA_PERIOD + TREND_SLOPE_LOOKBACK,
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
    entry_lane: str | None,
    entry_subtype: str | None,
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
        entry_lane=entry_lane,
        entry_subtype=entry_subtype,
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


def _get_range_position(position_snapshot: PositionSnapshot) -> OpenPosition | None:
    for item in position_snapshot.positions:
        if item.magic_number == RANGE_MAGIC_NUMBER:
            return item
    return None


def _get_trend_position(position_snapshot: PositionSnapshot) -> OpenPosition | None:
    for item in position_snapshot.positions:
        if item.magic_number == TREND_MAGIC_NUMBER:
            return item
    return None


def evaluate_bollinger_range_v4_6(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_range_v4_6",
) -> SignalDecision:
    bars = market_snapshot.bars
    if len(bars) < required_bars():
        raise SignalEngineError(
            f"At least {required_bars()} bars are required to evaluate bollinger_range_v4_6"
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
    _, latest_upper_extreme, latest_lower_extreme, _ = _calculate_latest_bollinger_bands(
        closes,
        BOLLINGER_EXTREME_SIGMA,
    )

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
        latest_close=latest_close,
        middle_band=latest_middle,
        trend_current_ma=trend_current_ma,
        range_slope=range_slope,
        trend_slope=trend_slope,
        normalized_band_width=normalized_width,
    )

    range_position = _get_range_position(position_snapshot)
    trend_position = _get_trend_position(position_snapshot)

    latest_band_width = latest_upper - latest_lower

    reason_suffix = (
        f" (bollinger_period={BOLLINGER_PERIOD}, bollinger_sigma={BOLLINGER_SIGMA},"
        f" bollinger_extreme_sigma={BOLLINGER_EXTREME_SIGMA},"
        f" range_ma_period={RANGE_MA_PERIOD},"
        f" range_slope_lookback={RANGE_SLOPE_LOOKBACK},"
        f" range_slope_threshold={RANGE_SLOPE_THRESHOLD},"
        f" range_band_width_threshold={RANGE_BAND_WIDTH_THRESHOLD},"
        f" range_middle_distance_threshold={RANGE_MIDDLE_DISTANCE_THRESHOLD},"
        f" trend_ma_period={TREND_MA_PERIOD},"
        f" trend_slope_lookback={TREND_SLOPE_LOOKBACK},"
        f" trend_slope_threshold={TREND_SLOPE_THRESHOLD},"
        f" trend_price_position_filter_enabled={TREND_PRICE_POSITION_FILTER_ENABLED},"
        f" range_require_reentry_confirmation={RANGE_REQUIRE_REENTRY_CONFIRMATION},"
        f" trend_require_break_confirmation={TREND_REQUIRE_BREAK_CONFIRMATION},"
        f" exit_on_range_middle_band={EXIT_ON_RANGE_MIDDLE_BAND},"
        f" close_on_opposite_trend_state={CLOSE_ON_OPPOSITE_TREND_STATE},"
        f" enable_range_failure_exit={ENABLE_RANGE_FAILURE_EXIT},"
        f" range_failure_adverse_move_ratio={RANGE_FAILURE_ADVERSE_MOVE_RATIO},"
        f" enable_range_extreme_touch_entry={ENABLE_RANGE_EXTREME_TOUCH_ENTRY},"
        f" disable_extreme_touch_entry_in_trend={DISABLE_EXTREME_TOUCH_ENTRY_IN_TREND},"
        f" state={market_state}, middle={latest_middle}, upper={latest_upper},"
        f" lower={latest_lower}, upper_3sigma={latest_upper_extreme},"
        f" lower_3sigma={latest_lower_extreme},"
        f" previous_upper={previous_upper}, previous_lower={previous_lower},"
        f" normalized_band_width={normalized_width:.6f},"
        f" latest_band_width={latest_band_width:.6f},"
        f" distance_from_middle={distance_from_middle:.6f},"
        f" range_slope={range_slope:.6f}, trend_slope={trend_slope:.6f},"
        f" trend_current_ma={trend_current_ma},"
        f" latest_high={latest_bar.high}, latest_low={latest_bar.low})"
    )

    # 1. range lane の決済判定を最優先
    if range_position is not None:
        current_type = range_position.position_type.lower()
        entry_price = range_position.open_price

        if ENABLE_RANGE_FAILURE_EXIT and market_state == "range":
            if current_type == "buy" and _range_buy_failure_exit(
                latest_close=latest_close,
                previous_close=previous_close,
                entry_price=entry_price,
                middle_band=latest_middle,
                band_width=latest_band_width,
            ):
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "range buy position closed because range recovery failed and adverse move resumed"
                        f" (entry_price={entry_price}, previous_close={previous_close},"
                        f" latest_close={latest_close}, middle={latest_middle},"
                        f" band_width={latest_band_width})"
                        + reason_suffix
                    ),
                    previous_bar_time=previous_bar.time,
                    latest_bar_time=latest_bar.time,
                    previous_close=previous_close,
                    latest_close=latest_close,
                    current_position_ticket=range_position.ticket,
                    current_position_type=current_type,
                    entry_lane="range",
                    entry_subtype="range_failure_exit",
                    market_state=market_state,
                    middle_band=latest_middle,
                    upper_band=latest_upper,
                    lower_band=latest_lower,
                    normalized_width=normalized_width,
                    range_slope=range_slope,
                    trend_slope=trend_slope,
                    trend_current_ma=trend_current_ma,
                    distance_from_middle=distance_from_middle,
                )

            if current_type == "sell" and _range_sell_failure_exit(
                latest_close=latest_close,
                previous_close=previous_close,
                entry_price=entry_price,
                middle_band=latest_middle,
                band_width=latest_band_width,
            ):
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "range sell position closed because range recovery failed and adverse move resumed"
                        f" (entry_price={entry_price}, previous_close={previous_close},"
                        f" latest_close={latest_close}, middle={latest_middle},"
                        f" band_width={latest_band_width})"
                        + reason_suffix
                    ),
                    previous_bar_time=previous_bar.time,
                    latest_bar_time=latest_bar.time,
                    previous_close=previous_close,
                    latest_close=latest_close,
                    current_position_ticket=range_position.ticket,
                    current_position_type=current_type,
                    entry_lane="range",
                    entry_subtype="range_failure_exit",
                    market_state=market_state,
                    middle_band=latest_middle,
                    upper_band=latest_upper,
                    lower_band=latest_lower,
                    normalized_width=normalized_width,
                    range_slope=range_slope,
                    trend_slope=trend_slope,
                    trend_current_ma=trend_current_ma,
                    distance_from_middle=distance_from_middle,
                )

        if market_state == "range" and EXIT_ON_RANGE_MIDDLE_BAND:
            if current_type == "buy" and latest_close >= latest_middle:
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        f"range buy position closed because range state returned to middle band:"
                        f" latest close {latest_close} >= middle {latest_middle}"
                        + reason_suffix
                    ),
                    previous_bar_time=previous_bar.time,
                    latest_bar_time=latest_bar.time,
                    previous_close=previous_close,
                    latest_close=latest_close,
                    current_position_ticket=range_position.ticket,
                    current_position_type=current_type,
                    entry_lane="range",
                    entry_subtype="range_middle_exit",
                    market_state=market_state,
                    middle_band=latest_middle,
                    upper_band=latest_upper,
                    lower_band=latest_lower,
                    normalized_width=normalized_width,
                    range_slope=range_slope,
                    trend_slope=trend_slope,
                    trend_current_ma=trend_current_ma,
                    distance_from_middle=distance_from_middle,
                )

            if current_type == "sell" and latest_close <= latest_middle:
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        f"range sell position closed because range state returned to middle band:"
                        f" latest close {latest_close} <= middle {latest_middle}"
                        + reason_suffix
                    ),
                    previous_bar_time=previous_bar.time,
                    latest_bar_time=latest_bar.time,
                    previous_close=previous_close,
                    latest_close=latest_close,
                    current_position_ticket=range_position.ticket,
                    current_position_type=current_type,
                    entry_lane="range",
                    entry_subtype="range_middle_exit",
                    market_state=market_state,
                    middle_band=latest_middle,
                    upper_band=latest_upper,
                    lower_band=latest_lower,
                    normalized_width=normalized_width,
                    range_slope=range_slope,
                    trend_slope=trend_slope,
                    trend_current_ma=trend_current_ma,
                    distance_from_middle=distance_from_middle,
                )

        if CLOSE_ON_OPPOSITE_TREND_STATE:
            if current_type == "buy" and market_state == "trend_down":
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason="range buy position closed because state switched to trend_down"
                    + reason_suffix,
                    previous_bar_time=previous_bar.time,
                    latest_bar_time=latest_bar.time,
                    previous_close=previous_close,
                    latest_close=latest_close,
                    current_position_ticket=range_position.ticket,
                    current_position_type=current_type,
                    entry_lane="range",
                    entry_subtype="range_opposite_trend_exit",
                    market_state=market_state,
                    middle_band=latest_middle,
                    upper_band=latest_upper,
                    lower_band=latest_lower,
                    normalized_width=normalized_width,
                    range_slope=range_slope,
                    trend_slope=trend_slope,
                    trend_current_ma=trend_current_ma,
                    distance_from_middle=distance_from_middle,
                )

            if current_type == "sell" and market_state == "trend_up":
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason="range sell position closed because state switched to trend_up"
                    + reason_suffix,
                    previous_bar_time=previous_bar.time,
                    latest_bar_time=latest_bar.time,
                    previous_close=previous_close,
                    latest_close=latest_close,
                    current_position_ticket=range_position.ticket,
                    current_position_type=current_type,
                    entry_lane="range",
                    entry_subtype="range_opposite_trend_exit",
                    market_state=market_state,
                    middle_band=latest_middle,
                    upper_band=latest_upper,
                    lower_band=latest_lower,
                    normalized_width=normalized_width,
                    range_slope=range_slope,
                    trend_slope=trend_slope,
                    trend_current_ma=trend_current_ma,
                    distance_from_middle=distance_from_middle,
                )

    # 2. trend lane の決済判定
    if trend_position is not None:
        current_type = trend_position.position_type.lower()

        if current_type == "buy" and market_state == "trend_down":
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.CLOSE,
                reason="trend buy position closed because state switched to trend_down"
                + reason_suffix,
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=trend_position.ticket,
                current_position_type=current_type,
                entry_lane="trend",
                entry_subtype="trend_reverse_exit",
                market_state=market_state,
                middle_band=latest_middle,
                upper_band=latest_upper,
                lower_band=latest_lower,
                normalized_width=normalized_width,
                range_slope=range_slope,
                trend_slope=trend_slope,
                trend_current_ma=trend_current_ma,
                distance_from_middle=distance_from_middle,
            )

        if current_type == "sell" and market_state == "trend_up":
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.CLOSE,
                reason="trend sell position closed because state switched to trend_up"
                + reason_suffix,
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=trend_position.ticket,
                current_position_type=current_type,
                entry_lane="trend",
                entry_subtype="trend_reverse_exit",
                market_state=market_state,
                middle_band=latest_middle,
                upper_band=latest_upper,
                lower_band=latest_lower,
                normalized_width=normalized_width,
                range_slope=range_slope,
                trend_slope=trend_slope,
                trend_current_ma=trend_current_ma,
                distance_from_middle=distance_from_middle,
            )

    # 3. range lane の反対条件による close
    if range_position is not None and market_state == "range":
        current_type = range_position.position_type.lower()

        range_extreme_touch_allowed = ENABLE_RANGE_EXTREME_TOUCH_ENTRY and not (
            DISABLE_EXTREME_TOUCH_ENTRY_IN_TREND
            and market_state in {"trend_up", "trend_down"}
        )

        range_sell_signal = False
        range_buy_signal = False
        range_subtype = None

        if range_extreme_touch_allowed and _range_extreme_sell_touch_confirmed(
            latest_high=latest_bar.high,
            latest_upper_extreme_band=latest_upper_extreme,
        ):
            range_sell_signal = True
            range_subtype = "range_3sigma"

        elif range_extreme_touch_allowed and _range_extreme_buy_touch_confirmed(
            latest_low=latest_bar.low,
            latest_lower_extreme_band=latest_lower_extreme,
        ):
            range_buy_signal = True
            range_subtype = "range_3sigma"

        elif _range_sell_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            previous_upper_band=previous_upper,
            latest_upper_band=latest_upper,
        ):
            range_sell_signal = True
            range_subtype = "range_2sigma"

        elif _range_buy_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            previous_lower_band=previous_lower,
            latest_lower_band=latest_lower,
        ):
            range_buy_signal = True
            range_subtype = "range_2sigma"

        if current_type == "buy" and range_sell_signal:
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.CLOSE,
                reason=(
                    "range buy position closed because opposite range sell signal was detected"
                    f" (range_subtype={range_subtype})"
                    + reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=range_position.ticket,
                current_position_type=current_type,
                entry_lane="range",
                entry_subtype=range_subtype,
                market_state=market_state,
                middle_band=latest_middle,
                upper_band=latest_upper,
                lower_band=latest_lower,
                normalized_width=normalized_width,
                range_slope=range_slope,
                trend_slope=trend_slope,
                trend_current_ma=trend_current_ma,
                distance_from_middle=distance_from_middle,
            )

        if current_type == "sell" and range_buy_signal:
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.CLOSE,
                reason=(
                    "range sell position closed because opposite range buy signal was detected"
                    f" (range_subtype={range_subtype})"
                    + reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=range_position.ticket,
                current_position_type=current_type,
                entry_lane="range",
                entry_subtype=range_subtype,
                market_state=market_state,
                middle_band=latest_middle,
                upper_band=latest_upper,
                lower_band=latest_lower,
                normalized_width=normalized_width,
                range_slope=range_slope,
                trend_slope=trend_slope,
                trend_current_ma=trend_current_ma,
                distance_from_middle=distance_from_middle,
            )

    # 4. trend lane の反対条件による close
    if trend_position is not None:
        current_type = trend_position.position_type.lower()
        trend_buy_signal = (
            market_state == "trend_up"
            and _trend_buy_confirmed(
                previous_close=previous_close,
                latest_close=latest_close,
                previous_upper_band=previous_upper,
                latest_upper_band=latest_upper,
            )
        )
        trend_sell_signal = (
            market_state == "trend_down"
            and _trend_sell_confirmed(
                previous_close=previous_close,
                latest_close=latest_close,
                previous_lower_band=previous_lower,
                latest_lower_band=latest_lower,
            )
        )

        if current_type == "buy" and trend_sell_signal:
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.CLOSE,
                reason="trend buy position closed because opposite trend sell signal was detected"
                + reason_suffix,
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=trend_position.ticket,
                current_position_type=current_type,
                entry_lane="trend",
                entry_subtype="trend_follow",
                market_state=market_state,
                middle_band=latest_middle,
                upper_band=latest_upper,
                lower_band=latest_lower,
                normalized_width=normalized_width,
                range_slope=range_slope,
                trend_slope=trend_slope,
                trend_current_ma=trend_current_ma,
                distance_from_middle=distance_from_middle,
            )

        if current_type == "sell" and trend_buy_signal:
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.CLOSE,
                reason="trend sell position closed because opposite trend buy signal was detected"
                + reason_suffix,
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=trend_position.ticket,
                current_position_type=current_type,
                entry_lane="trend",
                entry_subtype="trend_follow",
                market_state=market_state,
                middle_band=latest_middle,
                upper_band=latest_upper,
                lower_band=latest_lower,
                normalized_width=normalized_width,
                range_slope=range_slope,
                trend_slope=trend_slope,
                trend_current_ma=trend_current_ma,
                distance_from_middle=distance_from_middle,
            )

    # 5. range lane の新規エントリー
    if range_position is None and market_state == "range":
        range_extreme_touch_allowed = ENABLE_RANGE_EXTREME_TOUCH_ENTRY and not (
            DISABLE_EXTREME_TOUCH_ENTRY_IN_TREND
            and market_state in {"trend_up", "trend_down"}
        )

        if range_extreme_touch_allowed and _range_extreme_sell_touch_confirmed(
            latest_high=latest_bar.high,
            latest_upper_extreme_band=latest_upper_extreme,
        ):
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.SELL,
                reason=(
                    f"range extreme-touch sell confirmed by 3sigma upper band touch;"
                    f" latest_high={latest_bar.high}, latest_upper_3sigma={latest_upper_extreme};"
                    f" {state_reason}"
                    + reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=None,
                current_position_type=None,
                entry_lane="range",
                entry_subtype="range_3sigma",
                market_state=market_state,
                middle_band=latest_middle,
                upper_band=latest_upper,
                lower_band=latest_lower,
                normalized_width=normalized_width,
                range_slope=range_slope,
                trend_slope=trend_slope,
                trend_current_ma=trend_current_ma,
                distance_from_middle=distance_from_middle,
            )

        if range_extreme_touch_allowed and _range_extreme_buy_touch_confirmed(
            latest_low=latest_bar.low,
            latest_lower_extreme_band=latest_lower_extreme,
        ):
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.BUY,
                reason=(
                    f"range extreme-touch buy confirmed by 3sigma lower band touch;"
                    f" latest_low={latest_bar.low}, latest_lower_3sigma={latest_lower_extreme};"
                    f" {state_reason}"
                    + reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=None,
                current_position_type=None,
                entry_lane="range",
                entry_subtype="range_3sigma",
                market_state=market_state,
                middle_band=latest_middle,
                upper_band=latest_upper,
                lower_band=latest_lower,
                normalized_width=normalized_width,
                range_slope=range_slope,
                trend_slope=trend_slope,
                trend_current_ma=trend_current_ma,
                distance_from_middle=distance_from_middle,
            )

        if _range_sell_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            previous_upper_band=previous_upper,
            latest_upper_band=latest_upper,
        ):
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.SELL,
                reason=(
                    f"range mean-reversion sell confirmed by reentry from outside upper band;"
                    f" previous_close={previous_close}, latest_close={latest_close},"
                    f" previous_upper={previous_upper}, latest_upper={latest_upper};"
                    f" {state_reason}"
                    + reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=None,
                current_position_type=None,
                entry_lane="range",
                entry_subtype="range_2sigma",
                market_state=market_state,
                middle_band=latest_middle,
                upper_band=latest_upper,
                lower_band=latest_lower,
                normalized_width=normalized_width,
                range_slope=range_slope,
                trend_slope=trend_slope,
                trend_current_ma=trend_current_ma,
                distance_from_middle=distance_from_middle,
            )

        if _range_buy_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            previous_lower_band=previous_lower,
            latest_lower_band=latest_lower,
        ):
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.BUY,
                reason=(
                    f"range mean-reversion buy confirmed by reentry from outside lower band;"
                    f" previous_close={previous_close}, latest_close={latest_close},"
                    f" previous_lower={previous_lower}, latest_lower={latest_lower};"
                    f" {state_reason}"
                    + reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=None,
                current_position_type=None,
                entry_lane="range",
                entry_subtype="range_2sigma",
                market_state=market_state,
                middle_band=latest_middle,
                upper_band=latest_upper,
                lower_band=latest_lower,
                normalized_width=normalized_width,
                range_slope=range_slope,
                trend_slope=trend_slope,
                trend_current_ma=trend_current_ma,
                distance_from_middle=distance_from_middle,
            )

    # 6. trend lane の新規エントリー
    if trend_position is None:
        if market_state == "trend_up" and _trend_buy_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            previous_upper_band=previous_upper,
            latest_upper_band=latest_upper,
        ):
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.BUY,
                reason=(
                    f"trend-follow buy confirmed by upper band breakout;"
                    f" previous_close={previous_close}, latest_close={latest_close},"
                    f" previous_upper={previous_upper}, latest_upper={latest_upper};"
                    f" {state_reason}"
                    + reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=None,
                current_position_type=None,
                entry_lane="trend",
                entry_subtype="trend_follow",
                market_state=market_state,
                middle_band=latest_middle,
                upper_band=latest_upper,
                lower_band=latest_lower,
                normalized_width=normalized_width,
                range_slope=range_slope,
                trend_slope=trend_slope,
                trend_current_ma=trend_current_ma,
                distance_from_middle=distance_from_middle,
            )

        if market_state == "trend_down" and _trend_sell_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            previous_lower_band=previous_lower,
            latest_lower_band=latest_lower,
        ):
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.SELL,
                reason=(
                    f"trend-follow sell confirmed by lower band breakout;"
                    f" previous_close={previous_close}, latest_close={latest_close},"
                    f" previous_lower={previous_lower}, latest_lower={latest_lower};"
                    f" {state_reason}"
                    + reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_close,
                latest_close=latest_close,
                current_position_ticket=None,
                current_position_type=None,
                entry_lane="trend",
                entry_subtype="trend_follow",
                market_state=market_state,
                middle_band=latest_middle,
                upper_band=latest_upper,
                lower_band=latest_lower,
                normalized_width=normalized_width,
                range_slope=range_slope,
                trend_slope=trend_slope,
                trend_current_ma=trend_current_ma,
                distance_from_middle=distance_from_middle,
            )

    # 7. no action
    if market_state == "range":
        no_signal_reason = (
            f"range state but no confirmed signal"
            f" (previous_close={previous_close}, latest_close={latest_close},"
            f" previous_upper={previous_upper}, latest_upper={latest_upper},"
            f" previous_lower={previous_lower}, latest_lower={latest_lower},"
            f" latest_upper_3sigma={latest_upper_extreme},"
            f" latest_lower_3sigma={latest_lower_extreme},"
            f" latest_high={latest_bar.high}, latest_low={latest_bar.low});"
            f" {state_reason}"
            + reason_suffix
        )
    elif market_state == "trend_up":
        no_signal_reason = (
            f"trend_up state but no confirmed upper band breakout"
            f" (previous_close={previous_close}, latest_close={latest_close},"
            f" previous_upper={previous_upper}, latest_upper={latest_upper});"
            f" {state_reason}"
            + reason_suffix
        )
    elif market_state == "trend_down":
        no_signal_reason = (
            f"trend_down state but no confirmed lower band breakout"
            f" (previous_close={previous_close}, latest_close={latest_close},"
            f" previous_lower={previous_lower}, latest_lower={latest_lower});"
            f" {state_reason}"
            + reason_suffix
        )
    else:
        no_signal_reason = (
            f"neutral state so entry is skipped"
            f" (previous_close={previous_close}, latest_close={latest_close},"
            f" previous_upper={previous_upper}, latest_upper={latest_upper},"
            f" previous_lower={previous_lower}, latest_lower={latest_lower},"
            f" latest_upper_3sigma={latest_upper_extreme},"
            f" latest_lower_3sigma={latest_lower_extreme},"
            f" latest_high={latest_bar.high}, latest_low={latest_bar.low});"
            f" {state_reason}"
            + reason_suffix
        )

    return _build_signal_decision(
        strategy_name=strategy_name,
        action=SignalAction.HOLD,
        reason=no_signal_reason,
        previous_bar_time=previous_bar.time,
        latest_bar_time=latest_bar.time,
        previous_close=previous_close,
        latest_close=latest_close,
        current_position_ticket=None,
        current_position_type=None,
        entry_lane=None,
        entry_subtype=None,
        market_state=market_state,
        middle_band=latest_middle,
        upper_band=latest_upper,
        lower_band=latest_lower,
        normalized_width=normalized_width,
        range_slope=range_slope,
        trend_slope=trend_slope,
        trend_current_ma=trend_current_ma,
        distance_from_middle=distance_from_middle,
    )