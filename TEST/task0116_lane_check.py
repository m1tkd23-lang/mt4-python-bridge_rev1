"""Quick check of lane distribution for v4_4 strategies on one month."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from backtest.service import BacktestRunConfig, run_backtest
from backtest.simulator.intrabar import IntrabarFillPolicy


def check(strategy: str):
    csv_path = ROOT / "data" / "USDJPY-cd5_20250521_monthly" / "USDJPY-cd5_20250521_2025-11.csv"
    config = BacktestRunConfig(
        csv_path=csv_path,
        strategy_name=strategy,
        symbol="USDJPY",
        timeframe="M1",
        pip_size=0.01,
        sl_pips=10.0,
        tp_pips=10.0,
        intrabar_fill_policy=IntrabarFillPolicy.CONSERVATIVE,
        close_open_position_at_end=True,
        initial_balance=1_000_000.0,
        money_per_pip=100.0,
    )
    artifacts = run_backtest(config)
    trades = artifacts.backtest_result.trades
    lanes = Counter(t.lane for t in trades)
    middle_none = sum(1 for t in trades if t.entry_middle_band is None)
    print(f"[{strategy}] trades={len(trades)} lanes={dict(lanes)} entry_middle_band_none={middle_none}")


if __name__ == "__main__":
    check("bollinger_range_v4_4")
    check("bollinger_range_v4_4_tuned_a")
