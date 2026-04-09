# src\backtest\runner.py
from __future__ import annotations

import argparse
from pathlib import Path
import sys


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.csv_loader import CsvLoadError
from backtest.service import BacktestRunConfig, run_backtest, run_all_months, compare_ab
from backtest.simulator import BacktestSimulationError, IntrabarFillPolicy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a simple bar-based backtest for mt4-python-bridge strategies."
    )
    csv_group = parser.add_mutually_exclusive_group(required=True)
    csv_group.add_argument("--csv", help="Path to historical bar CSV file (single month).")
    csv_group.add_argument("--csv-dir", help="Path to directory containing monthly CSV files (all-month batch).")
    parser.add_argument(
        "--strategy",
        required=True,
        help="Strategy name, e.g. close_compare_v1 or ma_cross_v1.",
    )
    parser.add_argument(
        "--symbol",
        default="BACKTEST",
        help="Symbol name used in the simulated MarketSnapshot.",
    )
    parser.add_argument(
        "--timeframe",
        default="M1",
        help="Timeframe label used in the simulated MarketSnapshot.",
    )
    parser.add_argument(
        "--pip-size",
        type=float,
        required=True,
        help="Pip size for P/L calculation, e.g. 0.01 for JPY pairs, 0.0001 for many FX pairs.",
    )
    parser.add_argument(
        "--sl-pips",
        type=float,
        default=10.0,
        help="Stop-loss distance in pips for simulated entries.",
    )
    parser.add_argument(
        "--tp-pips",
        type=float,
        default=10.0,
        help="Take-profit distance in pips for simulated entries.",
    )
    parser.add_argument(
        "--intrabar-fill-policy",
        choices=[policy.value for policy in IntrabarFillPolicy],
        default=IntrabarFillPolicy.CONSERVATIVE.value,
        help="Conflict policy when both SL and TP are touched within the same bar.",
    )
    parser.add_argument(
        "--keep-open-position",
        action="store_true",
        help="Do not force-close any remaining open position at the end of the dataset.",
    )
    parser.add_argument(
        "--show-trades",
        type=int,
        default=5,
        help="Number of latest trades to print.",
    )
    parser.add_argument(
        "--initial-balance",
        type=float,
        default=1_000_000.0,
        help="Initial balance used for converted balance display.",
    )
    parser.add_argument(
        "--money-per-pip",
        type=float,
        default=100.0,
        help="Converted monetary value of 1 pip.",
    )
    parser.add_argument(
        "--compare-ab",
        action="store_true",
        help="Run A-lane / B-lane / A+B combo comparison. Requires --csv-dir and --strategy (combo strategy name).",
    )
    parser.add_argument(
        "--trade-log-dir",
        help="Directory to write per-month JSONL trade logs (used with --csv-dir).",
    )
    parser.add_argument(
        "--trade-log-path",
        help="Path to write JSONL trade log file (used with --csv for single month).",
    )
    return parser


def _format_profit_factor(value: float | None) -> str:
    if value is None:
        return "None"
    if value == float("inf"):
        return "inf"
    return f"{value:.2f}"


def print_summary(artifacts) -> None:
    summary = artifacts.summary

    print("Backtest result:")
    print(f"  Strategy: {summary.strategy_name}")
    print(f"  Symbol: {summary.symbol}")
    print(f"  Timeframe: {summary.timeframe}")
    print(f"  Intrabar fill policy: {summary.intrabar_fill_policy}")
    print(f"  SL pips: {summary.sl_pips}")
    print(f"  TP pips: {summary.tp_pips}")
    print(f"  Total bars: {summary.total_bars}")
    print(f"  Processed bars: {summary.processed_bars}")
    print(f"  Trades: {summary.trades}")
    print(f"  Wins: {summary.wins}")
    print(f"  Losses: {summary.losses}")
    print(f"  Win rate: {summary.win_rate_percent:.2f}%")
    print(f"  Total pips: {summary.total_pips:.2f}")
    print(f"  Average pips: {summary.average_pips:.2f}")
    print(f"  Average win pips: {summary.average_win_pips:.2f}")
    print(f"  Average loss pips: {summary.average_loss_pips:.2f}")
    print(f"  Profit factor: {_format_profit_factor(summary.profit_factor)}")
    print(f"  Max drawdown pips: {summary.max_drawdown_pips:.2f}")
    print(f"  Initial balance: {summary.initial_balance:.2f}")
    print(f"  Final balance: {summary.final_balance:.2f}")
    print(f"  Total profit amount: {summary.total_profit_amount:.2f}")
    print(f"  Return rate: {summary.return_rate_percent:.2f}%")
    print(f"  Max drawdown amount: {summary.max_drawdown_amount:.2f}")
    print(f"  Max consecutive wins: {summary.max_consecutive_wins}")
    print(f"  Max consecutive losses: {summary.max_consecutive_losses}")
    print(f"  Verdict: {summary.verdict}")
    print(f"  Verdict reasons: {'; '.join(summary.verdict_reasons) if summary.verdict_reasons else 'none'}")
    print(f"  Final open position type: {summary.final_open_position_type}")


def print_aggregate_summary(result) -> None:
    agg = result.aggregate
    print("=" * 60)
    print("All-month aggregate result:")
    print(f"  Months: {agg.month_count}")
    print(f"  Total trades: {agg.total_trades}")
    print(f"  Total wins: {agg.total_wins}")
    print(f"  Total losses: {agg.total_losses}")
    print(f"  Overall win rate: {agg.overall_win_rate:.2f}%")
    print(f"  Total pips: {agg.total_pips:.2f}")
    print(f"  Average pips/month: {agg.average_pips_per_month:.2f}")
    print(f"  Profit factor: {_format_profit_factor(agg.overall_profit_factor)}")
    print(f"  Max drawdown pips (worst month): {agg.max_drawdown_pips:.2f}")
    if agg.monthly_pips_stddev is not None:
        print(f"  Monthly pips stddev: {agg.monthly_pips_stddev:.2f}")
    else:
        print("  Monthly pips stddev: N/A")
    print(f"  Deficit months: {agg.deficit_month_count}")
    print(f"  Max consecutive deficit months: {agg.max_consecutive_deficit_months}")
    if agg.avg_mfe_mae_ratio is not None:
        print(f"  Avg MFE/MAE ratio: {agg.avg_mfe_mae_ratio:.2f}")
    else:
        print("  Avg MFE/MAE ratio: N/A")
    print()
    print("Monthly breakdown:")
    for entry in agg.monthly_entries:
        marker = " [DEFICIT]" if entry.total_pips < 0 else ""
        print(f"  {entry.label}: {entry.total_pips:.2f} pips{marker}")
    print("=" * 60)


def print_recent_trades(artifacts, show_trades: int) -> None:
    if show_trades <= 0:
        return

    trade_rows = artifacts.trade_rows[-show_trades:]
    if not trade_rows:
        print("Recent trades: none")
        return

    print("Recent trades:")
    for row in trade_rows:
        print(
            "  "
            f"#{row.trade_no} "
            f"{row.position_type.upper()} "
            f"entry={row.entry_time} @{row.entry_price} "
            f"exit={row.exit_time} @{row.exit_price} "
            f"pips={row.pips:.2f} "
            f"cum_pips={row.cumulative_pips:.2f} "
            f"balance={row.balance_after_trade:.2f} "
            f"reason={row.exit_reason}"
        )


def print_compare_ab_table(result) -> None:
    a = result.lane_a_result.aggregate
    b = result.lane_b_result.aggregate
    c = result.combo_result.aggregate

    labels = [
        f"A ({result.lane_a_strategy})",
        f"B ({result.lane_b_strategy})",
        f"A+B ({result.combo_strategy})",
    ]
    aggregates = [a, b, c]

    col_width = max(len(lbl) for lbl in labels) + 2
    col_width = max(col_width, 16)
    metric_width = 30

    header = f"{'Metric':<{metric_width}}"
    for lbl in labels:
        header += f"{lbl:>{col_width}}"
    sep = "=" * len(header)

    print(sep)
    print("A / B / A+B Comparison")
    print(sep)
    print(header)
    print("-" * len(header))

    rows = [
        ("Months", [str(ag.month_count) for ag in aggregates]),
        ("Total trades", [str(ag.total_trades) for ag in aggregates]),
        ("Total wins", [str(ag.total_wins) for ag in aggregates]),
        ("Total losses", [str(ag.total_losses) for ag in aggregates]),
        ("Win rate (%)", [f"{ag.overall_win_rate:.2f}" for ag in aggregates]),
        ("Total pips", [f"{ag.total_pips:.2f}" for ag in aggregates]),
        ("Avg pips/month", [f"{ag.average_pips_per_month:.2f}" for ag in aggregates]),
        ("Profit factor", [_format_profit_factor(ag.overall_profit_factor) for ag in aggregates]),
        ("Max DD pips", [f"{ag.max_drawdown_pips:.2f}" for ag in aggregates]),
        ("Pips stddev", [
            f"{ag.monthly_pips_stddev:.2f}" if ag.monthly_pips_stddev is not None else "N/A"
            for ag in aggregates
        ]),
        ("Deficit months", [str(ag.deficit_month_count) for ag in aggregates]),
        ("Max consec deficit", [str(ag.max_consecutive_deficit_months) for ag in aggregates]),
        ("Avg MFE/MAE ratio", [
            f"{ag.avg_mfe_mae_ratio:.2f}" if ag.avg_mfe_mae_ratio is not None else "N/A"
            for ag in aggregates
        ]),
    ]

    for metric, values in rows:
        line = f"{metric:<{metric_width}}"
        for val in values:
            line += f"{val:>{col_width}}"
        print(line)

    print(sep)

    # Monthly breakdown
    print()
    print("Monthly pips breakdown:")
    month_header = f"{'Month':<{metric_width}}"
    for lbl in labels:
        month_header += f"{lbl:>{col_width}}"
    print(month_header)
    print("-" * len(month_header))

    for i, entry_a in enumerate(a.monthly_entries):
        label = entry_a.label
        vals = []
        for ag in aggregates:
            if i < len(ag.monthly_entries):
                vals.append(f"{ag.monthly_entries[i].total_pips:.2f}")
            else:
                vals.append("N/A")
        line = f"{label:<{metric_width}}"
        for val in vals:
            line += f"{val:>{col_width}}"
        print(line)

    print(sep)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.compare_ab:
        if not args.csv_dir:
            print("[ERROR] --compare-ab requires --csv-dir")
            return 1
        return _run_compare_ab(args)
    elif args.csv_dir:
        return _run_all_months(args)
    else:
        return _run_single(args)


def _run_single(args) -> int:
    trade_log_path = Path(args.trade_log_path) if args.trade_log_path else None
    try:
        artifacts = run_backtest(
            BacktestRunConfig(
                csv_path=Path(args.csv),
                strategy_name=args.strategy,
                symbol=args.symbol,
                timeframe=args.timeframe,
                pip_size=args.pip_size,
                sl_pips=args.sl_pips,
                tp_pips=args.tp_pips,
                intrabar_fill_policy=IntrabarFillPolicy(args.intrabar_fill_policy),
                close_open_position_at_end=not args.keep_open_position,
                initial_balance=args.initial_balance,
                money_per_pip=args.money_per_pip,
                trade_log_path=trade_log_path,
            )
        )
    except (CsvLoadError, BacktestSimulationError, ValueError) as exc:
        print(f"[ERROR] {exc}")
        return 1

    print_summary(artifacts)
    print_recent_trades(artifacts, args.show_trades)
    return 0


def _run_all_months(args) -> int:
    trade_log_dir = Path(args.trade_log_dir) if args.trade_log_dir else None
    try:
        result = run_all_months(
            csv_dir=Path(args.csv_dir),
            strategy_name=args.strategy,
            symbol=args.symbol,
            timeframe=args.timeframe,
            pip_size=args.pip_size,
            sl_pips=args.sl_pips,
            tp_pips=args.tp_pips,
            intrabar_fill_policy=IntrabarFillPolicy(args.intrabar_fill_policy),
            close_open_position_at_end=not args.keep_open_position,
            initial_balance=args.initial_balance,
            money_per_pip=args.money_per_pip,
            trade_log_dir=trade_log_dir,
        )
    except (CsvLoadError, BacktestSimulationError, ValueError) as exc:
        print(f"[ERROR] {exc}")
        return 1

    for label, artifacts in result.monthly_artifacts:
        print(f"\n--- {label} ---")
        print_summary(artifacts)

    print()
    print_aggregate_summary(result)
    return 0


def _run_compare_ab(args) -> int:
    trade_log_dir = Path(args.trade_log_dir) if args.trade_log_dir else None
    try:
        result = compare_ab(
            csv_dir=Path(args.csv_dir),
            combo_strategy_name=args.strategy,
            symbol=args.symbol,
            timeframe=args.timeframe,
            pip_size=args.pip_size,
            sl_pips=args.sl_pips,
            tp_pips=args.tp_pips,
            intrabar_fill_policy=IntrabarFillPolicy(args.intrabar_fill_policy),
            close_open_position_at_end=not args.keep_open_position,
            initial_balance=args.initial_balance,
            money_per_pip=args.money_per_pip,
            trade_log_dir=trade_log_dir,
        )
    except (CsvLoadError, BacktestSimulationError, ValueError) as exc:
        print(f"[ERROR] {exc}")
        return 1

    print_compare_ab_table(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())