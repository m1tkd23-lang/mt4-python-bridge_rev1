# src/mt4_bridge/models.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


@dataclass(frozen=True)
class Bar:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    spread: int


@dataclass(frozen=True)
class MarketSnapshot:
    schema_version: str
    generated_at: datetime
    symbol: str
    timeframe: str
    bars_requested: int
    bars_copied: int
    bid: float
    ask: float
    spread_points: int
    digits: int
    point: float
    last_tick_time: datetime
    bars: list[Bar]


@dataclass(frozen=True)
class RuntimeStatus:
    schema_version: str
    updated_at: datetime
    ea_name: str
    ea_version: str
    symbol: str
    terminal_connected: bool
    trade_allowed: bool
    use_common_files: bool
    bridge_root: str
    timeframe: str
    last_tick_time: datetime
    mode: str
    detail: str


@dataclass(frozen=True)
class OpenPosition:
    ticket: int
    symbol: str
    position_type: str
    lots: float
    open_price: float
    open_time: datetime
    magic_number: int
    comment: str


@dataclass(frozen=True)
class PositionSnapshot:
    schema_version: str
    generated_at: datetime
    positions: list[OpenPosition]


@dataclass(frozen=True)
class SnapshotHealth:
    is_stale: bool
    age_seconds: float


@dataclass(frozen=True)
class CommandResult:
    schema_version: str
    command_id: str
    processed_at: datetime
    status: str
    action: str
    ticket: int | None
    error_code: int | None
    message: str


@dataclass(frozen=True)
class BridgeReadResult:
    market_snapshot: MarketSnapshot
    runtime_status: RuntimeStatus
    position_snapshot: PositionSnapshot
    market_health: SnapshotHealth
    runtime_health: SnapshotHealth
    results: list[CommandResult]


class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    CLOSE = "CLOSE"
    HOLD = "HOLD"


class ResultCommandMatchStatus(str, Enum):
    MATCHED = "matched"
    UNTRACKED = "untracked"
    MISMATCHED = "mismatched"


class ActiveCommandStatus(str, Enum):
    PENDING = "pending"
    FILLED = "filled"
    CLOSED = "closed"
    REJECTED = "rejected"


@dataclass(frozen=True)
class ResultCommandMatch:
    status: ResultCommandMatchStatus
    expected_command_id: str | None
    actual_command_id: str
    lane: str | None = None


@dataclass(frozen=True)
class SignalDecision:
    strategy_name: str
    action: SignalAction
    reason: str
    previous_bar_time: datetime | None
    latest_bar_time: datetime | None
    previous_close: float | None
    latest_close: float | None
    current_position_ticket: int | None
    current_position_type: str | None
    sl_price: float | None = None
    tp_price: float | None = None

    # lane / subtype fields
    entry_lane: str | None = None
    entry_subtype: str | None = None
    exit_subtype: str | None = None

    # shared analysis fields
    market_state: str | None = None
    middle_band: float | None = None
    upper_band: float | None = None
    lower_band: float | None = None
    normalized_band_width: float | None = None
    range_slope: float | None = None
    trend_slope: float | None = None
    trend_current_ma: float | None = None
    distance_from_middle: float | None = None

    # v7 detector fields
    detected_market_state: str | None = None
    candidate_market_state: str | None = None
    state_transition_event: str | None = None
    state_age: int | None = None
    candidate_age: int | None = None
    detector_reason: str | None = None
    range_score: float | None = None
    transition_up_score: float | None = None
    transition_down_score: float | None = None
    trend_up_score: float | None = None
    trend_down_score: float | None = None

    # optional structured debug fields
    debug_metrics: dict[str, object] | None = None


@dataclass(frozen=True)
class RuntimeState:
    # range lane
    range_last_command_bar_time: str | None
    range_last_command_action: str | None
    range_last_command_id: str | None
    range_active_command_status: str | None
    range_active_ticket: int | None

    # trend lane
    trend_last_command_bar_time: str | None
    trend_last_command_action: str | None
    trend_last_command_id: str | None
    trend_active_command_status: str | None
    trend_active_ticket: int | None

    # shared latest result / consumption tracking
    last_result_command_id: str | None
    last_result_status: str | None
    last_result_ticket: int | None
    last_result_processed_at: str | None
    last_consumed_result_command_id: str | None
    last_consumed_result_processed_at: str | None

    # snapshot markers
    last_seen_market_generated_at: str | None
    last_seen_runtime_updated_at: str | None
    last_seen_latest_bar_time: str | None


@dataclass(frozen=True)
class CommandWriteResult:
    command_id: str
    command_path: str