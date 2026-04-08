# src\mt4_bridge\strategies\bollinger_range_v2.py
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

# レンジ判定用 MA
RANGE_MA_PERIOD = 20
RANGE_SLOPE_LOOKBACK = 5
RANGE_SLOPE_THRESHOLD = 0.0002

# トレンド判定用 MA
TREND_MA_PERIOD = 50
TREND_SLOPE_LOOKBACK = 5
TREND_SLOPE_THRESHOLD = 0.0005

# 決済ルール
EXIT_ON_RANGE_MIDDLE_BAND = True
CLOSE_ON_OPPOSITE_TREND_STATE = True


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


def _calculate_bollinger_bands(
    closes: list[float],
) -> tuple[float, float, float, float]:
    if len(closes) < BOLLINGER_PERIOD:
        raise SignalEngineError(
            f"At least {BOLLINGER_PERIOD} closes are required for Bollinger Bands"
        )

    window = closes[-BOLLINGER_PERIOD:]
    middle = _simple_moving_average(window)
    stddev = _standard_deviation(window, middle)
    upper = middle + (BOLLINGER_SIGMA * stddev)
    lower = middle - (BOLLINGER_SIGMA * stddev)
    band_width = upper - lower
    return middle, upper, lower, band_width


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


def _determine_market_state(
    range_slope: float,
    trend_slope: float,
) -> tuple[str, str]:
    if trend_slope > TREND_SLOPE_THRESHOLD:
        return (
            "trend_up",
            (
                f"trend_up because trend_slope={trend_slope:.6f}"
                f" > threshold={TREND_SLOPE_THRESHOLD:.6f}"
            ),
        )

    if trend_slope < -TREND_SLOPE_THRESHOLD:
        return (
            "trend_down",
            (
                f"trend_down because trend_slope={trend_slope:.6f}"
                f" < -threshold={TREND_SLOPE_THRESHOLD:.6f}"
            ),
        )

    if abs(range_slope) <= RANGE_SLOPE_THRESHOLD:
        return (
            "range",
            (
                f"range because abs(range_slope)={abs(range_slope):.6f}"
                f" <= threshold={RANGE_SLOPE_THRESHOLD:.6f}"
            ),
        )

    return (
        "neutral",
        (
            f"neutral because trend_slope={trend_slope:.6f} did not exceed"
            f" trend threshold and abs(range_slope)={abs(range_slope):.6f}"
            f" exceeded range threshold={RANGE_SLOPE_THRESHOLD:.6f}"
        ),
    )


def _base_signal(
    market_snapshot: MarketSnapshot,
) -> tuple[SignalAction, str, str, float, float, float, float, float, float]:
    bars = market_snapshot.bars

    if len(bars) < required_bars():
        raise SignalEngineError(
            f"At least {required_bars()} bars are required to evaluate bollinger_range_v2"
        )

    closes = [bar.close for bar in bars]
    latest_close = closes[-1]

    middle_band, upper_band, lower_band, band_width = _calculate_bollinger_bands(closes)

    range_slope, range_current_ma, range_past_ma = _normalized_slope(
        closes=closes,
        period=RANGE_MA_PERIOD,
        lookback=RANGE_SLOPE_LOOKBACK,
    )
    trend_slope, trend_current_ma, trend_past_ma = _normalized_slope(
        closes=closes,
        period=TREND_MA_PERIOD,
        lookback=TREND_SLOPE_LOOKBACK,
    )

    market_state, state_reason = _determine_market_state(
        range_slope=range_slope,
        trend_slope=trend_slope,
    )

    if market_state == "range":
        if latest_close >= upper_band:
            return (
                SignalAction.SELL,
                (
                    f"range mean-reversion sell because latest close {latest_close}"
                    f" reached or exceeded upper band {upper_band}; {state_reason}"
                ),
                market_state,
                middle_band,
                upper_band,
                lower_band,
                range_slope,
                trend_slope,
                band_width,
            )

        if latest_close <= lower_band:
            return (
                SignalAction.BUY,
                (
                    f"range mean-reversion buy because latest close {latest_close}"
                    f" reached or fell below lower band {lower_band}; {state_reason}"
                ),
                market_state,
                middle_band,
                upper_band,
                lower_band,
                range_slope,
                trend_slope,
                band_width,
            )

        return (
            SignalAction.HOLD,
            (
                f"range state but latest close {latest_close} stayed within bands"
                f" (upper={upper_band}, lower={lower_band}); {state_reason}"
            ),
            market_state,
            middle_band,
            upper_band,
            lower_band,
            range_slope,
            trend_slope,
            band_width,
        )

    if market_state == "trend_up":
        if latest_close >= upper_band:
            return (
                SignalAction.BUY,
                (
                    f"trend-follow buy because latest close {latest_close}"
                    f" reached or exceeded upper band {upper_band}; {state_reason}"
                ),
                market_state,
                middle_band,
                upper_band,
                lower_band,
                range_slope,
                trend_slope,
                band_width,
            )

        return (
            SignalAction.HOLD,
            (
                f"trend_up state but latest close {latest_close}"
                f" did not reach upper band {upper_band}; {state_reason}"
            ),
            market_state,
            middle_band,
            upper_band,
            lower_band,
            range_slope,
            trend_slope,
            band_width,
        )

    if market_state == "trend_down":
        if latest_close <= lower_band:
            return (
                SignalAction.SELL,
                (
                    f"trend-follow sell because latest close {latest_close}"
                    f" reached or fell below lower band {lower_band}; {state_reason}"
                ),
                market_state,
                middle_band,
                upper_band,
                lower_band,
                range_slope,
                trend_slope,
                band_width,
            )

        return (
            SignalAction.HOLD,
            (
                f"trend_down state but latest close {latest_close}"
                f" did not reach lower band {lower_band}; {state_reason}"
            ),
            market_state,
            middle_band,
            upper_band,
            lower_band,
            range_slope,
            trend_slope,
            band_width,
        )

    return (
        SignalAction.HOLD,
        (
            f"neutral state so entry is skipped"
            f" (latest_close={latest_close}, upper={upper_band}, lower={lower_band});"
            f" {state_reason}"
        ),
        market_state,
        middle_band,
        upper_band,
        lower_band,
        range_slope,
        trend_slope,
        band_width,
    )


def evaluate_bollinger_range_v2(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_range_v2",
) -> SignalDecision:
    bars = market_snapshot.bars
    if len(bars) < required_bars():
        raise SignalEngineError(
            f"At least {required_bars()} bars are required to evaluate bollinger_range_v2"
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
        range_slope,
        trend_slope,
        band_width,
    ) = _base_signal(market_snapshot)

    current_position = position_snapshot.positions[0] if position_snapshot.positions else None

    reason_suffix = (
        f" (bollinger_period={BOLLINGER_PERIOD}, bollinger_sigma={BOLLINGER_SIGMA},"
        f" range_ma_period={RANGE_MA_PERIOD},"
        f" range_slope_lookback={RANGE_SLOPE_LOOKBACK},"
        f" range_slope_threshold={RANGE_SLOPE_THRESHOLD},"
        f" trend_ma_period={TREND_MA_PERIOD},"
        f" trend_slope_lookback={TREND_SLOPE_LOOKBACK},"
        f" trend_slope_threshold={TREND_SLOPE_THRESHOLD},"
        f" exit_on_range_middle_band={EXIT_ON_RANGE_MIDDLE_BAND},"
        f" close_on_opposite_trend_state={CLOSE_ON_OPPOSITE_TREND_STATE},"
        f" state={market_state}, middle={middle_band}, upper={upper_band},"
        f" lower={lower_band}, band_width={band_width},"
        f" range_slope={range_slope:.6f}, trend_slope={trend_slope:.6f})"
    )

    if current_position is None:
        return SignalDecision(
            strategy_name=strategy_name,
            action=base_action,
            reason=base_reason + reason_suffix,
            previous_bar_time=previous_bar.time,
            latest_bar_time=latest_bar.time,
            previous_close=previous_bar.close,
            latest_close=latest_bar.close,
            current_position_ticket=None,
            current_position_type=None,
        )

    current_type = current_position.position_type.lower()

    if market_state == "range" and EXIT_ON_RANGE_MIDDLE_BAND:
        if current_type == "buy" and latest_bar.close >= middle_band:
            return SignalDecision(
                strategy_name=strategy_name,
                action=SignalAction.CLOSE,
                reason=(
                    f"buy position closed because range state returned to middle band:"
                    f" latest close {latest_bar.close} >= middle {middle_band}"
                    + reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_bar.close,
                latest_close=latest_bar.close,
                current_position_ticket=current_position.ticket,
                current_position_type=current_type,
            )

        if current_type == "sell" and latest_bar.close <= middle_band:
            return SignalDecision(
                strategy_name=strategy_name,
                action=SignalAction.CLOSE,
                reason=(
                    f"sell position closed because range state returned to middle band:"
                    f" latest close {latest_bar.close} <= middle {middle_band}"
                    + reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_bar.close,
                latest_close=latest_bar.close,
                current_position_ticket=current_position.ticket,
                current_position_type=current_type,
            )

    if CLOSE_ON_OPPOSITE_TREND_STATE:
        if current_type == "buy" and market_state == "trend_down":
            return SignalDecision(
                strategy_name=strategy_name,
                action=SignalAction.CLOSE,
                reason="buy position closed because state switched to trend_down" + reason_suffix,
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_bar.close,
                latest_close=latest_bar.close,
                current_position_ticket=current_position.ticket,
                current_position_type=current_type,
            )

        if current_type == "sell" and market_state == "trend_up":
            return SignalDecision(
                strategy_name=strategy_name,
                action=SignalAction.CLOSE,
                reason="sell position closed because state switched to trend_up" + reason_suffix,
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_bar.close,
                latest_close=latest_bar.close,
                current_position_ticket=current_position.ticket,
                current_position_type=current_type,
            )

    if base_action == SignalAction.HOLD:
        return SignalDecision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=f"{base_reason}{reason_suffix}; existing {current_type} position kept",
            previous_bar_time=previous_bar.time,
            latest_bar_time=latest_bar.time,
            previous_close=previous_bar.close,
            latest_close=latest_bar.close,
            current_position_ticket=current_position.ticket,
            current_position_type=current_type,
        )

    if current_type == "buy":
        if base_action == SignalAction.BUY:
            return SignalDecision(
                strategy_name=strategy_name,
                action=SignalAction.HOLD,
                reason="buy signal but buy position already exists" + reason_suffix,
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_bar.close,
                latest_close=latest_bar.close,
                current_position_ticket=current_position.ticket,
                current_position_type=current_type,
            )
        return SignalDecision(
            strategy_name=strategy_name,
            action=SignalAction.CLOSE,
            reason="sell signal detected while buy position exists" + reason_suffix,
            previous_bar_time=previous_bar.time,
            latest_bar_time=latest_bar.time,
            previous_close=previous_bar.close,
            latest_close=latest_bar.close,
            current_position_ticket=current_position.ticket,
            current_position_type=current_type,
        )

    if current_type == "sell":
        if base_action == SignalAction.SELL:
            return SignalDecision(
                strategy_name=strategy_name,
                action=SignalAction.HOLD,
                reason="sell signal but sell position already exists" + reason_suffix,
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_bar.close,
                latest_close=latest_bar.close,
                current_position_ticket=current_position.ticket,
                current_position_type=current_type,
            )
        return SignalDecision(
            strategy_name=strategy_name,
            action=SignalAction.CLOSE,
            reason="buy signal detected while sell position exists" + reason_suffix,
            previous_bar_time=previous_bar.time,
            latest_bar_time=latest_bar.time,
            previous_close=previous_bar.close,
            latest_close=latest_bar.close,
            current_position_ticket=current_position.ticket,
            current_position_type=current_type,
        )

    raise SignalEngineError(f"Unsupported position type: {current_type}")