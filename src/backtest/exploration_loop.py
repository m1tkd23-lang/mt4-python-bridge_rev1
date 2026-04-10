# src\backtest\exploration_loop.py
"""Tactical exploration loop: generate → backtest → evaluate → verdict.

This module orchestrates exploration cycles of strategy generation and evaluation.
It supports both single-cycle execution (run_single_exploration) and multi-cycle
loop execution (run_exploration_loop) with verdict-based control flow.

Bollinger override mode (run_bollinger_exploration / run_bollinger_exploration_loop)
uses existing strategy files with parameter overrides instead of generating new files.
"""
from __future__ import annotations

import copy
import logging
import os
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from mt4_bridge.strategy_generator import generate_param_variations, generate_strategy_file
from backtest.csv_loader import load_historical_bars_csv
from backtest.aggregate_stats import AggregateStats, aggregate_monthly_stats
from backtest.simulator import BacktestSimulator, IntrabarFillPolicy
from backtest.evaluator import (
    CrossMonthEvaluationResult,
    CrossMonthThresholds,
    EvaluationResult,
    EvaluationThresholds,
    IntegratedEvaluationResult,
    IntegratedThresholds,
    evaluate_backtest_with_log_guard,
    evaluate_cross_month,
    evaluate_integrated,
)
from backtest_gui_app.services.strategy_params import (
    apply_strategy_overrides,
    get_param_specs,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExplorationConfig:
    """Configuration for a single exploration cycle."""

    signal_type: str
    strategy_name: str
    csv_path: str
    symbol: str = "BACKTEST"
    timeframe: str = "M5"
    pip_size: float = 0.01
    sl_pips: float = 10.0
    tp_pips: float = 30.0
    intrabar_fill_policy: IntrabarFillPolicy = IntrabarFillPolicy.CONSERVATIVE
    strategy_params: dict[str, object] | None = None
    thresholds: EvaluationThresholds | None = None
    csv_dir: str | None = None
    cross_month_thresholds: CrossMonthThresholds | None = None
    integrated_thresholds: IntegratedThresholds | None = None
    csv_paths: list[str] | None = None


@dataclass(frozen=True)
class ExplorationResult:
    """Result of a single exploration cycle."""

    strategy_name: str
    strategy_file: str
    evaluation: EvaluationResult
    verdict: str
    cross_month_evaluation: CrossMonthEvaluationResult | None = None
    integrated_evaluation: IntegratedEvaluationResult | None = None
    aggregate_stats: AggregateStats | None = None


def _resolve_csv_files(
    csv_paths: list[str] | None,
    csv_dir: str | None,
) -> list[Path] | None:
    """Resolve CSV file list using priority: csv_paths > csv_dir.

    Args:
        csv_paths: Explicit list of CSV file paths (highest priority).
        csv_dir: Directory to glob for ``*.csv`` files (fallback).

    Returns:
        Sorted list of CSV file paths, or ``None`` if no multi-month
        evaluation should be performed.

    Raises:
        ValueError: If *csv_paths* is an empty list (``[]``).
            Pass ``None`` to skip multi-month evaluation instead.
    """
    if csv_paths is not None:
        if len(csv_paths) == 0:
            raise ValueError(
                "csv_paths must not be an empty list. "
                "Pass None to skip multi-month evaluation."
            )
        return [Path(p) for p in csv_paths]

    if csv_dir is not None:
        csv_dir_path = Path(csv_dir)
        csv_files = sorted(csv_dir_path.glob("*.csv"))
        if len(csv_files) >= 2:
            return csv_files

    return None


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

    # 4. Evaluate single-month (with log quality guard)
    evaluation = evaluate_backtest_with_log_guard(
        result=backtest_result,
        thresholds=config.thresholds,
    )

    # 5. Cross-month & integrated evaluation (csv_paths > csv_dir > csv_path only)
    cross_month_eval: CrossMonthEvaluationResult | None = None
    integrated_eval: IntegratedEvaluationResult | None = None
    agg_stats: AggregateStats | None = None
    final_verdict = evaluation.verdict.value

    resolved_csvs = _resolve_csv_files(config.csv_paths, config.csv_dir)
    if resolved_csvs is not None:
        monthly_stats: list[tuple[str, object]] = []
        for csv_file in resolved_csvs:
            month_dataset = load_historical_bars_csv(csv_file)
            month_sim = BacktestSimulator(
                strategy_name=config.strategy_name,
                symbol=config.symbol,
                timeframe=config.timeframe,
                pip_size=config.pip_size,
                sl_pips=config.sl_pips,
                tp_pips=config.tp_pips,
                intrabar_fill_policy=config.intrabar_fill_policy,
            )
            month_result = month_sim.run(dataset=month_dataset)
            monthly_stats.append((csv_file.stem, month_result.stats))

        agg_stats = aggregate_monthly_stats(monthly_stats)

        cross_month_eval = evaluate_cross_month(
            agg=agg_stats,
            thresholds=config.cross_month_thresholds,
        )
        integrated_eval = evaluate_integrated(
            agg=agg_stats,
            thresholds=config.integrated_thresholds,
        )
        final_verdict = integrated_eval.verdict.value
        logger.info(
            "Cross-month evaluation: verdict=%s, Integrated: verdict=%s",
            cross_month_eval.verdict.value,
            integrated_eval.verdict.value,
        )

    return ExplorationResult(
        strategy_name=config.strategy_name,
        strategy_file=str(strategy_file),
        evaluation=evaluation,
        verdict=final_verdict,
        cross_month_evaluation=cross_month_eval,
        integrated_evaluation=integrated_eval,
        aggregate_stats=agg_stats,
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
    timeframe: str = "M5"
    pip_size: float = 0.01
    sl_pips: float = 10.0
    tp_pips: float = 30.0
    intrabar_fill_policy: IntrabarFillPolicy = IntrabarFillPolicy.CONSERVATIVE
    strategy_params: dict[str, object] | None = None
    thresholds: EvaluationThresholds | None = None
    max_iterations: int = 10
    max_improve_retries: int = 1
    max_param_variations: int = 3
    cleanup_discarded: bool = False
    random_seed: int = 42
    csv_dir: str | None = None
    cross_month_thresholds: CrossMonthThresholds | None = None
    integrated_thresholds: IntegratedThresholds | None = None
    csv_paths: list[str] | None = None


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


def run_exploration_loop(config: LoopConfig, thread: object | None = None) -> LoopResult:
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
    if config.csv_paths is not None and len(config.csv_paths) == 0:
        raise ValueError(
            "csv_paths must not be an empty list. "
            "Pass None to skip multi-month evaluation."
        )

    random.seed(config.random_seed)
    logger.info("Random seed fixed: %d", config.random_seed)

    loop_result = LoopResult()
    improve_retries = 0
    param_variations: list[dict[str, object]] = []
    current_params = config.strategy_params

    effective_csv_path = config.csv_path
    if config.csv_paths is not None and len(config.csv_paths) > 0:
        effective_csv_path = config.csv_paths[-1]

    for iteration in range(1, config.max_iterations + 1):
        if thread is not None and getattr(thread, "isInterruptionRequested", lambda: False)():
            loop_result.stopped_reason = "user_stopped"
            logger.info("Loop stopped: user interruption requested")
            return loop_result

        strategy_name = _make_strategy_name(
            config.base_strategy_name, iteration
        )

        exploration_config = ExplorationConfig(
            signal_type=config.signal_type,
            strategy_name=strategy_name,
            csv_path=effective_csv_path,
            symbol=config.symbol,
            timeframe=config.timeframe,
            pip_size=config.pip_size,
            sl_pips=config.sl_pips,
            tp_pips=config.tp_pips,
            intrabar_fill_policy=config.intrabar_fill_policy,
            strategy_params=current_params,
            thresholds=config.thresholds,
            csv_dir=config.csv_dir,
            cross_month_thresholds=config.cross_month_thresholds,
            integrated_thresholds=config.integrated_thresholds,
            csv_paths=config.csv_paths,
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


# ---------------------------------------------------------------------------
# Bollinger override exploration
# ---------------------------------------------------------------------------

# Parameter variation ranges for bollinger strategies.
# Each entry maps a qualified key (module_path::CONST_NAME) to (min, max, step).
BOLLINGER_PARAM_VARIATION_RANGES: dict[str, dict[str, tuple[float, float, float]]] = {
    "bollinger_range_v4_4": {
        "mt4_bridge.strategies.bollinger_range_v4_4::BOLLINGER_PERIOD": (10, 40, 5),
        "mt4_bridge.strategies.bollinger_range_v4_4::BOLLINGER_SIGMA": (1.5, 3.0, 0.25),
        "mt4_bridge.strategies.bollinger_range_v4_4::RANGE_SLOPE_THRESHOLD": (0.0002, 0.001, 0.0001),
        "mt4_bridge.strategies.bollinger_range_v4_4::RANGE_BAND_WIDTH_THRESHOLD": (0.001, 0.006, 0.0005),
        "mt4_bridge.strategies.bollinger_range_v4_4::RANGE_MIDDLE_DISTANCE_THRESHOLD": (0.001, 0.004, 0.0005),
    },
    "bollinger_trend_B": {
        "mt4_bridge.strategies.bollinger_trend_B::BOLLINGER_PERIOD": (10, 40, 5),
        "mt4_bridge.strategies.bollinger_trend_B::BOLLINGER_SIGMA": (1.5, 3.0, 0.25),
        "mt4_bridge.strategies.bollinger_trend_B::TREND_SLOPE_THRESHOLD": (0.00001, 0.0001, 0.00001),
        "mt4_bridge.strategies.bollinger_trend_B::STRONG_TREND_SLOPE_THRESHOLD": (0.0002, 0.001, 0.0001),
    },
    "bollinger_combo_AB": {
        "mt4_bridge.strategies.bollinger_range_v4_4::BOLLINGER_PERIOD": (10, 40, 5),
        "mt4_bridge.strategies.bollinger_range_v4_4::BOLLINGER_SIGMA": (1.5, 3.0, 0.25),
        "mt4_bridge.strategies.bollinger_range_v4_4::RANGE_SLOPE_THRESHOLD": (0.0002, 0.001, 0.0001),
        "mt4_bridge.strategies.bollinger_range_v4_4::RANGE_BAND_WIDTH_THRESHOLD": (0.001, 0.006, 0.0005),
        "mt4_bridge.strategies.bollinger_range_v4_4::RANGE_MIDDLE_DISTANCE_THRESHOLD": (0.001, 0.004, 0.0005),
        "mt4_bridge.strategies.bollinger_trend_B::BOLLINGER_PERIOD": (10, 40, 5),
        "mt4_bridge.strategies.bollinger_trend_B::BOLLINGER_SIGMA": (1.5, 3.0, 0.25),
        "mt4_bridge.strategies.bollinger_trend_B::TREND_SLOPE_THRESHOLD": (0.00001, 0.0001, 0.00001),
        "mt4_bridge.strategies.bollinger_trend_B::STRONG_TREND_SLOPE_THRESHOLD": (0.0002, 0.001, 0.0001),
    },
}


def _build_bollinger_spec_index(strategy_name: str) -> dict[str, object]:
    specs = get_param_specs(strategy_name)
    return {f"{spec.module_path}::{spec.name}": spec for spec in specs}


def _apply_bollinger_override_constraints(
    strategy_name: str,
    overrides: dict[str, float],
) -> dict[str, float]:
    constrained = dict(overrides)
    spec_index = _build_bollinger_spec_index(strategy_name)

    trend_key = "mt4_bridge.strategies.bollinger_trend_B::TREND_SLOPE_THRESHOLD"
    strong_key = "mt4_bridge.strategies.bollinger_trend_B::STRONG_TREND_SLOPE_THRESHOLD"

    if strategy_name in {"bollinger_trend_B", "bollinger_combo_AB", "bollinger_combo_AB_v1"}:
        trend_val = constrained.get(trend_key)
        strong_val = constrained.get(strong_key)
        if trend_val is not None and strong_val is not None and strong_val < trend_val:
            constrained[strong_key] = trend_val

    for key, value in list(constrained.items()):
        spec = spec_index.get(key)
        if spec is None:
            continue
        bounded = min(max(float(value), spec.min_val), spec.max_val)
        if spec.param_type == "int":
            constrained[key] = int(round(bounded))
        else:
            constrained[key] = round(bounded, spec.decimals)

    return constrained


@dataclass(frozen=True)
class BollingerExplorationConfig:
    """Configuration for a bollinger override exploration cycle."""

    strategy_name: str
    csv_path: str
    symbol: str = "BACKTEST"
    timeframe: str = "M5"
    pip_size: float = 0.01
    sl_pips: float = 10.0
    tp_pips: float = 10.0
    intrabar_fill_policy: IntrabarFillPolicy = IntrabarFillPolicy.CONSERVATIVE
    param_overrides: dict[str, float] | None = None
    thresholds: EvaluationThresholds | None = None
    csv_dir: str | None = None
    cross_month_thresholds: CrossMonthThresholds | None = None
    integrated_thresholds: IntegratedThresholds | None = None
    csv_paths: list[str] | None = None


@dataclass(frozen=True)
class BollingerExplorationResult:
    """Result of a single bollinger override exploration cycle."""

    strategy_name: str
    param_overrides: dict[str, float]
    evaluation: EvaluationResult
    verdict: str
    cross_month_evaluation: CrossMonthEvaluationResult | None = None
    integrated_evaluation: IntegratedEvaluationResult | None = None
    aggregate_stats: AggregateStats | None = None


def run_bollinger_exploration(
    config: BollingerExplorationConfig,
) -> BollingerExplorationResult:
    """Execute one bollinger exploration cycle: override params → backtest → evaluate.

    Uses ``apply_strategy_overrides`` to temporarily patch module-level
    constants in the target strategy modules, then runs a standard backtest
    and evaluation cycle.  No strategy files are generated or modified.

    Args:
        config: Configuration for this bollinger exploration cycle.

    Returns:
        BollingerExplorationResult containing the verdict and evaluation details.
    """
    overrides = _apply_bollinger_override_constraints(
        config.strategy_name,
        config.param_overrides or {},
    )
    specs = get_param_specs(config.strategy_name)

    with apply_strategy_overrides(overrides, specs):
        # 1. Load historical data
        dataset = load_historical_bars_csv(Path(config.csv_path))

        # 2. Run backtest
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

        # 3. Evaluate single-month (with log quality guard)
        evaluation = evaluate_backtest_with_log_guard(
            result=backtest_result,
            thresholds=config.thresholds,
        )

        # 4. Cross-month & integrated evaluation (csv_paths > csv_dir > csv_path only)
        cross_month_eval: CrossMonthEvaluationResult | None = None
        integrated_eval: IntegratedEvaluationResult | None = None
        agg_stats: AggregateStats | None = None
        final_verdict = evaluation.verdict.value

        resolved_csvs = _resolve_csv_files(config.csv_paths, config.csv_dir)
        if resolved_csvs is not None:
            monthly_stats: list[tuple[str, object]] = []
            for csv_file in resolved_csvs:
                month_dataset = load_historical_bars_csv(csv_file)
                month_sim = BacktestSimulator(
                    strategy_name=config.strategy_name,
                    symbol=config.symbol,
                    timeframe=config.timeframe,
                    pip_size=config.pip_size,
                    sl_pips=config.sl_pips,
                    tp_pips=config.tp_pips,
                    intrabar_fill_policy=config.intrabar_fill_policy,
                )
                month_result = month_sim.run(dataset=month_dataset)
                monthly_stats.append((csv_file.stem, month_result.stats))

            agg_stats = aggregate_monthly_stats(monthly_stats)

            cross_month_eval = evaluate_cross_month(
                agg=agg_stats,
                thresholds=config.cross_month_thresholds,
            )
            integrated_eval = evaluate_integrated(
                agg=agg_stats,
                thresholds=config.integrated_thresholds,
            )
            final_verdict = integrated_eval.verdict.value
            logger.info(
                "Bollinger cross-month: verdict=%s, Integrated: verdict=%s",
                cross_month_eval.verdict.value,
                integrated_eval.verdict.value,
            )

    return BollingerExplorationResult(
        strategy_name=config.strategy_name,
        param_overrides=overrides,
        evaluation=evaluation,
        verdict=final_verdict,
        cross_month_evaluation=cross_month_eval,
        integrated_evaluation=integrated_eval,
        aggregate_stats=agg_stats,
    )


def generate_bollinger_param_variations(
    strategy_name: str,
    base_overrides: dict[str, float] | None = None,
    count: int = 3,
    ranges_override: dict[str, tuple[float, float, float]] | None = None,
) -> list[dict[str, float]]:
    """Generate parameter variations for a bollinger strategy.

    Uses ``BOLLINGER_PARAM_VARIATION_RANGES`` to produce up to *count*
    parameter override dicts that differ from *base_overrides*.

    Args:
        strategy_name: Bollinger strategy name (key in
            ``BOLLINGER_PARAM_VARIATION_RANGES``).
        base_overrides: Current override values.  Keys are qualified
            ``module_path::CONST_NAME`` strings.
        count: Maximum number of variations to generate.
        ranges_override: If provided, used instead of looking up
            ``BOLLINGER_PARAM_VARIATION_RANGES[strategy_name]``.

    Returns:
        A list of override dicts, each different from *base_overrides*.
    """
    ranges_orig = ranges_override or BOLLINGER_PARAM_VARIATION_RANGES.get(strategy_name)
    if not ranges_orig:
        logger.warning(
            "No bollinger param variation ranges for strategy '%s'",
            strategy_name,
        )
        return []

    ranges = copy.deepcopy(ranges_orig)
    effective_base = _apply_bollinger_override_constraints(
        strategy_name,
        dict(base_overrides or {}),
    )
    variations: list[dict[str, float]] = []
    seen: set[tuple[tuple[str, float], ...]] = set()
    base_key = tuple(sorted((k, float(v)) for k, v in effective_base.items()))
    seen.add(base_key)

    attempts = 0
    max_attempts = count * 10

    while len(variations) < count and attempts < max_attempts:
        attempts += 1
        candidate: dict[str, float] = {}
        for param_key, (lo, hi, step) in ranges.items():
            # Build list of possible values
            n_steps = int(round((hi - lo) / step)) + 1
            possible = [round(lo + i * step, 10) for i in range(n_steps)]
            candidate[param_key] = random.choice(possible)

        candidate = _apply_bollinger_override_constraints(strategy_name, candidate)
        key = tuple(sorted((k, float(v)) for k, v in candidate.items()))
        if key in seen:
            continue
        seen.add(key)
        variations.append(candidate)

    return variations


@dataclass(frozen=True)
class BollingerLoopConfig:
    """Configuration for the bollinger exploration loop."""

    strategy_name: str
    csv_path: str
    symbol: str = "BACKTEST"
    timeframe: str = "M5"
    pip_size: float = 0.01
    sl_pips: float = 10.0
    tp_pips: float = 10.0
    intrabar_fill_policy: IntrabarFillPolicy = IntrabarFillPolicy.CONSERVATIVE
    param_overrides: dict[str, float] | None = None
    thresholds: EvaluationThresholds | None = None
    max_iterations: int = 10
    max_improve_retries: int = 1
    max_param_variations: int = 3
    random_seed: int = 42
    csv_dir: str | None = None
    cross_month_thresholds: CrossMonthThresholds | None = None
    integrated_thresholds: IntegratedThresholds | None = None
    param_variation_ranges: dict[str, tuple[float, float, float]] | None = None
    seed_overrides_list: list[dict[str, float]] | None = None
    csv_paths: list[str] | None = None


@dataclass
class BollingerLoopResult:
    """Aggregated result of a full bollinger exploration loop run."""

    iterations: int = 0
    results: list[BollingerExplorationResult] = field(default_factory=list)
    adopted: BollingerExplorationResult | None = None
    stopped_reason: str = ""


def run_bollinger_exploration_loop(
    config: BollingerLoopConfig,
    thread: object | None = None,
    on_iteration_done: "Callable[[int, BollingerExplorationResult], None] | None" = None,
) -> BollingerLoopResult:
    """Run the bollinger exploration loop until adopt or max_iterations.

    This loop uses parameter overrides on existing strategy modules instead
    of generating new strategy files.  The cycle structure mirrors
    ``run_exploration_loop``: override → backtest → evaluate → verdict.

    Verdict handling:
    - **adopt**: stop the loop and record the adopted parameters.
    - **discard**: reset to base overrides and try new random variations.
    - **improve**: generate parameter variations from the current overrides
      and retry up to ``max_improve_retries`` times.

    Args:
        config: Loop configuration including safety limits.

    Returns:
        BollingerLoopResult with all iteration details.
    """
    if config.csv_paths is not None and len(config.csv_paths) == 0:
        raise ValueError(
            "csv_paths must not be an empty list. "
            "Pass None to skip multi-month evaluation."
        )

    random.seed(config.random_seed)
    logger.info(
        "Bollinger loop start: strategy=%s, seed=%d",
        config.strategy_name,
        config.random_seed,
    )

    loop_result = BollingerLoopResult()
    improve_retries = 0
    param_variations: list[dict[str, float]] = []
    seed_queue = [
        _apply_bollinger_override_constraints(config.strategy_name, dict(seed))
        for seed in (config.seed_overrides_list or [])
        if seed
    ]
    base_overrides = _apply_bollinger_override_constraints(
        config.strategy_name,
        dict(config.param_overrides or {}),
    )
    current_overrides = dict(base_overrides)

    if not current_overrides and seed_queue:
        current_overrides = seed_queue.pop(0)

    for iteration in range(1, config.max_iterations + 1):
        if thread is not None and getattr(thread, "isInterruptionRequested", lambda: False)():
            loop_result.stopped_reason = "user_stopped"
            logger.info("Bollinger loop stopped: user interruption requested")
            return loop_result

        effective_csv_path = config.csv_path
        if config.csv_paths is not None and len(config.csv_paths) > 0:
            effective_csv_path = config.csv_paths[-1]

        exploration_config = BollingerExplorationConfig(
            strategy_name=config.strategy_name,
            csv_path=effective_csv_path,
            symbol=config.symbol,
            timeframe=config.timeframe,
            pip_size=config.pip_size,
            sl_pips=config.sl_pips,
            tp_pips=config.tp_pips,
            intrabar_fill_policy=config.intrabar_fill_policy,
            param_overrides=current_overrides if current_overrides else None,
            thresholds=config.thresholds,
            csv_dir=config.csv_dir,
            cross_month_thresholds=config.cross_month_thresholds,
            integrated_thresholds=config.integrated_thresholds,
            csv_paths=config.csv_paths,
        )

        logger.info(
            "Bollinger iteration %d/%d: strategy=%s overrides=%s",
            iteration,
            config.max_iterations,
            config.strategy_name,
            current_overrides,
        )

        try:
            result = run_bollinger_exploration(exploration_config)
        except Exception:
            logger.exception(
                "Bollinger iteration %d failed, skipping",
                iteration,
            )
            loop_result.iterations = iteration
            continue

        loop_result.results.append(result)
        loop_result.iterations = iteration

        if on_iteration_done is not None:
            try:
                on_iteration_done(iteration, result)
            except Exception:
                logger.warning(
                    "on_iteration_done callback raised an exception at iteration %d",
                    iteration,
                    exc_info=True,
                )

        verdict = result.verdict

        if verdict == "adopt":
            loop_result.adopted = result
            loop_result.stopped_reason = "adopt"
            logger.info(
                "Bollinger parameters adopted: %s", current_overrides
            )
            return loop_result

        if verdict == "discard":
            logger.info("Bollinger parameters discarded: %s", current_overrides)
            improve_retries = 0
            param_variations = []

            if seed_queue:
                current_overrides = seed_queue.pop(0)
            else:
                fresh = generate_bollinger_param_variations(
                    strategy_name=config.strategy_name,
                    base_overrides=base_overrides,
                    count=1,
                    ranges_override=config.param_variation_ranges,
                )
                current_overrides = fresh[0] if fresh else dict(base_overrides)
            continue

        if verdict == "improve":
            improve_retries += 1
            if improve_retries == 1:
                try:
                    param_variations = generate_bollinger_param_variations(
                        strategy_name=config.strategy_name,
                        base_overrides=current_overrides,
                        count=config.max_param_variations,
                        ranges_override=config.param_variation_ranges,
                    )
                except Exception:
                    logger.warning(
                        "Bollinger param variation generation failed, "
                        "falling back to next set"
                    )
                    param_variations = []

            if (
                improve_retries <= config.max_improve_retries
                and param_variations
            ):
                current_overrides = param_variations.pop(0)
                logger.info(
                    "Bollinger improve retry %d/%d with overrides: %s",
                    improve_retries,
                    config.max_improve_retries,
                    current_overrides,
                )
            else:
                logger.info(
                    "Max bollinger improve retries reached or no variations, "
                    "moving to next parameter set"
                )
                improve_retries = 0
                param_variations = []
                if seed_queue:
                    current_overrides = seed_queue.pop(0)
                else:
                    fresh = generate_bollinger_param_variations(
                        strategy_name=config.strategy_name,
                        base_overrides=base_overrides,
                        count=1,
                        ranges_override=config.param_variation_ranges,
                    )
                    current_overrides = fresh[0] if fresh else dict(base_overrides)
            continue

    loop_result.stopped_reason = "max_iterations"
    logger.info(
        "Bollinger loop stopped: max_iterations (%d) reached",
        config.max_iterations,
    )
    return loop_result