# src/mt4_bridge/strategies/bollinger_trend_B2_indicators.py
"""bollinger_trend_B2 が使う指標計算。

外部依存なし(numpy/pandas 不使用)。既存戦術のスタイルに合わせた手実装。
"""
from __future__ import annotations

import statistics
from typing import Sequence


def ema(values: Sequence[float], period: int) -> list[float]:
    """標準的な EMA。最初の period 本は SMA で初期化。

    戻り値の長さは len(values) - period + 1(period 不足なら空リスト)。
    """
    if period <= 0 or len(values) < period:
        return []
    multiplier = 2.0 / (period + 1)
    seed = sum(values[:period]) / period
    result: list[float] = [seed]
    for v in values[period:]:
        result.append((v - result[-1]) * multiplier + result[-1])
    return result


def _true_range(high: float, low: float, prev_close: float) -> float:
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int,
) -> list[float]:
    """Wilder's smoothing で ATR を計算。戻り値の長さ = len(closes) - period。"""
    if period <= 0 or len(closes) < period + 1:
        return []
    trs: list[float] = []
    for i in range(1, len(closes)):
        trs.append(_true_range(highs[i], lows[i], closes[i - 1]))
    first = sum(trs[:period]) / period
    result = [first]
    for tr in trs[period:]:
        result.append((result[-1] * (period - 1) + tr) / period)
    return result


def adx(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> list[float]:
    """標準的な ADX 計算 (Wilder's smoothing 2 回)。戻り値の長さは
    len(closes) - 2*period 程度(計算に余裕要)。
    """
    if period <= 0 or len(closes) < 2 * period + 1:
        return []

    plus_dm: list[float] = []
    minus_dm: list[float] = []
    trs: list[float] = []
    for i in range(1, len(closes)):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus = up_move if up_move > down_move and up_move > 0 else 0.0
        minus = down_move if down_move > up_move and down_move > 0 else 0.0
        plus_dm.append(plus)
        minus_dm.append(minus)
        trs.append(_true_range(highs[i], lows[i], closes[i - 1]))

    # Wilder smooth seed = 最初 period の合計
    sm_plus: list[float] = [sum(plus_dm[:period])]
    sm_minus: list[float] = [sum(minus_dm[:period])]
    sm_tr: list[float] = [sum(trs[:period])]
    for i in range(period, len(trs)):
        sm_plus.append(sm_plus[-1] - sm_plus[-1] / period + plus_dm[i])
        sm_minus.append(sm_minus[-1] - sm_minus[-1] / period + minus_dm[i])
        sm_tr.append(sm_tr[-1] - sm_tr[-1] / period + trs[i])

    di_plus = [100.0 * sp / st if st > 0 else 0.0 for sp, st in zip(sm_plus, sm_tr)]
    di_minus = [100.0 * sm / st if st > 0 else 0.0 for sm, st in zip(sm_minus, sm_tr)]
    dx = [
        100.0 * abs(dp - dm) / (dp + dm) if (dp + dm) > 0 else 0.0
        for dp, dm in zip(di_plus, di_minus)
    ]

    if len(dx) < period:
        return []
    adx_seed = sum(dx[:period]) / period
    result = [adx_seed]
    for d in dx[period:]:
        result.append((result[-1] * (period - 1) + d) / period)
    return result


def bollinger_bands(
    closes: Sequence[float], period: int, sigma: float
) -> tuple[float, float, float] | None:
    """最新値のみ返す (mid, upper, lower)。データ不足は None。"""
    if len(closes) < period:
        return None
    recent = list(closes[-period:])
    mid = sum(recent) / period
    sd = statistics.pstdev(recent)
    return mid, mid + sigma * sd, mid - sigma * sd


def compose_h1_closes(closes: Sequence[float], h1_bars: int) -> list[float]:
    """5分足 close 列から、末尾側 h1_bars ごとの close を H1 1 本と見なして束ねる。

    最後のバーを H1 1 本の終端とし、遡って h1_bars 刻みで H1 close を作る。
    """
    if h1_bars <= 0 or len(closes) < h1_bars:
        return []
    n = len(closes) // h1_bars
    h1_closes: list[float] = []
    # 末尾から h1_bars ステップで遡って、n 本を時系列順で組む
    for i in range(n):
        # 最新側から順に i 番目の H1 1 本の終端 index
        end = len(closes) - i * h1_bars - 1
        h1_closes.append(closes[end])
    # 時系列昇順に並べ直す (最新を末尾に)
    h1_closes.reverse()
    return h1_closes
