# src/mt4_bridge/strategies/bollinger_trend_B3_weak_start.py
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from mt4_bridge.models import (
    MarketSnapshot,
    OpenPosition,
    PositionSnapshot,
    SignalAction,
    SignalDecision,
)
from mt4_bridge.signal_exceptions import SignalEngineError

BOLLINGER_PERIOD = 20
BOLLINGER_SIGMA = 2.0

TREND_MA_PERIOD = 30
TREND_SLOPE_LOOKBACK = 2

# 緩やかなトレンド初動を拾うため、B2よりはっきり低い閾値にする
WEAK_TREND_SLOPE_THRESHOLD = 0.00005
STRONG_TREND_SLOPE_THRESHOLD = 0.00022

TREND_PRICE_POSITION_FILTER_ENABLED = True

TREND_MAGIC_NUMBER = 44002

# エントリー用
ENTRY_PULLBACK_LOOKBACK_BARS = 3
ENTRY_MAX_DISTANCE_FROM_MIDDLE = 0.00110
ENTRY_MIN_DISTANCE_FROM_MIDDLE = 0.00002

# 決済用
EXIT_ON_MIDDLE_CROSS = True
EXIT_ON_OPPOSITE_STATE = True
EXIT_ON_SLOPE_FLAT = True
EXIT_ON_OUTER_BAND_TOUCH = True

# 緩やかな初動狙いなので、早めに失速撤退する
EARLY_FAILURE_LOOKAHEAD_BARS = 4
EARLY_FAILURE_MIN_PROGRESS_PIPS = 2.0
JPY_PIP_SIZE = 0.01


@dataclass(frozen=True)
class _AnalysisContext:
    previous_bar_time: object
    latest_bar_time: object
    previous_close: float
    latest_close: float
    latest_high: float
    latest_low: float
    previous_high: float
    previous_low: float
    previous_middle_band: float
    middle_band: float
    upper_band: float
    lower_band: float
    band_width: float
    normalized_width: float
    trend_slope: float
    trend_current_ma: float
    previous_upper_band: float
    previous_lower_band: float
    distance_from_middle: float
    market_state: str
    state_reason: str
    trend_up_slope_passed: bool
    trend_up_price_passed: bool
    trend_down_slope_passed: bool
    trend_down_price_passed: bool


def required_bars() -> int:
    return max(
        BOLLINGER_PERIOD + 1,
        TREND_MA_PERIOD + TREND_SLOPE_LOOKBACK,
        TREND_MA_PERIOD + TREND_SLOPE_LOOKBACK + ENTRY_PULLBACK_LOOKBACK_BARS,
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
            f"At least {BOLLINGER_PERIOD} closes are required to calculate Bollinger Bands"
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


def _analyze_trend_up(
    latest_close: float,
    trend_current_ma: float,
    trend_slope: float,
) -> tuple[bool, bool, bool]:
    slope_passed = trend_slope >= WEAK_TREND_SLOPE_THRESHOLD
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
    slope_passed = trend_slope <= -WEAK_TREND_SLOPE_THRESHOLD
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
) -> tuple[str, str, float, bool, bool, bool, bool]:
    distance_from_middle = _distance_from_middle(latest_close, middle_band)

    is_trend_up, trend_up_slope_passed, trend_up_price_passed = _analyze_trend_up(
        latest_close=latest_close,
        trend_current_ma=trend_current_ma,
        trend_slope=trend_slope,
    )
    if is_trend_up:
        if trend_slope >= STRONG_TREND_SLOPE_THRESHOLD:
            return (
                "trend_up",
                (
                    f"trend_up because trend_slope={trend_slope:.6f}"
                    f" >= strong_threshold={STRONG_TREND_SLOPE_THRESHOLD:.6f}"
                    f" and latest_close={latest_close} >= trend_ma={trend_current_ma}"
                ),
                distance_from_middle,
                trend_up_slope_passed,
                trend_up_price_passed,
                False,
                False,
            )

        return (
            "weak_trend_up",
            (
                f"weak_trend_up because trend_slope={trend_slope:.6f}"
                f" >= weak_threshold={WEAK_TREND_SLOPE_THRESHOLD:.6f}"
                f" and < strong_threshold={STRONG_TREND_SLOPE_THRESHOLD:.6f}"
                f" and latest_close={latest_close} >= trend_ma={trend_current_ma}"
            ),
            distance_from_middle,
            trend_up_slope_passed,
            trend_up_price_passed,
            False,
            False,
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
                "trend_down",
                (
                    f"trend_down because trend_slope={trend_slope:.6f}"
                    f" <= -strong_threshold={STRONG_TREND_SLOPE_THRESHOLD:.6f}"
                    f" and latest_close={latest_close} <= trend_ma={trend_current_ma}"
                ),
                distance_from_middle,
                trend_up_slope_passed,
                trend_up_price_passed,
                trend_down_slope_passed,
                trend_down_price_passed,
            )

        return (
            "weak_trend_down",
            (
                f"weak_trend_down because trend_slope={trend_slope:.6f}"
                f" <= -weak_threshold={WEAK_TREND_SLOPE_THRESHOLD:.6f}"
                f" and > -strong_threshold={STRONG_TREND_SLOPE_THRESHOLD:.6f}"
                f" and latest_close={latest_close} <= trend_ma={trend_current_ma}"
            ),
            distance_from_middle,
            trend_up_slope_passed,
            trend_up_price_passed,
            trend_down_slope_passed,
            trend_down_price_passed,
        )

    if trend_up_slope_passed and not trend_up_price_passed:
        state_reason = (
            "neutral because up-slope passed but up price-position filter failed"
            f" (latest_close={latest_close}, trend_ma={trend_current_ma},"
            f" trend_slope={trend_slope:.6f})"
        )
    elif trend_down_slope_passed and not trend_down_price_passed:
        state_reason = (
            "neutral because down-slope passed but down price-position filter failed"
            f" (latest_close={latest_close}, trend_ma={trend_current_ma},"
            f" trend_slope={trend_slope:.6f})"
        )
    else:
        state_reason = (
            "neutral because no weak/strong trend was confirmed"
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
    )


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


def _extract_entry_progress_bar_count(comment: str | None) -> int | None:
    if not comment:
        return None

    marker = "entry_bar_index="
    index = comment.find(marker)
    if index < 0:
        return None

    start = index + len(marker)
    end = start
    while end < len(comment) and comment[end].isdigit():
        end += 1

    raw_value = comment[start:end]
    if not raw_value:
        return None

    try:
        return int(raw_value)
    except ValueError:
        return None


def _extract_entry_price_from_position(position: OpenPosition) -> float:
    return position.open_price


def _calculate_buy_progress_pips(
    entry_price: float,
    latest_high: float,
) -> float:
    return (latest_high - entry_price) / JPY_PIP_SIZE


def _calculate_sell_progress_pips(
    entry_price: float,
    latest_low: float,
) -> float:
    return (entry_price - latest_low) / JPY_PIP_SIZE


def _should_early_failure_exit_buy(
    *,
    trend_position: OpenPosition,
    latest_high: float,
    latest_close: float,
    middle_band: float,
) -> tuple[bool, int | None, float]:
    entry_bar_index = _extract_entry_progress_bar_count(trend_position.comment)
    progress_pips = _calculate_buy_progress_pips(
        entry_price=_extract_entry_price_from_position(trend_position),
        latest_high=latest_high,
    )

    if entry_bar_index is None:
        return False, None, progress_pips

    should_close = (
        entry_bar_index <= EARLY_FAILURE_LOOKAHEAD_BARS
        and progress_pips < EARLY_FAILURE_MIN_PROGRESS_PIPS
        and latest_close < middle_band
    )
    return should_close, entry_bar_index, progress_pips


def _should_early_failure_exit_sell(
    *,
    trend_position: OpenPosition,
    latest_low: float,
    latest_close: float,
    middle_band: float,
) -> tuple[bool, int | None, float]:
    entry_bar_index = _extract_entry_progress_bar_count(trend_position.comment)
    progress_pips = _calculate_sell_progress_pips(
        entry_price=_extract_entry_price_from_position(trend_position),
        latest_low=latest_low,
    )

    if entry_bar_index is None:
        return False, None, progress_pips

    should_close = (
        entry_bar_index <= EARLY_FAILURE_LOOKAHEAD_BARS
        and progress_pips < EARLY_FAILURE_MIN_PROGRESS_PIPS
        and latest_close > middle_band
    )
    return should_close, entry_bar_index, progress_pips


def _recent_pullback_exists_for_buy(closes: list[float], middle_band: float) -> bool:
    recent = closes[-(ENTRY_PULLBACK_LOOKBACK_BARS + 1) : -1]
    return any(close <= middle_band for close in recent)


def _recent_pullback_exists_for_sell(closes: list[float], middle_band: float) -> bool:
    recent = closes[-(ENTRY_PULLBACK_LOOKBACK_BARS + 1) : -1]
    return any(close >= middle_band for close in recent)


def _buy_entry_confirmed(
    *,
    closes: list[float],
    previous_close: float,
    latest_close: float,
    middle_band: float,
    trend_current_ma: float,
    trend_slope: float,
) -> bool:
    distance = _distance_from_middle(latest_close, middle_band)
    return (
        trend_slope >= WEAK_TREND_SLOPE_THRESHOLD
        and latest_close >= middle_band
        and latest_close >= trend_current_ma
        and latest_close > previous_close
        and distance >= ENTRY_MIN_DISTANCE_FROM_MIDDLE
        and distance <= ENTRY_MAX_DISTANCE_FROM_MIDDLE
        and _recent_pullback_exists_for_buy(closes, middle_band)
    )


def _sell_entry_confirmed(
    *,
    closes: list[float],
    previous_close: float,
    latest_close: float,
    middle_band: float,
    trend_current_ma: float,
    trend_slope: float,
) -> bool:
    distance = _distance_from_middle(latest_close, middle_band)
    return (
        trend_slope <= -WEAK_TREND_SLOPE_THRESHOLD
        and latest_close <= middle_band
        and latest_close <= trend_current_ma
        and latest_close < previous_close
        and distance >= ENTRY_MIN_DISTANCE_FROM_MIDDLE
        and distance <= ENTRY_MAX_DISTANCE_FROM_MIDDLE
        and _recent_pullback_exists_for_sell(closes, middle_band)
    )


def _buy_take_profit_confirmed(
    latest_high: float,
    latest_upper_band: float,
) -> bool:
    return latest_high >= latest_upper_band


def _sell_take_profit_confirmed(
    latest_low: float,
    latest_lower_band: float,
) -> bool:
    return latest_low <= latest_lower_band


def _buy_middle_cross_exit_confirmed(
    latest_close: float,
    latest_middle_band: float,
) -> bool:
    return latest_close < latest_middle_band


def _sell_middle_cross_exit_confirmed(
    latest_close: float,
    latest_middle_band: float,
) -> bool:
    return latest_close > latest_middle_band


def _build_reason_suffix(
    context: _AnalysisContext,
) -> str:
    return (
        f" (bollinger_period={BOLLINGER_PERIOD}, bollinger_sigma={BOLLINGER_SIGMA},"
        f" trend_ma_period={TREND_MA_PERIOD},"
        f" trend_slope_lookback={TREND_SLOPE_LOOKBACK},"
        f" weak_trend_slope_threshold={WEAK_TREND_SLOPE_THRESHOLD},"
        f" strong_trend_slope_threshold={STRONG_TREND_SLOPE_THRESHOLD},"
        f" trend_price_position_filter_enabled={TREND_PRICE_POSITION_FILTER_ENABLED},"
        f" entry_pullback_lookback_bars={ENTRY_PULLBACK_LOOKBACK_BARS},"
        f" entry_max_distance_from_middle={ENTRY_MAX_DISTANCE_FROM_MIDDLE},"
        f" entry_min_distance_from_middle={ENTRY_MIN_DISTANCE_FROM_MIDDLE},"
        f" early_failure_lookahead_bars={EARLY_FAILURE_LOOKAHEAD_BARS},"
        f" early_failure_min_progress_pips={EARLY_FAILURE_MIN_PROGRESS_PIPS},"
        f" exit_on_middle_cross={EXIT_ON_MIDDLE_CROSS},"
        f" exit_on_opposite_state={EXIT_ON_OPPOSITE_STATE},"
        f" exit_on_slope_flat={EXIT_ON_SLOPE_FLAT},"
        f" exit_on_outer_band_touch={EXIT_ON_OUTER_BAND_TOUCH},"
        f" state={context.market_state}, previous_middle={context.previous_middle_band},"
        f" middle={context.middle_band}, upper={context.upper_band},"
        f" lower={context.lower_band}, previous_upper={context.previous_upper_band},"
        f" previous_lower={context.previous_lower_band},"
        f" normalized_band_width={context.normalized_width:.6f},"
        f" latest_band_width={context.band_width:.6f},"
        f" distance_from_middle={context.distance_from_middle:.6f},"
        f" trend_slope={context.trend_slope:.6f},"
        f" trend_current_ma={context.trend_current_ma},"
        f" trend_up_slope_passed={context.trend_up_slope_passed},"
        f" trend_up_price_passed={context.trend_up_price_passed},"
        f" trend_down_slope_passed={context.trend_down_slope_passed},"
        f" trend_down_price_passed={context.trend_down_price_passed},"
        f" previous_high={context.previous_high}, previous_low={context.previous_low},"
        f" latest_high={context.latest_high}, latest_low={context.latest_low})"
    )


def _build_signal_decision(
    *,
    strategy_name: str,
    action: SignalAction,
    reason: str,
    entry_subtype: str | None,
    current_position: OpenPosition | None,
    context: _AnalysisContext,
) -> SignalDecision:
    return SignalDecision(
        strategy_name=strategy_name,
        action=action,
        reason=reason,
        previous_bar_time=context.previous_bar_time,
        latest_bar_time=context.latest_bar_time,
        previous_close=context.previous_close,
        latest_close=context.latest_close,
        current_position_ticket=current_position.ticket if current_position else None,
        current_position_type=(
            current_position.position_type.lower() if current_position else None
        ),
        entry_lane="trend",
        entry_subtype=entry_subtype,
        market_state=context.market_state,
        middle_band=context.middle_band,
        upper_band=context.upper_band,
        lower_band=context.lower_band,
        normalized_band_width=context.normalized_width,
        range_slope=0.0,
        trend_slope=context.trend_slope,
        trend_current_ma=context.trend_current_ma,
        distance_from_middle=context.distance_from_middle,
    )


def _build_analysis_context(
    market_snapshot: MarketSnapshot,
) -> tuple[_AnalysisContext, list[float]]:
    bars = market_snapshot.bars
    if len(bars) < required_bars():
        raise SignalEngineError(
            f"At least {required_bars()} bars are required to evaluate bollinger_trend_B3_weak_start"
        )

    closes = [bar.close for bar in bars]
    previous_bar = bars[-2]
    latest_bar = bars[-1]
    previous_close = previous_bar.close
    latest_close = latest_bar.close

    latest_middle, latest_upper, latest_lower, latest_band_width = (
        _calculate_latest_bollinger_bands(closes, BOLLINGER_SIGMA)
    )
    previous_middle, previous_upper, previous_lower, _ = (
        _calculate_previous_bollinger_bands(closes, BOLLINGER_SIGMA)
    )

    normalized_width = _normalized_band_width(latest_middle, latest_band_width)
    trend_slope, trend_current_ma, _ = _normalized_slope(
        closes=closes,
        period=TREND_MA_PERIOD,
        lookback=TREND_SLOPE_LOOKBACK,
    )

    (
        market_state,
        state_reason,
        distance_from_middle,
        trend_up_slope_passed,
        trend_up_price_passed,
        trend_down_slope_passed,
        trend_down_price_passed,
    ) = _determine_market_state(
        latest_close=latest_close,
        middle_band=latest_middle,
        trend_current_ma=trend_current_ma,
        trend_slope=trend_slope,
        normalized_band_width=normalized_width,
    )

    context = _AnalysisContext(
        previous_bar_time=previous_bar.time,
        latest_bar_time=latest_bar.time,
        previous_close=previous_close,
        latest_close=latest_close,
        latest_high=latest_bar.high,
        latest_low=latest_bar.low,
        previous_high=previous_bar.high,
        previous_low=previous_bar.low,
        previous_middle_band=previous_middle,
        middle_band=latest_middle,
        upper_band=latest_upper,
        lower_band=latest_lower,
        band_width=latest_band_width,
        normalized_width=normalized_width,
        trend_slope=trend_slope,
        trend_current_ma=trend_current_ma,
        previous_upper_band=previous_upper,
        previous_lower_band=previous_lower,
        distance_from_middle=distance_from_middle,
        market_state=market_state,
        state_reason=state_reason,
        trend_up_slope_passed=trend_up_slope_passed,
        trend_up_price_passed=trend_up_price_passed,
        trend_down_slope_passed=trend_down_slope_passed,
        trend_down_price_passed=trend_down_price_passed,
    )
    return context, closes


def evaluate_bollinger_trend_B3_weak_start(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_trend_B3_weak_start",
) -> SignalDecision:
    context, closes = _build_analysis_context(market_snapshot)
    trend_position = _get_trend_position(position_snapshot)
    reason_suffix = _build_reason_suffix(context)

    if trend_position is not None:
        current_type = trend_position.position_type.lower()

        if current_type == "buy":
            should_early_fail, entry_bar_index, progress_pips = (
                _should_early_failure_exit_buy(
                    trend_position=trend_position,
                    latest_high=context.latest_high,
                    latest_close=context.latest_close,
                    middle_band=context.middle_band,
                )
            )
            if should_early_fail:
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "buy trend position closed by early failure exit because progress stayed weak"
                        f" within lookahead bars (entry_bar_index={entry_bar_index},"
                        f" progress_pips={progress_pips:.2f})"
                        + reason_suffix
                    ),
                    entry_subtype="early_failure_exit",
                    current_position=trend_position,
                    context=context,
                )

            if EXIT_ON_OUTER_BAND_TOUCH and _buy_take_profit_confirmed(
                latest_high=context.latest_high,
                latest_upper_band=context.upper_band,
            ):
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "buy trend position closed because upper 2sigma was touched"
                        f" (latest_high={context.latest_high}, upper_band={context.upper_band})"
                        + reason_suffix
                    ),
                    entry_subtype="tp_upper_2sigma",
                    current_position=trend_position,
                    context=context,
                )

            if EXIT_ON_OPPOSITE_STATE and context.market_state in {
                "trend_down",
                "weak_trend_down",
            }:
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "buy trend position closed because opposite down-trend side was detected"
                        + reason_suffix
                    ),
                    entry_subtype="opposite_state_exit",
                    current_position=trend_position,
                    context=context,
                )

            if EXIT_ON_MIDDLE_CROSS and _buy_middle_cross_exit_confirmed(
                latest_close=context.latest_close,
                latest_middle_band=context.middle_band,
            ):
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "buy trend position closed because close fell below middle band"
                        f" (latest_close={context.latest_close}, middle={context.middle_band})"
                        + reason_suffix
                    ),
                    entry_subtype="middle_cross_exit",
                    current_position=trend_position,
                    context=context,
                )

            if EXIT_ON_SLOPE_FLAT and abs(context.trend_slope) < WEAK_TREND_SLOPE_THRESHOLD:
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "buy trend position closed because trend slope flattened below weak threshold"
                        + reason_suffix
                    ),
                    entry_subtype="slope_flat_exit",
                    current_position=trend_position,
                    context=context,
                )

            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.HOLD,
                reason="buy trend position kept" + reason_suffix,
                entry_subtype="hold_existing",
                current_position=trend_position,
                context=context,
            )

        if current_type == "sell":
            should_early_fail, entry_bar_index, progress_pips = (
                _should_early_failure_exit_sell(
                    trend_position=trend_position,
                    latest_low=context.latest_low,
                    latest_close=context.latest_close,
                    middle_band=context.middle_band,
                )
            )
            if should_early_fail:
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "sell trend position closed by early failure exit because progress stayed weak"
                        f" within lookahead bars (entry_bar_index={entry_bar_index},"
                        f" progress_pips={progress_pips:.2f})"
                        + reason_suffix
                    ),
                    entry_subtype="early_failure_exit",
                    current_position=trend_position,
                    context=context,
                )

            if EXIT_ON_OUTER_BAND_TOUCH and _sell_take_profit_confirmed(
                latest_low=context.latest_low,
                latest_lower_band=context.lower_band,
            ):
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "sell trend position closed because lower 2sigma was touched"
                        f" (latest_low={context.latest_low}, lower_band={context.lower_band})"
                        + reason_suffix
                    ),
                    entry_subtype="tp_lower_2sigma",
                    current_position=trend_position,
                    context=context,
                )

            if EXIT_ON_OPPOSITE_STATE and context.market_state in {
                "trend_up",
                "weak_trend_up",
            }:
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "sell trend position closed because opposite up-trend side was detected"
                        + reason_suffix
                    ),
                    entry_subtype="opposite_state_exit",
                    current_position=trend_position,
                    context=context,
                )

            if EXIT_ON_MIDDLE_CROSS and _sell_middle_cross_exit_confirmed(
                latest_close=context.latest_close,
                latest_middle_band=context.middle_band,
            ):
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "sell trend position closed because close rose above middle band"
                        f" (latest_close={context.latest_close}, middle={context.middle_band})"
                        + reason_suffix
                    ),
                    entry_subtype="middle_cross_exit",
                    current_position=trend_position,
                    context=context,
                )

            if EXIT_ON_SLOPE_FLAT and abs(context.trend_slope) < WEAK_TREND_SLOPE_THRESHOLD:
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "sell trend position closed because trend slope flattened below weak threshold"
                        + reason_suffix
                    ),
                    entry_subtype="slope_flat_exit",
                    current_position=trend_position,
                    context=context,
                )

            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.HOLD,
                reason="sell trend position kept" + reason_suffix,
                entry_subtype="hold_existing",
                current_position=trend_position,
                context=context,
            )

        raise SignalEngineError(f"Unsupported trend position type: {current_type}")

    if context.market_state in {"weak_trend_up", "trend_up"}:
        if _buy_entry_confirmed(
            closes=closes,
            previous_close=context.previous_close,
            latest_close=context.latest_close,
            middle_band=context.middle_band,
            trend_current_ma=context.trend_current_ma,
            trend_slope=context.trend_slope,
        ):
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.BUY,
                reason=(
                    "trend buy confirmed by weak-start continuation entry;"
                    f" previous_close={context.previous_close}, latest_close={context.latest_close},"
                    f" middle={context.middle_band}, trend_ma={context.trend_current_ma};"
                    f" {context.state_reason}"
                    + reason_suffix
                ),
                entry_subtype="weak_start_continuation_buy",
                current_position=None,
                context=context,
            )

        return _build_signal_decision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=(
                "up-trend side detected but buy weak-start continuation entry was not confirmed"
                f" (previous_close={context.previous_close}, latest_close={context.latest_close},"
                f" middle={context.middle_band}, trend_ma={context.trend_current_ma})"
                + reason_suffix
            ),
            entry_subtype="debug_up_continuation_miss",
            current_position=None,
            context=context,
        )

    if context.market_state in {"weak_trend_down", "trend_down"}:
        if _sell_entry_confirmed(
            closes=closes,
            previous_close=context.previous_close,
            latest_close=context.latest_close,
            middle_band=context.middle_band,
            trend_current_ma=context.trend_current_ma,
            trend_slope=context.trend_slope,
        ):
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.SELL,
                reason=(
                    "trend sell confirmed by weak-start continuation entry;"
                    f" previous_close={context.previous_close}, latest_close={context.latest_close},"
                    f" middle={context.middle_band}, trend_ma={context.trend_current_ma};"
                    f" {context.state_reason}"
                    + reason_suffix
                ),
                entry_subtype="weak_start_continuation_sell",
                current_position=None,
                context=context,
            )

        return _build_signal_decision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=(
                "down-trend side detected but sell weak-start continuation entry was not confirmed"
                f" (previous_close={context.previous_close}, latest_close={context.latest_close},"
                f" middle={context.middle_band}, trend_ma={context.trend_current_ma})"
                + reason_suffix
            ),
            entry_subtype="debug_down_continuation_miss",
            current_position=None,
            context=context,
        )

    if context.trend_up_slope_passed and not context.trend_up_price_passed:
        return _build_signal_decision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=(
                "up-slope passed but price-position filter blocked entry"
                + reason_suffix
            ),
            entry_subtype="debug_trend_up_price_filter_blocked",
            current_position=None,
            context=context,
        )

    if context.trend_down_slope_passed and not context.trend_down_price_passed:
        return _build_signal_decision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=(
                "down-slope passed but price-position filter blocked entry"
                + reason_suffix
            ),
            entry_subtype="debug_trend_down_price_filter_blocked",
            current_position=None,
            context=context,
        )

    if context.trend_slope > 0:
        return _build_signal_decision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=(
                "positive slope observed but weak up-trend threshold or price filter was not satisfied"
                + reason_suffix
            ),
            entry_subtype="debug_trend_up_slope_blocked",
            current_position=None,
            context=context,
        )

    if context.trend_slope < 0:
        return _build_signal_decision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=(
                "negative slope observed but weak down-trend threshold or price filter was not satisfied"
                + reason_suffix
            ),
            entry_subtype="debug_trend_down_slope_blocked",
            current_position=None,
            context=context,
        )

    return _build_signal_decision(
        strategy_name=strategy_name,
        action=SignalAction.HOLD,
        reason=(
            "flat slope so no actionable trend decision"
            f" (market_state={context.market_state}; {context.state_reason})"
            + reason_suffix
        ),
        entry_subtype="debug_flat_slope",
        current_position=None,
        context=context,
    )