# src/mt4_bridge/strategies/bollinger_trend_B3.py
"""bollinger_trend_B3: BB 拡大 + ミドル交差 型の新 B 戦術。

構造:
- 入口: BB 幅が直前 bar より拡大 + ミドルライン交差
- 早期撤退: 反対側 2σ 接触で逃げ
- TP: 順方向 3σ タッチ or 数本先でミドル戻り
- 保険: simulator 側 SL_PIPS/TP_PIPS
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
from mt4_bridge.strategies.bollinger_trend_B3_params import (  # noqa: F401
    BANDWIDTH_EXPANSION_RATIO,
    BOLLINGER_EXTREME_SIGMA,
    BOLLINGER_PERIOD,
    BOLLINGER_SIGMA,
    MIDDLE_REVERT_MIN_BARS,
    PIP_MULTIPLIER,
    SL_PIPS,
    TP_PIPS,
    TREND_B3_MAGIC_NUMBER,
    required_bars,
)
from mt4_bridge.strategies.bollinger_trend_B3_rules import (
    build_snapshot,
    compute_unrealized_pips,
    evaluate_early_exit,
    evaluate_entry,
    evaluate_take_profit,
)


def _find_own_position(
    positions: list[OpenPosition],
) -> OpenPosition | None:
    """B3 のポジションを探す。BT では magic/comment が空なので先頭を採用。"""
    if not positions:
        return None
    for pos in positions:
        comment = (pos.comment or "").lower()
        if (
            pos.magic_number == TREND_B3_MAGIC_NUMBER
            or "lane:trend_b3" in comment
            or "trend_b3" in comment
        ):
            return pos
    return positions[0]


def _bars_since_entry(
    open_time, latest_bar_time, timeframe_minutes: int = 5
) -> int:
    if open_time is None or latest_bar_time is None:
        return 0
    delta: timedelta = latest_bar_time - open_time
    secs = max(int(delta.total_seconds()), 0)
    return secs // (timeframe_minutes * 60)


def _compute_mfe_mae(
    bars, entry_open_time, position_type: str, entry_price: float
) -> tuple[float, float]:
    """entry 以降の bar を逆走査して MFE (max favorable pips, 正数) と
    MAE (max adverse pips, 正数で深さ) を返す。

    bars 時系列昇順前提。最後から entry_open_time 未満で break するので O(hold)。
    """
    if entry_open_time is None:
        return 0.0, 0.0
    subset: list = []
    for bar in reversed(bars):
        if bar.time < entry_open_time:
            break
        subset.append(bar)
    if not subset:
        return 0.0, 0.0
    subset.reverse()

    max_fav = 0.0
    max_adv = 0.0
    for bar in subset:
        if position_type == "buy":
            fav = (bar.high - entry_price) * 100.0
            adv = (entry_price - bar.low) * 100.0
        else:
            fav = (entry_price - bar.low) * 100.0
            adv = (bar.high - entry_price) * 100.0
        if fav > max_fav:
            max_fav = fav
        if adv > max_adv:
            max_adv = adv
    return max_fav, max_adv


def evaluate_bollinger_trend_B3(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_trend_B3",
) -> SignalDecision:
    bars = market_snapshot.bars
    if len(bars) < required_bars():
        return _hold(
            bars=bars,
            strategy_name=strategy_name,
            reason=f"insufficient bars ({len(bars)} < {required_bars()})",
        )

    snap = build_snapshot(bars)
    if snap is None:
        return _hold(
            bars=bars, strategy_name=strategy_name, reason="indicator unavailable"
        )

    own_pos = _find_own_position(position_snapshot.positions)

    # =======================
    # 保有中: 出口判定のみ
    # =======================
    if own_pos is not None:
        position_type = (own_pos.position_type or "").lower()
        holding_bars = _bars_since_entry(own_pos.open_time, bars[-1].time)
        unrealized = compute_unrealized_pips(
            position_type, own_pos.open_price, snap.latest_close
        )
        mfe_pips, mae_pips = _compute_mfe_mae(
            bars=bars,
            entry_open_time=own_pos.open_time,
            position_type=position_type,
            entry_price=own_pos.open_price,
        )

        # 早期撤退 (反対 2σ / MAE 早切り / 時間ベース逃げ) を優先
        early_sub = evaluate_early_exit(
            snap, position_type, mae_pips, holding_bars, unrealized
        )
        if early_sub is not None:
            return _close(
                bars=bars,
                strategy_name=strategy_name,
                snap=snap,
                position=own_pos,
                exit_subtype=early_sub,
                reason=(
                    f"{early_sub}: mae={mae_pips:.1f} "
                    f"held={holding_bars} unrealized={unrealized:.1f}"
                ),
            )

        # TP 判定
        tp_sub = evaluate_take_profit(snap, position_type, holding_bars, unrealized, mfe_pips)
        if tp_sub is not None:
            return _close(
                bars=bars,
                strategy_name=strategy_name,
                snap=snap,
                position=own_pos,
                exit_subtype=tp_sub,
                reason=f"take profit: {tp_sub}",
            )

        # 握り続ける
        return _hold(
            bars=bars,
            strategy_name=strategy_name,
            reason=(
                f"holding: held_bars={holding_bars} unrealized={unrealized:.1f}p "
                f"bw={snap.bandwidth:.4f}"
            ),
            snap=snap,
            position=own_pos,
        )

    # =======================
    # 保有なし: エントリー判定
    # =======================
    direction = evaluate_entry(snap)
    if direction is None:
        return _hold(
            bars=bars,
            strategy_name=strategy_name,
            reason=(
                f"no entry: bw_ratio={snap.bandwidth/max(snap.bandwidth_prev,1e-9):.3f} "
                f"prev_close={snap.prev_close:.3f} latest_close={snap.latest_close:.3f} "
                f"bb_mid={snap.bb_mid:.3f}"
            ),
            snap=snap,
        )

    action = SignalAction.BUY if direction == "buy" else SignalAction.SELL
    return SignalDecision(
        strategy_name=strategy_name,
        action=action,
        reason=(
            f"B3 entry: bw_expand={snap.bandwidth/snap.bandwidth_prev:.2f} "
            f"middle_cross {direction} mid={snap.bb_mid:.3f} "
            f"prev_close={snap.prev_close:.3f} latest_close={snap.latest_close:.3f}"
        ),
        previous_bar_time=bars[-2].time,
        latest_bar_time=bars[-1].time,
        previous_close=snap.prev_close,
        latest_close=snap.latest_close,
        current_position_ticket=None,
        current_position_type=None,
        sl_price=None,
        tp_price=None,
        entry_lane="trend",
        entry_subtype="b3_middle_cross",
        exit_subtype=None,
        market_state=f"bw_expanding_{direction}",
        middle_band=snap.bb_mid,
        upper_band=snap.bb_upper,
        lower_band=snap.bb_lower,
        normalized_band_width=None,
        range_slope=None,
        trend_slope=None,
        trend_current_ma=None,
        distance_from_middle=snap.latest_close - snap.bb_mid,
        detected_market_state=f"bw_expanding_{direction}",
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
            "b3_bw": snap.bandwidth,
            "b3_bw_prev": snap.bandwidth_prev,
            "b3_bw_expansion": snap.bandwidth / max(snap.bandwidth_prev, 1e-9),
            "b3_upper_3sigma": snap.bb_upper_3sigma,
            "b3_lower_3sigma": snap.bb_lower_3sigma,
        },
    )


# ---------------------------------------------------------------------------
# Helpers: HOLD / CLOSE decision builders
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
        latest_bar_time=bars[-1].time if bars else None,
        previous_close=bars[-2].close if len(bars) >= 2 else 0.0,
        latest_close=bars[-1].close if bars else 0.0,
        current_position_ticket=position.ticket if position else None,
        current_position_type=position.position_type if position else None,
        sl_price=None,
        tp_price=None,
        entry_lane="trend",
        entry_subtype=None,
        exit_subtype=None,
        market_state=None,
        middle_band=snap.bb_mid if snap else None,
        upper_band=snap.bb_upper if snap else None,
        lower_band=snap.bb_lower if snap else None,
        normalized_band_width=None,
        range_slope=None,
        trend_slope=None,
        trend_current_ma=None,
        distance_from_middle=(
            snap.latest_close - snap.bb_mid if snap else None
        ),
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


def _close(
    *,
    bars,
    strategy_name: str,
    snap,
    position: OpenPosition,
    exit_subtype: str,
    reason: str,
) -> SignalDecision:
    return SignalDecision(
        strategy_name=strategy_name,
        action=SignalAction.CLOSE,
        reason=reason,
        previous_bar_time=bars[-2].time,
        latest_bar_time=bars[-1].time,
        previous_close=snap.prev_close,
        latest_close=snap.latest_close,
        current_position_ticket=position.ticket,
        current_position_type=position.position_type,
        sl_price=None,
        tp_price=None,
        entry_lane="trend",
        entry_subtype=None,
        exit_subtype=exit_subtype,
        market_state=None,
        middle_band=snap.bb_mid,
        upper_band=snap.bb_upper,
        lower_band=snap.bb_lower,
        normalized_band_width=None,
        range_slope=None,
        trend_slope=None,
        trend_current_ma=None,
        distance_from_middle=snap.latest_close - snap.bb_mid,
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
        debug_metrics={
            "b3_bw": snap.bandwidth,
            "b3_bw_prev": snap.bandwidth_prev,
        },
    )
