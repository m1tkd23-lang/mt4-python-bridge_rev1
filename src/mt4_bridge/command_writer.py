# src/mt4_bridge/command_writer.py
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from mt4_bridge.models import CommandWriteResult, SignalAction, SignalDecision


class CommandWriteError(Exception):
    """Raised when a command file cannot be written safely."""


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _build_command_dict(
    decision: SignalDecision,
    symbol: str,
    command_id: str,
) -> dict:
    payload = {
        "command_id": command_id,
        "action": decision.action.value,
        "symbol": symbol,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "strategy": decision.strategy_name,
            "reason": decision.reason,
            "previous_bar_time": (
                decision.previous_bar_time.isoformat()
                if decision.previous_bar_time is not None
                else None
            ),
            "latest_bar_time": (
                decision.latest_bar_time.isoformat()
                if decision.latest_bar_time is not None
                else None
            ),
            "previous_close": decision.previous_close,
            "latest_close": decision.latest_close,
            "current_position_type": decision.current_position_type,
            "entry_lane": decision.entry_lane,
            "entry_subtype": decision.entry_subtype,
        },
    }

    if decision.action in (SignalAction.BUY, SignalAction.SELL):
        payload["sl"] = decision.sl_price
        payload["tp"] = decision.tp_price

    if decision.action == SignalAction.CLOSE and decision.current_position_ticket is not None:
        payload["ticket"] = decision.current_position_ticket

    return payload


def write_command(
    decision: SignalDecision,
    bridge_root: Path,
    symbol: str,
) -> CommandWriteResult | None:
    if decision.action == SignalAction.HOLD:
        return None

    command_dir = bridge_root / "command_queue"
    _ensure_directory(command_dir)

    command_id = str(uuid.uuid4())
    command = _build_command_dict(
        decision=decision,
        symbol=symbol,
        command_id=command_id,
    )

    filename = f"cmd_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}.json"
    filepath = command_dir / filename
    temp_path = filepath.with_suffix(filepath.suffix + ".tmp")

    try:
        temp_path.write_text(
            json.dumps(command, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(filepath)
    except OSError as exc:
        raise CommandWriteError(f"Failed to write command: {filepath}") from exc

    return CommandWriteResult(
        command_id=command_id,
        command_path=str(filepath),
    )