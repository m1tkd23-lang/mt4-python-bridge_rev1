# src/backtest/exploration_loop.py
"""Tactical exploration loop: generate → backtest → evaluate → verdict.

This module orchestrates exploration cycles of strategy generation and evaluation.
It supports both single-cycle execution (run_single_exploration) and multi-cycle
loop execution (run_exploration_loop) with verdict-based control flow.
"""
from __future__ import annotations

import logging
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from mt4_bridge.strategy_generator import generate_param_variations, generate_strategy_file
from backtest.csv_loader import load_historical_bars_csv
from backtest.simulator import BacktestSimulator, IntrabarFillPolicy
from backtest.evaluator import (
    EvaluationResult,
    EvaluationThresholds,
    evaluate_backtest,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExplorationConfig:
    """Configuration for a single exploration cycle."""

    signal_type: str
    strategy_name: str
    csv_path: str
    symbol: str = "BACKTEST"
    timeframe: str = "M1"
    pip_size: float = 0.01
    sl_pips: float = 10.0
    tp_pips: float = 10.0
    intrabar_fill_policy: IntrabarFillPolicy = IntrabarFillPolicy.CONSERVATIVE
    strategy_params: dict[str, object] | None = None
    thresholds: EvaluationThresholds | None = None


@dataclass(frozen=True)
class ExplorationResult:
    """Result of a single exploration cycle."""

    strategy_name: str
    strategy_file: str
    evaluation: EvaluationResult
    verdict: str


def run_single_exploration(config: ExplorationConfig) -> ExplorationResult:
    """Execute one exploration cycle: generate → backtest → evaluate.

    Args:
        config: Configuration for this exploration cycle.

    Returns:
        ExplorationResult containing the verdict and evaluation details.

    Raises:
        ValueError: If strategy_name or signal_type is invalid.
        backtest.csv_loader.CsvLoadError: If the CSV file cannot be loaded.
        backtest.simulator.BacktestSimulationError: If the backtest fails.
    """
    # 1. Generate strategy file
    strategy_file = generate_strategy_file(
        strategy_name=config.strategy_name,
        signal_type=config.signal_type,
        params=config.strategy_params,
    )

    # 2. Load historical data
    dataset = load_historical_bars_csv(Path(config.csv_path))

    # 3. Run backtest
    simulator = BacktestSimulator(
        strategy_name=config.strategy_name,
        symbol=config.symbol,
        timeframe=config.timeframe,
        pip_size=config.pip_size,
        sl_pips=config.sl_pips,
        tp_pips=config.tp_pips,
        intrabar_fill_policy=config.intrabar_fill_policy,
    )
    backtest_result = simulator.run(dataset=dataset)

    # 4. Evaluate
    evaluation = evaluate_backtest(
        stats=backtest_result.stats,
        thresholds=config.thresholds,
    )

    return ExplorationResult(
        strategy_name=config.strategy_name,
        strategy_file=str(strategy_file),
        evaluation=evaluation,
        verdict=evaluation.verdict.value,
    )


# ---------------------------------------------------------------------------
# Loop control
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoopConfig:
    """Configuration for the exploration loop."""

    signal_type: str
    csv_path: str
    base_strategy_name: str = "strategy"
    symbol: str = "BACKTEST"
    timeframe: str = "M1"
    pip_size: float = 0.01
    sl_pips: float = 10.0
    tp_pips: float = 10.0
    intrabar_fill_policy: IntrabarFillPolicy = IntrabarFillPolicy.CONSERVATIVE
    strategy_params: dict[str, object] | None = None
    thresholds: EvaluationThresholds | None = None
    max_iterations: int = 10
    max_improve_retries: int = 1
    max_param_variations: int = 3
    cleanup_discarded: bool = False
    random_seed: int = 42


@dataclass
class LoopResult:
    """Aggregated result of a full exploration loop run."""

    iterations: int = 0
    results: list[ExplorationResult] = field(default_factory=list)
    adopted: ExplorationResult | None = None
    stopped_reason: str = ""
    discarded_files: list[str] = field(default_factory=list)


def _make_strategy_name(base_name: str, iteration: int) -> str:
    """Generate a unique strategy name using timestamp and iteration counter.

    Returns a name like ``strategy_20260403t184500_i01_v1`` which satisfies
    the ``^[a-z][a-z0-9_]*_v\\d+$`` naming convention.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%S")
    return f"{base_name}_{ts}_i{iteration:02d}_v1"


def _cleanup_strategy_file(file_path: str) -> bool:
    """Remove a strategy file from disk. Returns True if removed.

    Only files under the strategies/ directory are allowed to be removed.
    """
    strategies_dir = Path(__file__).resolve().parent.parent / "mt4_bridge" / "strategies"
    resolved = Path(file_path).resolve()
    is_under_strategies = resolved.is_relative_to(strategies_dir)
    if not is_under_strategies:
        logger.warning(
            "Refused to remove file outside strategies directory: %s",
            file_path,
        )
        return False
    try:
        os.remove(file_path)
        return True
    except OSError:
        logger.warning("Failed to remove strategy file: %s", file_path)
        return False


def run_exploration_loop(config: LoopConfig) -> LoopResult:
    """Run the exploration loop until adopt or max_iterations reached.

    Verdict handling:
    - **adopt**: stop the loop and record the adopted strategy.
    - **discard**: optionally clean up the strategy file, generate a new
      strategy, and continue.
    - **improve**: generate parameter variations and retry with different
      params up to ``max_improve_retries`` times.  If no variations can
      be produced (e.g. the signal type has no tunable parameters), fall
      back to generating a new strategy immediately.

    Args:
        config: Loop configuration including safety limits.

    Returns:
        LoopResult with all iteration details.
    """
    random.seed(config.random_seed)
    logger.info("Random seed fixed: %d", config.random_seed)

    loop_result = LoopResult()
    improve_retries = 0
    param_variations: list[dict[str, object]] = []
    current_params = config.strategy_params

    for iteration in range(1, config.max_iterations + 1):
        strategy_name = _make_strategy_name(
            config.base_strategy_name, iteration
        )

        exploration_config = ExplorationConfig(
            signal_type=config.signal_type,
            strategy_name=strategy_name,
            csv_path=config.csv_path,
            symbol=config.symbol,
            timeframe=config.timeframe,
            pip_size=config.pip_size,
            sl_pips=config.sl_pips,
            tp_pips=config.tp_pips,
            intrabar_fill_policy=config.intrabar_fill_policy,
            strategy_params=current_params,
            thresholds=config.thresholds,
        )

        logger.info(
            "Iteration %d/%d: strategy=%s params=%s",
            iteration,
            config.max_iterations,
            strategy_name,
            current_params,
        )

        try:
            result = run_single_exploration(exploration_config)
        except Exception:
            logger.exception(
                "Iteration %d failed for strategy %s, skipping",
                iteration,
                strategy_name,
            )
            loop_result.iterations = iteration
            continue

        loop_result.results.append(result)
        loop_result.iterations = iteration

        verdict = result.verdict

        if verdict == "adopt":
            loop_result.adopted = result
            loop_result.stopped_reason = "adopt"
            logger.info("Strategy adopted: %s", strategy_name)
            return loop_result

        if verdict == "discard":
            logger.info("Strategy discarded: %s", strategy_name)
            if config.cleanup_discarded:
                if _cleanup_strategy_file(result.strategy_file):
                    loop_result.discarded_files.append(result.strategy_file)
            improve_retries = 0
            param_variations = []
            current_params = config.strategy_params
            continue

        if verdict == "improve":
            improve_retries += 1
            if improve_retries == 1:
                try:
                    param_variations = generate_param_variations(
                        signal_type=config.signal_type,
                        base_params=current_params,
                        count=config.max_param_variations,
                    )
                except Exception:
                    logger.warning(
                        "Param variation generation failed, "
                        "falling back to next strategy"
                    )
                    param_variations = []

            if (
                improve_retries <= config.max_improve_retries
                and param_variations
            ):
                current_params = param_variations.pop(0)
                logger.info(
                    "Improve retry %d/%d with varied params: %s",
                    improve_retries,
                    config.max_improve_retries,
                    current_params,
                )
            else:
                logger.info(
                    "Max improve retries reached or no variations, "
                    "moving to next strategy"
                )
                improve_retries = 0
                param_variations = []
                current_params = config.strategy_params
            continue

    loop_result.stopped_reason = "max_iterations"
    logger.info(
        "Loop stopped: max_iterations (%d) reached", config.max_iterations
    )
    return loop_result
