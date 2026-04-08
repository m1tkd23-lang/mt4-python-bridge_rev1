# src\backtest\runner.py
from __future__ import annotations

import argparse
from pathlib import Path
import sys


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.csv_loader import CsvLoadError
from backtest.service import BacktestRunConfig, run_backtest
from backtest.simulator import BacktestSimulationError, IntrabarFillPolicy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a simple bar-based backtest for mt4-python-bridge strategies."
    )
    parser.add_argument("--csv", required=True, help="Path to historical bar CSV file.")
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


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

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
            )
        )
    except (CsvLoadError, BacktestSimulationError, ValueError) as exc:
        print(f"[ERROR] {exc}")
        return 1

    print_summary(artifacts)
    print_recent_trades(artifacts, args.show_trades)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())