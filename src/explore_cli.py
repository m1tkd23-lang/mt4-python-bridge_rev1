# src/explore_cli.py
"""CLI entry point for the tactical exploration loop.

Usage:
    python -m explore_cli data/USDJPY-cd1.csv
    python -m explore_cli data/USDJPY-cd1.csv --signal-type ma_cross --max-iterations 20
"""
from __future__ import annotations

import argparse
import logging
import sys

from backtest.exploration_loop import LoopConfig, run_exploration_loop

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
        description="Run the tactical exploration loop.",
    )
    parser.add_argument(
        "csv_path",
        help="Path to the historical bars CSV file (required).",
    )
    parser.add_argument(
        "--signal-type",
        default="ma_cross",
        help="Signal type to explore (default: ma_cross).",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum loop iterations (default: 10).",
    )
    parser.add_argument(
        "--base-name",
        default="strategy",
        help="Base strategy name prefix (default: strategy).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    _setup_exploration_logging()
    logger = logging.getLogger(__name__)

    config = LoopConfig(
        signal_type=args.signal_type,
        csv_path=args.csv_path,
        base_strategy_name=args.base_name,
        max_iterations=args.max_iterations,
    )

    logger.info(
        "Starting exploration: csv=%s signal_type=%s max_iterations=%d",
        config.csv_path,
        config.signal_type,
        config.max_iterations,
    )

    try:
        result = run_exploration_loop(config)
    except Exception:
        logger.exception("Exploration loop failed with an unexpected error")
        return 1

    logger.info(
        "Exploration finished: iterations=%d stopped_reason=%s adopted=%s",
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
            f"  win_rate={s.get('win_rate', 0):.1%}"
            f"  max_dd={s.get('max_drawdown_pips', 0):.1f}pips"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
