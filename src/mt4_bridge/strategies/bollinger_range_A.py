# src/mt4_bridge/strategies/bollinger_range_A.py
from __future__ import annotations

from mt4_bridge.models import (
    MarketSnapshot,
    PositionSnapshot,
    SignalAction,
    SignalDecision,
)
from mt4_bridge.strategies.bollinger_range_v4_4 import (
    evaluate_bollinger_range_v4_4,
    required_bars as required_bars_v4_4,
)

# ===================================================================
# A戦術ゲーティング パラメータ (対策①〜④, 2026-04-21)
# ===================================================================
# 各フィルタは _ENABLED フラグで個別に有効/無効を切り替え可能。
# 既定値は 1年分 BT で最良バランスを確認した設定。
# 本番稼働前に再度 BT して閾値を確定させること。

# --- 対策①: trend 状態でのエントリーを見送る (B戦術の領域に踏み込まない) ---
A_SKIP_TREND_STATE_ENABLED = True
_TREND_STATES_FOR_A_SKIP = {"trend_up", "trend_down"}

# --- 対策②: レンジ崩壊兆候フィルタ (observation flag ベース) ---
A_UNSUITABLE_FLAG_FILTER_ENABLED = True
A_REJECT_ON_SLOPE_ACCELERATION = False  # 検証で slope_ac のみは過剰フィルタ
A_REJECT_ON_BANDWIDTH_EXPANSION = True

# --- 対策③: 時刻フィルタ (broker server hour) ---
# ※ 現データは broker サーバー時刻 (GMT+2/+3 系, EET 想定)。
#    ライブ稼働前に実ブローカーの実サーバー時刻との対応を確認すること。
A_TIME_FILTER_ENABLED = True
A_ENTRY_BANNED_HOURS = {5, 7, 13}  # 負け平均 < -1.0 pips の 3 時刻

# --- 対策④: H1 コンテキストフィルタ (逆張り禁止) ---
# 直近 60 本 (5 分足 × 60 = 5 時間 ≈ H1 ×5本) の close 変化で
# H1 トレンドを近似し、逆方向の BB 逆張りエントリーを見送る。
A_H1_TREND_FILTER_ENABLED = True
A_H1_LOOKBACK_BARS = 60
A_H1_TREND_THRESHOLD_PIPS = 15.0  # 2026-04-21 BT 比較で最良 (崩壊月数×総pips のバランス)
A_PIP_MULTIPLIER = 100.0          # USDJPY 用 (他通貨対応時は要修正)

# --- 対策⑤: D24 コンテキストフィルタ (日足逆張り禁止) ---
# 対策④(H1)では catch できない週足レベルのトレンドを遮断する。
# 直近 288 本 (5 分足 × 288 = 24 時間 ≈ 日足 1 本) の close 変化で
# 日足トレンドを近似し、逆方向の BB 逆張りエントリーを見送る。
# 2026-04-22 検証: dukascopy 2024 では +121.7 改善だが broker 2025-26 で
# -337.3 悪化 (機会損失)。24ヶ月合計 -215.6 pips で過学習と判断し OFF。
A_D24_TREND_FILTER_ENABLED = False
A_D24_LOOKBACK_BARS = 288
A_D24_TREND_THRESHOLD_PIPS = 40.0

# --- 対策⑥: 過剰展開下落時の SELL 抑制 (底拾い禁止) ---
# 2026-04-22 検証: 対策⑤と同じ理由で OFF。
A_D24_BOTTOM_SELL_BLOCK_ENABLED = False
A_D24_BOTTOM_SELL_MOM_THRESHOLD_PIPS = -80.0

# ===================================================================
# リスク設定 (戦術固有の SL/TP)
# ===================================================================
# A戦術はレンジ反転ベースだが、TP を SL より広く取って R:R=1.25 とする。
# これは BT / ライブ双方で戦術固有値として使われ、
# config/app.yaml の risk.sl_pips/tp_pips はフォールバック扱い。
#
# 2026-04-22 SL/TP 25パターン sweep (DUK 2024 + BRK 2025-26 の 24ヶ月):
#   SL=20/TP=25 (rr=1.25) が総pips +1273, 最悪月 -49.4, 崩壊月 7 で全候補中最良。
#   現行 20/20 との比較: 総pips +91 改善、最悪月はほぼ同等 (-48.7→-49.4)。
#   - SL=20 が sweet spot (10は浅すぎ worst -100〜, 30は深すぎ pips 減)
#   - TP=25 が山頂 (20→25 で +91, 25→30 で -47 と逆戻り)
SL_PIPS = 20.0
TP_PIPS = 25.0


def required_bars() -> int:
    return required_bars_v4_4()


def evaluate_bollinger_range_A(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_range_A",
) -> SignalDecision:
    decision = evaluate_bollinger_range_v4_4(
        market_snapshot=market_snapshot,
        position_snapshot=position_snapshot,
        strategy_name=strategy_name,
    )

    action = decision.action
    reason = decision.reason

    # A戦術 gating #1 (対策①): trend 状態でのエントリー(BUY/SELL)はHOLDに矯正
    if (
        A_SKIP_TREND_STATE_ENABLED
        and action in (SignalAction.BUY, SignalAction.SELL)
        and decision.market_state in _TREND_STATES_FOR_A_SKIP
    ):
        action = SignalAction.HOLD
        reason = (
            f"A strategy entry suppressed because market_state={decision.market_state}"
            f" is owned by B strategy (trend-follow); original decision: {decision.reason}"
        )

    # A戦術 gating #2 (対策②): range 状態でもレンジ崩壊兆候が出ていたら見送り
    if (
        A_UNSUITABLE_FLAG_FILTER_ENABLED
        and action in (SignalAction.BUY, SignalAction.SELL)
        and decision.market_state == "range"
        and isinstance(decision.debug_metrics, dict)
    ):
        obs = decision.debug_metrics
        slope_accel = bool(obs.get("range_unsuitable_flag_slope_acceleration"))
        bw_expansion = bool(obs.get("range_unsuitable_flag_bandwidth_expansion"))
        blocked_reasons: list[str] = []
        if A_REJECT_ON_SLOPE_ACCELERATION and slope_accel:
            blocked_reasons.append("slope_acceleration=True")
        if A_REJECT_ON_BANDWIDTH_EXPANSION and bw_expansion:
            blocked_reasons.append("bandwidth_expansion=True")
        if blocked_reasons:
            action = SignalAction.HOLD
            reason = (
                "A strategy entry suppressed because range is at risk of breaking:"
                f" {', '.join(blocked_reasons)}; original decision: {decision.reason}"
            )

    # A戦術 gating #3 (対策③): 時刻フィルタ
    # broker server hour で弱い時刻帯はエントリー見送り
    if (
        A_TIME_FILTER_ENABLED
        and action in (SignalAction.BUY, SignalAction.SELL)
    ):
        latest_bar_time = decision.latest_bar_time
        if latest_bar_time is not None and latest_bar_time.hour in A_ENTRY_BANNED_HOURS:
            action = SignalAction.HOLD
            reason = (
                f"A strategy entry suppressed by time filter: broker hour "
                f"{latest_bar_time.hour} is historically weak; "
                f"original decision: {decision.reason}"
            )

    # A戦術 gating #4 (対策④): H1 コンテキストフィルタ(逆張り禁止)
    # 直近 60 本 (=5時間 ≈ H1×5本) の close 変化が閾値を超えて
    # 逆方向に流れている場合、その方向への BB 逆張りエントリーは見送る
    if (
        A_H1_TREND_FILTER_ENABLED
        and action in (SignalAction.BUY, SignalAction.SELL)
    ):
        bars = market_snapshot.bars
        if len(bars) >= A_H1_LOOKBACK_BARS + 1:
            h1_mom_pips = (
                bars[-1].close - bars[-(A_H1_LOOKBACK_BARS + 1)].close
            ) * A_PIP_MULTIPLIER
            if (
                action == SignalAction.BUY
                and h1_mom_pips < -A_H1_TREND_THRESHOLD_PIPS
            ):
                action = SignalAction.HOLD
                reason = (
                    f"A strategy BUY suppressed because H1 is in downtrend:"
                    f" last-{A_H1_LOOKBACK_BARS}-bar mom={h1_mom_pips:.2f} pips"
                    f" (threshold=-{A_H1_TREND_THRESHOLD_PIPS});"
                    f" original decision: {decision.reason}"
                )
            elif (
                action == SignalAction.SELL
                and h1_mom_pips > A_H1_TREND_THRESHOLD_PIPS
            ):
                action = SignalAction.HOLD
                reason = (
                    f"A strategy SELL suppressed because H1 is in uptrend:"
                    f" last-{A_H1_LOOKBACK_BARS}-bar mom=+{h1_mom_pips:.2f} pips"
                    f" (threshold=+{A_H1_TREND_THRESHOLD_PIPS});"
                    f" original decision: {decision.reason}"
                )

    # A戦術 gating #5 (対策⑤): D24 コンテキストフィルタ(日足逆張り禁止)
    # 直近 288 本 (=24時間 ≈ 日足1本) の close 変化が閾値を超えて
    # 逆方向に流れている場合、その方向への BB 逆張りエントリーは見送る
    if (
        A_D24_TREND_FILTER_ENABLED
        and action in (SignalAction.BUY, SignalAction.SELL)
    ):
        bars = market_snapshot.bars
        if len(bars) >= A_D24_LOOKBACK_BARS + 1:
            d24_mom_pips = (
                bars[-1].close - bars[-(A_D24_LOOKBACK_BARS + 1)].close
            ) * A_PIP_MULTIPLIER
            if (
                action == SignalAction.BUY
                and d24_mom_pips < -A_D24_TREND_THRESHOLD_PIPS
            ):
                action = SignalAction.HOLD
                reason = (
                    f"A strategy BUY suppressed because D24 is in downtrend:"
                    f" last-{A_D24_LOOKBACK_BARS}-bar mom={d24_mom_pips:.2f} pips"
                    f" (threshold=-{A_D24_TREND_THRESHOLD_PIPS});"
                    f" original decision: {decision.reason}"
                )
            elif (
                action == SignalAction.SELL
                and d24_mom_pips > A_D24_TREND_THRESHOLD_PIPS
            ):
                action = SignalAction.HOLD
                reason = (
                    f"A strategy SELL suppressed because D24 is in uptrend:"
                    f" last-{A_D24_LOOKBACK_BARS}-bar mom=+{d24_mom_pips:.2f} pips"
                    f" (threshold=+{A_D24_TREND_THRESHOLD_PIPS});"
                    f" original decision: {decision.reason}"
                )

    # A戦術 gating #6 (対策⑥): 過剰展開下落時の SELL 抑制(底拾い禁止)
    # 24h で既に大きく下落している状況での SELL は勝率劣化するため遮断。
    # BUY 側は実測で有害(押し目買いは有効)のため非対称のまま SELL のみ。
    if (
        A_D24_BOTTOM_SELL_BLOCK_ENABLED
        and action == SignalAction.SELL
    ):
        bars = market_snapshot.bars
        if len(bars) >= A_D24_LOOKBACK_BARS + 1:
            d24_mom_pips = (
                bars[-1].close - bars[-(A_D24_LOOKBACK_BARS + 1)].close
            ) * A_PIP_MULTIPLIER
            if d24_mom_pips < A_D24_BOTTOM_SELL_MOM_THRESHOLD_PIPS:
                action = SignalAction.HOLD
                reason = (
                    f"A strategy SELL suppressed because D24 is over-extended down:"
                    f" last-{A_D24_LOOKBACK_BARS}-bar mom={d24_mom_pips:.2f} pips"
                    f" (block-threshold={A_D24_BOTTOM_SELL_MOM_THRESHOLD_PIPS});"
                    f" original decision: {decision.reason}"
                )

    return SignalDecision(
        strategy_name=strategy_name,
        action=action,
        reason=reason,
        previous_bar_time=decision.previous_bar_time,
        latest_bar_time=decision.latest_bar_time,
        previous_close=decision.previous_close,
        latest_close=decision.latest_close,
        current_position_ticket=decision.current_position_ticket,
        current_position_type=decision.current_position_type,
        sl_price=decision.sl_price,
        tp_price=decision.tp_price,
        entry_lane="range",
        entry_subtype="v4_4",
        exit_subtype=decision.exit_subtype,
        market_state=decision.market_state,
        middle_band=decision.middle_band,
        upper_band=decision.upper_band,
        lower_band=decision.lower_band,
        normalized_band_width=decision.normalized_band_width,
        range_slope=decision.range_slope,
        trend_slope=decision.trend_slope,
        trend_current_ma=decision.trend_current_ma,
        distance_from_middle=decision.distance_from_middle,
        detected_market_state=decision.detected_market_state,
        candidate_market_state=decision.candidate_market_state,
        state_transition_event=decision.state_transition_event,
        state_age=decision.state_age,
        candidate_age=decision.candidate_age,
        detector_reason=decision.detector_reason,
        range_score=decision.range_score,
        transition_up_score=decision.transition_up_score,
        transition_down_score=decision.transition_down_score,
        trend_up_score=decision.trend_up_score,
        trend_down_score=decision.trend_down_score,
        debug_metrics=decision.debug_metrics,
    )
