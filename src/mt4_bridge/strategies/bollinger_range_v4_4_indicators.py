# src/mt4_bridge/strategies/bollinger_range_v4_4_indicators.py
from __future__ import annotations

from math import sqrt

from mt4_bridge.signal_exceptions import SignalEngineError

from mt4_bridge.strategies.bollinger_range_v4_4_params import (
    BOLLINGER_PERIOD,
    BAND_WALK_LOOKBACK_BARS,
    BAND_EDGE_ZONE_RATIO,
    MIDDLE_CROSS_LOOKBACK_BARS,
    ONE_SIDE_STAY_LOOKBACK_BARS,
    BAND_WIDTH_EXPANSION_LOOKBACK_BARS,
    TREND_SLOPE_ACCEL_LOOKBACK_BARS,
    MEAN_REVERSION_LOOKAHEAD_BARS_LIST,
    MEAN_REVERSION_TOUCH_EPSILON,
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


# =============================================================================
# 観測用関数 (TASK-0107)
# 既存売買ロジックには接続しない純粋関数群
# =============================================================================


def _calculate_band_walk_stats(
    closes: list[float],
    upper_band: list[float],
    lower_band: list[float],
    lookback: int = BAND_WALK_LOOKBACK_BARS,
    edge_zone_ratio: float = BAND_EDGE_ZONE_RATIO,
) -> dict:
    n = min(lookback, len(closes), len(upper_band), len(lower_band))
    if n == 0:
        return {
            "upper_hits_count": 0,
            "lower_hits_count": 0,
            "total_lookback": 0,
            "upper_hit_ratio": 0.0,
            "lower_hit_ratio": 0.0,
        }

    upper_hits = 0
    lower_hits = 0
    for i in range(1, n + 1):
        c = closes[-i]
        u = upper_band[-i]
        lo = lower_band[-i]
        bw = u - lo
        if bw <= 0:
            continue
        zone = bw * edge_zone_ratio
        if c >= u - zone:
            upper_hits += 1
        if c <= lo + zone:
            lower_hits += 1

    return {
        "upper_hits_count": upper_hits,
        "lower_hits_count": lower_hits,
        "total_lookback": n,
        "upper_hit_ratio": upper_hits / n if n > 0 else 0.0,
        "lower_hit_ratio": lower_hits / n if n > 0 else 0.0,
    }


def _calculate_middle_cross_stats(
    closes: list[float],
    middle_band: list[float],
    lookback: int = MIDDLE_CROSS_LOOKBACK_BARS,
) -> dict:
    n = min(lookback, len(closes) - 1, len(middle_band) - 1)
    if n <= 0:
        return {"cross_count": 0, "has_cross": False}

    cross_count = 0
    for i in range(1, n + 1):
        idx_cur = len(closes) - i
        idx_prev = idx_cur - 1
        cur_side = closes[idx_cur] - middle_band[idx_cur]
        prev_side = closes[idx_prev] - middle_band[idx_prev]
        if cur_side * prev_side < 0:
            cross_count += 1

    return {"cross_count": cross_count, "has_cross": cross_count > 0}


def _calculate_one_side_stay_stats(
    closes: list[float],
    middle_band: list[float],
    lookback: int = ONE_SIDE_STAY_LOOKBACK_BARS,
) -> dict:
    n = min(lookback, len(closes), len(middle_band))
    if n == 0:
        return {
            "above_count": 0,
            "below_count": 0,
            "above_ratio": 0.0,
            "below_ratio": 0.0,
            "is_one_side": False,
        }

    above = 0
    below = 0
    for i in range(1, n + 1):
        if closes[-i] > middle_band[-i]:
            above += 1
        elif closes[-i] < middle_band[-i]:
            below += 1

    above_ratio = above / n
    below_ratio = below / n
    is_one_side = above == n or below == n

    return {
        "above_count": above,
        "below_count": below,
        "above_ratio": above_ratio,
        "below_ratio": below_ratio,
        "is_one_side": is_one_side,
    }


def _calculate_band_width_expansion_ratio(
    upper_band: list[float],
    lower_band: list[float],
    lookback: int = BAND_WIDTH_EXPANSION_LOOKBACK_BARS,
) -> dict:
    if len(upper_band) < 1 or len(lower_band) < 1:
        return {
            "current_band_width": 0.0,
            "past_band_width": 0.0,
            "expansion_ratio": 0.0,
        }

    current_bw = upper_band[-1] - lower_band[-1]

    past_idx = max(0, len(upper_band) - 1 - lookback)
    past_bw = upper_band[past_idx] - lower_band[past_idx]

    if past_bw == 0:
        expansion_ratio = 0.0
    else:
        expansion_ratio = current_bw / past_bw

    return {
        "current_band_width": current_bw,
        "past_band_width": past_bw,
        "expansion_ratio": expansion_ratio,
    }


def _calculate_trend_slope_acceleration_ratio(
    closes: list[float],
    period: int,
    lookback: int = TREND_SLOPE_ACCEL_LOOKBACK_BARS,
) -> dict:
    required = period + lookback * 2
    if len(closes) < required:
        return {
            "current_slope": 0.0,
            "past_slope": 0.0,
            "acceleration_ratio": 0.0,
        }

    current_ma = _simple_moving_average(closes[-period:])
    past_ma_1 = _simple_moving_average(
        closes[-(period + lookback) : -lookback]
    )
    if current_ma == 0:
        current_slope = 0.0
    else:
        current_slope = (current_ma - past_ma_1) / current_ma

    past_ma_2 = _simple_moving_average(
        closes[-(period + lookback * 2) : -(lookback * 2)]
    )
    if past_ma_1 == 0:
        past_slope = 0.0
    else:
        past_slope = (past_ma_1 - past_ma_2) / past_ma_1

    if past_slope == 0:
        acceleration_ratio = 0.0
    else:
        acceleration_ratio = current_slope / past_slope

    return {
        "current_slope": current_slope,
        "past_slope": past_slope,
        "acceleration_ratio": acceleration_ratio,
    }


def _calculate_progress_to_middle(
    current_close: float,
    entry_price: float,
    middle_band: float,
) -> dict:
    entry_to_middle = middle_band - entry_price
    if entry_to_middle == 0:
        return {
            "progress_ratio_to_middle": 0.0,
            "distance_to_middle": 0.0,
            "normalized_progress": 0.0,
        }

    distance_to_middle = middle_band - current_close
    moved = current_close - entry_price
    progress_ratio = moved / entry_to_middle

    if middle_band == 0:
        normalized_progress = 0.0
    else:
        normalized_progress = abs(moved) / abs(middle_band)

    return {
        "progress_ratio_to_middle": progress_ratio,
        "distance_to_middle": distance_to_middle,
        "normalized_progress": normalized_progress,
    }


def _check_mean_reversion_lookahead(
    closes: list[float],
    entry_bar_index: int,
    middle_band_at_entry: float,
    lookahead_bars_list: list[int] | None = None,
    touch_epsilon: float = MEAN_REVERSION_TOUCH_EPSILON,
) -> dict:
    if lookahead_bars_list is None:
        lookahead_bars_list = list(MEAN_REVERSION_LOOKAHEAD_BARS_LIST)

    success_within_n: dict[int, bool] = {}
    first_hit_bar_index: int | None = None

    max_look = max(lookahead_bars_list) if lookahead_bars_list else 0
    threshold = abs(middle_band_at_entry * touch_epsilon)

    for offset in range(1, max_look + 1):
        bar_idx = entry_bar_index + offset
        if bar_idx >= len(closes):
            break
        if abs(closes[bar_idx] - middle_band_at_entry) <= threshold:
            if first_hit_bar_index is None:
                first_hit_bar_index = bar_idx
            break

    for n in lookahead_bars_list:
        if first_hit_bar_index is not None:
            success_within_n[n] = (first_hit_bar_index - entry_bar_index) <= n
        else:
            success_within_n[n] = False

    return {
        "success_within_n": success_within_n,
        "first_hit_bar_index": first_hit_bar_index,
    }
