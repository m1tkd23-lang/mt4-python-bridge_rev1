# src\explore_cli.py
"""CLI entry point for exploration loops.

Usage:
    python -m explore_cli data/USDJPY-cd1.csv
    python -m explore_cli data/USDJPY-cd1.csv --signal-type ma_cross --max-iterations 20

Bollinger mode examples:
    python -m explore_cli data/USDJPY-cd5_20250521_monthly/USDJPY-cd5_20250521_2025-05.csv \
        --mode bollinger \
        --strategy-name bollinger_range_v4_4 \
        --csv-dir data/USDJPY-cd5_20250521_monthly \
        --max-iterations 3

    python -m explore_cli data/USDJPY-cd5_20250521_monthly/USDJPY-cd5_20250521_2025-05.csv \
        --mode bollinger \
        --strategy-name bollinger_trend_B \
        --csv-dir data/USDJPY-cd5_20250521_monthly \
        --max-iterations 3
"""
from __future__ import annotations

import argparse
import logging
import sys

from backtest.exploration_loop import (
    BollingerLoopConfig,
    LoopConfig,
    run_bollinger_exploration_loop,
    run_exploration_loop,
)

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _setup_exploration_logging() -> None:
    """Configure root logger so exploration loop messages appear on the terminal."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
        root.addHandler(handler)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run exploration loops (generic or bollinger-specific).",
    )
    parser.add_argument(
        "csv_path",
        help="Path to the historical bars CSV file (required).",
    )
    parser.add_argument(
        "--mode",
        choices=("generic", "bollinger"),
        default="generic",
        help="Exploration mode: generic template loop or bollinger override loop (default: generic).",
    )
    parser.add_argument(
        "--signal-type",
        default="ma_cross",
        help="Signal type for generic exploration (default: ma_cross).",
    )
    parser.add_argument(
        "--strategy-name",
        default="bollinger_range_v4_4",
        help=(
            "Strategy name for bollinger exploration "
            "(default: bollinger_range_v4_4)."
        ),
    )
    parser.add_argument(
        "--csv-dir",
        default=None,
        help="Optional directory of monthly CSV files for cross-month evaluation.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum loop iterations (default: 10).",
    )
    parser.add_argument(
        "--max-improve-retries",
        type=int,
        default=1,
        help="Maximum improve retries per candidate (default: 1).",
    )
    parser.add_argument(
        "--max-param-variations",
        type=int,
        default=3,
        help="Maximum generated parameter variations (default: 3).",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=42,
        help="Random seed for reproducible exploration (default: 42).",
    )
    parser.add_argument(
        "--base-name",
        default="strategy",
        help="Base strategy name prefix for generic mode (default: strategy).",
    )
    parser.add_argument(
        "--symbol",
        default="BACKTEST",
        help="Symbol used in backtest metadata (default: BACKTEST).",
    )
    parser.add_argument(
        "--timeframe",
        default="M5",
        help="Timeframe used in backtest metadata (default: M5).",
    )
    parser.add_argument(
        "--pip-size",
        type=float,
        default=0.01,
        help="Pip size for the instrument (default: 0.01).",
    )
    parser.add_argument(
        "--sl-pips",
        type=float,
        default=10.0,
        help="Stop-loss in pips (default: 10.0).",
    )
    parser.add_argument(
        "--tp-pips",
        type=float,
        default=10.0,
        help="Take-profit in pips (default: 10.0).",
    )
    return parser


def _run_generic_mode(args: argparse.Namespace) -> int:
    logger = logging.getLogger(__name__)

    config = LoopConfig(
        signal_type=args.signal_type,
        csv_path=args.csv_path,
        base_strategy_name=args.base_name,
        symbol=args.symbol,
        timeframe=args.timeframe,
        pip_size=args.pip_size,
        sl_pips=args.sl_pips,
        tp_pips=args.tp_pips,
        max_iterations=args.max_iterations,
        max_improve_retries=args.max_improve_retries,
        max_param_variations=args.max_param_variations,
        random_seed=args.random_seed,
        csv_dir=args.csv_dir,
    )

    logger.info(
        "Starting generic exploration: csv=%s signal_type=%s max_iterations=%d",
        config.csv_path,
        config.signal_type,
        config.max_iterations,
    )

    try:
        result = run_exploration_loop(config)
    except Exception:
        logger.exception("Generic exploration loop failed with an unexpected error")
        return 1

    logger.info(
        "Generic exploration finished: iterations=%d stopped_reason=%s adopted=%s",
        result.iterations,
        result.stopped_reason,
        result.adopted.strategy_name if result.adopted else "none",
    )

    if result.adopted:
        print(f"Adopted strategy: {result.adopted.strategy_name}")
        print(f"  File: {result.adopted.strategy_file}")
        print(f"  Verdict: {result.adopted.verdict}")
    else:
        print(f"No strategy adopted (stopped: {result.stopped_reason})")

    print(f"Total iterations: {result.iterations}")
    for i, r in enumerate(result.results, 1):
        s = r.evaluation.stats_summary
        pf = s.get("profit_factor")
        pf_str = f"{pf:.2f}" if pf is not None else "N/A"
        print(
            f"  [{i}] {r.strategy_name}  verdict={r.verdict}"
            f"  pf={pf_str}  total_pips={s.get('total_pips', 0):.1f}"
            f"  win_rate={s.get('win_rate', 0):.1f}%"
            f"  max_dd={s.get('max_drawdown_pips', 0):.1f}pips"
        )

    return 0


def _run_bollinger_mode(args: argparse.Namespace) -> int:
    logger = logging.getLogger(__name__)

    config = BollingerLoopConfig(
        strategy_name=args.strategy_name,
        csv_path=args.csv_path,
        symbol=args.symbol,
        timeframe=args.timeframe,
        pip_size=args.pip_size,
        sl_pips=args.sl_pips,
        tp_pips=args.tp_pips,
        max_iterations=args.max_iterations,
        max_improve_retries=args.max_improve_retries,
        max_param_variations=args.max_param_variations,
        random_seed=args.random_seed,
        csv_dir=args.csv_dir,
    )

    logger.info(
        "Starting bollinger exploration: strategy=%s csv=%s csv_dir=%s max_iterations=%d",
        config.strategy_name,
        config.csv_path,
        config.csv_dir,
        config.max_iterations,
    )

    try:
        result = run_bollinger_exploration_loop(config)
    except Exception:
        logger.exception("Bollinger exploration loop failed with an unexpected error")
        return 1

    logger.info(
        "Bollinger exploration finished: iterations=%d stopped_reason=%s adopted=%s",
        result.iterations,
        result.stopped_reason,
        result.adopted.param_overrides if result.adopted else "none",
    )

    if result.adopted:
        print(f"Adopted bollinger strategy: {result.adopted.strategy_name}")
        print(f"  Verdict: {result.adopted.verdict}")
        print(f"  Param overrides: {result.adopted.param_overrides}")
    else:
        print(f"No bollinger parameters adopted (stopped: {result.stopped_reason})")

    print(f"Total iterations: {result.iterations}")
    for i, r in enumerate(result.results, 1):
        s = r.evaluation.stats_summary
        pf = s.get("profit_factor")
        pf_str = f"{pf:.2f}" if pf is not None else "N/A"

        line = (
            f"  [{i}] {r.strategy_name}  verdict={r.verdict}"
            f"  pf={pf_str}  total_pips={s.get('total_pips', 0):.1f}"
            f"  win_rate={s.get('win_rate', 0):.1f}%"
            f"  max_dd={s.get('max_drawdown_pips', 0):.1f}pips"
            f"  overrides={r.param_overrides}"
        )

        if r.aggregate_stats is not None:
            line += (
                f"  agg_total={r.aggregate_stats.total_pips:.1f}"
                f"  avg_month={r.aggregate_stats.average_pips_per_month:.1f}"
            )

        print(line)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    _setup_exploration_logging()

    if args.mode == "bollinger":
        return _run_bollinger_mode(args)

    return _run_generic_mode(args)


if __name__ == "__main__":
    raise SystemExit(main())