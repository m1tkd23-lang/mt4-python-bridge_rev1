# src/mt4_bridge/strategies/bollinger_combo_AB.py
from __future__ import annotations

from dataclasses import replace

from mt4_bridge.models import (
    MarketSnapshot,
    OpenPosition,
    PositionSnapshot,
    SignalDecision,
)
from mt4_bridge.strategies.bollinger_range_A import (
    evaluate_bollinger_range_A,
    required_bars as range_required_bars,
)
from mt4_bridge.strategies.bollinger_trend_B import (
    evaluate_bollinger_trend_B,
    required_bars as trend_required_bars,
)

LANE_A_STRATEGY = "bollinger_range_A"
LANE_B_STRATEGY = "bollinger_trend_B"

# combo_AB 内部の lane 名 → 実体戦術名のマッピング。
# lane 別 SL/TP 解決(resolve_lane_risk_pips)で使用する。
LANE_STRATEGY_MAP: dict[str, str] = {
    "range": LANE_A_STRATEGY,
    "trend": LANE_B_STRATEGY,
}

RANGE_MAGIC_NUMBER = 44001
TREND_MAGIC_NUMBER = 44002


def required_bars() -> int:
    return max(range_required_bars(), trend_required_bars())


def _is_range_lane_position(position: OpenPosition) -> bool:
    comment = (position.comment or "").lower()
    return (
        position.magic_number == RANGE_MAGIC_NUMBER
        or "lane:range" in comment
        or "entry_lane=range" in comment
    )


def _is_trend_lane_position(position: OpenPosition) -> bool:
    comment = (position.comment or "").lower()
    return (
        position.magic_number == TREND_MAGIC_NUMBER
        or "lane:trend" in comment
        or "entry_lane=trend" in comment
    )


def _build_filtered_snapshot(
    *,
    position_snapshot: PositionSnapshot,
    generated_at,
    mode: str,
) -> PositionSnapshot:
    if mode == "range":
        positions = [
            position
            for position in position_snapshot.positions
            if _is_range_lane_position(position)
        ]
    elif mode == "trend":
        positions = [
            position
            for position in position_snapshot.positions
            if _is_trend_lane_position(position)
        ]
    else:
        positions = []

    return PositionSnapshot(
        schema_version=position_snapshot.schema_version,
        generated_at=generated_at,
        positions=positions,
    )


def _rename_strategy(
    decision: SignalDecision,
    strategy_name: str,
) -> SignalDecision:
    return replace(decision, strategy_name=strategy_name)


def evaluate_bollinger_combo_AB_signals(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_combo_AB",
) -> list[SignalDecision]:
    range_snapshot = _build_filtered_snapshot(
        position_snapshot=position_snapshot,
        generated_at=market_snapshot.generated_at,
        mode="range",
    )
    trend_snapshot = _build_filtered_snapshot(
        position_snapshot=position_snapshot,
        generated_at=market_snapshot.generated_at,
        mode="trend",
    )

    range_decision = _rename_strategy(
        evaluate_bollinger_range_A(
            market_snapshot=market_snapshot,
            position_snapshot=range_snapshot,
            strategy_name="bollinger_range_A",
        ),
        strategy_name,
    )
    trend_decision = _rename_strategy(
        evaluate_bollinger_trend_B(
            market_snapshot=market_snapshot,
            position_snapshot=trend_snapshot,
            strategy_name="bollinger_trend_B",
        ),
        strategy_name,
    )

    decisions: list[SignalDecision] = []

    if range_decision.action.name != "HOLD":
        decisions.append(range_decision)

    if trend_decision.action.name != "HOLD":
        decisions.append(trend_decision)

    if decisions:
        return decisions

    return [
        replace(
            range_decision,
            strategy_name=strategy_name,
            reason=(
                "no actionable lane decision"
                f" (range_action={range_decision.action.value},"
                f" trend_action={trend_decision.action.value})"
            ),
            entry_lane=None,
            entry_subtype=None,
            current_position_ticket=None,
            current_position_type=None,
        )
    ]


def evaluate_bollinger_combo_AB(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_combo_AB",
) -> SignalDecision:
    return evaluate_bollinger_combo_AB_signals(
        market_snapshot=market_snapshot,
        position_snapshot=position_snapshot,
        strategy_name=strategy_name,
    )[0]