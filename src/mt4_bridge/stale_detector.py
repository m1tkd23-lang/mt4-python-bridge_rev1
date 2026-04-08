# src\mt4_bridge\stale_detector.py
from __future__ import annotations

from dataclasses import dataclass

from mt4_bridge.models import BridgeReadResult, RuntimeState


@dataclass(frozen=True)
class UpdateBasedStaleStatus:
    market_unchanged: bool
    runtime_unchanged: bool
    latest_bar_unchanged: bool
    should_block: bool
    reason: str


def _latest_bar_time_iso(result: BridgeReadResult) -> str | None:
    if not result.market_snapshot.bars:
        return None
    return result.market_snapshot.bars[-1].time.isoformat()


def evaluate_update_based_staleness(
    result: BridgeReadResult,
    runtime_state: RuntimeState,
) -> UpdateBasedStaleStatus:
    current_market_generated_at = result.market_snapshot.generated_at.isoformat()
    current_runtime_updated_at = result.runtime_status.updated_at.isoformat()
    current_latest_bar_time = _latest_bar_time_iso(result)

    previous_market_generated_at = runtime_state.last_seen_market_generated_at
    previous_runtime_updated_at = runtime_state.last_seen_runtime_updated_at
    previous_latest_bar_time = runtime_state.last_seen_latest_bar_time

    if (
        previous_market_generated_at is None
        or previous_runtime_updated_at is None
        or previous_latest_bar_time is None
    ):
        return UpdateBasedStaleStatus(
            market_unchanged=False,
            runtime_unchanged=False,
            latest_bar_unchanged=False,
            should_block=False,
            reason="no previous snapshot markers",
        )

    market_unchanged = current_market_generated_at == previous_market_generated_at
    runtime_unchanged = current_runtime_updated_at == previous_runtime_updated_at
    latest_bar_unchanged = current_latest_bar_time == previous_latest_bar_time

    should_block = market_unchanged and runtime_unchanged and latest_bar_unchanged

    if should_block:
        reason = "market/runtime/latest_bar markers did not advance"
    else:
        reason = "snapshot markers advanced"

    return UpdateBasedStaleStatus(
        market_unchanged=market_unchanged,
        runtime_unchanged=runtime_unchanged,
        latest_bar_unchanged=latest_bar_unchanged,
        should_block=should_block,
        reason=reason,
    )