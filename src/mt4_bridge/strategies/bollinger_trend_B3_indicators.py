# src/mt4_bridge/strategies/bollinger_trend_B3_indicators.py
"""bollinger_trend_B3 用の指標計算。BB (2σ, 3σ) と前 bar 相当 BB 幅。"""
from __future__ import annotations

import statistics
from typing import Sequence


def _bb_from_closes(
    closes: Sequence[float], period: int, sigma: float
) -> tuple[float, float, float] | None:
    """closes の末尾 period 本で BB (mid, upper, lower) を返す。"""
    if len(closes) < period:
        return None
    recent = list(closes[-period:])
    mid = sum(recent) / period
    sd = statistics.pstdev(recent)
    return mid, mid + sigma * sd, mid - sigma * sd


def bollinger_pair(
    closes: Sequence[float], period: int, sigma: float, extreme_sigma: float
) -> tuple[
    tuple[float, float, float] | None,
    tuple[float, float, float] | None,
]:
    """(2σ, 3σ) を同時返却。"""
    return (
        _bb_from_closes(closes, period, sigma),
        _bb_from_closes(closes, period, extreme_sigma),
    )


def bandwidth_current_and_prev(
    closes: Sequence[float], period: int, sigma: float
) -> tuple[float | None, float | None]:
    """最新 bar と 1 本前の BB 幅を返す (upper - lower)。計算不能は None。"""
    if len(closes) < period + 1:
        return None, None
    now = _bb_from_closes(closes, period, sigma)
    prev = _bb_from_closes(closes[:-1], period, sigma)
    if now is None or prev is None:
        return None, None
    return (now[1] - now[2]), (prev[1] - prev[2])
