# src/mt4_bridge/strategies/strategy_20260403t102002_i02_v1.py
from __future__ import annotations

from mt4_bridge.models import (
    MarketSnapshot,
    PositionSnapshot,
    SignalAction,
    SignalDecision,
)
from mt4_bridge.signal_exceptions import SignalEngineError

SHORT_WINDOW = 5
LONG_WINDOW = 20

def required_bars() -> int:
    return 20


def _simple_moving_average(values: list[float]) -> float:
    if not values:
        raise SignalEngineError("Moving average requires at least 1 value")
    return sum(values) / len(values)

def _base_signal(
    market_snapshot: MarketSnapshot,
) -> tuple[SignalAction, str]:
    bars = market_snapshot.bars

    if len(bars) < required_bars():
        raise SignalEngineError(
            f"At least {required_bars()} bars are required to evaluate strategy_20260403t102002_i02_v1"
        )

    closes = [bar.close for bar in bars]
    short_ma = _simple_moving_average(closes[-SHORT_WINDOW:])
    long_ma = _simple_moving_average(closes[-LONG_WINDOW:])
    
    if short_ma > long_ma:
        return SignalAction.BUY, f"short MA {short_ma} > long MA {long_ma}"
    
    if short_ma < long_ma:
        return SignalAction.SELL, f"short MA {short_ma} < long MA {long_ma}"
    
    return SignalAction.HOLD, f"short MA {short_ma} == long MA {long_ma}"

def evaluate_strategy_20260403t102002_i02_v1(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "strategy_20260403t102002_i02_v1",
) -> SignalDecision:
    bars = market_snapshot.bars
    if len(bars) < required_bars():
        raise SignalEngineError(
            f"At least {required_bars()} bars are required to evaluate strategy_20260403t102002_i02_v1"
        )

    previous_bar = bars[-2]
    latest_bar = bars[-1]
    base_action, base_reason = _base_signal(market_snapshot)

    current_position = (
        position_snapshot.positions[0] if position_snapshot.positions else None
    )

    if current_position is None:
        return SignalDecision(
            strategy_name=strategy_name,
            action=base_action,
            reason=base_reason,
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
            reason=f"{base_reason}; existing {current_type} position kept",
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
                reason="buy signal but buy position already exists",
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
            reason="sell signal detected while buy position exists",
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
                reason="sell signal but sell position already exists",
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
            reason="buy signal detected while sell position exists",
            previous_bar_time=previous_bar.time,
            latest_bar_time=latest_bar.time,
            previous_close=previous_bar.close,
            latest_close=latest_bar.close,
            current_position_ticket=current_position.ticket,
            current_position_type=current_type,
        )

    raise SignalEngineError(f"Unsupported position type: {current_type}")
