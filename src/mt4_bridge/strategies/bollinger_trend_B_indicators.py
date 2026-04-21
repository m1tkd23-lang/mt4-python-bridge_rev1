# src/mt4_bridge/strategies/bollinger_trend_B_indicators.py
from __future__ import annotations

from math import sqrt

from mt4_bridge.signal_exceptions import SignalEngineError

from mt4_bridge.strategies.bollinger_trend_B_params import (
    BOLLINGER_PERIOD,
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
