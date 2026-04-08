# src\mt4_bridge\snapshot_reader.py
from __future__ import annotations

from datetime import datetime
from typing import Any

from .json_loader import load_json_file
from .models import (
    Bar,
    BridgeReadResult,
    CommandResult,
    MarketSnapshot,
    OpenPosition,
    PositionSnapshot,
    RuntimeStatus,
    SnapshotHealth,
)
from .time_utils import age_seconds, is_stale, parse_mt4_datetime


class SnapshotValidationError(Exception):
    """Raised when snapshot JSON structure is invalid."""


def _require_key(data: dict[str, Any], key: str) -> Any:
    if key not in data:
        raise SnapshotValidationError(f"Missing required key: {key}")
    return data[key]


def _parse_bar(item: dict[str, Any]) -> Bar:
    return Bar(
        time=parse_mt4_datetime(str(_require_key(item, "time"))),
        open=float(_require_key(item, "open")),
        high=float(_require_key(item, "high")),
        low=float(_require_key(item, "low")),
        close=float(_require_key(item, "close")),
        tick_volume=int(_require_key(item, "tick_volume")),
        spread=int(_require_key(item, "spread")),
    )


def _parse_position(item: dict[str, Any]) -> OpenPosition:
    return OpenPosition(
        ticket=int(_require_key(item, "ticket")),
        symbol=str(_require_key(item, "symbol")),
        position_type=str(_require_key(item, "position_type")),
        lots=float(_require_key(item, "lots")),
        open_price=float(_require_key(item, "open_price")),
        open_time=parse_mt4_datetime(str(_require_key(item, "open_time"))),
        magic_number=int(_require_key(item, "magic_number")),
        comment=str(_require_key(item, "comment")),
    )


def parse_market_snapshot(data: dict[str, Any]) -> MarketSnapshot:
    raw_bars = _require_key(data, "bars")
    if not isinstance(raw_bars, list):
        raise SnapshotValidationError("bars must be a list")

    bars: list[Bar] = []
    for raw_bar in raw_bars:
        if not isinstance(raw_bar, dict):
            raise SnapshotValidationError("each bar must be an object")
        bars.append(_parse_bar(raw_bar))

    bars.sort(key=lambda bar: bar.time)

    return MarketSnapshot(
        schema_version=str(_require_key(data, "schema_version")),
        generated_at=parse_mt4_datetime(str(_require_key(data, "generated_at"))),
        symbol=str(_require_key(data, "symbol")),
        timeframe=str(_require_key(data, "timeframe")),
        bars_requested=int(_require_key(data, "bars_requested")),
        bars_copied=int(_require_key(data, "bars_copied")),
        bid=float(_require_key(data, "bid")),
        ask=float(_require_key(data, "ask")),
        spread_points=int(_require_key(data, "spread_points")),
        digits=int(_require_key(data, "digits")),
        point=float(_require_key(data, "point")),
        last_tick_time=parse_mt4_datetime(str(_require_key(data, "last_tick_time"))),
        bars=bars,
    )


def parse_runtime_status(data: dict[str, Any]) -> RuntimeStatus:
    return RuntimeStatus(
        schema_version=str(_require_key(data, "schema_version")),
        updated_at=parse_mt4_datetime(str(_require_key(data, "updated_at"))),
        ea_name=str(_require_key(data, "ea_name")),
        ea_version=str(_require_key(data, "ea_version")),
        symbol=str(_require_key(data, "symbol")),
        terminal_connected=bool(_require_key(data, "terminal_connected")),
        trade_allowed=bool(_require_key(data, "trade_allowed")),
        use_common_files=bool(_require_key(data, "use_common_files")),
        bridge_root=str(_require_key(data, "bridge_root")),
        timeframe=str(_require_key(data, "timeframe")),
        last_tick_time=parse_mt4_datetime(str(_require_key(data, "last_tick_time"))),
        mode=str(_require_key(data, "mode")),
        detail=str(_require_key(data, "detail")),
    )


def parse_position_snapshot(data: dict[str, Any]) -> PositionSnapshot:
    raw_positions = _require_key(data, "positions")
    if not isinstance(raw_positions, list):
        raise SnapshotValidationError("positions must be a list")

    positions: list[OpenPosition] = []
    for raw_position in raw_positions:
        if not isinstance(raw_position, dict):
            raise SnapshotValidationError("each position must be an object")
        positions.append(_parse_position(raw_position))

    return PositionSnapshot(
        schema_version=str(_require_key(data, "schema_version")),
        generated_at=parse_mt4_datetime(str(_require_key(data, "generated_at"))),
        positions=positions,
    )


def evaluate_market_health(
    snapshot: MarketSnapshot,
    now: datetime,
    stale_seconds: int,
) -> SnapshotHealth:
    age = age_seconds(now, snapshot.generated_at)
    return SnapshotHealth(
        is_stale=is_stale(now, snapshot.generated_at, stale_seconds),
        age_seconds=age,
    )


def evaluate_runtime_health(
    status: RuntimeStatus,
    now: datetime,
    stale_seconds: int,
) -> SnapshotHealth:
    age = age_seconds(now, status.updated_at)
    return SnapshotHealth(
        is_stale=is_stale(now, status.updated_at, stale_seconds),
        age_seconds=age,
    )


def read_market_snapshot(path) -> MarketSnapshot:
    data = load_json_file(path)
    return parse_market_snapshot(data)


def read_runtime_status(path) -> RuntimeStatus:
    data = load_json_file(path)
    return parse_runtime_status(data)


def read_position_snapshot(path) -> PositionSnapshot:
    data = load_json_file(path)
    return parse_position_snapshot(data)


def build_read_result(
    market_snapshot: MarketSnapshot,
    runtime_status: RuntimeStatus,
    position_snapshot: PositionSnapshot,
    results: list[CommandResult],
    market_stale_seconds: int,
    runtime_stale_seconds: int,
    now: datetime,
) -> BridgeReadResult:
    market_health = evaluate_market_health(
        snapshot=market_snapshot,
        now=now,
        stale_seconds=market_stale_seconds,
    )
    runtime_health = evaluate_runtime_health(
        status=runtime_status,
        now=now,
        stale_seconds=runtime_stale_seconds,
    )

    return BridgeReadResult(
        market_snapshot=market_snapshot,
        runtime_status=runtime_status,
        position_snapshot=position_snapshot,
        market_health=market_health,
        runtime_health=runtime_health,
        results=results,
    )