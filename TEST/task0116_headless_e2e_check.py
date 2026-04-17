"""TASK-0116 headless e2e verification.

Mimics AllMonthsWorker.run() + AllMonthsTab display paths to validate
that real 12-month USDJPY CSV data flows through the monthly MR 5-col
display and the all-period MR panel exactly as the GUI would render it.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from backtest.mean_reversion_analysis import (
    AllMonthsMeanReversionSummary,
    MeanReversionSummary,
    analyze_all_months_mean_reversion,
)
from backtest.service import run_all_months
from backtest.simulator.intrabar import IntrabarFillPolicy


def _format_optional_percent(value):
    return "N/A" if value is None else f"{value:.2f}%"


def _format_optional_number(value):
    return "N/A" if value is None else f"{value:.2f}"


def simulate_monthly_row(label, stats, mr):
    mr_trades = str(mr.total_range_trades) if mr is not None else "N/A"
    mr_fail = str(mr.reversion_failure_count) if mr is not None else "N/A"
    mr_succ5 = str(mr.success_within_5_count) if mr is not None else "N/A"
    mr_rate5 = (
        _format_optional_percent(mr.success_within_5_rate)
        if mr is not None
        else "N/A"
    )
    mr_avg_bars = (
        _format_optional_number(mr.avg_bars_to_reversion)
        if mr is not None
        else "N/A"
    )
    return [
        label,
        stats.trades,
        mr_trades,
        mr_fail,
        mr_succ5,
        mr_rate5,
        mr_avg_bars,
    ]


def simulate_mr_panel(mr_summary):
    if mr_summary is None:
        return {k: "N/A" for k in [
            "total_range_trades",
            "reversion_failure_count",
            "reversion_success_count",
            "success_rate",
            "avg_bars_to_reversion",
            "success_within_3",
            "success_within_5",
            "success_within_8",
            "success_within_12",
            "avg_max_progress_ratio",
            "avg_max_adverse_excursion",
        ]}
    agg = mr_summary.all_period
    return {
        "total_range_trades": str(agg.total_range_trades),
        "reversion_failure_count": str(agg.reversion_failure_count),
        "reversion_success_count": str(agg.reversion_success_count),
        "success_rate": _format_optional_percent(agg.success_rate),
        "avg_bars_to_reversion": _format_optional_number(agg.avg_bars_to_reversion),
        "success_within_3": f"{agg.success_within_3_count} ({_format_optional_percent(agg.success_within_3_rate)})",
        "success_within_5": f"{agg.success_within_5_count} ({_format_optional_percent(agg.success_within_5_rate)})",
        "success_within_8": f"{agg.success_within_8_count} ({_format_optional_percent(agg.success_within_8_rate)})",
        "success_within_12": f"{agg.success_within_12_count} ({_format_optional_percent(agg.success_within_12_rate)})",
        "avg_max_progress_ratio": _format_optional_number(agg.avg_max_progress_ratio),
        "avg_max_adverse_excursion": _format_optional_number(agg.avg_max_adverse_excursion),
    }


def main():
    csv_dir = ROOT / "data" / "USDJPY-cd5_20250521_monthly"
    strategy = "bollinger_range_v4_4"

    print(f"[config] csv_dir={csv_dir}")
    print(f"[config] strategy={strategy}")

    def progress(done, total):
        print(f"[progress] {done}/{total}")

    result = run_all_months(
        csv_dir=csv_dir,
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
        progress_callback=progress,
    )

    print(f"\n[artifacts] monthly_count={len(result.monthly_artifacts)}")
    assert len(result.monthly_artifacts) == 12, "expected 12 months"

    try:
        mr_summary = analyze_all_months_mean_reversion(result.monthly_artifacts)
    except Exception as exc:
        print(f"[MR ANALYSIS ERROR] {type(exc).__name__}: {exc}")
        mr_summary = None

    assert mr_summary is not None, "MR summary must not be None for real data"
    assert isinstance(mr_summary, AllMonthsMeanReversionSummary)
    assert len(mr_summary.monthly) == 12

    mr_by_label = {lbl: s for lbl, s in mr_summary.monthly}

    print("\n=== monthly_table (simulated GUI rows) ===")
    print(f"{'Month':40} {'Trades':>7} {'MRtr':>5} {'MRfl':>5} {'S<=5':>5} {'S<=5%':>8} {'AvgB':>6}")
    zero_range_months = 0
    for label, artifacts in result.monthly_artifacts:
        stats = artifacts.backtest_result.stats
        mr = mr_by_label.get(label)
        row = simulate_monthly_row(label, stats, mr)
        print(f"{row[0]:40} {row[1]:>7} {row[2]:>5} {row[3]:>5} {row[4]:>5} {row[5]:>8} {row[6]:>6}")
        if mr is not None and mr.total_range_trades == 0:
            zero_range_months += 1
            # row must not crash - verify rendered as numeric 0 or N/A
            assert row[2] == "0", f"zero-range month should show 0 mr trades, got {row[2]}"

    print(f"\n[zero-range months] {zero_range_months}")

    print("\n=== all_period MR panel (simulated GUI labels) ===")
    panel = simulate_mr_panel(mr_summary)
    for k, v in panel.items():
        print(f"  {k:32} = {v}")

    # sanity: monthly MR counts sum == all_period total_range_trades
    monthly_total = sum(s.total_range_trades for _, s in mr_summary.monthly)
    all_period_total = mr_summary.all_period.total_range_trades
    assert monthly_total == all_period_total, (
        f"monthly MR total {monthly_total} != all_period {all_period_total}"
    )
    print(f"\n[consistency] monthly_sum total_range_trades = all_period total_range_trades = {all_period_total}")

    print("\n=== OK: headless e2e check passed ===")


if __name__ == "__main__":
    main()
