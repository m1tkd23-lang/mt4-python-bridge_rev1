# src\mt4_bridge\strategies\v7_features.py
from __future__ import annotations

from math import sqrt

from mt4_bridge.models import Bar, MarketSnapshot
from mt4_bridge.signal_exceptions import SignalEngineError

from mt4_bridge.strategies.v7_state_models import (
    V7DetectorParams,
    V7FeatureSnapshot,
)


def required_bars_for_v7_features(params: V7DetectorParams) -> int:
    feature = params.feature
    return max(
        feature.bollinger_period + feature.band_width_slope_lookback,
        feature.range_ma_period + feature.range_slope_lookback,
        feature.trend_ma_period + feature.trend_slope_lookback,
        feature.trend_ma_period + feature.streak_lookback_bars - 1,
        feature.structure_lookback_bars + 1,
    )


def _simple_moving_average(values: list[float]) -> float:
    if not values:
        raise SignalEngineError("Moving average requires at least one value")
    return sum(values) / len(values)


def _standard_deviation(values: list[float], mean: float) -> float:
    if not values:
        raise SignalEngineError("Standard deviation requires at least one value")
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return sqrt(variance)


def _calculate_bollinger_from_window(
    closes: list[float],
    period: int,
    sigma: float,
) -> tuple[float, float, float, float]:
    if len(closes) < period:
        raise SignalEngineError(
            f"At least {period} closes are required for Bollinger calculation"
        )
    window = closes[-period:]
    middle = _simple_moving_average(window)
    stddev = _standard_deviation(window, middle)
    upper = middle + (sigma * stddev)
    lower = middle - (sigma * stddev)
    band_width = upper - lower
    return middle, upper, lower, band_width


def _normalized_band_width(middle: float, band_width: float) -> float:
    if middle == 0:
        raise SignalEngineError("Middle band is zero; normalized band width undefined")
    return band_width / middle


def _distance_from_middle(close: float, middle: float) -> float:
    if middle == 0:
        raise SignalEngineError("Middle band is zero; distance from middle undefined")
    return abs(close - middle) / middle


def _calculate_recent_ma(closes: list[float], period: int) -> float:
    if len(closes) < period:
        raise SignalEngineError(f"At least {period} closes are required to calculate MA")
    return _simple_moving_average(closes[-period:])


def _calculate_past_ma(closes: list[float], period: int, lookback: int) -> float:
    if len(closes) < period + lookback:
        raise SignalEngineError(
            f"At least {period + lookback} closes are required to calculate past MA"
        )
    end_index = len(closes) - lookback
    start_index = end_index - period
    return _simple_moving_average(closes[start_index:end_index])


def _normalized_slope(
    closes: list[float],
    period: int,
    lookback: int,
) -> tuple[float, float]:
    current_ma = _calculate_recent_ma(closes, period)
    past_ma = _calculate_past_ma(closes, period, lookback)
    if current_ma == 0:
        raise SignalEngineError("Current MA is zero; normalized slope undefined")
    return (current_ma - past_ma) / current_ma, current_ma


def _count_sequential_comparisons(
    values: list[float],
    *,
    comparator,
    epsilon: float = 0.0,
) -> int:
    count = 0
    for previous, current in zip(values[:-1], values[1:]):
        if comparator(current, previous, epsilon):
            count += 1
    return count


def _extract_closes_from_bars(bars: list[Bar]) -> list[float]:
    return [bar.close for bar in bars]


def _validate_required_bars_for_feature_build(
    bars: list[Bar],
    params: V7DetectorParams,
) -> None:
    required_bars = required_bars_for_v7_features(params)
    if len(bars) < required_bars:
        raise SignalEngineError(
            f"At least {required_bars} bars are required to build v7 features"
        )


def compute_recent_high_break_count(bars: list[Bar], params: V7DetectorParams) -> int:
    lookback = params.feature.structure_lookback_bars
    if len(bars) < lookback + 1:
        raise SignalEngineError(
            f"At least {lookback + 1} bars are required for recent high break count"
        )
    highs = [bar.high for bar in bars[-(lookback + 1) :]]
    return _count_sequential_comparisons(
        highs,
        comparator=lambda current, previous, epsilon: current > previous,
    )


def compute_recent_low_break_count(bars: list[Bar], params: V7DetectorParams) -> int:
    lookback = params.feature.structure_lookback_bars
    if len(bars) < lookback + 1:
        raise SignalEngineError(
            f"At least {lookback + 1} bars are required for recent low break count"
        )
    lows = [bar.low for bar in bars[-(lookback + 1) :]]
    return _count_sequential_comparisons(
        lows,
        comparator=lambda current, previous, epsilon: current < previous,
    )


def compute_higher_lows_count(bars: list[Bar], params: V7DetectorParams) -> int:
    lookback = params.feature.structure_lookback_bars
    epsilon = params.feature.price_epsilon
    if len(bars) < lookback + 1:
        raise SignalEngineError(
            f"At least {lookback + 1} bars are required for higher lows count"
        )
    lows = [bar.low for bar in bars[-(lookback + 1) :]]
    return _count_sequential_comparisons(
        lows,
        comparator=lambda current, previous, eps: current > (previous + eps),
        epsilon=epsilon,
    )


def compute_lower_highs_count(bars: list[Bar], params: V7DetectorParams) -> int:
    lookback = params.feature.structure_lookback_bars
    epsilon = params.feature.price_epsilon
    if len(bars) < lookback + 1:
        raise SignalEngineError(
            f"At least {lookback + 1} bars are required for lower highs count"
        )
    highs = [bar.high for bar in bars[-(lookback + 1) :]]
    return _count_sequential_comparisons(
        highs,
        comparator=lambda current, previous, eps: current < (previous - eps),
        epsilon=epsilon,
    )


def compute_price_above_ma_streak(closes: list[float], params: V7DetectorParams) -> int:
    lookback = params.feature.streak_lookback_bars
    period = params.feature.trend_ma_period
    if len(closes) < period + lookback - 1:
        raise SignalEngineError(
            f"At least {period + lookback - 1} closes are required for above-MA streak"
        )

    streak = 0
    for offset in range(lookback):
        end_index = len(closes) - offset
        start_index = end_index - period
        window = closes[start_index:end_index]
        trend_ma = _simple_moving_average(window)
        latest_close = closes[end_index - 1]
        if latest_close > trend_ma:
            streak += 1
        else:
            break
    return streak


def compute_price_below_ma_streak(closes: list[float], params: V7DetectorParams) -> int:
    lookback = params.feature.streak_lookback_bars
    period = params.feature.trend_ma_period
    if len(closes) < period + lookback - 1:
        raise SignalEngineError(
            f"At least {period + lookback - 1} closes are required for below-MA streak"
        )

    streak = 0
    for offset in range(lookback):
        end_index = len(closes) - offset
        start_index = end_index - period
        window = closes[start_index:end_index]
        trend_ma = _simple_moving_average(window)
        latest_close = closes[end_index - 1]
        if latest_close < trend_ma:
            streak += 1
        else:
            break
    return streak


def compute_band_width_slope(closes: list[float], params: V7DetectorParams) -> float:
    period = params.feature.bollinger_period
    sigma = params.feature.bollinger_sigma
    lookback = params.feature.band_width_slope_lookback
    if len(closes) < period + lookback:
        raise SignalEngineError(
            f"At least {period + lookback} closes are required for band width slope"
        )

    current_middle, _, _, current_band_width = _calculate_bollinger_from_window(
        closes, period, sigma
    )
    current_normalized = _normalized_band_width(current_middle, current_band_width)

    past_closes = closes[:-lookback]
    past_middle, _, _, past_band_width = _calculate_bollinger_from_window(
        past_closes, period, sigma
    )
    past_normalized = _normalized_band_width(past_middle, past_band_width)

    return current_normalized - past_normalized


def build_v7_feature_snapshot_from_bars(
    bars: list[Bar],
    params: V7DetectorParams,
) -> V7FeatureSnapshot:
    _validate_required_bars_for_feature_build(bars, params)

    closes = _extract_closes_from_bars(bars)
    latest_close = closes[-1]

    middle_band, upper_band, lower_band, band_width = _calculate_bollinger_from_window(
        closes,
        params.feature.bollinger_period,
        params.feature.bollinger_sigma,
    )
    normalized_band_width = _normalized_band_width(middle_band, band_width)
    band_width_slope = compute_band_width_slope(closes, params)
    distance_from_middle = _distance_from_middle(latest_close, middle_band)
    range_slope, _ = _normalized_slope(
        closes,
        params.feature.range_ma_period,
        params.feature.range_slope_lookback,
    )
    trend_slope, trend_ma = _normalized_slope(
        closes,
        params.feature.trend_ma_period,
        params.feature.trend_slope_lookback,
    )

    return V7FeatureSnapshot(
        latest_close=latest_close,
        middle_band=middle_band,
        upper_band=upper_band,
        lower_band=lower_band,
        normalized_band_width=normalized_band_width,
        band_width_slope=band_width_slope,
        distance_from_middle=distance_from_middle,
        range_slope=range_slope,
        trend_slope=trend_slope,
        trend_ma=trend_ma,
        recent_high_break_count=compute_recent_high_break_count(bars, params),
        recent_low_break_count=compute_recent_low_break_count(bars, params),
        higher_lows_count=compute_higher_lows_count(bars, params),
        lower_highs_count=compute_lower_highs_count(bars, params),
        price_above_ma_streak=compute_price_above_ma_streak(closes, params),
        price_below_ma_streak=compute_price_below_ma_streak(closes, params),
    )


def build_v7_feature_snapshot(
    market_snapshot: MarketSnapshot,
    params: V7DetectorParams,
) -> V7FeatureSnapshot:
    return build_v7_feature_snapshot_from_bars(market_snapshot.bars, params)