# src/mt4_bridge/strategies/bollinger_trend_B2_rules.py
"""bollinger_trend_B2 の判定ロジック。

役割:
- 入口: 5 条件 AND で方向 (buy/sell/None) を返す
- 早期撤退: 4 条件 OR で CLOSE 判定
- TP: 4 条件 OR で CLOSE 判定

結果の戻り値は文字列 (entry_subtype / exit_subtype 用) として decision に乗せる。
"""
from __future__ import annotations

from dataclasses import dataclass

from mt4_bridge.strategies.bollinger_trend_B2_indicators import (
    adx as _adx,
    atr as _atr,
    bollinger_bands,
    compose_h1_closes,
    ema as _ema,
)
from mt4_bridge.strategies.bollinger_trend_B2_params import (
    ADX_PERIOD,
    ADX_THRESHOLD_ENTRY,
    ADX_THRESHOLD_EXIT,
    ATR_PERIOD,
    BOLLINGER_PERIOD,
    BOLLINGER_SIGMA,
    CONFIRMATION_CANDLE_ENABLED,
    EARLY_EXIT_BARS,
    EARLY_EXIT_MIN_PROFIT_PIPS,
    EMA_FAST_PERIOD,
    EMA_SLOW_PERIOD,
    H1_BARS,
    H1_EMA_PERIOD,
    H1_SLOPE_ATR_RATIO,
    H1_SLOPE_LOOKBACK,
    PEAK_TRAIL_GIVEBACK_RATIO,
    PEAK_TRAIL_TRIGGER_PIPS,
    PIP_MULTIPLIER,
    PULLBACK_ATR_RATIO,
    TIME_EXIT_BARS,
    TP_PROFIT_THRESHOLD_PIPS,
    TP_STALL_BARS,
)


@dataclass(frozen=True)
class IndicatorSnapshot:
    """判定に使う最新の指標値一式。"""
    ema_fast: float
    ema_slow: float
    adx: float
    atr: float
    bb_mid: float
    bb_upper: float
    bb_lower: float
    h1_direction: str   # "up" / "down" / "neutral"
    latest_open: float
    latest_close: float
    latest_high: float
    latest_low: float


def build_snapshot(bars) -> IndicatorSnapshot | None:
    """bars (時系列昇順) から最新時点の各指標を計算。データ不足なら None。

    計算負荷対策: required_bars 相当 (H1_BARS × H1_EMA_PERIOD + 余裕) の末尾だけ
    を使う。bars が長大な BT 連結データでも O(1) 相当の安定計算時間になる。
    """
    _NEEDED = max(
        EMA_SLOW_PERIOD + 2,
        ADX_PERIOD * 2 + 2,
        ATR_PERIOD + 2,
        BOLLINGER_PERIOD + 2,
        H1_BARS * (H1_EMA_PERIOD + H1_SLOPE_LOOKBACK) + 2,
    )
    tail = bars[-_NEEDED:] if len(bars) > _NEEDED else bars
    closes = [b.close for b in tail]
    highs = [b.high for b in tail]
    lows = [b.low for b in tail]

    ema_fast_series = _ema(closes, EMA_FAST_PERIOD)
    ema_slow_series = _ema(closes, EMA_SLOW_PERIOD)
    atr_series = _atr(highs, lows, closes, ATR_PERIOD)
    adx_series = _adx(highs, lows, closes, ADX_PERIOD)
    bb = bollinger_bands(closes, BOLLINGER_PERIOD, BOLLINGER_SIGMA)

    if (
        not ema_fast_series
        or not ema_slow_series
        or not atr_series
        or not adx_series
        or bb is None
    ):
        return None

    # H1 合成
    h1_closes = compose_h1_closes(closes, H1_BARS)
    h1_ema_series = _ema(h1_closes, H1_EMA_PERIOD) if h1_closes else []
    h1_direction = "neutral"
    if len(h1_ema_series) >= H1_SLOPE_LOOKBACK + 1 and atr_series:
        slope_pips = (
            h1_ema_series[-1] - h1_ema_series[-1 - H1_SLOPE_LOOKBACK]
        )
        # ATR で正規化 (5分足 ATR × H1_BARS ≒ H1 相当)
        atr_h1_scaled = atr_series[-1] * H1_BARS
        if atr_h1_scaled > 0:
            ratio = slope_pips / atr_h1_scaled
            if ratio > H1_SLOPE_ATR_RATIO:
                h1_direction = "up"
            elif ratio < -H1_SLOPE_ATR_RATIO:
                h1_direction = "down"

    opens = [b.open for b in tail]
    return IndicatorSnapshot(
        ema_fast=ema_fast_series[-1],
        ema_slow=ema_slow_series[-1],
        adx=adx_series[-1],
        atr=atr_series[-1],
        bb_mid=bb[0],
        bb_upper=bb[1],
        bb_lower=bb[2],
        h1_direction=h1_direction,
        latest_open=opens[-1],
        latest_close=closes[-1],
        latest_high=highs[-1],
        latest_low=lows[-1],
    )


# ---------------------------------------------------------------------------
# 入口判定
# ---------------------------------------------------------------------------

def evaluate_entry(snap: IndicatorSnapshot) -> str | None:
    """6 条件 AND で buy / sell / None を返す。"""
    # 条件 2: ADX > 閾値 (レンジ排除)
    if snap.adx < ADX_THRESHOLD_ENTRY:
        return None
    # 条件 3: EMA(9) と EMA(21) が同方向
    ema_direction = "up" if snap.ema_fast > snap.ema_slow else "down"
    # 条件 1 & 5: H1 trend と短期 EMA 方向が一致
    if snap.h1_direction == "neutral" or snap.h1_direction != ema_direction:
        return None
    # 条件 4: EMA(21) 近接 (pullback)
    distance = abs(snap.latest_close - snap.ema_slow)
    if distance > snap.atr * PULLBACK_ATR_RATIO:
        return None

    # 条件 6 (確認バー): 現 bar の price action が trend 方向と一致
    # buy: 陽線 (close > open)、sell: 陰線 (close < open)
    # pullback のナイフ掴みを避ける
    if CONFIRMATION_CANDLE_ENABLED:
        is_bullish_bar = snap.latest_close > snap.latest_open
        is_bearish_bar = snap.latest_close < snap.latest_open
        if ema_direction == "up" and not is_bullish_bar:
            return None
        if ema_direction == "down" and not is_bearish_bar:
            return None

    return "buy" if ema_direction == "up" else "sell"


# ---------------------------------------------------------------------------
# 早期撤退判定
# ---------------------------------------------------------------------------

def evaluate_early_exit(
    snap: IndicatorSnapshot,
    position_type: str,   # "buy" / "sell"
    unrealized_pips: float,
    holding_bars: int,
) -> str | None:
    """4 条件のうちどれか 1 つで CLOSE。返り値は exit_subtype。"""
    # 条件 A: 3 bar 以内に含み益 +5 pips 未達 → CLOSE
    if (
        holding_bars >= EARLY_EXIT_BARS
        and unrealized_pips < EARLY_EXIT_MIN_PROFIT_PIPS
    ):
        return "early_exit_no_progress"

    # 条件 B: EMA(9) と EMA(21) が逆方向クロス
    is_buy = position_type == "buy"
    if is_buy and snap.ema_fast < snap.ema_slow:
        return "early_exit_ema_reverse"
    if not is_buy and snap.ema_fast > snap.ema_slow:
        return "early_exit_ema_reverse"

    # 条件 C: ADX が 15 未満に低下 (trend 消失)
    if snap.adx < ADX_THRESHOLD_EXIT:
        return "early_exit_adx_drop"

    # 条件 D: H1 trend が反対方向に転換
    if is_buy and snap.h1_direction == "down":
        return "early_exit_h1_flip"
    if not is_buy and snap.h1_direction == "up":
        return "early_exit_h1_flip"

    return None


# ---------------------------------------------------------------------------
# TP 判定
# ---------------------------------------------------------------------------

def evaluate_take_profit(
    snap: IndicatorSnapshot,
    position_type: str,
    unrealized_pips: float,
    holding_bars: int,
    max_favorable_pips: float,
    bars_since_max_favorable: int,
) -> str | None:
    """5 条件 OR で TP 判定。返り値は exit_subtype。"""
    is_buy = position_type == "buy"

    # 条件 I: 反対側 2σ タッチ (伸び切り確定)
    if is_buy and snap.latest_high >= snap.bb_upper:
        return "tp_upper_2sigma"
    if not is_buy and snap.latest_low <= snap.bb_lower:
        return "tp_lower_2sigma"

    # 条件 V (B3 の学び): Peak-trail TP
    # MFE が閾値に到達したら peak 追跡、peak から GIVEBACK 戻りで CLOSE
    # 取り逃し削減用 (B3 で効果実証済み、B2 v3 に移植)
    if max_favorable_pips >= PEAK_TRAIL_TRIGGER_PIPS:
        giveback_threshold = max_favorable_pips * (1.0 - PEAK_TRAIL_GIVEBACK_RATIO)
        if unrealized_pips <= giveback_threshold:
            return "tp_peak_trail"

    # 条件 III: 含み益 +30 pips 到達 → その後 5 bar 新高値/新安値更新なしで TP
    if (
        max_favorable_pips >= TP_PROFIT_THRESHOLD_PIPS
        and bars_since_max_favorable >= TP_STALL_BARS
    ):
        return "tp_stall_after_profit"

    # 条件 IV: 保有 6 時間超 かつ 含み益 >= 0 で TP
    if holding_bars >= TIME_EXIT_BARS and unrealized_pips >= 0:
        return "tp_time_exit"

    return None


# ---------------------------------------------------------------------------
# Pips 計算ヘルパー
# ---------------------------------------------------------------------------

def compute_unrealized_pips(
    position_type: str, entry_price: float, latest_price: float
) -> float:
    sign = 1.0 if position_type == "buy" else -1.0
    return (latest_price - entry_price) * PIP_MULTIPLIER * sign
