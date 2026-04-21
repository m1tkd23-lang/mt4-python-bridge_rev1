# src/backtest/service.py
from __future__ import annotations

import importlib
from collections.abc import Callable
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from pathlib import Path

import logging

from backtest.aggregate_stats import AggregateStats, aggregate_monthly_stats
from backtest.csv_loader import (
    HistoricalBarDataset,
    load_historical_bars_csv,
    load_historical_bars_csv_multi,
)
from backtest.mean_reversion_analysis import (
    MeanReversionSummary,
    analyze_mean_reversion,
    summarize_mean_reversion,
)
from backtest.simulator.trade_logger import write_trade_log_jsonl
from backtest.evaluator import (
    EvaluationResult,
    EvaluationThresholds,
    evaluate_backtest_with_log_guard,
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


logger = logging.getLogger(__name__)


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
    trade_log_path: Path | None = None


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
    mean_reversion_summary: MeanReversionSummary | None = None


def _build_override_context(config: BacktestRunConfig):
    """Return a context manager that applies strategy param overrides if present."""
    if not config.strategy_params:
        return nullcontext()

    from gui_common.strategy_params import (
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

    evaluation = evaluate_backtest_with_log_guard(
        result=backtest_result,
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

    if config.trade_log_path is not None:
        write_trade_log_jsonl(
            result=backtest_result,
            strategy_name=config.strategy_name,
            output_path=config.trade_log_path,
        )

    mean_reversion_summary: MeanReversionSummary | None
    try:
        mean_reversion_summary = summarize_mean_reversion(
            analyze_mean_reversion(result=backtest_result, dataset=dataset)
        )
    except Exception:
        logger.exception(
            "mean reversion analysis failed in run_backtest; summary set to None"
        )
        mean_reversion_summary = None

    return BacktestRunArtifacts(
        config=config,
        dataset=dataset,
        backtest_result=backtest_result,
        evaluation=evaluation,
        summary=summary,
        trade_rows=trade_rows,
        equity_points=equity_points,
        decision_log_rows=decision_log_rows,
        mean_reversion_summary=mean_reversion_summary,
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
    trade_log_dir: Path | None = None,
    connected: bool = False,
) -> AllMonthsResult:
    """複数 CSV を全月 BT する。

    connected=False (default): 月ごと独立 BT。後方互換挙動。
    connected=True: 全 CSV を時系列連結して 1 本の BT を実行し、trade.entry_time
      で月別に後処理集計。月跨ぎの強制決済/ウォームアップ不連続を排除する。
    """
    csv_files = sorted(csv_dir.glob("*.csv"))
    if not csv_files:
        raise ValueError(f"No CSV files found in directory: {csv_dir}")

    if connected:
        return _run_connected(
            csv_files=csv_files,
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
            thresholds=thresholds,
            progress_callback=progress_callback,
            strategy_params=strategy_params,
            trade_log_dir=trade_log_dir,
        )

    total = len(csv_files)
    monthly_artifacts: list[tuple[str, BacktestRunArtifacts]] = []

    for idx, csv_path in enumerate(csv_files):
        label = csv_path.stem
        trade_log_path: Path | None = None
        if trade_log_dir is not None:
            trade_log_path = trade_log_dir / f"{label}.jsonl"
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
            trade_log_path=trade_log_path,
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


def _run_connected(
    *,
    csv_files: list[Path],
    strategy_name: str,
    symbol: str,
    timeframe: str,
    pip_size: float,
    sl_pips: float,
    tp_pips: float,
    intrabar_fill_policy: IntrabarFillPolicy,
    close_open_position_at_end: bool,
    initial_balance: float,
    money_per_pip: float,
    thresholds: EvaluationThresholds | None,
    progress_callback: Callable[[int, int], None] | None,
    strategy_params: dict[str, float] | None,
    trade_log_dir: Path | None,
) -> AllMonthsResult:
    """全 CSV を結合して 1 回の BT を走らせ、trade.entry_time で月別集計する。"""
    dataset = load_historical_bars_csv_multi(csv_files)

    simulator = BacktestSimulator(
        strategy_name=strategy_name,
        symbol=symbol,
        timeframe=timeframe,
        pip_size=pip_size,
        sl_pips=sl_pips,
        tp_pips=tp_pips,
        intrabar_fill_policy=intrabar_fill_policy,
    )

    override_ctx = _build_override_context(
        BacktestRunConfig(
            csv_path=csv_files[0],
            strategy_name=strategy_name,
            strategy_params=strategy_params,
        )
    )
    with override_ctx:
        backtest_result = simulator.run(
            dataset=dataset,
            close_open_position_at_end=close_open_position_at_end,
        )

    # 月別集計: trades を entry_time.year-month でバケット分け
    monthly_stats_list = _split_result_by_month(
        backtest_result=backtest_result,
        csv_files=csv_files,
        pip_size=pip_size,
        sl_pips=sl_pips,
        tp_pips=tp_pips,
    )
    aggregate = aggregate_monthly_stats(monthly_stats_list)

    # 全期間 1 つの artifact を作る(連結 BT 結果そのもの)
    evaluation = evaluate_backtest_with_log_guard(
        result=backtest_result,
        thresholds=thresholds,
    )
    trade_rows = build_trade_view_rows(
        trades=backtest_result.trades,
        initial_balance=initial_balance,
        money_per_pip=money_per_pip,
    )
    equity_points = build_equity_points(trade_rows=trade_rows)
    decision_log_rows = build_decision_log_view_rows(
        decision_logs=backtest_result.decision_logs
    )
    summary = build_display_summary(
        stats=backtest_result.stats,
        evaluation=evaluation,
        initial_balance=initial_balance,
        money_per_pip=money_per_pip,
        trade_rows=trade_rows,
    )
    connected_config = BacktestRunConfig(
        csv_path=csv_files[0],
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
    connected_artifacts = BacktestRunArtifacts(
        config=connected_config,
        dataset=dataset,
        backtest_result=backtest_result,
        evaluation=evaluation,
        summary=summary,
        trade_rows=trade_rows,
        equity_points=equity_points,
        decision_log_rows=decision_log_rows,
    )

    if progress_callback is not None:
        progress_callback(len(csv_files), len(csv_files))

    if trade_log_dir is not None:
        write_trade_log_jsonl(
            result=backtest_result,
            strategy_name=strategy_name,
            output_path=trade_log_dir / "connected.jsonl",
        )

    return AllMonthsResult(
        monthly_artifacts=[("connected", connected_artifacts)],
        aggregate=aggregate,
    )


def _split_result_by_month(
    *,
    backtest_result: BacktestResult,
    csv_files: list[Path],
    pip_size: float,
    sl_pips: float,
    tp_pips: float,
) -> list[tuple[str, object]]:
    """連結 BT の trades を entry_time で月別にバケット分けし、簡易 BacktestStats を構築。"""
    from collections import defaultdict
    from backtest.simulator import BacktestStats

    buckets: dict[str, list] = defaultdict(list)
    for trade in backtest_result.trades:
        key = f"{trade.entry_time.year:04d}-{trade.entry_time.month:02d}"
        buckets[key].append(trade)

    result: list[tuple[str, BacktestStats]] = []
    base = backtest_result.stats
    for key in sorted(buckets.keys()):
        trades = buckets[key]
        total_pips = sum(t.pips for t in trades)
        wins = sum(1 for t in trades if t.pips > 0)
        losses = sum(1 for t in trades if t.pips < 0)
        count = len(trades)
        gross_profit = sum(t.pips for t in trades if t.pips > 0)
        gross_loss = sum(t.pips for t in trades if t.pips < 0)
        win_rate = (wins / count) if count > 0 else 0.0
        avg_pips = (total_pips / count) if count > 0 else 0.0
        avg_win = (gross_profit / wins) if wins > 0 else 0.0
        avg_loss = (gross_loss / losses) if losses > 0 else 0.0
        pf = (gross_profit / abs(gross_loss)) if gross_loss < 0 else None
        stats = BacktestStats(
            strategy_name=base.strategy_name,
            symbol=base.symbol,
            timeframe=base.timeframe,
            intrabar_fill_policy=base.intrabar_fill_policy,
            sl_pips=sl_pips,
            tp_pips=tp_pips,
            total_bars=0,
            processed_bars=0,
            trades=count,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            total_pips=total_pips,
            average_pips=avg_pips,
            average_win_pips=avg_win,
            average_loss_pips=avg_loss,
            profit_factor=pf,
            max_drawdown_pips=0.0,
            gross_profit_pips=gross_profit,
            gross_loss_pips=gross_loss,
            final_open_position_type=None,
        )
        result.append((key, stats))
    return result


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
    trade_log_dir: Path | None = None,
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

    lane_a_log_dir: Path | None = None
    lane_b_log_dir: Path | None = None
    combo_log_dir: Path | None = None
    if trade_log_dir is not None:
        lane_a_log_dir = trade_log_dir / "lane_a"
        lane_b_log_dir = trade_log_dir / "lane_b"
        combo_log_dir = trade_log_dir / "combo"

    lane_a_result = run_all_months(strategy_name=lane_a_name, trade_log_dir=lane_a_log_dir, **common_kwargs)
    lane_b_result = run_all_months(strategy_name=lane_b_name, trade_log_dir=lane_b_log_dir, **common_kwargs)
    combo_result = run_all_months(strategy_name=combo_strategy_name, trade_log_dir=combo_log_dir, **common_kwargs)

    return CompareABResult(
        lane_a_strategy=lane_a_name,
        lane_b_strategy=lane_b_name,
        combo_strategy=combo_strategy_name,
        lane_a_result=lane_a_result,
        lane_b_result=lane_b_result,
        combo_result=combo_result,
    )