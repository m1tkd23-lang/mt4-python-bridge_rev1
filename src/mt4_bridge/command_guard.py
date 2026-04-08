# src/mt4_bridge/command_guard.py
from __future__ import annotations

import json
from pathlib import Path

from mt4_bridge.models import ActiveCommandStatus, RuntimeState, SignalAction, SignalDecision


class CommandGuardResult:
    def __init__(self, allowed: bool, reason: str) -> None:
        self.allowed = allowed
        self.reason = reason


def _normalize_lane(lane: str | None) -> str | None:
    if lane is None:
        return None

    normalized = lane.strip().lower()
    if normalized in {"range", "trend"}:
        return normalized
    return None


def _get_lane_last_command_bar_time(
    runtime_state: RuntimeState,
    lane: str | None,
) -> str | None:
    normalized_lane = _normalize_lane(lane)

    if normalized_lane == "range":
        return runtime_state.range_last_command_bar_time
    if normalized_lane == "trend":
        return runtime_state.trend_last_command_bar_time
    return None


def _get_lane_last_command_action(
    runtime_state: RuntimeState,
    lane: str | None,
) -> str | None:
    normalized_lane = _normalize_lane(lane)

    if normalized_lane == "range":
        return runtime_state.range_last_command_action
    if normalized_lane == "trend":
        return runtime_state.trend_last_command_action
    return None


def _get_lane_active_command_status(
    runtime_state: RuntimeState,
    lane: str | None,
) -> str | None:
    normalized_lane = _normalize_lane(lane)

    if normalized_lane == "range":
        return runtime_state.range_active_command_status
    if normalized_lane == "trend":
        return runtime_state.trend_active_command_status
    return None


def _read_pending_command_lane(path: Path) -> str | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(raw, dict):
        return None

    meta = raw.get("meta")
    if not isinstance(meta, dict):
        return None

    entry_lane = meta.get("entry_lane")
    if entry_lane is None:
        return None

    return _normalize_lane(str(entry_lane))


def has_pending_command_file(
    command_queue_path: Path,
    lane: str | None,
) -> bool:
    normalized_lane = _normalize_lane(lane)

    if not command_queue_path.exists():
        return False
    if not command_queue_path.is_dir():
        return False

    for path in command_queue_path.glob("*.json"):
        if not path.is_file():
            continue

        if normalized_lane is None:
            return True

        pending_lane = _read_pending_command_lane(path)

        # lane情報がない古いコマンドは安全側でブロック
        if pending_lane is None or pending_lane == normalized_lane:
            return True

    return False


def has_pending_command_state(
    runtime_state: RuntimeState,
    lane: str | None,
) -> bool:
    active_status = _get_lane_active_command_status(runtime_state, lane)
    return active_status == ActiveCommandStatus.PENDING.value


def has_effective_pending_command(
    command_queue_path: Path,
    runtime_state: RuntimeState,
    lane: str | None,
) -> tuple[bool, str]:
    if has_pending_command_file(command_queue_path, lane):
        return True, "pending command file exists for the same lane in command_queue"

    if has_pending_command_state(runtime_state, lane):
        return True, "active command is still pending in runtime_state for the same lane"

    return False, "no pending command"


def should_emit_command(
    decision: SignalDecision,
    runtime_state: RuntimeState,
    command_queue_path: Path,
    skip_if_pending_command: bool,
) -> CommandGuardResult:
    if decision.action == SignalAction.HOLD:
        return CommandGuardResult(
            allowed=False,
            reason="signal is HOLD",
        )

    normalized_lane = _normalize_lane(decision.entry_lane)

    latest_bar_time = (
        decision.latest_bar_time.isoformat()
        if decision.latest_bar_time is not None
        else None
    )
    last_command_bar_time = _get_lane_last_command_bar_time(
        runtime_state=runtime_state,
        lane=normalized_lane,
    )
    last_command_action = _get_lane_last_command_action(
        runtime_state=runtime_state,
        lane=normalized_lane,
    )
    current_action = decision.action.value

    if (
        latest_bar_time is not None
        and last_command_bar_time == latest_bar_time
        and last_command_action == current_action
    ):
        return CommandGuardResult(
            allowed=False,
            reason="command already emitted for the same lane, same bar, and same action",
        )

    if skip_if_pending_command:
        has_pending, pending_reason = has_effective_pending_command(
            command_queue_path=command_queue_path,
            runtime_state=runtime_state,
            lane=normalized_lane,
        )
        if has_pending:
            return CommandGuardResult(
                allowed=False,
                reason=pending_reason,
            )

    return CommandGuardResult(
        allowed=True,
        reason="allowed",
    )