# src/mt4_bridge/strategies/bollinger_trend_B3_rules.py
"""bollinger_trend_B3 のルール判定。"""
from __future__ import annotations

from dataclasses import dataclass

from mt4_bridge.strategies.bollinger_trend_B3_indicators import (
    bandwidth_current_and_prev,
    bollinger_pair,
)
from mt4_bridge.strategies.bollinger_trend_B3_params import (
    BANDWIDTH_EXPANSION_RATIO,
    BOLLINGER_EXTREME_SIGMA,
    BOLLINGER_PERIOD,
    BOLLINGER_SIGMA,
    MAE_EARLY_CUT_PIPS,
    MIDDLE_REVERT_MIN_BARS,
    PEAK_TRAIL_GIVEBACK_RATIO,
    PEAK_TRAIL_TRIGGER_PIPS,
    PIP_MULTIPLIER,
    TIME_EXIT_STAGNANT_BARS,
    TIME_EXIT_STAGNANT_MIN_PIPS,
)


@dataclass(frozen=True)
class IndicatorSnapshot:
    bb_mid: float
    bb_upper: float
    bb_lower: float
    bb_upper_3sigma: float
    bb_lower_3sigma: float
    bandwidth: float
    bandwidth_prev: float
    prev_close: float
    latest_close: float
    latest_high: float
    latest_low: float


def build_snapshot(bars) -> IndicatorSnapshot | None:
    """bars (時系列昇順) から最新 bar での指標 snapshot を作る。"""
    if len(bars) < BOLLINGER_PERIOD + 2:
        return None
    closes = [b.close for b in bars]
    # 計算範囲制限 (末尾必要本数だけ)
    tail_len = BOLLINGER_PERIOD + 3
    closes_tail = closes[-tail_len:]

    bb_2, bb_3 = bollinger_pair(
        closes_tail, BOLLINGER_PERIOD, BOLLINGER_SIGMA, BOLLINGER_EXTREME_SIGMA
    )
    if bb_2 is None or bb_3 is None:
        return None
    bw_now, bw_prev = bandwidth_current_and_prev(
        closes_tail, BOLLINGER_PERIOD, BOLLINGER_SIGMA
    )
    if bw_now is None or bw_prev is None:
        return None

    latest = bars[-1]
    prev = bars[-2]
    return IndicatorSnapshot(
        bb_mid=bb_2[0],
        bb_upper=bb_2[1],
        bb_lower=bb_2[2],
        bb_upper_3sigma=bb_3[1],
        bb_lower_3sigma=bb_3[2],
        bandwidth=bw_now,
        bandwidth_prev=bw_prev,
        prev_close=prev.close,
        latest_close=latest.close,
        latest_high=latest.high,
        latest_low=latest.low,
    )


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

def evaluate_entry(snap: IndicatorSnapshot) -> str | None:
    """入口: BB 幅拡大 + ミドルライン交差 で buy / sell を返す。"""
    # 条件 1: BB 幅が直前 bar より拡大
    if snap.bandwidth_prev <= 0:
        return None
    expansion_ratio = snap.bandwidth / snap.bandwidth_prev
    if expansion_ratio < BANDWIDTH_EXPANSION_RATIO:
        return None

    # 条件 2: ミドルライン交差
    # BUY: 前 close < mid かつ 現 close > mid
    # SELL: 前 close > mid かつ 現 close < mid
    if snap.prev_close < snap.bb_mid and snap.latest_close > snap.bb_mid:
        return "buy"
    if snap.prev_close > snap.bb_mid and snap.latest_close < snap.bb_mid:
        return "sell"
    return None


# ---------------------------------------------------------------------------
# Early exit (反対 2σ 接触 / MAE 早切り)
# ---------------------------------------------------------------------------

def evaluate_early_exit(
    snap: IndicatorSnapshot,
    position_type: str,
    mae_pips: float,
    holding_bars: int,
    unrealized_pips: float,
) -> str | None:
    """反対側 2σ / MAE 早切り / 時間ベース逃げ で CLOSE。

    mae_pips: 含み損側の最大値 (正の数で深さ表現)
    holding_bars: エントリーからの経過バー数
    unrealized_pips: 現在の含み益 (正=利益, 負=損失)
    """
    # 条件 A: 反対 2σ 接触 (明確な逆行確定)
    if position_type == "buy":
        if snap.latest_low <= snap.bb_lower:
            return "early_exit_opposite_2sigma"
    else:
        if snap.latest_high >= snap.bb_upper:
            return "early_exit_opposite_2sigma"

    # 条件 B: MAE 早切り
    if mae_pips >= MAE_EARLY_CUT_PIPS:
        return "early_exit_mae_cut"

    # 条件 C: 時間ベース逃げ (含み益未達の長期保有)
    # N bar 経過しても含み益が TIME_EXIT_STAGNANT_MIN_PIPS を超えていなければ CLOSE
    if (
        holding_bars >= TIME_EXIT_STAGNANT_BARS
        and unrealized_pips <= TIME_EXIT_STAGNANT_MIN_PIPS
    ):
        return "early_exit_time_stagnant"

    return None


# ---------------------------------------------------------------------------
# TP
# ---------------------------------------------------------------------------

def evaluate_take_profit(
    snap: IndicatorSnapshot,
    position_type: str,
    holding_bars: int,
    unrealized_pips: float,
    mfe_pips: float,
) -> str | None:
    """TP 判断: 順方向 3σ タッチ / peak trail / 含み益ミドル戻り。

    - 3σ: 伸び切り上限
    - peak trail: MFE が閾値に到達したら、pick から一定割合戻ったら CLOSE
      (勝ちトレードの取り逃し削減)
    - ミドル戻り: 含み益プラス時のみ (trend 不発の利確)
    """
    # 条件 I: 順方向 3σ タッチ (利伸ばし上限)
    if position_type == "buy":
        if snap.latest_high >= snap.bb_upper_3sigma:
            return "tp_upper_3sigma"
    else:
        if snap.latest_low <= snap.bb_lower_3sigma:
            return "tp_lower_3sigma"

    # 条件 II: Peak-trail TP
    # MFE が PEAK_TRAIL_TRIGGER_PIPS に到達していたら、peak から giveback 戻りで CLOSE
    if mfe_pips >= PEAK_TRAIL_TRIGGER_PIPS:
        giveback_threshold = mfe_pips * (1.0 - PEAK_TRAIL_GIVEBACK_RATIO)
        if unrealized_pips <= giveback_threshold:
            return "tp_peak_trail"

    # 条件 III: 数本先でミドル戻り (含み益プラス時のみ)
    if holding_bars >= MIDDLE_REVERT_MIN_BARS and unrealized_pips > 0:
        if position_type == "buy" and snap.latest_close < snap.bb_mid:
            return "tp_middle_revert"
        if position_type == "sell" and snap.latest_close > snap.bb_mid:
            return "tp_middle_revert"

    return None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def compute_unrealized_pips(
    position_type: str, entry_price: float, latest_price: float
) -> float:
    sign = 1.0 if position_type == "buy" else -1.0
    return (latest_price - entry_price) * PIP_MULTIPLIER * sign
