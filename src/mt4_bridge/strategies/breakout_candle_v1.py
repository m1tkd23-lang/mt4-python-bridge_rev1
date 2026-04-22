# src/mt4_bridge/strategies/breakout_candle_v1.py
"""超シンプルなブレイクアウト戦術 v1。

入口:
  - BUY: 現 bar の close が前 bar の high を上抜け
  - SELL: 現 bar の close が前 bar の low を下抜け

早期撤退 (逃げ):
  - BUY: 最新 bar と前 bar の両方で close が下がった (2 bar 連続) ら CLOSE
  - SELL: 最新 bar と前 bar の両方で close が上がった (2 bar 連続) ら CLOSE
  (1 bar のノイズ戻しを許容、連続下げ/上げを確認してから撤退)

TP 判定:
  - 戦術側には無し、simulator 保険 TP_PIPS に任せる(基本は逃げで CLOSE)

1 position / 1 決済。partial close なし。
"""
from __future__ import annotations

from mt4_bridge.models import (
    MarketSnapshot,
    OpenPosition,
    PositionSnapshot,
    SignalAction,
    SignalDecision,
)


# ===================================================================
# Risk constants (戦術ファイル正本)
# ===================================================================
SL_PIPS = 20.0
TP_PIPS = 100.0
BREAKOUT_MAGIC_NUMBER = 44010


def required_bars() -> int:
    # 前 bar と 前々 bar を参照するので 3 本あれば安全
    return 3


def evaluate_breakout_candle_v1(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "breakout_candle_v1",
) -> SignalDecision:
    bars = market_snapshot.bars
    if len(bars) < required_bars():
        return _hold(bars, strategy_name, "insufficient bars")

    prev2 = bars[-3]
    prev = bars[-2]
    latest = bars[-1]

    own_pos = _find_own_position(position_snapshot.positions)

    # 保有中: 逃げ判定のみ (2 bar 連続で実体が逆方向に動いた場合のみ CLOSE)
    if own_pos is not None:
        position_type = (own_pos.position_type or "").lower()
        # BUY: 前 bar の close < 前々 bar の close かつ 最新 close < 前 close (2 連続下落)
        if (
            position_type == "buy"
            and latest.close < prev.close
            and prev.close < prev2.close
        ):
            return _close(
                bars, strategy_name, own_pos,
                exit_subtype="body_down_2bar",
                reason=(
                    f"2-bar body down: {prev2.close:.3f} -> "
                    f"{prev.close:.3f} -> {latest.close:.3f}"
                ),
            )
        # SELL: 連続上昇
        if (
            position_type == "sell"
            and latest.close > prev.close
            and prev.close > prev2.close
        ):
            return _close(
                bars, strategy_name, own_pos,
                exit_subtype="body_up_2bar",
                reason=(
                    f"2-bar body up: {prev2.close:.3f} -> "
                    f"{prev.close:.3f} -> {latest.close:.3f}"
                ),
            )
        return _hold(
            bars, strategy_name,
            reason=(
                f"holding: close {latest.close:.3f} (prev {prev.close:.3f}, "
                f"prev2 {prev2.close:.3f})"
            ),
            position=own_pos,
        )

    # ポジションなし: 入口判定
    if latest.close > prev.high:
        return _entry(
            bars, strategy_name,
            action=SignalAction.BUY,
            subtype="breakout_above_prev_high",
            reason=(
                f"close {latest.close:.3f} > prev_high {prev.high:.3f}"
            ),
        )
    if latest.close < prev.low:
        return _entry(
            bars, strategy_name,
            action=SignalAction.SELL,
            subtype="breakdown_below_prev_low",
            reason=(
                f"close {latest.close:.3f} < prev_low {prev.low:.3f}"
            ),
        )

    return _hold(
        bars, strategy_name,
        reason=(
            f"no breakout: close {latest.close:.3f} "
            f"in [{prev.low:.3f}, {prev.high:.3f}]"
        ),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_own_position(
    positions: list[OpenPosition],
) -> OpenPosition | None:
    """この戦術のポジションを探す。BT では magic/comment が無いので先頭採用。"""
    if not positions:
        return None
    for pos in positions:
        comment = (pos.comment or "").lower()
        if (
            pos.magic_number == BREAKOUT_MAGIC_NUMBER
            or "breakout_candle_v1" in comment
        ):
            return pos
    return positions[0]


def _hold(
    bars, strategy_name: str, reason: str, position: OpenPosition | None = None,
) -> SignalDecision:
    return SignalDecision(
        strategy_name=strategy_name,
        action=SignalAction.HOLD,
        reason=reason,
        previous_bar_time=bars[-2].time if len(bars) >= 2 else None,
        latest_bar_time=bars[-1].time if bars else None,
        previous_close=bars[-2].close if len(bars) >= 2 else 0.0,
        latest_close=bars[-1].close if bars else 0.0,
        current_position_ticket=position.ticket if position else None,
        current_position_type=position.position_type if position else None,
        sl_price=None, tp_price=None,
        entry_lane="trend", entry_subtype=None, exit_subtype=None,
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


def _entry(
    bars, strategy_name: str, action: SignalAction, subtype: str, reason: str,
) -> SignalDecision:
    return SignalDecision(
        strategy_name=strategy_name,
        action=action,
        reason=reason,
        previous_bar_time=bars[-2].time,
        latest_bar_time=bars[-1].time,
        previous_close=bars[-2].close,
        latest_close=bars[-1].close,
        current_position_ticket=None,
        current_position_type=None,
        sl_price=None, tp_price=None,
        entry_lane="trend", entry_subtype=subtype, exit_subtype=None,
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


def _close(
    bars, strategy_name: str, position: OpenPosition,
    exit_subtype: str, reason: str,
) -> SignalDecision:
    return SignalDecision(
        strategy_name=strategy_name,
        action=SignalAction.CLOSE,
        reason=reason,
        previous_bar_time=bars[-2].time,
        latest_bar_time=bars[-1].time,
        previous_close=bars[-2].close,
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
