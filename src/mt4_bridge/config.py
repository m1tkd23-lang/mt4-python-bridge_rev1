# src\mt4_bridge\config.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BridgeConfig:
    bridge_root: Path
    market_snapshot_filename: str = "market_snapshot.json"
    runtime_status_filename: str = "runtime_status.json"
    market_stale_seconds: int = 10
    runtime_stale_seconds: int = 10

    @property
    def market_snapshot_path(self) -> Path:
        return self.bridge_root / self.market_snapshot_filename

    @property
    def runtime_status_path(self) -> Path:
        return self.bridge_root / self.runtime_status_filename


DEFAULT_CONFIG = BridgeConfig(
    bridge_root=Path(
        r"C:\Users\tokuda\AppData\Roaming\MetaQuotes\Terminal\F1DD1D6E7C4A311D1B1CA0D34E33291D\MQL4\Files\mt4-python-bridge"
    )
)