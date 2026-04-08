# src\mt4_bridge\risk_manager.py
from __future__ import annotations

from mt4_bridge.models import SignalAction


def calculate_sl_tp(
    action: SignalAction,
    bid: float,
    ask: float,
    point: float,
    sl_pips: float,
    tp_pips: float,
) -> tuple[float | None, float | None]:
    if action not in (SignalAction.BUY, SignalAction.SELL):
        return None, None

    pip_value = point * 10.0

    sl_distance = sl_pips * pip_value
    tp_distance = tp_pips * pip_value

    if action == SignalAction.BUY:
        entry = ask
        sl = entry - sl_distance
        tp = entry + tp_distance
        return sl, tp

    entry = bid
    sl = entry + sl_distance
    tp = entry - tp_distance
    return sl, tp