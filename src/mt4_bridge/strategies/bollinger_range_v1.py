# src\mt4_bridge\strategies\bollinger_range_v1.py
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
# ボリンジャーバンド計算本数
BOLLINGER_PERIOD = 20

# 標準偏差係数
BOLLINGER_SIGMA = 2.0

# レンジ判定を使うか
RANGE_FILTER_ENABLED = True

# レンジ判定しきい値
# normalized_band_width = (upper - lower) / middle
# これがこの値以下ならレンジとみなす
RANGE_WIDTH_THRESHOLD = 0.002

# ミドルライン到達で決済するか
EXIT_ON_MIDDLE_BAND = True


def required_bars() -> int:
    return BOLLINGER_PERIOD


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


def _normalized_band_width(middle: float, band_width: float) -> float:
    if middle == 0:
        raise SignalEngineError("Middle band is zero; normalized band width undefined")
    return band_width / middle


def _is_range_market(normalized_band_width: float) -> bool:
    if not RANGE_FILTER_ENABLED:
        return True
    return normalized_band_width <= RANGE_WIDTH_THRESHOLD


def _base_signal(
    market_snapshot: MarketSnapshot,
) -> tuple[SignalAction, str, float, float, float, float, bool]:
    bars = market_snapshot.bars

    if len(bars) < required_bars():
        raise SignalEngineError(
            f"At least {required_bars()} bars are required to evaluate bollinger_range_v1"
        )

    closes = [bar.close for bar in bars]
    latest_close = closes[-1]

    middle, upper, lower, band_width = _calculate_bollinger_bands(closes)
    normalized_width = _normalized_band_width(middle, band_width)
    is_range = _is_range_market(normalized_width)

    if not is_range:
        return (
            SignalAction.HOLD,
            (
                "range filter blocked entry"
                f" (normalized_band_width={normalized_width:.6f}"
                f" > threshold={RANGE_WIDTH_THRESHOLD:.6f})"
            ),
            middle,
            upper,
            lower,
            normalized_width,
            False,
        )

    if latest_close >= upper:
        return (
            SignalAction.SELL,
            (
                f"latest close {latest_close} reached or exceeded upper band {upper}"
                f" in range market"
                f" (middle={middle}, lower={lower}, normalized_band_width={normalized_width:.6f})"
            ),
            middle,
            upper,
            lower,
            normalized_width,
            True,
        )

    if latest_close <= lower:
        return (
            SignalAction.BUY,
            (
                f"latest close {latest_close} reached or fell below lower band {lower}"
                f" in range market"
                f" (middle={middle}, upper={upper}, normalized_band_width={normalized_width:.6f})"
            ),
            middle,
            upper,
            lower,
            normalized_width,
            True,
        )

    return (
        SignalAction.HOLD,
        (
            f"latest close {latest_close} stayed within bands"
            f" (upper={upper}, lower={lower}, middle={middle},"
            f" normalized_band_width={normalized_width:.6f})"
        ),
        middle,
        upper,
        lower,
        normalized_width,
        True,
    )


def evaluate_bollinger_range_v1(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_range_v1",
) -> SignalDecision:
    bars = market_snapshot.bars
    if len(bars) < required_bars():
        raise SignalEngineError(
            f"At least {required_bars()} bars are required to evaluate bollinger_range_v1"
        )

    previous_bar = bars[-2]
    latest_bar = bars[-1]

    (
        base_action,
        base_reason,
        middle_band,
        upper_band,
        lower_band,
        normalized_width,
        is_range,
    ) = _base_signal(market_snapshot)

    current_position = position_snapshot.positions[0] if position_snapshot.positions else None

    reason_suffix = (
        f" (period={BOLLINGER_PERIOD}, sigma={BOLLINGER_SIGMA},"
        f" range_filter_enabled={RANGE_FILTER_ENABLED},"
        f" range_width_threshold={RANGE_WIDTH_THRESHOLD},"
        f" exit_on_middle_band={EXIT_ON_MIDDLE_BAND},"
        f" middle={middle_band}, upper={upper_band}, lower={lower_band},"
        f" normalized_band_width={normalized_width:.6f}, is_range={is_range})"
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

    if EXIT_ON_MIDDLE_BAND:
        if current_type == "buy" and latest_bar.close >= middle_band:
            return SignalDecision(
                strategy_name=strategy_name,
                action=SignalAction.CLOSE,
                reason=(
                    f"buy position closed because latest close {latest_bar.close}"
                    f" returned to or exceeded middle band {middle_band}"
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
                    f"sell position closed because latest close {latest_bar.close}"
                    f" returned to or fell below middle band {middle_band}"
                    + reason_suffix
                ),
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