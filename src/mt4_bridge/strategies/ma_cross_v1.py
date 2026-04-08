# src/mt4_bridge/strategies/ma_cross_v1.py
from __future__ import annotations

from mt4_bridge.models import MarketSnapshot, PositionSnapshot, SignalAction, SignalDecision
from mt4_bridge.signal_exceptions import SignalEngineError


SHORT_WINDOW = 5
LONG_WINDOW = 20


def required_bars() -> int:
    return LONG_WINDOW


def _simple_moving_average(values: list[float]) -> float:
    if not values:
        raise SignalEngineError("Moving average requires at least 1 value")
    return sum(values) / len(values)


def _base_ma_cross_signal(
    market_snapshot: MarketSnapshot,
) -> tuple[SignalAction, str, float, float]:
    bars = market_snapshot.bars

    if len(bars) < required_bars():
        raise SignalEngineError(
            f"At least {required_bars()} bars are required to evaluate ma_cross_v1"
        )

    closes = [bar.close for bar in bars]
    short_ma = _simple_moving_average(closes[-SHORT_WINDOW:])
    long_ma = _simple_moving_average(closes[-LONG_WINDOW:])

    if short_ma > long_ma:
        return (
            SignalAction.BUY,
            f"short MA {short_ma} is greater than long MA {long_ma}",
            short_ma,
            long_ma,
        )

    if short_ma < long_ma:
        return (
            SignalAction.SELL,
            f"short MA {short_ma} is lower than long MA {long_ma}",
            short_ma,
            long_ma,
        )

    return (
        SignalAction.HOLD,
        f"short MA {short_ma} is equal to long MA {long_ma}",
        short_ma,
        long_ma,
    )


def evaluate_ma_cross_v1(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "ma_cross_v1",
) -> SignalDecision:
    bars = market_snapshot.bars
    if len(bars) < required_bars():
        raise SignalEngineError(
            f"At least {required_bars()} bars are required to evaluate ma_cross_v1"
        )

    previous_bar = bars[-2]
    latest_bar = bars[-1]

    base_action, base_reason, short_ma, long_ma = _base_ma_cross_signal(market_snapshot)
    current_position = position_snapshot.positions[0] if position_snapshot.positions else None

    reason_suffix = f" (short_window={SHORT_WINDOW}, long_window={LONG_WINDOW})"

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
                reason=f"buy signal but buy position already exists (short_ma={short_ma}, long_ma={long_ma})",
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
            reason=f"sell signal detected while buy position exists (short_ma={short_ma}, long_ma={long_ma})",
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
                reason=f"sell signal but sell position already exists (short_ma={short_ma}, long_ma={long_ma})",
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
            reason=f"buy signal detected while sell position exists (short_ma={short_ma}, long_ma={long_ma})",
            previous_bar_time=previous_bar.time,
            latest_bar_time=latest_bar.time,
            previous_close=previous_bar.close,
            latest_close=latest_bar.close,
            current_position_ticket=current_position.ticket,
            current_position_type=current_type,
        )

    raise SignalEngineError(f"Unsupported position type: {current_type}")
