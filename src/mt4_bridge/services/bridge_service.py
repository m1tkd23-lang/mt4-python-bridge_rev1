# src\mt4_bridge\services\bridge_service.py
from __future__ import annotations

from datetime import datetime

from mt4_bridge.app_config import AppConfig
from mt4_bridge.models import BridgeReadResult
from mt4_bridge.result_reader import read_result_queue
from mt4_bridge.snapshot_reader import (
    build_read_result,
    read_market_snapshot,
    read_position_snapshot,
    read_runtime_status,
)


class BridgeService:
    """Service layer shared by future CLI and GUI entry points."""

    def __init__(self, app_config: AppConfig) -> None:
        self._config = app_config

    @property
    def app_config(self) -> AppConfig:
        return self._config

    def read_current_state(self, now: datetime | None = None) -> BridgeReadResult:
        resolved_now = now or datetime.now()

        runtime_status = read_runtime_status(self._config.bridge.runtime_status_path)
        market_snapshot = read_market_snapshot(self._config.bridge.market_snapshot_path)
        position_snapshot = read_position_snapshot(self._config.bridge.position_snapshot_path)
        results = read_result_queue(self._config.bridge.result_queue_path)

        return build_read_result(
            market_snapshot=market_snapshot,
            runtime_status=runtime_status,
            position_snapshot=position_snapshot,
            results=results,
            market_stale_seconds=self._config.snapshot.market_stale_seconds,
            runtime_stale_seconds=self._config.snapshot.runtime_stale_seconds,
            now=resolved_now,
        )