# src/mt4_bridge/runtime_state.py
from __future__ import annotations

import json
from pathlib import Path

from mt4_bridge.models import (
    ActiveCommandStatus,
    CommandResult,
    PositionSnapshot,
    ResultCommandMatch,
    ResultCommandMatchStatus,
    RuntimeState,
)


class RuntimeStateError(Exception):
    """Raised when runtime state cannot be loaded or saved safely."""


def ensure_runtime_state_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _empty_runtime_state() -> RuntimeState:
    return RuntimeState(
        range_last_command_bar_time=None,
        range_last_command_action=None,
        range_last_command_id=None,
        range_active_command_status=None,
        range_active_ticket=None,
        trend_last_command_bar_time=None,
        trend_last_command_action=None,
        trend_last_command_id=None,
        trend_active_command_status=None,
        trend_active_ticket=None,
        last_result_command_id=None,
        last_result_status=None,
        last_result_ticket=None,
        last_result_processed_at=None,
        last_consumed_result_command_id=None,
        last_consumed_result_processed_at=None,
        last_seen_market_generated_at=None,
        last_seen_runtime_updated_at=None,
        last_seen_latest_bar_time=None,
    )


def load_runtime_state(path: Path) -> RuntimeState:
    if not path.exists():
        return _empty_runtime_state()

    if not path.is_file():
        raise RuntimeStateError(f"Runtime state path is not a file: {path}")

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeStateError(f"Failed to read runtime state: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeStateError(f"Invalid runtime state JSON: {path}") from exc

    if not isinstance(raw, dict):
        raise RuntimeStateError(f"Runtime state must be an object: {path}")

    # 旧形式からの移行時は存在しない項目は None 扱いに寄せる
    return RuntimeState(
        range_last_command_bar_time=_optional_str(raw.get("range_last_command_bar_time")),
        range_last_command_action=_optional_str(raw.get("range_last_command_action")),
        range_last_command_id=_optional_str(raw.get("range_last_command_id")),
        range_active_command_status=_optional_str(raw.get("range_active_command_status")),
        range_active_ticket=_optional_int(raw.get("range_active_ticket")),
        trend_last_command_bar_time=_optional_str(raw.get("trend_last_command_bar_time")),
        trend_last_command_action=_optional_str(raw.get("trend_last_command_action")),
        trend_last_command_id=_optional_str(raw.get("trend_last_command_id")),
        trend_active_command_status=_optional_str(raw.get("trend_active_command_status")),
        trend_active_ticket=_optional_int(raw.get("trend_active_ticket")),
        last_result_command_id=_optional_str(raw.get("last_result_command_id")),
        last_result_status=_optional_str(raw.get("last_result_status")),
        last_result_ticket=_optional_int(raw.get("last_result_ticket")),
        last_result_processed_at=_optional_str(raw.get("last_result_processed_at")),
        last_consumed_result_command_id=_optional_str(
            raw.get("last_consumed_result_command_id")
        ),
        last_consumed_result_processed_at=_optional_str(
            raw.get("last_consumed_result_processed_at")
        ),
        last_seen_market_generated_at=_optional_str(
            raw.get("last_seen_market_generated_at")
        ),
        last_seen_runtime_updated_at=_optional_str(
            raw.get("last_seen_runtime_updated_at")
        ),
        last_seen_latest_bar_time=_optional_str(raw.get("last_seen_latest_bar_time")),
    )


def save_runtime_state(path: Path, state: RuntimeState) -> None:
    ensure_runtime_state_parent(path)

    payload = {
        "range_last_command_bar_time": state.range_last_command_bar_time,
        "range_last_command_action": state.range_last_command_action,
        "range_last_command_id": state.range_last_command_id,
        "range_active_command_status": state.range_active_command_status,
        "range_active_ticket": state.range_active_ticket,
        "trend_last_command_bar_time": state.trend_last_command_bar_time,
        "trend_last_command_action": state.trend_last_command_action,
        "trend_last_command_id": state.trend_last_command_id,
        "trend_active_command_status": state.trend_active_command_status,
        "trend_active_ticket": state.trend_active_ticket,
        "last_result_command_id": state.last_result_command_id,
        "last_result_status": state.last_result_status,
        "last_result_ticket": state.last_result_ticket,
        "last_result_processed_at": state.last_result_processed_at,
        "last_consumed_result_command_id": state.last_consumed_result_command_id,
        "last_consumed_result_processed_at": state.last_consumed_result_processed_at,
        "last_seen_market_generated_at": state.last_seen_market_generated_at,
        "last_seen_runtime_updated_at": state.last_seen_runtime_updated_at,
        "last_seen_latest_bar_time": state.last_seen_latest_bar_time,
    }

    temp_path = path.with_suffix(path.suffix + ".tmp")

    try:
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(path)
    except OSError as exc:
        raise RuntimeStateError(f"Failed to save runtime state: {path}") from exc


def _normalize_lane(lane: str | None) -> str | None:
    if lane is None:
        return None

    normalized = lane.strip().lower()
    if normalized in {"range", "trend"}:
        return normalized
    return None


def _replace_lane_command_fields(
    current_state: RuntimeState,
    lane: str | None,
    *,
    last_command_bar_time: str | None = None,
    last_command_action: str | None = None,
    last_command_id: str | None = None,
    active_command_status: str | None = None,
    active_ticket: int | None = None,
    replace_bar_time: bool = False,
    replace_action: bool = False,
    replace_command_id: bool = False,
    replace_active_status: bool = False,
    replace_active_ticket: bool = False,
) -> RuntimeState:
    normalized_lane = _normalize_lane(lane)
    if normalized_lane not in {"range", "trend"}:
        return current_state

    range_last_command_bar_time = current_state.range_last_command_bar_time
    range_last_command_action = current_state.range_last_command_action
    range_last_command_id = current_state.range_last_command_id
    range_active_command_status = current_state.range_active_command_status
    range_active_ticket = current_state.range_active_ticket

    trend_last_command_bar_time = current_state.trend_last_command_bar_time
    trend_last_command_action = current_state.trend_last_command_action
    trend_last_command_id = current_state.trend_last_command_id
    trend_active_command_status = current_state.trend_active_command_status
    trend_active_ticket = current_state.trend_active_ticket

    if normalized_lane == "range":
        if replace_bar_time:
            range_last_command_bar_time = last_command_bar_time
        if replace_action:
            range_last_command_action = last_command_action
        if replace_command_id:
            range_last_command_id = last_command_id
        if replace_active_status:
            range_active_command_status = active_command_status
        if replace_active_ticket:
            range_active_ticket = active_ticket
    elif normalized_lane == "trend":
        if replace_bar_time:
            trend_last_command_bar_time = last_command_bar_time
        if replace_action:
            trend_last_command_action = last_command_action
        if replace_command_id:
            trend_last_command_id = last_command_id
        if replace_active_status:
            trend_active_command_status = active_command_status
        if replace_active_ticket:
            trend_active_ticket = active_ticket

    return RuntimeState(
        range_last_command_bar_time=range_last_command_bar_time,
        range_last_command_action=range_last_command_action,
        range_last_command_id=range_last_command_id,
        range_active_command_status=range_active_command_status,
        range_active_ticket=range_active_ticket,
        trend_last_command_bar_time=trend_last_command_bar_time,
        trend_last_command_action=trend_last_command_action,
        trend_last_command_id=trend_last_command_id,
        trend_active_command_status=trend_active_command_status,
        trend_active_ticket=trend_active_ticket,
        last_result_command_id=current_state.last_result_command_id,
        last_result_status=current_state.last_result_status,
        last_result_ticket=current_state.last_result_ticket,
        last_result_processed_at=current_state.last_result_processed_at,
        last_consumed_result_command_id=current_state.last_consumed_result_command_id,
        last_consumed_result_processed_at=current_state.last_consumed_result_processed_at,
        last_seen_market_generated_at=current_state.last_seen_market_generated_at,
        last_seen_runtime_updated_at=current_state.last_seen_runtime_updated_at,
        last_seen_latest_bar_time=current_state.last_seen_latest_bar_time,
    )


def build_updated_runtime_state(
    current_state: RuntimeState,
    lane: str | None = None,
    latest_bar_time: str | None = None,
    action: str | None = None,
    command_id: str | None = None,
    latest_result: CommandResult | None = None,
) -> RuntimeState:
    next_state = current_state
    normalized_lane = _normalize_lane(lane)

    if normalized_lane is not None and (
        latest_bar_time is not None or action is not None or command_id is not None
    ):
        if normalized_lane == "range":
            existing_bar_time = next_state.range_last_command_bar_time
            existing_action = next_state.range_last_command_action
            existing_command_id = next_state.range_last_command_id
        else:
            existing_bar_time = next_state.trend_last_command_bar_time
            existing_action = next_state.trend_last_command_action
            existing_command_id = next_state.trend_last_command_id

        next_state = _replace_lane_command_fields(
            current_state=next_state,
            lane=normalized_lane,
            last_command_bar_time=(
                latest_bar_time if latest_bar_time is not None else existing_bar_time
            ),
            last_command_action=action if action is not None else existing_action,
            last_command_id=command_id if command_id is not None else existing_command_id,
            replace_bar_time=latest_bar_time is not None,
            replace_action=action is not None,
            replace_command_id=command_id is not None,
        )

    return RuntimeState(
        range_last_command_bar_time=next_state.range_last_command_bar_time,
        range_last_command_action=next_state.range_last_command_action,
        range_last_command_id=next_state.range_last_command_id,
        range_active_command_status=next_state.range_active_command_status,
        range_active_ticket=next_state.range_active_ticket,
        trend_last_command_bar_time=next_state.trend_last_command_bar_time,
        trend_last_command_action=next_state.trend_last_command_action,
        trend_last_command_id=next_state.trend_last_command_id,
        trend_active_command_status=next_state.trend_active_command_status,
        trend_active_ticket=next_state.trend_active_ticket,
        last_result_command_id=(
            latest_result.command_id
            if latest_result is not None
            else next_state.last_result_command_id
        ),
        last_result_status=(
            latest_result.status
            if latest_result is not None
            else next_state.last_result_status
        ),
        last_result_ticket=(
            latest_result.ticket
            if latest_result is not None
            else next_state.last_result_ticket
        ),
        last_result_processed_at=(
            latest_result.processed_at.isoformat()
            if latest_result is not None
            else next_state.last_result_processed_at
        ),
        last_consumed_result_command_id=next_state.last_consumed_result_command_id,
        last_consumed_result_processed_at=next_state.last_consumed_result_processed_at,
        last_seen_market_generated_at=next_state.last_seen_market_generated_at,
        last_seen_runtime_updated_at=next_state.last_seen_runtime_updated_at,
        last_seen_latest_bar_time=next_state.last_seen_latest_bar_time,
    )


def mark_result_consumed(
    current_state: RuntimeState,
    result: CommandResult | None,
) -> RuntimeState:
    if result is None:
        return current_state

    return RuntimeState(
        range_last_command_bar_time=current_state.range_last_command_bar_time,
        range_last_command_action=current_state.range_last_command_action,
        range_last_command_id=current_state.range_last_command_id,
        range_active_command_status=current_state.range_active_command_status,
        range_active_ticket=current_state.range_active_ticket,
        trend_last_command_bar_time=current_state.trend_last_command_bar_time,
        trend_last_command_action=current_state.trend_last_command_action,
        trend_last_command_id=current_state.trend_last_command_id,
        trend_active_command_status=current_state.trend_active_command_status,
        trend_active_ticket=current_state.trend_active_ticket,
        last_result_command_id=current_state.last_result_command_id,
        last_result_status=current_state.last_result_status,
        last_result_ticket=current_state.last_result_ticket,
        last_result_processed_at=current_state.last_result_processed_at,
        last_consumed_result_command_id=result.command_id,
        last_consumed_result_processed_at=result.processed_at.isoformat(),
        last_seen_market_generated_at=current_state.last_seen_market_generated_at,
        last_seen_runtime_updated_at=current_state.last_seen_runtime_updated_at,
        last_seen_latest_bar_time=current_state.last_seen_latest_bar_time,
    )


def mark_command_pending(
    current_state: RuntimeState,
    lane: str | None,
) -> RuntimeState:
    return _replace_lane_command_fields(
        current_state=current_state,
        lane=lane,
        active_command_status=ActiveCommandStatus.PENDING.value,
        replace_active_status=True,
    )


def apply_result_to_active_command_status(
    current_state: RuntimeState,
    result: CommandResult | None,
    result_match: ResultCommandMatch | None,
) -> RuntimeState:
    if result is None or result_match is None:
        return current_state

    if result_match.status != ResultCommandMatchStatus.MATCHED:
        return current_state

    normalized_status = result.status.strip().lower()

    if normalized_status == ActiveCommandStatus.FILLED.value:
        next_status = ActiveCommandStatus.FILLED.value
        next_ticket = result.ticket
        replace_ticket = True
    elif normalized_status == ActiveCommandStatus.CLOSED.value:
        next_status = ActiveCommandStatus.CLOSED.value
        next_ticket = None
        replace_ticket = True
    elif normalized_status == ActiveCommandStatus.REJECTED.value:
        next_status = ActiveCommandStatus.REJECTED.value
        next_ticket = None
        replace_ticket = False
    else:
        return current_state

    return _replace_lane_command_fields(
        current_state=current_state,
        lane=result_match.lane,
        active_command_status=next_status,
        active_ticket=next_ticket,
        replace_active_status=True,
        replace_active_ticket=replace_ticket,
    )


def reconcile_active_tickets_with_position_snapshot(
    current_state: RuntimeState,
    position_snapshot: PositionSnapshot | None,
) -> RuntimeState:
    if position_snapshot is None:
        return current_state

    existing_tickets = {
        position.ticket
        for position in position_snapshot.positions
    }

    next_state = current_state

    if (
        next_state.range_active_ticket is not None
        and next_state.range_active_ticket not in existing_tickets
    ):
        next_state = _replace_lane_command_fields(
            current_state=next_state,
            lane="range",
            active_command_status=ActiveCommandStatus.CLOSED.value,
            active_ticket=None,
            replace_active_status=True,
            replace_active_ticket=True,
        )

    if (
        next_state.trend_active_ticket is not None
        and next_state.trend_active_ticket not in existing_tickets
    ):
        next_state = _replace_lane_command_fields(
            current_state=next_state,
            lane="trend",
            active_command_status=ActiveCommandStatus.CLOSED.value,
            active_ticket=None,
            replace_active_status=True,
            replace_active_ticket=True,
        )

    return next_state


def mark_snapshot_observed(
    current_state: RuntimeState,
    market_generated_at: str | None,
    runtime_updated_at: str | None,
    latest_bar_time: str | None,
) -> RuntimeState:
    return RuntimeState(
        range_last_command_bar_time=current_state.range_last_command_bar_time,
        range_last_command_action=current_state.range_last_command_action,
        range_last_command_id=current_state.range_last_command_id,
        range_active_command_status=current_state.range_active_command_status,
        range_active_ticket=current_state.range_active_ticket,
        trend_last_command_bar_time=current_state.trend_last_command_bar_time,
        trend_last_command_action=current_state.trend_last_command_action,
        trend_last_command_id=current_state.trend_last_command_id,
        trend_active_command_status=current_state.trend_active_command_status,
        trend_active_ticket=current_state.trend_active_ticket,
        last_result_command_id=current_state.last_result_command_id,
        last_result_status=current_state.last_result_status,
        last_result_ticket=current_state.last_result_ticket,
        last_result_processed_at=current_state.last_result_processed_at,
        last_consumed_result_command_id=current_state.last_consumed_result_command_id,
        last_consumed_result_processed_at=current_state.last_consumed_result_processed_at,
        last_seen_market_generated_at=market_generated_at,
        last_seen_runtime_updated_at=runtime_updated_at,
        last_seen_latest_bar_time=latest_bar_time,
    )


def get_lane_last_command_id(
    current_state: RuntimeState,
    lane: str | None,
) -> str | None:
    normalized_lane = _normalize_lane(lane)
    if normalized_lane == "range":
        return current_state.range_last_command_id
    if normalized_lane == "trend":
        return current_state.trend_last_command_id
    return None


def get_lane_active_command_status(
    current_state: RuntimeState,
    lane: str | None,
) -> str | None:
    normalized_lane = _normalize_lane(lane)
    if normalized_lane == "range":
        return current_state.range_active_command_status
    if normalized_lane == "trend":
        return current_state.trend_active_command_status
    return None


def get_lane_active_ticket(
    current_state: RuntimeState,
    lane: str | None,
) -> int | None:
    normalized_lane = _normalize_lane(lane)
    if normalized_lane == "range":
        return current_state.range_active_ticket
    if normalized_lane == "trend":
        return current_state.trend_active_ticket
    return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeStateError(
            f"Runtime state value must be int-compatible: {value}"
        ) from exc