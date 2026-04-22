# src/mt4_bridge/strategies/bollinger_trend_B2.py
"""bollinger_trend_B2: 新世代 B 戦術 (入口・早期撤退・TP を戦術ロジックで握る)。

設計意図:
- partial close なし、1 ポジション = 1 エントリー〜1 決済
- simulator 側 SL/TP は保険のみ、signal_close 主体で運用する
- 入口: H1 trend + ADX + EMA cross + EMA21 pullback + H1 方向一致 (5条件 AND)
- 早期撤退: no_progress / ema_reverse / adx_drop / h1_flip (4条件 OR)
- TP: 反対 2σ / stall_after_profit / time_exit (4条件 OR)

制限事項:
- max_favorable / bars_since_max_favorable は MarketSnapshot から直接取れないため、
  entry 以降の price を bar で再生する簡易方式で近似する。
"""
from __future__ import annotations

from datetime import timedelta

from mt4_bridge.models import (
    MarketSnapshot,
    OpenPosition,
    PositionSnapshot,
    SignalAction,
    SignalDecision,
)
from mt4_bridge.strategies.bollinger_trend_B2_indicators import (
    bollinger_bands,
)
from mt4_bridge.strategies.bollinger_trend_B2_params import (  # noqa: F401
    ADX_PERIOD,
    ADX_THRESHOLD_ENTRY,
    ADX_THRESHOLD_EXIT,
    ATR_PERIOD,
    BOLLINGER_PERIOD,
    BOLLINGER_SIGMA,
    EARLY_EXIT_BARS,
    EARLY_EXIT_MIN_PROFIT_PIPS,
    EMA_FAST_PERIOD,
    EMA_SLOW_PERIOD,
    H1_BARS,
    H1_EMA_PERIOD,
    H1_SLOPE_ATR_RATIO,
    H1_SLOPE_LOOKBACK,
    PIP_MULTIPLIER,
    PULLBACK_ATR_RATIO,
    SL_PIPS,
    TIME_EXIT_BARS,
    TP_PIPS,
    TP_PROFIT_THRESHOLD_PIPS,
    TP_STALL_BARS,
    TREND_B2_MAGIC_NUMBER,
    required_bars,
)
from mt4_bridge.strategies.bollinger_trend_B2_rules import (
    build_snapshot,
    compute_unrealized_pips,
    evaluate_early_exit,
    evaluate_entry,
    evaluate_take_profit,
)


def _find_own_position(
    positions: list[OpenPosition],
) -> OpenPosition | None:
    """B2 自分の lane のオープンポジションを探す。

    BT では magic_number/comment は使われないので、any position 1 件を採用。
    ライブでは magic_number == TREND_B2_MAGIC_NUMBER または comment に
    'lane:trend_b2' を含むものを優先。
    """
    if not positions:
        return None
    # lane:trend_b2 や magic 一致を優先
    for pos in positions:
        comment = (pos.comment or "").lower()
        if (
            pos.magic_number == TREND_B2_MAGIC_NUMBER
            or "lane:trend_b2" in comment
            or "trend_b2" in comment
        ):
            return pos
    # BT 等でマッチしなければ先頭
    return positions[0]


def _estimate_bars_since_entry(
    open_time, latest_bar_time, timeframe_minutes: int = 5
) -> int:
    """bar 数の近似。5 分足前提で (latest - entry) / 5分 を切り捨て。"""
    if open_time is None or latest_bar_time is None:
        return 0
    delta: timedelta = latest_bar_time - open_time
    secs = max(int(delta.total_seconds()), 0)
    return secs // (timeframe_minutes * 60)


def _estimate_max_favorable_and_stall(
    bars,
    entry_open_time,
    position_type: str,
    entry_price: float,
) -> tuple[float, int]:
    """entry 以降の bar を走査して max_favorable_pips と
    "最大到達から何 bar 経過したか" を返す。

    bars は時系列昇順。末尾から逆方向に走査し、entry_open_time 未満に
    達したら break。全履歴 O(N) 走査の O(N^2) 性能問題を回避。
    """
    if entry_open_time is None:
        return 0.0, 0

    # 末尾から entry 以降の subset を抽出 (時系列 昇順 のまま)
    subset: list = []
    for bar in reversed(bars):
        if bar.time < entry_open_time:
            break
        subset.append(bar)
    if not subset:
        return 0.0, 0
    subset.reverse()

    max_fav = 0.0
    max_fav_index = -1  # 0-based
    for i, bar in enumerate(subset):
        if position_type == "buy":
            fav_pips = (bar.high - entry_price) * PIP_MULTIPLIER
        else:
            fav_pips = (entry_price - bar.low) * PIP_MULTIPLIER
        if fav_pips > max_fav:
            max_fav = fav_pips
            max_fav_index = i
    if max_fav_index < 0:
        return 0.0, 0
    bars_since = (len(subset) - 1) - max_fav_index
    return max_fav, bars_since


def evaluate_bollinger_trend_B2(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_trend_B2",
) -> SignalDecision:
    bars = market_snapshot.bars
    if len(bars) < required_bars():
        return SignalDecision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=f"insufficient bars ({len(bars)} < {required_bars()})",
            previous_bar_time=bars[-2].time if len(bars) >= 2 else None,
            latest_bar_time=bars[-1].time if bars else None,
            previous_close=bars[-2].close if len(bars) >= 2 else 0.0,
            latest_close=bars[-1].close if bars else 0.0,
            current_position_ticket=None,
            current_position_type=None,
            sl_price=None,
            tp_price=None,
            entry_lane="trend",
            entry_subtype=None,
            exit_subtype=None,
            market_state=None,
            middle_band=None,
            upper_band=None,
            lower_band=None,
            normalized_band_width=None,
            range_slope=None,
            trend_slope=None,
            trend_current_ma=None,
            distance_from_middle=None,
            detected_market_state=None,
            candidate_market_state=None,
            state_transition_event=None,
            state_age=None,
            candidate_age=None,
            detector_reason=None,
            range_score=None,
            transition_up_score=None,
            transition_down_score=None,
            trend_up_score=None,
            trend_down_score=None,
            debug_metrics=None,
        )

    snap = build_snapshot(bars)
    if snap is None:
        return _hold(
            bars=bars,
            strategy_name=strategy_name,
            reason="indicator snapshot unavailable",
        )

    own_pos = _find_own_position(position_snapshot.positions)

    # ==========================
    # ポジション保有中: 出口判定のみ
    # ==========================
    if own_pos is not None:
        position_type = (own_pos.position_type or "").lower()
        entry_price = own_pos.open_price
        holding_bars = _estimate_bars_since_entry(
            own_pos.open_time, bars[-1].time
        )
        unrealized_pips = compute_unrealized_pips(
            position_type, entry_price, snap.latest_close
        )
        max_fav, stall = _estimate_max_favorable_and_stall(
            bars=bars,
            entry_open_time=own_pos.open_time,
            position_type=position_type,
            entry_price=entry_price,
        )

        # 早期撤退優先 (損失膨張防止)
        early_sub = evaluate_early_exit(
            snap=snap,
            position_type=position_type,
            unrealized_pips=unrealized_pips,
            holding_bars=holding_bars,
        )
        if early_sub is not None:
            return _close(
                bars=bars,
                strategy_name=strategy_name,
                snap=snap,
                exit_subtype=early_sub,
                reason=f"early exit: {early_sub}",
                position=own_pos,
            )

        # TP 判定
        tp_sub = evaluate_take_profit(
            snap=snap,
            position_type=position_type,
            unrealized_pips=unrealized_pips,
            holding_bars=holding_bars,
            max_favorable_pips=max_fav,
            bars_since_max_favorable=stall,
        )
        if tp_sub is not None:
            return _close(
                bars=bars,
                strategy_name=strategy_name,
                snap=snap,
                exit_subtype=tp_sub,
                reason=f"take profit: {tp_sub}",
                position=own_pos,
            )

        # どれにも該当しなければ HOLD
        return _hold(
            bars=bars,
            strategy_name=strategy_name,
            reason=(
                "holding: no exit condition met "
                f"(held_bars={holding_bars}, unrealized={unrealized_pips:.1f}p, "
                f"max_fav={max_fav:.1f}p, stall={stall})"
            ),
            snap=snap,
            position=own_pos,
        )

    # ==========================
    # ポジションなし: エントリー判定
    # ==========================
    entry_direction = evaluate_entry(snap)
    if entry_direction is None:
        return _hold(
            bars=bars,
            strategy_name=strategy_name,
            reason=(
                f"no entry: adx={snap.adx:.1f} h1={snap.h1_direction} "
                f"ema_fast={snap.ema_fast:.3f} ema_slow={snap.ema_slow:.3f} "
                f"pullback_dist={abs(snap.latest_close-snap.ema_slow):.4f} "
                f"atr={snap.atr:.4f}"
            ),
            snap=snap,
        )

    action = SignalAction.BUY if entry_direction == "buy" else SignalAction.SELL
    return SignalDecision(
        strategy_name=strategy_name,
        action=action,
        reason=(
            f"B2 entry: adx={snap.adx:.1f} h1={snap.h1_direction} "
            f"ema_fast={snap.ema_fast:.3f} ema_slow={snap.ema_slow:.3f} "
            f"pullback_dist_atr={abs(snap.latest_close-snap.ema_slow)/snap.atr:.2f}"
        ),
        previous_bar_time=bars[-2].time,
        latest_bar_time=bars[-1].time,
        previous_close=bars[-2].close,
        latest_close=snap.latest_close,
        current_position_ticket=None,
        current_position_type=None,
        sl_price=None,
        tp_price=None,
        entry_lane="trend",
        entry_subtype="b2_pullback",
        exit_subtype=None,
        market_state=f"trend_{snap.h1_direction}",
        middle_band=snap.bb_mid,
        upper_band=snap.bb_upper,
        lower_band=snap.bb_lower,
        normalized_band_width=None,
        range_slope=None,
        trend_slope=None,
        trend_current_ma=snap.ema_slow,
        distance_from_middle=snap.latest_close - snap.bb_mid,
        detected_market_state=f"trend_{snap.h1_direction}",
        candidate_market_state=None,
        state_transition_event=None,
        state_age=None,
        candidate_age=None,
        detector_reason=None,
        range_score=None,
        transition_up_score=None,
        transition_down_score=None,
        trend_up_score=None,
        trend_down_score=None,
        debug_metrics={
            "b2_adx": snap.adx,
            "b2_atr": snap.atr,
            "b2_ema_fast": snap.ema_fast,
            "b2_ema_slow": snap.ema_slow,
            "b2_h1_direction": snap.h1_direction,
        },
    )


# ---------------------------------------------------------------------------
# Helper: HOLD / CLOSE decision builders
# ---------------------------------------------------------------------------

def _hold(
    *,
    bars,
    strategy_name: str,
    reason: str,
    snap=None,
    position: OpenPosition | None = None,
) -> SignalDecision:
    return SignalDecision(
        strategy_name=strategy_name,
        action=SignalAction.HOLD,
        reason=reason,
        previous_bar_time=bars[-2].time if len(bars) >= 2 else None,
        latest_bar_time=bars[-1].time,
        previous_close=bars[-2].close if len(bars) >= 2 else 0.0,
        latest_close=bars[-1].close,
        current_position_ticket=position.ticket if position else None,
        current_position_type=position.position_type if position else None,
        sl_price=None,
        tp_price=None,
        entry_lane="trend",
        entry_subtype=None,
        exit_subtype=None,
        market_state=(
            f"trend_{snap.h1_direction}" if snap else None
        ),
        middle_band=snap.bb_mid if snap else None,
        upper_band=snap.bb_upper if snap else None,
        lower_band=snap.bb_lower if snap else None,
        normalized_band_width=None,
        range_slope=None,
        trend_slope=None,
        trend_current_ma=snap.ema_slow if snap else None,
        distance_from_middle=(
            snap.latest_close - snap.bb_mid if snap else None
        ),
        detected_market_state=(
            f"trend_{snap.h1_direction}" if snap else None
        ),
        candidate_market_state=None,
        state_transition_event=None,
        state_age=None,
        candidate_age=None,
        detector_reason=None,
        range_score=None,
        transition_up_score=None,
        transition_down_score=None,
        trend_up_score=None,
        trend_down_score=None,
        debug_metrics=None,
    )


def _close(
    *,
    bars,
    strategy_name: str,
    snap,
    exit_subtype: str,
    reason: str,
    position: OpenPosition,
) -> SignalDecision:
    return SignalDecision(
        strategy_name=strategy_name,
        action=SignalAction.CLOSE,
        reason=reason,
        previous_bar_time=bars[-2].time if len(bars) >= 2 else None,
        latest_bar_time=bars[-1].time,
        previous_close=bars[-2].close if len(bars) >= 2 else 0.0,
        latest_close=snap.latest_close,
        current_position_ticket=position.ticket,
        current_position_type=position.position_type,
        sl_price=None,
        tp_price=None,
        entry_lane="trend",
        entry_subtype=None,
        exit_subtype=exit_subtype,
        market_state=f"trend_{snap.h1_direction}",
        middle_band=snap.bb_mid,
        upper_band=snap.bb_upper,
        lower_band=snap.bb_lower,
        normalized_band_width=None,
        range_slope=None,
        trend_slope=None,
        trend_current_ma=snap.ema_slow,
        distance_from_middle=snap.latest_close - snap.bb_mid,
        detected_market_state=f"trend_{snap.h1_direction}",
        candidate_market_state=None,
        state_transition_event=None,
        state_age=None,
        candidate_age=None,
        detector_reason=None,
        range_score=None,
        transition_up_score=None,
        transition_down_score=None,
        trend_up_score=None,
        trend_down_score=None,
        debug_metrics={
            "b2_adx": snap.adx,
            "b2_atr": snap.atr,
            "b2_h1_direction": snap.h1_direction,
        },
    )
