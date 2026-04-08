# src/mt4_bridge/result_reader.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from mt4_bridge.json_loader import JsonLoadError, load_json_file
from mt4_bridge.models import (
    ActiveCommandStatus,
    CommandResult,
    ResultCommandMatch,
    ResultCommandMatchStatus,
    RuntimeState,
)
from mt4_bridge.runtime_state import (
    get_lane_active_ticket,
    get_lane_last_command_id,
)
from mt4_bridge.time_utils import parse_mt4_datetime


class ResultReadError(Exception):
    """Raised when result queue files cannot be read safely."""


def _require_key(data: dict[str, Any], key: str) -> Any:
    if key not in data:
        raise ResultReadError(f"Missing required key in result JSON: {key}")
    return data[key]


def parse_command_result(data: dict[str, Any]) -> CommandResult:
    ticket_raw = data.get("ticket")
    error_code_raw = data.get("error_code")

    return CommandResult(
        schema_version=str(_require_key(data, "schema_version")),
        command_id=str(_require_key(data, "command_id")),
        processed_at=parse_mt4_datetime(str(_require_key(data, "processed_at"))),
        status=str(_require_key(data, "status")),
        action=str(_require_key(data, "action")),
        ticket=int(ticket_raw) if ticket_raw is not None else None,
        error_code=int(error_code_raw) if error_code_raw is not None else None,
        message=str(_require_key(data, "message")),
    )


def read_result_file(path: Path) -> CommandResult:
    try:
        data = load_json_file(path)
    except JsonLoadError as exc:
        raise ResultReadError(str(exc)) from exc

    return parse_command_result(data)


def read_result_queue(result_queue_path: Path) -> list[CommandResult]:
    if not result_queue_path.exists():
        return []

    if not result_queue_path.is_dir():
        raise ResultReadError(
            f"Result queue path is not a directory: {result_queue_path}"
        )

    results: list[CommandResult] = []
    for path in sorted(result_queue_path.glob("*.json")):
        if not path.is_file():
            continue
        results.append(read_result_file(path))

    results.sort(key=lambda item: (item.processed_at, item.command_id))
    return results


def find_unconsumed_results(
    results: list[CommandResult],
    runtime_state: RuntimeState,
) -> list[CommandResult]:
    last_command_id = runtime_state.last_consumed_result_command_id
    last_processed_at = runtime_state.last_consumed_result_processed_at

    if last_command_id is None or last_processed_at is None:
        return results

    consumed_index = -1
    for index, item in enumerate(results):
        if (
            item.command_id == last_command_id
            and item.processed_at.isoformat() == last_processed_at
        ):
            consumed_index = index

    if consumed_index < 0:
        return results

    return results[consumed_index + 1 :]


def _match_by_command_id(
    result: CommandResult,
    runtime_state: RuntimeState,
) -> ResultCommandMatch | None:
    range_expected_command_id = get_lane_last_command_id(runtime_state, "range")
    trend_expected_command_id = get_lane_last_command_id(runtime_state, "trend")

    if (
        range_expected_command_id is not None
        and result.command_id == range_expected_command_id
    ):
        return ResultCommandMatch(
            status=ResultCommandMatchStatus.MATCHED,
            expected_command_id=range_expected_command_id,
            actual_command_id=result.command_id,
            lane="range",
        )

    if (
        trend_expected_command_id is not None
        and result.command_id == trend_expected_command_id
    ):
        return ResultCommandMatch(
            status=ResultCommandMatchStatus.MATCHED,
            expected_command_id=trend_expected_command_id,
            actual_command_id=result.command_id,
            lane="trend",
        )

    return None


def _match_by_active_ticket(
    result: CommandResult,
    runtime_state: RuntimeState,
) -> ResultCommandMatch | None:
    if result.ticket is None:
        return None

    range_active_ticket = get_lane_active_ticket(runtime_state, "range")
    trend_active_ticket = get_lane_active_ticket(runtime_state, "trend")

    matched_lanes: list[str] = []
    if range_active_ticket is not None and result.ticket == range_active_ticket:
        matched_lanes.append("range")
    if trend_active_ticket is not None and result.ticket == trend_active_ticket:
        matched_lanes.append("trend")

    if len(matched_lanes) != 1:
        return None

    lane = matched_lanes[0]
    return ResultCommandMatch(
        status=ResultCommandMatchStatus.MATCHED,
        expected_command_id=f"ticket:{result.ticket}",
        actual_command_id=result.command_id,
        lane=lane,
    )


def _match_filled_result_to_pending_lane(
    result: CommandResult,
    runtime_state: RuntimeState,
) -> ResultCommandMatch | None:
    normalized_status = result.status.strip().lower()
    normalized_action = result.action.strip().upper()

    if normalized_status != ActiveCommandStatus.FILLED.value:
        return None

    if normalized_action not in {"BUY", "SELL"}:
        return None

    pending_candidates: list[tuple[str, str | None]] = []

    if runtime_state.range_active_command_status == ActiveCommandStatus.PENDING.value:
        pending_candidates.append(("range", runtime_state.range_last_command_action))

    if runtime_state.trend_active_command_status == ActiveCommandStatus.PENDING.value:
        pending_candidates.append(("trend", runtime_state.trend_last_command_action))

    action_matched = [
        (lane, command_id)
        for lane, command_id in [
            ("range", get_lane_last_command_id(runtime_state, "range")),
            ("trend", get_lane_last_command_id(runtime_state, "trend")),
        ]
        if any(
            pending_lane == lane and pending_action == normalized_action
            for pending_lane, pending_action in pending_candidates
        )
    ]

    if len(action_matched) != 1:
        return None

    lane, expected_command_id = action_matched[0]
    return ResultCommandMatch(
        status=ResultCommandMatchStatus.MATCHED,
        expected_command_id=expected_command_id,
        actual_command_id=result.command_id,
        lane=lane,
    )


def match_result_to_runtime_state(
    result: CommandResult,
    runtime_state: RuntimeState,
) -> ResultCommandMatch:
    command_id_match = _match_by_command_id(
        result=result,
        runtime_state=runtime_state,
    )
    if command_id_match is not None:
        return command_id_match

    ticket_match = _match_by_active_ticket(
        result=result,
        runtime_state=runtime_state,
    )
    if ticket_match is not None:
        return ticket_match

    pending_match = _match_filled_result_to_pending_lane(
        result=result,
        runtime_state=runtime_state,
    )
    if pending_match is not None:
        return pending_match

    range_expected_command_id = get_lane_last_command_id(runtime_state, "range")
    trend_expected_command_id = get_lane_last_command_id(runtime_state, "trend")

    if range_expected_command_id is None and trend_expected_command_id is None:
        return ResultCommandMatch(
            status=ResultCommandMatchStatus.UNTRACKED,
            expected_command_id=None,
            actual_command_id=result.command_id,
            lane=None,
        )

    expected_ids = [
        value
        for value in [range_expected_command_id, trend_expected_command_id]
        if value is not None
    ]
    expected_label = ", ".join(expected_ids) if expected_ids else None

    return ResultCommandMatch(
        status=ResultCommandMatchStatus.MISMATCHED,
        expected_command_id=expected_label,
        actual_command_id=result.command_id,
        lane=None,
    )