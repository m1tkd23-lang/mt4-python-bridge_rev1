# src\main.py
from __future__ import annotations

from datetime import datetime

from mt4_bridge.config import DEFAULT_CONFIG
from mt4_bridge.json_loader import JsonLoadError
from mt4_bridge.snapshot_reader import (
    BridgeReadResult,
    SnapshotValidationError,
    read_all,
)


def print_summary(result: BridgeReadResult) -> None:
    market = result.market_snapshot
    runtime = result.runtime_status

    latest_bar = market.bars[-1] if market.bars else None

    print(f"Bridge root: {DEFAULT_CONFIG.bridge_root}")
    print(f"Runtime mode: {runtime.mode}")
    print(f"Runtime detail: {runtime.detail}")
    print(f"Terminal connected: {runtime.terminal_connected}")
    print(f"Trade allowed: {runtime.trade_allowed}")
    print(f"Runtime stale: {result.runtime_health.is_stale}")
    print(f"Runtime age seconds: {result.runtime_health.age_seconds:.2f}")
    print(f"Symbol: {market.symbol}")
    print(f"Timeframe: {market.timeframe}")
    print(f"Bid: {market.bid}")
    print(f"Ask: {market.ask}")
    print(f"Spread points: {market.spread_points}")
    print(f"Bars copied: {market.bars_copied}")
    print(f"Market stale: {result.market_health.is_stale}")
    print(f"Market age seconds: {result.market_health.age_seconds:.2f}")

    if latest_bar is None:
        print("Latest bar: none")
    else:
        print("Latest bar:")
        print(f"  Time: {latest_bar.time}")
        print(f"  Open: {latest_bar.open}")
        print(f"  High: {latest_bar.high}")
        print(f"  Low: {latest_bar.low}")
        print(f"  Close: {latest_bar.close}")
        print(f"  Tick volume: {latest_bar.tick_volume}")
        print(f"  Spread: {latest_bar.spread}")


def main() -> int:
    try:
        result = read_all(
            config=DEFAULT_CONFIG,
            now=datetime.now(),
        )
    except (JsonLoadError, SnapshotValidationError, ValueError) as exc:
        print(f"[ERROR] {exc}")
        return 1

    print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())