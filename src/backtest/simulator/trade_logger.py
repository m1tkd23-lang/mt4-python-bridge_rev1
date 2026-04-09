# src/backtest/simulator/trade_logger.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from backtest.simulator.models import BacktestResult, ExecutedTrade


_EXIT_REASON_TO_EVENT_TYPE: dict[str, str] = {
    "sl_hit": "SL_HIT",
    "tp_hit": "TP_HIT",
    "sl_same_bar_conflict": "SL_HIT",
    "tp_same_bar_conflict": "TP_HIT",
    "signal_close": "SIGNAL_CLOSE",
    "forced_end_of_data": "FORCED_END",
}


def _exit_event_type(exit_reason: str) -> str:
    return _EXIT_REASON_TO_EVENT_TYPE.get(exit_reason, "EXIT")


def _derive_entry_reason_code(trade: ExecutedTrade) -> str:
    lane = trade.lane or "legacy"
    pos = trade.position_type
    return f"{lane}_{pos}_entry"


def _derive_exit_reason_code(trade: ExecutedTrade) -> str:
    return trade.exit_reason


def _format_time(t: object) -> str:
    return str(t)


def build_trade_lifecycle_events(
    result: BacktestResult,
    strategy_name: str,
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for trade in result.trades:
        trade_id = trade.trade_id or "unknown"
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
        events.append(exit_event)

    return events


def write_trade_log_jsonl(
    result: BacktestResult,
    strategy_name: str,
    output_path: Path,
) -> int:
    events = build_trade_lifecycle_events(result, strategy_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
    return len(events)
