# src/mt4_bridge/position_consistency.py
from __future__ import annotations

from dataclasses import dataclass

from mt4_bridge.models import (
    ActiveCommandStatus,
    CommandResult,
    OpenPosition,
    PositionSnapshot,
    ResultCommandMatch,
    ResultCommandMatchStatus,
    RuntimeState,
)

RANGE_MAGIC_NUMBER = 44001
TREND_MAGIC_NUMBER = 44002


@dataclass(frozen=True)
class PositionConsistencyWarning:
    code: str
    message: str


def _get_lane_positions(position_snapshot: PositionSnapshot, lane: str) -> list[OpenPosition]:
    if lane == "range":
        return [
            item
            for item in position_snapshot.positions
            if item.magic_number == RANGE_MAGIC_NUMBER
        ]
    if lane == "trend":
        return [
            item
            for item in position_snapshot.positions
            if item.magic_number == TREND_MAGIC_NUMBER
        ]
    return []


def _get_lane_active_status(runtime_state: RuntimeState, lane: str) -> str | None:
    if lane == "range":
        return runtime_state.range_active_command_status
    if lane == "trend":
        return runtime_state.trend_active_command_status
    return None


def _get_lane_active_ticket(runtime_state: RuntimeState, lane: str) -> int | None:
    if lane == "range":
        return runtime_state.range_active_ticket
    if lane == "trend":
        return runtime_state.trend_active_ticket
    return None


def _lane_warning_prefix(lane: str) -> str:
    return f"{lane}_lane"


def _evaluate_lane_consistency(
    *,
    lane: str,
    lane_positions: list[OpenPosition],
    active_status: str | None,
    active_ticket: int | None,
    latest_unconsumed_result: CommandResult | None,
    result_match: ResultCommandMatch | None,
) -> list[PositionConsistencyWarning]:
    warnings: list[PositionConsistencyWarning] = []

    has_position = len(lane_positions) > 0
    lane_position_tickets = {item.ticket for item in lane_positions}

    if active_status == ActiveCommandStatus.FILLED.value and not has_position:
        warnings.append(
            PositionConsistencyWarning(
                code=f"{_lane_warning_prefix(lane)}_filled_without_position",
                message=(
                    f"{lane} lane active_command_status is filled but no open position exists in that lane"
                ),
            )
        )

    if active_status == ActiveCommandStatus.CLOSED.value and has_position:
        warnings.append(
            PositionConsistencyWarning(
                code=f"{_lane_warning_prefix(lane)}_closed_with_remaining_position",
                message=(
                    f"{lane} lane active_command_status is closed but an open position still exists in that lane"
                ),
            )
        )

    if active_status == ActiveCommandStatus.FILLED.value and active_ticket is None:
        warnings.append(
            PositionConsistencyWarning(
                code=f"{_lane_warning_prefix(lane)}_filled_without_active_ticket",
                message=(
                    f"{lane} lane active_command_status is filled but active ticket is not tracked"
                ),
            )
        )

    if active_ticket is not None and not has_position:
        warnings.append(
            PositionConsistencyWarning(
                code=f"{_lane_warning_prefix(lane)}_active_ticket_without_position",
                message=(
                    f"{lane} lane active ticket is tracked but no open position exists in that lane"
                ),
            )
        )

    if has_position and active_status == ActiveCommandStatus.FILLED.value and active_ticket is None:
        warnings.append(
            PositionConsistencyWarning(
                code=f"{_lane_warning_prefix(lane)}_position_exists_but_active_ticket_missing",
                message=(
                    f"{lane} lane has an open position but active ticket is not tracked"
                ),
            )
        )

    if active_ticket is not None and has_position and active_ticket not in lane_position_tickets:
        warnings.append(
            PositionConsistencyWarning(
                code=f"{_lane_warning_prefix(lane)}_active_ticket_not_found_in_positions",
                message=(
                    f"{lane} lane active ticket {active_ticket} was not found in open positions for that lane"
                ),
            )
        )

    if len(lane_position_tickets) == 1:
        only_ticket = next(iter(lane_position_tickets))
        if (
            active_ticket is not None
            and has_position
            and active_ticket != only_ticket
        ):
            warnings.append(
                PositionConsistencyWarning(
                    code=f"{_lane_warning_prefix(lane)}_position_ticket_mismatch",
                    message=(
                        f"{lane} lane tracked active ticket {active_ticket} does not match open position ticket {only_ticket}"
                    ),
                )
            )

    if (
        latest_unconsumed_result is not None
        and result_match is not None
        and result_match.status == ResultCommandMatchStatus.MATCHED
        and result_match.lane == lane
    ):
        normalized_status = latest_unconsumed_result.status.strip().lower()

        if normalized_status == ActiveCommandStatus.FILLED.value and not has_position:
            warnings.append(
                PositionConsistencyWarning(
                    code=f"{_lane_warning_prefix(lane)}_matched_filled_result_without_position",
                    message=(
                        f"matched {lane} lane result status is filled but no open position exists in that lane"
                    ),
                )
            )

        if normalized_status == ActiveCommandStatus.CLOSED.value and has_position:
            warnings.append(
                PositionConsistencyWarning(
                    code=f"{_lane_warning_prefix(lane)}_matched_closed_result_with_position",
                    message=(
                        f"matched {lane} lane result status is closed but an open position still exists in that lane"
                    ),
                )
            )

        if (
            latest_unconsumed_result.action == "CLOSE"
            and normalized_status == ActiveCommandStatus.CLOSED.value
            and has_position
        ):
            warnings.append(
                PositionConsistencyWarning(
                    code=f"{_lane_warning_prefix(lane)}_close_result_but_position_remains",
                    message=(
                        f"{lane} lane CLOSE result is closed but an open position still remains in that lane"
                    ),
                )
            )

        if (
            normalized_status == ActiveCommandStatus.FILLED.value
            and latest_unconsumed_result.ticket is not None
            and has_position
            and latest_unconsumed_result.ticket not in lane_position_tickets
        ):
            warnings.append(
                PositionConsistencyWarning(
                    code=f"{_lane_warning_prefix(lane)}_matched_filled_ticket_not_found",
                    message=(
                        f"matched {lane} lane filled result ticket {latest_unconsumed_result.ticket} was not found in open positions for that lane"
                    ),
                )
            )

    return warnings


def evaluate_position_consistency(
    position_snapshot: PositionSnapshot,
    runtime_state: RuntimeState,
    latest_unconsumed_result: CommandResult | None,
    result_match: ResultCommandMatch | None,
) -> list[PositionConsistencyWarning]:
    warnings: list[PositionConsistencyWarning] = []

    range_positions = _get_lane_positions(position_snapshot, "range")
    trend_positions = _get_lane_positions(position_snapshot, "trend")

    warnings.extend(
        _evaluate_lane_consistency(
            lane="range",
            lane_positions=range_positions,
            active_status=_get_lane_active_status(runtime_state, "range"),
            active_ticket=_get_lane_active_ticket(runtime_state, "range"),
            latest_unconsumed_result=latest_unconsumed_result,
            result_match=result_match,
        )
    )
    warnings.extend(
        _evaluate_lane_consistency(
            lane="trend",
            lane_positions=trend_positions,
            active_status=_get_lane_active_status(runtime_state, "trend"),
            active_ticket=_get_lane_active_ticket(runtime_state, "trend"),
            latest_unconsumed_result=latest_unconsumed_result,
            result_match=result_match,
        )
    )

    if len(range_positions) > 1:
        warnings.append(
            PositionConsistencyWarning(
                code="range_lane_multiple_positions",
                message="range lane has more than one open position",
            )
        )

    if len(trend_positions) > 1:
        warnings.append(
            PositionConsistencyWarning(
                code="trend_lane_multiple_positions",
                message="trend lane has more than one open position",
            )
        )

    return warnings