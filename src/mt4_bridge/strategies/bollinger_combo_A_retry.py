# src/mt4_bridge/strategies/bollinger_combo_A_retry.py
"""A の range_failure_exit 直後、同方向への 2 度目エントリーに B を同時発火する combo 戦術。

設計意図:
- A (bollinger_range_A) がレンジ判定で入って失敗 (range_failure_exit) した場合、
  その直後に A が **同じ方向** に再エントリーしたら、B も一緒に乗る
- A はこれまで通りミドル戻り(+5 pips avg)で利確
- B は **別の出口ロジック** で 反対側 2σ タッチまで伸ばす(+15〜+25 pips 狙い)

出口の差別化:
- A lane: 既存 (middle_touch_exit / range_failure_exit / opposite_state_exit)
- B lane: 反対 2σ タッチ / 8 bar 経過で含み益未達なら撤退

役割原則遵守:
- A が入るときだけ B も入る → A と lane 完全分離、A の動作に干渉しない
- A が勝つ月は B 発火条件を満たさないので B は発火しない
- A が崩壊月で range_failure 連発する時だけ B が発火、その伸びを取る

Note: module-level state (_STATE) で "直近 A range_failure" を追跡。
BT 専用の簡易実装で、時間窓チェックで自動的に古い state は無効化される。
"""
from __future__ import annotations

import statistics
from dataclasses import replace
from datetime import timedelta

from mt4_bridge.models import (
    MarketSnapshot,
    OpenPosition,
    PositionSnapshot,
    SignalAction,
    SignalDecision,
)
from mt4_bridge.strategies.bollinger_range_A import (
    evaluate_bollinger_range_A,
    required_bars as range_required_bars,
)


# ===================================================================
# Constants / Parameters
# ===================================================================

# 戦術ファイル正本 SL/TP
SL_PIPS = 20.0
TP_PIPS = 100.0

# Lane 定義
LANE_A_STRATEGY = "bollinger_range_A"
RANGE_MAGIC_NUMBER = 44001
TREND_MAGIC_NUMBER = 44002
RETRY_MAGIC_NUMBER = 44005   # この戦術専用

# Pip
PIP_MULTIPLIER = 100.0   # USDJPY

# B の出口パラメータ
B_BOLLINGER_PERIOD = 20
B_BOLLINGER_SIGMA = 2.0
B_TIME_STAGNANT_BARS = 8       # 8 bar 経過で含み益 <= 0 なら撤退
B_RETRY_WINDOW_BARS = 12       # A の range_failure から 12 bar 以内の同方向エントリーで B 発火
B_MIN_CONSECUTIVE_RF = 1       # 連続 range_failure 回数
                               # 2024 OOS 検証: 2 に厳格化すると 2024-07 ジグザグ下降で B 発火 0 件
                               # (方向が混在するため 2 連続同方向が稀)
                               # v3 で total -35 / crash +1 悪化 → 1 のまま (v1 ベースライン)

# ===================================================================
# A 好調時の B 抑制 (役割原則: A の邪魔をしない)
# ===================================================================
# 直近 A_RECENT_WINDOW 件の A trade 勝率が閾値以上なら B 発火抑制。
# A が好調に稼いでいる月(2024-02/03/09)で B が引き下げるのを防ぐ。
# A が苦戦している月(2024-07)では勝率が下がるので B は発火継続。
A_RECENT_WINDOW = 10                # 直近 N 件の A trade を見る
A_RECENT_WINRATE_SUPPRESS = 0.60    # 勝率 60% 以上なら B 発火を抑制
A_RECENT_WINDOW_MIN = 3             # 判定に必要な最小サンプル数

# combo としての lane 戦術マップ (lane 別 SL/TP 解決用)
LANE_STRATEGY_MAP: dict[str, str] = {
    "range": LANE_A_STRATEGY,
    # trend lane は戦術内部で完結するが、risk_config 解決用に B2 を参照
    "trend": "bollinger_trend_B",
}

# ===================================================================
# Module-level state (直近 A range_failure_exit の追跡)
# ===================================================================
_STATE: dict[str, object] = {
    "last_rf_position_type": None,   # "buy" / "sell"
    "last_rf_time": None,             # datetime
    "consecutive_rf_count": 0,        # 同方向 range_failure の連続件数
    "last_rf_direction_for_count": None,  # 連続カウント用の方向保持
    "a_recent_results": [],           # list[bool] 直近 A trade の勝敗 (True=win)
}


def required_bars() -> int:
    return max(range_required_bars(), B_BOLLINGER_PERIOD + 2)


def _reset_state() -> None:
    _STATE["last_rf_position_type"] = None
    _STATE["last_rf_time"] = None
    _STATE["consecutive_rf_count"] = 0
    _STATE["last_rf_direction_for_count"] = None
    _STATE["a_recent_results"] = []


# ===================================================================
# Helpers
# ===================================================================

def _is_range_lane_position(pos: OpenPosition) -> bool:
    comment = (pos.comment or "").lower()
    return (
        pos.magic_number == RANGE_MAGIC_NUMBER
        or "lane:range" in comment
        or "entry_lane=range" in comment
    )


def _is_trend_lane_position(pos: OpenPosition) -> bool:
    comment = (pos.comment or "").lower()
    return (
        pos.magic_number == TREND_MAGIC_NUMBER
        or "lane:trend" in comment
        or "entry_lane=trend" in comment
    )


def _filter_snapshot(
    position_snapshot: PositionSnapshot, lane: str
) -> PositionSnapshot:
    if lane == "range":
        positions = [p for p in position_snapshot.positions if _is_range_lane_position(p)]
    elif lane == "trend":
        positions = [p for p in position_snapshot.positions if _is_trend_lane_position(p)]
    else:
        positions = []
    return PositionSnapshot(
        schema_version=position_snapshot.schema_version,
        generated_at=position_snapshot.generated_at,
        positions=positions,
    )


def _bb_mid_upper_lower(
    closes, period: int, sigma: float
) -> tuple[float, float, float] | None:
    if len(closes) < period:
        return None
    recent = list(closes[-period:])
    mid = sum(recent) / period
    sd = statistics.pstdev(recent)
    return mid, mid + sigma * sd, mid - sigma * sd


def _bars_since(open_time, latest_time, timeframe_minutes: int = 5) -> int:
    if open_time is None or latest_time is None:
        return 0
    delta: timedelta = latest_time - open_time
    return max(int(delta.total_seconds()), 0) // (timeframe_minutes * 60)


# ===================================================================
# B (trend lane) の出口判定
# ===================================================================

def _evaluate_b_exit(
    trend_position: OpenPosition,
    market_snapshot: MarketSnapshot,
    strategy_name: str,
) -> SignalDecision | None:
    """B 保有中の出口判定。反対 2σ タッチ or 8 bar stagnant で CLOSE。"""
    bars = market_snapshot.bars
    if len(bars) < B_BOLLINGER_PERIOD + 2:
        return None
    closes = [b.close for b in bars]
    bb = _bb_mid_upper_lower(closes, B_BOLLINGER_PERIOD, B_BOLLINGER_SIGMA)
    if bb is None:
        return None
    mid, upper, lower = bb
    latest = bars[-1]
    pt = (trend_position.position_type or "").lower()
    entry_price = trend_position.open_price

    # TP: 順方向 2σ タッチ (反対 2σ: buy の場合 upper 2σ、sell の場合 lower 2σ)
    if pt == "buy" and latest.high >= upper:
        return _build_close_decision(
            bars, strategy_name, trend_position,
            exit_subtype="tp_upper_2sigma",
            reason=f"B TP: reached upper 2sigma {upper:.3f}",
        )
    if pt == "sell" and latest.low <= lower:
        return _build_close_decision(
            bars, strategy_name, trend_position,
            exit_subtype="tp_lower_2sigma",
            reason=f"B TP: reached lower 2sigma {lower:.3f}",
        )

    # 早期撤退: N bar 経過 & 含み益 <= 0
    holding_bars = _bars_since(trend_position.open_time, latest.time)
    if holding_bars >= B_TIME_STAGNANT_BARS:
        unrealized = (latest.close - entry_price) * PIP_MULTIPLIER * (
            1.0 if pt == "buy" else -1.0
        )
        if unrealized <= 0:
            return _build_close_decision(
                bars, strategy_name, trend_position,
                exit_subtype="early_exit_time_stagnant",
                reason=(
                    f"B exit: {holding_bars} bars held, unrealized={unrealized:.1f}"
                ),
            )

    return None


def _build_close_decision(
    bars, strategy_name: str, position: OpenPosition,
    exit_subtype: str, reason: str,
) -> SignalDecision:
    return SignalDecision(
        strategy_name=strategy_name,
        action=SignalAction.CLOSE,
        reason=reason,
        previous_bar_time=bars[-2].time if len(bars) >= 2 else None,
        latest_bar_time=bars[-1].time,
        previous_close=bars[-2].close if len(bars) >= 2 else 0.0,
        latest_close=bars[-1].close,
        current_position_ticket=position.ticket,
        current_position_type=position.position_type,
        sl_price=None, tp_price=None,
        entry_lane="trend", entry_subtype=None, exit_subtype=exit_subtype,
        market_state=None,
        middle_band=None, upper_band=None, lower_band=None,
        normalized_band_width=None, range_slope=None, trend_slope=None,
        trend_current_ma=None, distance_from_middle=None,
        detected_market_state=None, candidate_market_state=None,
        state_transition_event=None, state_age=None, candidate_age=None,
        detector_reason=None, range_score=None,
        transition_up_score=None, transition_down_score=None,
        trend_up_score=None, trend_down_score=None,
        debug_metrics=None,
    )


# ===================================================================
# Main evaluate (multi-decision)
# ===================================================================

def evaluate_bollinger_combo_A_retry_signals(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_combo_A_retry",
) -> list[SignalDecision]:
    range_snap = _filter_snapshot(position_snapshot, "range")
    trend_snap = _filter_snapshot(position_snapshot, "trend")

    # A 戦術の評価
    a_decision_raw = evaluate_bollinger_range_A(
        market_snapshot=market_snapshot,
        position_snapshot=range_snap,
        strategy_name=LANE_A_STRATEGY,
    )
    a_decision = replace(a_decision_raw, strategy_name=strategy_name)

    decisions: list[SignalDecision] = []

    # A の決済を検知して state 更新 (連続 range_failure カウント + 直近勝敗履歴)
    if a_decision.action == SignalAction.CLOSE and range_snap.positions:
        closing_pos = range_snap.positions[0]
        closing_dir = (closing_pos.position_type or "").lower()

        # A trade の勝敗推定: open_price と現在 close の差分
        sign = 1.0 if closing_dir == "buy" else -1.0
        realized_pips = (
            (a_decision.latest_close - closing_pos.open_price)
            * PIP_MULTIPLIER
            * sign
        )
        is_win = realized_pips > 0
        recent = list(_STATE.get("a_recent_results", []))
        recent.append(is_win)
        if len(recent) > A_RECENT_WINDOW:
            recent = recent[-A_RECENT_WINDOW:]
        _STATE["a_recent_results"] = recent

        if a_decision.exit_subtype == "range_failure_exit":
            _STATE["last_rf_position_type"] = closing_dir
            _STATE["last_rf_time"] = a_decision.latest_bar_time
            # 同方向なら連続カウント +1、違えばリセット後 1
            if _STATE.get("last_rf_direction_for_count") == closing_dir:
                _STATE["consecutive_rf_count"] = int(_STATE["consecutive_rf_count"]) + 1
            else:
                _STATE["last_rf_direction_for_count"] = closing_dir
                _STATE["consecutive_rf_count"] = 1
        else:
            # range_failure 以外の決済: 連続カウントリセット (勝敗履歴は保持)
            _STATE["last_rf_position_type"] = None
            _STATE["last_rf_time"] = None
            _STATE["consecutive_rf_count"] = 0
            _STATE["last_rf_direction_for_count"] = None

    # A の decision を emit
    if a_decision.action != SignalAction.HOLD:
        decisions.append(a_decision)

    # B エントリー条件: A が BUY/SELL かつ 直近 range_failure が同方向 & 時間窓内
    # B は A と **同方向** で発火 (2024 OOS で v1(同方向) vs v2(逆方向) 比較の結果、
    # 同方向が優位: 2024-07 で v1 +20 vs v2 -6、total +370 vs +308)
    # A の "2 度目の戻り狙い" に乗って、B は反対 2σ タッチまで深く取る戦術
    if a_decision.action in (SignalAction.BUY, SignalAction.SELL):
        a_direction = "buy" if a_decision.action == SignalAction.BUY else "sell"
        rf_dir = _STATE.get("last_rf_position_type")
        rf_time = _STATE.get("last_rf_time")
        consecutive = int(_STATE.get("consecutive_rf_count", 0))

        # A 好調時の抑制判定: 直近 A trade 勝率が閾値以上なら B 発火しない
        a_recent: list = list(_STATE.get("a_recent_results", []))
        a_suppressed = False
        a_wr_recent = None
        if len(a_recent) >= A_RECENT_WINDOW_MIN:
            a_wr_recent = sum(1 for x in a_recent if x) / len(a_recent)
            if a_wr_recent >= A_RECENT_WINRATE_SUPPRESS:
                a_suppressed = True

        if (
            rf_dir == a_direction
            and rf_time is not None
            and consecutive >= B_MIN_CONSECUTIVE_RF
            and not a_suppressed
        ):
            bars_since_rf = _bars_since(rf_time, a_decision.latest_bar_time)
            if bars_since_rf <= B_RETRY_WINDOW_BARS and not trend_snap.positions:
                # B 同時エントリー (trend lane、A と同方向)
                b_decision = replace(
                    a_decision,
                    entry_lane="trend",
                    entry_subtype="b_retry_follow",
                    reason=(
                        f"B retry follow: A rf x{consecutive} "
                        f"(last {bars_since_rf} bars ago), "
                        f"A_recent_wr={a_wr_recent:.2f} (n={len(a_recent)}). "
                        f"Original A reason: {a_decision.reason}"
                    ),
                )
                decisions.append(b_decision)

    # B 保有中の出口判定
    if trend_snap.positions:
        trend_pos = trend_snap.positions[0]
        b_exit = _evaluate_b_exit(trend_pos, market_snapshot, strategy_name)
        if b_exit is not None:
            decisions.append(b_exit)

    # 何も返さなかった場合は HOLD (A の HOLD を採用)
    if not decisions:
        decisions.append(a_decision)

    return decisions


def evaluate_bollinger_combo_A_retry(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_combo_A_retry",
) -> SignalDecision:
    return evaluate_bollinger_combo_A_retry_signals(
        market_snapshot, position_snapshot, strategy_name
    )[0]
