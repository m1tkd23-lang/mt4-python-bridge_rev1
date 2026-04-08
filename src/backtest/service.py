# src/backtest/service.py
from __future__ import annotations

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
) -> AllMonthsResult:
    csv_files = sorted(csv_dir.glob("*.csv"))
    if not csv_files:
        raise ValueError(f"No CSV files found in directory: {csv_dir}")

    monthly_artifacts: list[tuple[str, BacktestRunArtifacts]] = []

    for csv_path in csv_files:
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
        )
        artifacts = run_backtest(config, thresholds=thresholds)
        monthly_artifacts.append((label, artifacts))

    monthly_stats = [
        (label, artifacts.backtest_result.stats)
        for label, artifacts in monthly_artifacts
    ]
    aggregate = aggregate_monthly_stats(monthly_stats)

    return AllMonthsResult(
        monthly_artifacts=monthly_artifacts,
        aggregate=aggregate,
    )