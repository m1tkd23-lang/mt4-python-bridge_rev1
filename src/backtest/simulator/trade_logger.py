# src/backtest/simulator/trade_logger.py
from __future__ import annotations

import json
import logging
from pathlib import Path

from backtest.simulator.log_concept_mapping import (
    VALID_EVENT_TYPES,
    VALID_EXIT_REASON_CODES,
    VALID_LANE_IDS,
    VALID_SKIP_REASON_CODES,
)
from backtest.simulator.models import BacktestDecisionLog, BacktestResult, ExecutedTrade

logger = logging.getLogger(__name__)


# Exit reason -> event_type mapping.
# Aligned with log_concept_mapping.EVENT_TYPE_TO_MT4 / EXIT_REASON_TO_MT4.
_EXIT_REASON_TO_EVENT_TYPE: dict[str, str] = {
    "sl_hit": "SL_HIT",
    "tp_hit": "TP_HIT",
    "sl_same_bar_conflict": "SL_HIT",
    "tp_same_bar_conflict": "TP_HIT",
    "signal_close": "SIGNAL_CLOSE",
    "forced_end_of_data": "FORCED_END",
}


def _exit_event_type(exit_reason: str) -> str:
    event_type = _EXIT_REASON_TO_EVENT_TYPE.get(exit_reason, "EXIT")
    if event_type not in VALID_EVENT_TYPES:
        logger.warning(
            "Unmapped exit_reason '%s' produced non-standard event_type '%s'",
            exit_reason,
            event_type,
        )
    return event_type


def _derive_entry_reason_code(trade: ExecutedTrade) -> str:
    lane = trade.lane or "legacy"
    pos = trade.position_type
    return f"{lane}_{pos}_entry"


def _derive_exit_reason_code(trade: ExecutedTrade) -> str:
    return trade.exit_reason


def _format_time(t: object) -> str:
    return str(t)


def _derive_skip_reason_code(reason: str) -> str:
    lower = reason.lower()
    if "reentry blocked" in lower:
        return "range_reentry_blocked"
    if "entry blocked" in lower or "not an allowed entry event" in lower:
        return "entry_event_not_allowed"
    if "no entry condition matched" in lower:
        return "no_entry_condition"
    return "hold_no_entry"


def _is_skip_decision(log: BacktestDecisionLog) -> bool:
    if log.action != "hold":
        return False
    if log.current_position_ticket is not None:
        return False
    if log.has_range_position or log.has_trend_position or log.has_legacy_position:
        return False
    return True


def _validate_reason_code(event: dict[str, object], context: str) -> None:
    """Validate that reason_code exists and is non-empty. Logs a warning if missing."""
    reason_code = event.get("reason_code")
    if not reason_code:
        logger.warning(
            "reason_code missing or empty in %s event (event_type=%s, context=%s)",
            event.get("event_type", "UNKNOWN"),
            event.get("event_type"),
            context,
        )
        raise ValueError(
            f"reason_code is required for structured log events: "
            f"event_type={event.get('event_type')}, context={context}"
        )


def build_skip_events(
    decision_logs: list[BacktestDecisionLog],
    strategy_name: str,
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for log in decision_logs:
        if not _is_skip_decision(log):
            continue
        event: dict[str, object] = {
            "event_type": "SKIP",
            "strategy_name": strategy_name,
            "lane_id": log.entry_lane or "legacy",
            "reason_code": _derive_skip_reason_code(log.reason),
            "reason": log.reason,
            "bar_time": _format_time(log.bar_time),
            "market_state": log.market_state,
        }
        _validate_reason_code(event, f"SKIP at {log.bar_time}")
        events.append(event)
    return events


def build_trade_lifecycle_events(
    result: BacktestResult,
    strategy_name: str,
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for trade in result.trades:
        trade_id = trade.trade_id
        lane_id = trade.lane or "legacy"

        entry_event: dict[str, object] = {
            "event_type": "ENTRY",
            "trade_id": trade_id,
            "lane_id": lane_id,
            "strategy_name": strategy_name,
            "position_type": trade.position_type,
            "reason_code": _derive_entry_reason_code(trade),
            "entry_price": trade.entry_price,
            "entry_time": _format_time(trade.entry_time),
            "entry_signal_reason": trade.entry_signal_reason,
            "entry_market_state": trade.entry_market_state,
        }
        _validate_reason_code(entry_event, f"ENTRY trade_id={trade_id}")
        events.append(entry_event)

        exit_event: dict[str, object] = {
            "event_type": _exit_event_type(trade.exit_reason),
            "trade_id": trade_id,
            "lane_id": lane_id,
            "strategy_name": strategy_name,
            "position_type": trade.position_type,
            "reason_code": _derive_exit_reason_code(trade),
            "exit_price": trade.exit_price,
            "exit_time": _format_time(trade.exit_time),
            "pips": trade.pips,
            "mfe_pips": trade.mfe_pips,
            "mae_pips": trade.mae_pips,
            "holding_bars": trade.holding_bars,
            "exit_signal_reason": trade.exit_signal_reason,
            "exit_market_state": trade.exit_market_state,
        }
        _validate_reason_code(exit_event, f"EXIT trade_id={trade_id}")
        events.append(exit_event)

    return events


def write_trade_log_jsonl(
    result: BacktestResult,
    strategy_name: str,
    output_path: Path,
    *,
    include_skip_events: bool = True,
) -> int:
    events = build_trade_lifecycle_events(result, strategy_name)
    if include_skip_events:
        skip_events = build_skip_events(result.decision_logs, strategy_name)
        events.extend(skip_events)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
    return len(events)
