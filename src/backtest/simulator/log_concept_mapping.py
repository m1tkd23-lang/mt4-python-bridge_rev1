# src/backtest/simulator/log_concept_mapping.py
"""Formal mapping between simulator structured-log concepts and MT4 command/result concepts.

This module defines the correspondence table required by completion_definition
section 8 (data integrity). The simulator and MT4 use different abstraction
levels for the same trade lifecycle, so this mapping ensures the concepts
are aligned and translatable.

MT4 communication protocol (file-based JSON):
  - Python -> MT4: command_queue/*.json  (action: BUY/SELL/CLOSE)
  - MT4 -> Python: result_queue/*.json   (status: filled/closed/rejected)

Simulator structured log (JSONL via trade_logger.py):
  - event_type: ENTRY / SL_HIT / TP_HIT / SIGNAL_CLOSE / FORCED_END / SKIP
  - reason_code: semantic string describing why
  - lane_id:  "range" / "trend" / "legacy"
  - trade_id: "T-{ticket:04d}"
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# event_type mapping
# ---------------------------------------------------------------------------
# Simulator event_type -> (MT4 action, MT4 result status) correspondence
#
# The simulator captures the full trade lifecycle as discrete events.
# MT4 expresses the same lifecycle as command-action + result-status pairs.
EVENT_TYPE_TO_MT4: dict[str, dict[str, str]] = {
    "ENTRY": {
        "mt4_action": "BUY or SELL",
        "mt4_status": "filled",
        "description": "Position opened. MT4 equivalent: BUY/SELL command with filled result.",
    },
    "SL_HIT": {
        "mt4_action": "N/A (server-side SL)",
        "mt4_status": "closed",
        "description": "Stop-loss triggered. MT4 handles SL at server/broker level.",
    },
    "TP_HIT": {
        "mt4_action": "N/A (server-side TP)",
        "mt4_status": "closed",
        "description": "Take-profit triggered. MT4 handles TP at server/broker level.",
    },
    "SIGNAL_CLOSE": {
        "mt4_action": "CLOSE",
        "mt4_status": "closed",
        "description": "Strategy-driven close. MT4 equivalent: CLOSE command with closed result.",
    },
    "FORCED_END": {
        "mt4_action": "CLOSE",
        "mt4_status": "closed",
        "description": "End-of-data forced close. Simulator-only (no MT4 equivalent in live trading).",
    },
    "SKIP": {
        "mt4_action": "N/A (no command issued)",
        "mt4_status": "N/A",
        "description": "Entry opportunity skipped. No MT4 command is generated.",
    },
}

# Reverse: MT4 result status -> possible simulator event_types
MT4_STATUS_TO_EVENT_TYPES: dict[str, list[str]] = {
    "filled": ["ENTRY"],
    "closed": ["SL_HIT", "TP_HIT", "SIGNAL_CLOSE", "FORCED_END"],
    "rejected": [],  # No simulator equivalent; rejection means command failed
}

# All valid simulator event_type values
VALID_EVENT_TYPES: frozenset[str] = frozenset(EVENT_TYPE_TO_MT4.keys())

# ---------------------------------------------------------------------------
# lane_id mapping
# ---------------------------------------------------------------------------
# Simulator lane_id -> MT4 entry_lane / magic_number correspondence
LANE_TO_MT4: dict[str, dict[str, str | int]] = {
    "range": {
        "mt4_entry_lane": "range",
        "mt4_magic_number": 44001,
        "description": "Range (A) lane. MT4 uses magic_number 44001.",
    },
    "trend": {
        "mt4_entry_lane": "trend",
        "mt4_magic_number": 44002,
        "description": "Trend (B) lane. MT4 uses magic_number 44002.",
    },
    "legacy": {
        "mt4_entry_lane": "N/A",
        "mt4_magic_number": 0,
        "description": "Legacy single-lane mode. Not used in multi-lane MT4 execution.",
    },
}

VALID_LANE_IDS: frozenset[str] = frozenset(LANE_TO_MT4.keys())

# ---------------------------------------------------------------------------
# trade_id mapping
# ---------------------------------------------------------------------------
# Simulator: trade_id = "T-{ticket:04d}" (sequential integer ticket, formatted)
# MT4:       command_id = UUID (assigned by Python command_writer.py)
#            ticket = integer (assigned by MT4 OrderSend)
#
# The simulator's trade_id is a deterministic sequential identifier.
# In live trading, the command_id (UUID) tracks the command lifecycle,
# and the MT4 ticket tracks the resulting position.
# The trade_id in structured logs maps to command_id conceptually
# (both uniquely identify a trade lifecycle from entry to exit).

# ---------------------------------------------------------------------------
# reason_code mapping
# ---------------------------------------------------------------------------
# Simulator exit reason_code values and their MT4 equivalents
EXIT_REASON_TO_MT4: dict[str, dict[str, str]] = {
    "sl_hit": {
        "mt4_mechanism": "Server-side SL order",
        "description": "Stop-loss hit at SL price level.",
    },
    "tp_hit": {
        "mt4_mechanism": "Server-side TP order",
        "description": "Take-profit hit at TP price level.",
    },
    "sl_same_bar_conflict": {
        "mt4_mechanism": "Server-side SL order",
        "description": "SL hit in same-bar SL+TP conflict (conservative policy).",
    },
    "tp_same_bar_conflict": {
        "mt4_mechanism": "Server-side TP order",
        "description": "TP hit in same-bar SL+TP conflict (optimistic policy).",
    },
    "signal_close": {
        "mt4_mechanism": "CLOSE command via command_queue",
        "description": "Strategy signal triggered close.",
    },
    "forced_end_of_data": {
        "mt4_mechanism": "N/A (simulator-only)",
        "description": "Position closed at end of backtest data.",
    },
}

# Simulator skip reason_code values (no MT4 equivalent - entry not attempted)
VALID_SKIP_REASON_CODES: frozenset[str] = frozenset({
    "range_reentry_blocked",
    "entry_event_not_allowed",
    "no_entry_condition",
    "hold_no_entry",
})

# All valid exit reason codes
VALID_EXIT_REASON_CODES: frozenset[str] = frozenset(EXIT_REASON_TO_MT4.keys())


def validate_event_type(event_type: str) -> bool:
    """Check if event_type is a valid simulator event type."""
    return event_type in VALID_EVENT_TYPES


def validate_lane_id(lane_id: str) -> bool:
    """Check if lane_id is a valid simulator lane identifier."""
    return lane_id in VALID_LANE_IDS
