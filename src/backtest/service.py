# src/backtest/service.py
from __future__ import annotations

import importlib
from collections.abc import Callable
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from pathlib import Path

from backtest.aggregate_stats import AggregateStats, aggregate_monthly_stats
from backtest.csv_loader import HistoricalBarDataset, load_historical_bars_csv
from backtest.evaluator import (
    EvaluationResult,
    EvaluationThresholds,
    evaluate_backtest,
)
from backtest.simulator import (
    BacktestResult,
    BacktestSimulator,
    IntrabarFillPolicy,
)
from backtest.view_models import (
    BacktestDisplaySummary,
    DecisionLogViewRow,
    EquityPoint,
    TradeViewRow,
    build_decision_log_view_rows,
    build_display_summary,
    build_equity_points,
    build_trade_view_rows,
)


@dataclass(frozen=True)
class BacktestRunConfig:
    csv_path: Path
    strategy_name: str
    symbol: str = "BACKTEST"
    timeframe: str = "M1"
    pip_size: float = 0.01
    sl_pips: float = 10.0
    tp_pips: float = 10.0
    intrabar_fill_policy: IntrabarFillPolicy = IntrabarFillPolicy.CONSERVATIVE
    close_open_position_at_end: bool = True
    initial_balance: float = 1_000_000.0
    money_per_pip: float = 100.0
    risk_percent: float | None = None
    lot_size: float | None = None
    strategy_params: dict[str, float] | None = None


@dataclass(frozen=True)
class BacktestRunArtifacts:
    config: BacktestRunConfig
    dataset: HistoricalBarDataset
    backtest_result: BacktestResult
    evaluation: EvaluationResult
    summary: BacktestDisplaySummary
    trade_rows: list[TradeViewRow]
    equity_points: list[EquityPoint]
    decision_log_rows: list[DecisionLogViewRow]


def _build_override_context(config: BacktestRunConfig):
    """Return a context manager that applies strategy param overrides if present."""
    if not config.strategy_params:
        return nullcontext()

    from backtest_gui_app.services.strategy_params import (
        apply_strategy_overrides,
        get_param_specs,
    )

    specs = get_param_specs(config.strategy_name)
    if not specs:
        return nullcontext()
    return apply_strategy_overrides(config.strategy_params, specs)


def run_backtest(
    config: BacktestRunConfig,
    thresholds: EvaluationThresholds | None = None,
) -> BacktestRunArtifacts:
    dataset = load_historical_bars_csv(config.csv_path)

    simulator = BacktestSimulator(
        strategy_name=config.strategy_name,
        symbol=config.symbol,
        timeframe=config.timeframe,
        pip_size=config.pip_size,
        sl_pips=config.sl_pips,
        tp_pips=config.tp_pips,
        intrabar_fill_policy=config.intrabar_fill_policy,
    )

    override_ctx = _build_override_context(config)
    with override_ctx:
        backtest_result = simulator.run(
            dataset=dataset,
            close_open_position_at_end=config.close_open_position_at_end,
        )

    evaluation = evaluate_backtest(
        stats=backtest_result.stats,
        thresholds=thresholds,
    )

    trade_rows = build_trade_view_rows(
        trades=backtest_result.trades,
        initial_balance=config.initial_balance,
        money_per_pip=config.money_per_pip,
    )
    equity_points = build_equity_points(trade_rows=trade_rows)
    decision_log_rows = build_decision_log_view_rows(
        decision_logs=backtest_result.decision_logs
    )
    summary = build_display_summary(
        stats=backtest_result.stats,
        evaluation=evaluation,
        initial_balance=config.initial_balance,
        money_per_pip=config.money_per_pip,
        trade_rows=trade_rows,
    )

    return BacktestRunArtifacts(
        config=config,
        dataset=dataset,
        backtest_result=backtest_result,
        evaluation=evaluation,
        summary=summary,
        trade_rows=trade_rows,
        equity_points=equity_points,
        decision_log_rows=decision_log_rows,
    )


@dataclass(frozen=True)
class AllMonthsResult:
    monthly_artifacts: list[tuple[str, BacktestRunArtifacts]]
    aggregate: AggregateStats


def run_all_months(
    csv_dir: Path,
    strategy_name: str,
    symbol: str = "BACKTEST",
    timeframe: str = "M1",
    pip_size: float = 0.01,
    sl_pips: float = 10.0,
    tp_pips: float = 10.0,
    intrabar_fill_policy: IntrabarFillPolicy = IntrabarFillPolicy.CONSERVATIVE,
    close_open_position_at_end: bool = True,
    initial_balance: float = 1_000_000.0,
    money_per_pip: float = 100.0,
    thresholds: EvaluationThresholds | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    strategy_params: dict[str, float] | None = None,
) -> AllMonthsResult:
    csv_files = sorted(csv_dir.glob("*.csv"))
    if not csv_files:
        raise ValueError(f"No CSV files found in directory: {csv_dir}")

    total = len(csv_files)
    monthly_artifacts: list[tuple[str, BacktestRunArtifacts]] = []

    for idx, csv_path in enumerate(csv_files):
        label = csv_path.stem
        config = BacktestRunConfig(
            csv_path=csv_path,
            strategy_name=strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            pip_size=pip_size,
            sl_pips=sl_pips,
            tp_pips=tp_pips,
            intrabar_fill_policy=intrabar_fill_policy,
            close_open_position_at_end=close_open_position_at_end,
            initial_balance=initial_balance,
            money_per_pip=money_per_pip,
            strategy_params=strategy_params,
        )
        artifacts = run_backtest(config, thresholds=thresholds)
        monthly_artifacts.append((label, artifacts))
        if progress_callback is not None:
            progress_callback(idx + 1, total)

    monthly_stats = [
        (label, artifacts.backtest_result.stats)
        for label, artifacts in monthly_artifacts
    ]
    aggregate = aggregate_monthly_stats(monthly_stats)

    return AllMonthsResult(
        monthly_artifacts=monthly_artifacts,
        aggregate=aggregate,
    )


def _resolve_lane_strategies(combo_strategy_name: str) -> tuple[str, str]:
    """Resolve A/B lane strategy names from a combo strategy module.

    The combo module must expose LANE_A_STRATEGY and LANE_B_STRATEGY constants.
    """
    module_path = f"mt4_bridge.strategies.{combo_strategy_name}"
    try:
        mod = importlib.import_module(module_path)
    except ImportError as exc:
        raise ValueError(
            f"Cannot import combo strategy module: {combo_strategy_name}"
        ) from exc

    lane_a = getattr(mod, "LANE_A_STRATEGY", None)
    lane_b = getattr(mod, "LANE_B_STRATEGY", None)
    if lane_a is None or lane_b is None:
        raise ValueError(
            f"Combo strategy '{combo_strategy_name}' does not expose "
            "LANE_A_STRATEGY / LANE_B_STRATEGY constants"
        )
    return lane_a, lane_b


@dataclass(frozen=True)
class CompareABResult:
    lane_a_strategy: str
    lane_b_strategy: str
    combo_strategy: str
    lane_a_result: AllMonthsResult
    lane_b_result: AllMonthsResult
    combo_result: AllMonthsResult


def compare_ab(
    csv_dir: Path,
    combo_strategy_name: str,
    symbol: str = "BACKTEST",
    timeframe: str = "M1",
    pip_size: float = 0.01,
    sl_pips: float = 10.0,
    tp_pips: float = 10.0,
    intrabar_fill_policy: IntrabarFillPolicy = IntrabarFillPolicy.CONSERVATIVE,
    close_open_position_at_end: bool = True,
    initial_balance: float = 1_000_000.0,
    money_per_pip: float = 100.0,
    thresholds: EvaluationThresholds | None = None,
) -> CompareABResult:
    """Run all-month backtests for A-only, B-only, and A+B combo, returning all three results."""
    lane_a_name, lane_b_name = _resolve_lane_strategies(combo_strategy_name)

    common_kwargs = dict(
        csv_dir=csv_dir,
        symbol=symbol,
        timeframe=timeframe,
        pip_size=pip_size,
        sl_pips=sl_pips,
        tp_pips=tp_pips,
        intrabar_fill_policy=intrabar_fill_policy,
        close_open_position_at_end=close_open_position_at_end,
        initial_balance=initial_balance,
        money_per_pip=money_per_pip,
        thresholds=thresholds,
    )

    lane_a_result = run_all_months(strategy_name=lane_a_name, **common_kwargs)
    lane_b_result = run_all_months(strategy_name=lane_b_name, **common_kwargs)
    combo_result = run_all_months(strategy_name=combo_strategy_name, **common_kwargs)

    return CompareABResult(
        lane_a_strategy=lane_a_name,
        lane_b_strategy=lane_b_name,
        combo_strategy=combo_strategy_name,
        lane_a_result=lane_a_result,
        lane_b_result=lane_b_result,
        combo_result=combo_result,
    )