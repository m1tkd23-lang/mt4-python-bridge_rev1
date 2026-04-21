# src/backtest/export.py
"""Utilities to export BacktestResult data to CSV for external analysis."""
from __future__ import annotations

import csv
from dataclasses import fields
from pathlib import Path
from typing import Iterable

from backtest.simulator.models import (
    BacktestDecisionLog,
    BacktestResult,
    ExecutedTrade,
)


def _flatten_value(value: object) -> object:
    if isinstance(value, dict):
        return repr(value)
    return value


def _write_dataclass_rows(
    path: Path,
    rows: Iterable,
    field_names: list[str],
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=field_names)
        writer.writeheader()
        for row in rows:
            record = {name: _flatten_value(getattr(row, name)) for name in field_names}
            writer.writerow(record)
            written += 1
    return written


def export_trades_csv(result: BacktestResult, path: Path) -> int:
    field_names = [f.name for f in fields(ExecutedTrade)]
    return _write_dataclass_rows(path, result.trades, field_names)


def export_decision_logs_csv(result: BacktestResult, path: Path) -> int:
    field_names = [f.name for f in fields(BacktestDecisionLog)]
    return _write_dataclass_rows(path, result.decision_logs, field_names)


def get_bar_level_logs_for_trade(
    result: BacktestResult,
    trade: ExecutedTrade,
) -> list[BacktestDecisionLog]:
    if trade.entry_bar_index is None or trade.exit_bar_index is None:
        return [
            log for log in result.decision_logs
            if trade.entry_time <= log.bar_time <= trade.exit_time
        ]
    entry_time = trade.entry_time
    exit_time = trade.exit_time
    return [
        log for log in result.decision_logs
        if entry_time <= log.bar_time <= exit_time
    ]


def export_bar_level_log_for_trade(
    result: BacktestResult,
    trade: ExecutedTrade,
    path: Path,
) -> int:
    logs = get_bar_level_logs_for_trade(result, trade)
    field_names = [f.name for f in fields(BacktestDecisionLog)]
    return _write_dataclass_rows(path, logs, field_names)
