# src\explore_gui_app\views\main_window.py
from __future__ import annotations

import copy
import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QWidget,
)

from backtest.exploration_loop import (
    BOLLINGER_PARAM_VARIATION_RANGES,
    BollingerExplorationConfig,
    BollingerExplorationResult,
    BollingerLoopConfig,
    BollingerLoopResult,
    run_bollinger_exploration,
    run_bollinger_exploration_loop,
)
from backtest.mean_reversion_analysis import (
    MeanReversionSummary,
    analyze_all_months_mean_reversion,
)
from backtest.service import (
    AllMonthsResult,
    BacktestRunArtifacts,
    BacktestRunConfig,
    run_all_months,
    run_backtest,
)
from backtest.simulator import IntrabarFillPolicy
from explore_gui_app.styles.terminal_dark_theme import apply_terminal_dark_theme
from explore_gui_app.services.refinement import build_refinement_plan
from explore_gui_app.views.analysis_panel import AnalysisPanel
from explore_gui_app.views.backtest_panel import BacktestPanel
from explore_gui_app.views.chart_tab import ChartTab
from explore_gui_app.views.input_panel import ExploreInputPanel
from explore_gui_app.views.result_panel import ExploreResultPanel
from gui_common.strategy_params import get_param_specs

logger = logging.getLogger(__name__)


class _ExplorationWorker(QThread):
    """Runs run_bollinger_exploration_loop in a background thread."""

    iteration_done = Signal(int, object)  # (iteration, BollingerExplorationResult)
    finished_ok = Signal(object)  # BollingerLoopResult
    finished_error = Signal(str)
    log_message = Signal(str)

    def __init__(self, config: BollingerLoopConfig, parent: QThread | None = None) -> None:
        super().__init__(parent)
        self._config = config

    def run(self) -> None:
        try:
            self.log_message.emit(
                f"Starting exploration: strategy={self._config.strategy_name}, "
                f"max_iterations={self._config.max_iterations}, "
                f"seed={self._config.random_seed}"
            )
            result = run_bollinger_exploration_loop(
                self._config,
                thread=self,
                on_iteration_done=lambda idx, r: self.iteration_done.emit(idx, r),
            )
            self.finished_ok.emit(result)
        except Exception as exc:
            logger.exception("Exploration worker failed")
            self.finished_error.emit(str(exc))


class _Phase2Worker(QThread):
    """Runs Phase 2: re-evaluate top candidates with all CSVs."""

    candidate_done = Signal(int, object)  # (index, BollingerExplorationResult)
    finished_ok = Signal(list)  # list[BollingerExplorationResult]
    finished_error = Signal(str)
    log_message = Signal(str)

    def __init__(
        self,
        candidates: list[dict[str, float]],
        base_config: BollingerLoopConfig,
        parent: QThread | None = None,
    ) -> None:
        super().__init__(parent)
        self._candidates = candidates
        self._base_config = base_config

    def run(self) -> None:
        try:
            cfg = self._base_config
            results: list[BollingerExplorationResult] = []
            for idx, overrides in enumerate(self._candidates, 1):
                if self.isInterruptionRequested():
                    self.log_message.emit("Phase 2 stopped by user")
                    break

                self.log_message.emit(
                    f"Phase 2 candidate {idx}/{len(self._candidates)}: {overrides}"
                )
                exploration_config = BollingerExplorationConfig(
                    strategy_name=cfg.strategy_name,
                    csv_path=cfg.csv_path,
                    symbol=cfg.symbol,
                    timeframe=cfg.timeframe,
                    pip_size=cfg.pip_size,
                    sl_pips=cfg.sl_pips,
                    tp_pips=cfg.tp_pips,
                    intrabar_fill_policy=cfg.intrabar_fill_policy,
                    param_overrides=overrides if overrides else None,
                    thresholds=cfg.thresholds,
                    csv_dir=cfg.csv_dir,
                    cross_month_thresholds=cfg.cross_month_thresholds,
                    integrated_thresholds=cfg.integrated_thresholds,
                    csv_paths=None,
                )
                result = run_bollinger_exploration(exploration_config)
                results.append(result)
                self.candidate_done.emit(idx, result)

            self.finished_ok.emit(results)
        except Exception as exc:
            logger.exception("Phase 2 worker failed")
            self.finished_error.emit(str(exc))


class _MRAnalysisWorker(QThread):
    """Compute Phase 2 full-period mean-reversion summary in a background thread."""

    finished_ok = Signal(object)  # MeanReversionSummary | None
    finished_error = Signal(str)

    def __init__(
        self,
        csv_files: list[Path],
        base_config: BollingerLoopConfig,
        overrides: dict[str, float],
        parent: QThread | None = None,
    ) -> None:
        super().__init__(parent)
        self._csv_files = csv_files
        self._base_config = base_config
        self._overrides = overrides

    def run(self) -> None:
        try:
            cfg = self._base_config
            monthly_artifacts: list[tuple[str, BacktestRunArtifacts]] = []
            for csv_file in self._csv_files:
                if self.isInterruptionRequested():
                    return
                run_config = BacktestRunConfig(
                    csv_path=csv_file,
                    strategy_name=cfg.strategy_name,
                    symbol=cfg.symbol,
                    timeframe=cfg.timeframe,
                    pip_size=cfg.pip_size,
                    sl_pips=cfg.sl_pips,
                    tp_pips=cfg.tp_pips,
                    intrabar_fill_policy=cfg.intrabar_fill_policy,
                    strategy_params=self._overrides or None,
                )
                artifacts = run_backtest(run_config)
                monthly_artifacts.append((csv_file.stem, artifacts))

            summary = analyze_all_months_mean_reversion(monthly_artifacts)
            self.finished_ok.emit(summary.all_period)
        except Exception as exc:
            logger.exception("MR analysis worker failed")
            self.finished_error.emit(str(exc))


class _BacktestWorker(QThread):
    """Run a single ``run_backtest`` or ``run_all_months`` for タブ B."""

    finished_single = Signal(object)  # BacktestRunArtifacts
    finished_all_months = Signal(object)  # AllMonthsResult
    finished_error = Signal(str)
    log_message = Signal(str)
    progress_signal = Signal(int, int)  # (current, total). total<=0 は indeterminate

    def __init__(
        self,
        *,
        mode: str,
        single_config: BacktestRunConfig | None,
        csv_dir: Path | None,
        all_months_kwargs: dict | None,
        parent: QThread | None = None,
    ) -> None:
        super().__init__(parent)
        self._mode = mode
        self._single_config = single_config
        self._csv_dir = csv_dir
        self._all_months_kwargs = all_months_kwargs or {}

    def run(self) -> None:
        try:
            if self._mode == "single":
                if self._single_config is None:
                    raise ValueError("single_config is required for single mode")
                self.log_message.emit(
                    f"Single backtest started: csv={self._single_config.csv_path}"
                )
                # Single は内部 callback が無いので indeterminate のみ
                self.progress_signal.emit(0, 0)
                artifacts = run_backtest(self._single_config)
                self.progress_signal.emit(1, 1)
                self.finished_single.emit(artifacts)
            else:
                if self._csv_dir is None:
                    raise ValueError("csv_dir is required for all_months mode")
                self.log_message.emit(
                    f"All months backtest started: dir={self._csv_dir}"
                )
                kwargs = dict(self._all_months_kwargs)
                # 月独立モードでは月ごとの progress callback、connected モードでも
                # 最後に 1 回 (total, total) が返るので同じ callback でよい。
                # 開始直後に indeterminate を一瞬出して「動いている」ことを示す。
                self.progress_signal.emit(0, 0)
                kwargs["progress_callback"] = (
                    lambda current, total: self.progress_signal.emit(current, total)
                )
                result = run_all_months(
                    csv_dir=self._csv_dir,
                    **kwargs,
                )
                self.finished_all_months.emit(result)
        except Exception as exc:
            logger.exception("Backtest worker failed")
            self.finished_error.emit(str(exc))


class ExploreMainWindow(QMainWindow):
    """Main window for the bollinger exploration GUI."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Bollinger Exploration - A Single Strategy")
        self.resize(1320, 760)

        self._worker: _ExplorationWorker | None = None
        self._phase2_worker: _Phase2Worker | None = None
        self._mr_analysis_worker: _MRAnalysisWorker | None = None
        self._backtest_worker: _BacktestWorker | None = None
        self._max_iterations: int = 0
        self._current_phase: int = 0
        self._phase1_config: BollingerLoopConfig | None = None
        self._phase1_results: list[BollingerExplorationResult] = []

        self._input_panel = ExploreInputPanel()
        self._input_panel.setMinimumWidth(520)
        self._result_panel = ExploreResultPanel()

        self._tab_widget = QTabWidget()
        self.setCentralWidget(self._tab_widget)

        explore_tab = QWidget()
        explore_layout = QHBoxLayout(explore_tab)
        explore_layout.addWidget(self._input_panel)
        explore_layout.addWidget(self._result_panel, 1)
        self._tab_widget.addTab(explore_tab, "Explore")

        self._backtest_panel = BacktestPanel()
        self._tab_widget.addTab(self._backtest_panel, "Backtest 単発")

        self._chart_tab = ChartTab()
        self._tab_widget.addTab(self._chart_tab, "Chart")

        self._analysis_panel = AnalysisPanel()
        self._tab_widget.addTab(self._analysis_panel, "Analysis")

        self._input_panel.run_requested.connect(self._on_run)
        self._input_panel.refine_requested.connect(self._on_refine_from_trends)
        self._input_panel.stop_button.clicked.connect(self._on_stop)
        self._input_panel.confirm_all_requested.connect(self._on_confirm_all)
        self._backtest_panel.run_requested.connect(self._on_backtest_run)
        self._backtest_panel.stop_requested.connect(self._on_backtest_stop)

        apply_terminal_dark_theme(self)

    def _on_run(self) -> None:
        csv_path = self._input_panel.get_csv_path()
        csv_paths = self._input_panel.get_csv_paths()

        if csv_paths:
            csv_path = csv_paths[-1]
        elif not csv_path:
            QMessageBox.warning(self, "Input Error", "Please select a CSV file.")
            return

        strategy_name = self._input_panel.get_strategy_name()
        param_overrides = self._input_panel.get_base_param_overrides()

        param_variation_ranges: dict[str, tuple[float, float, float]] | None = None
        user_ranges = self._input_panel.get_param_override_ranges()
        if user_ranges:
            param_variation_ranges = {k: v for k, v in user_ranges.items()}
        else:
            default_ranges = BOLLINGER_PARAM_VARIATION_RANGES.get(strategy_name)
            if default_ranges:
                param_variation_ranges = copy.deepcopy(default_ranges)

        config = BollingerLoopConfig(
            strategy_name=strategy_name,
            csv_path=csv_path,
            csv_dir=self._input_panel.get_csv_dir(),
            csv_paths=csv_paths,
            max_iterations=self._input_panel.get_max_iterations(),
            max_improve_retries=self._input_panel.get_max_improve_retries(),
            max_param_variations=self._input_panel.get_max_param_variations(),
            random_seed=self._input_panel.get_random_seed(),
            param_overrides=param_overrides,
            param_variation_ranges=param_variation_ranges,
            seed_overrides_list=self._input_panel.get_seed_param_overrides_list(),
        )

        self._max_iterations = config.max_iterations
        self._phase1_config = config
        self._phase1_results = []

        is_phase1 = csv_paths is not None and self._input_panel.get_csv_dir()
        self._current_phase = 1 if is_phase1 else 0

        self._result_panel.clear()
        self._result_panel.show_phase2_results(False)
        self._result_panel.clear_phase2_results()
        self._result_panel.hide_phase2_summary()
        self._result_panel.set_phase(self._current_phase)
        self._result_panel.set_status("Running...")
        self._analysis_panel.set_summary(None)
        self._input_panel.run_button.setEnabled(False)
        self._input_panel.refine_button.setEnabled(False)
        self._input_panel.confirm_all_button.setEnabled(False)
        self._input_panel.stop_button.setEnabled(True)

        self._worker = _ExplorationWorker(config)
        self._worker.iteration_done.connect(self._on_iteration_done)
        self._worker.finished_ok.connect(self._on_finished_ok)
        self._worker.finished_error.connect(self._on_finished_error)
        self._worker.log_message.connect(self._result_panel.append_log)
        self._worker.start()

    def _on_refine_from_trends(self) -> None:
        results = self._result_panel.get_all_iteration_results()
        if len(results) < 3:
            QMessageBox.warning(
                self,
                "Refinement Error",
                "At least 3 exploration results are required before refinement.",
            )
            return

        strategy_name = self._input_panel.get_strategy_name()
        current_ranges = self._input_panel.get_param_override_ranges()
        if not current_ranges:
            QMessageBox.warning(
                self,
                "Refinement Error",
                "No exploration parameters are enabled.",
            )
            return

        specs = get_param_specs(strategy_name)
        if not specs:
            QMessageBox.warning(
                self,
                "Refinement Error",
                f"No parameter specs found for strategy '{strategy_name}'.",
            )
            return

        try:
            plan = build_refinement_plan(
                strategy_name=strategy_name,
                results=results,
                current_ranges=current_ranges,
                specs=specs,
            )
        except Exception as exc:
            logger.exception("Trend refinement failed")
            QMessageBox.critical(self, "Refinement Error", str(exc))
            return

        self._input_panel.set_param_override_ranges(plan.recommended_ranges)
        self._input_panel.set_base_param_overrides(plan.base_overrides)
        self._input_panel.set_seed_param_overrides_list(plan.seed_overrides_list)

        for line in plan.summary_lines:
            self._result_panel.append_log(line)

        self._result_panel.set_status(
            f"Refinement ready: {len(plan.top_results)} top result(s), "
            f"{len(plan.seed_overrides_list)} seed candidate(s)"
        )

    def _on_stop(self) -> None:
        if self._worker and self._worker.isRunning():
            self._result_panel.append_log("Stop requested (will finish current iteration)...")
            self._worker.requestInterruption()
        if self._phase2_worker and self._phase2_worker.isRunning():
            self._result_panel.append_log("Phase 2 stop requested...")
            self._phase2_worker.requestInterruption()
        if self._mr_analysis_worker and self._mr_analysis_worker.isRunning():
            self._result_panel.append_log("MR analysis stop requested...")
            self._mr_analysis_worker.requestInterruption()

    def _on_iteration_done(self, iteration: int, result: BollingerExplorationResult) -> None:
        self._result_panel.set_status(
            f"Running... Iteration {iteration} / {self._max_iterations}"
        )
        self._result_panel.add_iteration_result(iteration, result)
        base_cmp_line = ""
        if result.baseline_comparison is not None:
            if iteration == 1:
                bs = result.baseline_comparison.baseline_summary
                self._result_panel.append_log(
                    f"Baseline (no overrides): total_pips={bs.get('total_pips', 0.0):+.1f}, "
                    f"worst_month={bs.get('worst_month_pips', 0.0):+.1f}, "
                    f"deficit_months={bs.get('deficit_month_count', 0)}, "
                    f"consec_deficit={bs.get('max_consecutive_deficit_months', 0)}"
                )
            c = result.baseline_comparison.comparison
            base_cmp_line = (
                f" | Δpips={c.total_pips_delta:+.1f} "
                f"({c.total_pips_delta_ratio * 100:+.1f}%), "
                f"Δworst={c.worst_month_delta:+.1f}, "
                f"Δdeficit={-c.deficit_month_delta:+d}, "
                f"Δconsec={-c.consecutive_deficit_delta:+d}"
            )
        self._result_panel.append_log(
            f"Iteration {iteration}: verdict={result.verdict}{base_cmp_line}, "
            f"overrides={result.param_overrides}"
        )

    def _on_finished_ok(self, loop_result: BollingerLoopResult) -> None:
        self._result_panel.show_final_result(loop_result)
        self._result_panel.append_log(
            f"Exploration complete: {loop_result.stopped_reason} "
            f"({loop_result.iterations} iterations)"
        )

        self._phase1_results = list(loop_result.results)

        candidate = loop_result.adopted or self._best_phase1_result()
        if candidate is not None:
            self._push_candidate_to_backtest_panel(candidate.param_overrides)

        if (
            self._current_phase == 1
            and self._phase1_results
            and self._input_panel.get_csv_dir()
        ):
            self._input_panel.confirm_all_button.setEnabled(True)
            self._result_panel.append_log(
                f"Phase 1 complete with {len(self._phase1_results)} result(s). "
                "Click '全期間で確認する' to run Phase 2."
            )

        self._cleanup_worker()

    def _on_finished_error(self, error_msg: str) -> None:
        self._result_panel.set_status(f"Error: {error_msg}")
        self._result_panel.append_log(f"ERROR: {error_msg}")
        QMessageBox.critical(self, "Exploration Error", error_msg)
        self._cleanup_worker()

    def _cleanup_worker(self) -> None:
        self._input_panel.run_button.setEnabled(True)
        self._input_panel.refine_button.setEnabled(True)
        self._input_panel.stop_button.setEnabled(False)
        self._worker = None

    def _get_top_candidates(self, max_candidates: int = 5) -> list[dict[str, float]]:
        if not self._phase1_results:
            return []

        def _score(r: BollingerExplorationResult) -> float:
            if r.aggregate_stats:
                return r.aggregate_stats.average_pips_per_month
            ss = r.evaluation.stats_summary
            return ss.get("total_pips", 0.0) or 0.0

        sorted_results = sorted(self._phase1_results, key=_score, reverse=True)

        seen: set[tuple[tuple[str, float], ...]] = set()
        candidates: list[dict[str, float]] = []
        for r in sorted_results:
            key = tuple(sorted(r.param_overrides.items()))
            if key in seen:
                continue
            seen.add(key)
            candidates.append(dict(r.param_overrides))
            if len(candidates) >= max_candidates:
                break
        return candidates

    def _on_confirm_all(self) -> None:
        csv_dir = self._input_panel.get_csv_dir()
        if not csv_dir:
            QMessageBox.warning(
                self,
                "Phase 2 Error",
                "CSV Dir is required for Phase 2.",
            )
            return

        candidates = self._get_top_candidates()
        if not candidates:
            QMessageBox.warning(
                self,
                "Phase 2 Error",
                "No Phase 1 results available for confirmation.",
            )
            return

        if not self._phase1_config:
            QMessageBox.warning(
                self,
                "Phase 2 Error",
                "Phase 1 config not available.",
            )
            return

        self._current_phase = 2
        self._result_panel.set_phase(2)
        self._result_panel.show_phase2_results(True)
        self._result_panel.clear_phase2_results()
        self._result_panel.set_status(
            f"Phase 2: evaluating {len(candidates)} candidate(s) with all CSVs..."
        )
        self._result_panel.append_log(
            f"Phase 2 started: {len(candidates)} top candidate(s)"
        )

        self._input_panel.run_button.setEnabled(False)
        self._input_panel.refine_button.setEnabled(False)
        self._input_panel.confirm_all_button.setEnabled(False)
        self._input_panel.stop_button.setEnabled(True)

        self._phase2_worker = _Phase2Worker(
            candidates=candidates,
            base_config=self._phase1_config,
        )
        self._phase2_worker.candidate_done.connect(self._on_phase2_candidate_done)
        self._phase2_worker.finished_ok.connect(self._on_phase2_finished_ok)
        self._phase2_worker.finished_error.connect(self._on_phase2_finished_error)
        self._phase2_worker.log_message.connect(self._result_panel.append_log)
        self._phase2_worker.start()

    def _on_phase2_candidate_done(
        self,
        index: int,
        result: BollingerExplorationResult,
    ) -> None:
        self._result_panel.add_phase2_result(index, result)
        self._result_panel.show_monthly_breakdown(result)
        self._result_panel.set_status(f"Phase 2: candidate {index} evaluated")
        self._result_panel.append_log(
            f"Phase 2 candidate {index}: verdict={result.verdict}, "
            f"avg_pips={result.aggregate_stats.average_pips_per_month:.1f}"
            if result.aggregate_stats
            else f"Phase 2 candidate {index}: verdict={result.verdict}"
        )

    def _on_phase2_finished_ok(
        self,
        results: list[BollingerExplorationResult],
    ) -> None:
        self._result_panel.set_status(
            f"Phase 2 complete: {len(results)} candidate(s) evaluated"
        )
        self._result_panel.append_log(
            f"Phase 2 finished: {len(results)} candidate(s) confirmed"
        )
        if results:
            best = max(
                results,
                key=lambda r: (
                    r.aggregate_stats.average_pips_per_month
                    if r.aggregate_stats
                    else 0.0
                ),
            )
            self._result_panel.show_monthly_breakdown(best)
            self._result_panel.show_phase2_summary(results)
            self._push_candidate_to_backtest_panel(best.param_overrides)
            self._start_mr_analysis(best)
        self._cleanup_phase2_worker()

    def _start_mr_analysis(self, best: BollingerExplorationResult) -> None:
        cfg = self._phase1_config
        if cfg is None or not cfg.csv_dir:
            return

        csv_files = sorted(Path(cfg.csv_dir).glob("*.csv"))
        if not csv_files:
            return

        self._result_panel.append_log(
            f"Phase 2 MR analysis started for best candidate "
            f"(overrides={best.param_overrides})"
        )

        self._mr_analysis_worker = _MRAnalysisWorker(
            csv_files=csv_files,
            base_config=cfg,
            overrides=dict(best.param_overrides),
        )
        self._mr_analysis_worker.finished_ok.connect(self._on_mr_analysis_finished_ok)
        self._mr_analysis_worker.finished_error.connect(
            self._on_mr_analysis_finished_error
        )
        self._mr_analysis_worker.start()

    def _on_mr_analysis_finished_ok(self, summary: MeanReversionSummary) -> None:
        self._analysis_panel.set_summary(summary)
        self._result_panel.append_log("Phase 2 MR analysis complete (Analysis tab updated)")
        self._mr_analysis_worker = None

    def _on_mr_analysis_finished_error(self, error_msg: str) -> None:
        self._result_panel.append_log(f"Phase 2 MR analysis ERROR: {error_msg}")
        self._mr_analysis_worker = None

    def _on_phase2_finished_error(self, error_msg: str) -> None:
        self._result_panel.set_status(f"Phase 2 Error: {error_msg}")
        self._result_panel.append_log(f"Phase 2 ERROR: {error_msg}")
        QMessageBox.critical(self, "Phase 2 Error", error_msg)
        self._cleanup_phase2_worker()

    def _cleanup_phase2_worker(self) -> None:
        self._input_panel.run_button.setEnabled(True)
        self._input_panel.refine_button.setEnabled(True)
        self._input_panel.stop_button.setEnabled(False)
        self._input_panel.confirm_all_button.setEnabled(False)
        self._current_phase = 0
        self._phase2_worker = None

    def _best_phase1_result(self) -> BollingerExplorationResult | None:
        if not self._phase1_results:
            return None

        def _score(r: BollingerExplorationResult) -> float:
            if r.aggregate_stats:
                return r.aggregate_stats.average_pips_per_month
            ss = r.evaluation.stats_summary
            return ss.get("total_pips", 0.0) or 0.0

        return max(self._phase1_results, key=_score)

    def _push_candidate_to_backtest_panel(
        self,
        param_overrides: dict[str, float] | None,
    ) -> None:
        strategy_name = self._input_panel.get_strategy_name()
        self._backtest_panel.set_candidate(
            strategy_name=strategy_name,
            param_overrides=param_overrides,
        )

        csv_paths = self._input_panel.get_csv_paths()
        csv_dir = self._input_panel.get_csv_dir()
        if csv_paths:
            self._backtest_panel.set_csv_path(csv_paths[-1])
        else:
            existing = self._input_panel.get_csv_path()
            if existing:
                self._backtest_panel.set_csv_path(existing)
        if csv_dir:
            self._backtest_panel.set_csv_dir(csv_dir)

    def _on_backtest_run(self) -> None:
        if self._backtest_worker is not None and self._backtest_worker.isRunning():
            return

        strategy_name = self._backtest_panel.get_candidate_strategy()
        if not strategy_name:
            QMessageBox.warning(
                self,
                "Backtest Error",
                "No exploration candidate is available yet. "
                "Run an exploration first.",
            )
            return

        try:
            pip_size = self._backtest_panel.get_pip_size()
            sl_pips = self._backtest_panel.get_sl_pips()
            tp_pips = self._backtest_panel.get_tp_pips()
        except ValueError as exc:
            QMessageBox.warning(self, "Backtest Error", str(exc))
            return

        symbol = self._backtest_panel.get_symbol()
        timeframe = self._backtest_panel.get_timeframe()
        overrides = self._backtest_panel.get_candidate_overrides()
        mode = self._backtest_panel.get_mode()

        single_config: BacktestRunConfig | None = None
        csv_dir_path: Path | None = None
        all_months_kwargs: dict | None = None

        if mode == BacktestPanel.MODE_SINGLE:
            csv_path_text = self._backtest_panel.get_csv_path()
            if not csv_path_text:
                QMessageBox.warning(
                    self,
                    "Backtest Error",
                    "Single CSV path is not set.",
                )
                return
            csv_path = Path(csv_path_text)
            if not csv_path.exists():
                QMessageBox.warning(
                    self,
                    "Backtest Error",
                    f"CSV not found: {csv_path}",
                )
                return
            single_config = BacktestRunConfig(
                csv_path=csv_path,
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                pip_size=pip_size,
                sl_pips=sl_pips,
                tp_pips=tp_pips,
                intrabar_fill_policy=IntrabarFillPolicy.CONSERVATIVE,
                strategy_params=overrides,
            )
        else:
            csv_dir_text = self._backtest_panel.get_csv_dir()
            if not csv_dir_text:
                QMessageBox.warning(
                    self,
                    "Backtest Error",
                    "CSV directory is not set.",
                )
                return
            csv_dir_path = Path(csv_dir_text)
            if not csv_dir_path.is_dir():
                QMessageBox.warning(
                    self,
                    "Backtest Error",
                    f"Directory not found: {csv_dir_path}",
                )
                return
            all_months_kwargs = dict(
                strategy_name=strategy_name,
                symbol=symbol,
                timeframe=timeframe,
                pip_size=pip_size,
                sl_pips=sl_pips,
                tp_pips=tp_pips,
                intrabar_fill_policy=IntrabarFillPolicy.CONSERVATIVE,
                strategy_params=overrides,
                connected=self._backtest_panel.get_connected(),
            )

        self._backtest_panel.clear_summary()
        self._backtest_panel.set_running(True)
        self._backtest_panel.set_status("Running backtest...")

        self._backtest_worker = _BacktestWorker(
            mode="single" if mode == BacktestPanel.MODE_SINGLE else "all_months",
            single_config=single_config,
            csv_dir=csv_dir_path,
            all_months_kwargs=all_months_kwargs,
        )
        self._backtest_worker.finished_single.connect(
            self._on_backtest_finished_single
        )
        self._backtest_worker.finished_all_months.connect(
            self._on_backtest_finished_all_months
        )
        self._backtest_worker.finished_error.connect(
            self._on_backtest_finished_error
        )
        self._backtest_worker.log_message.connect(
            self._backtest_panel.append_log
        )
        self._backtest_worker.progress_signal.connect(
            self._backtest_panel.set_progress
        )
        self._backtest_worker.start()

    def _on_backtest_stop(self) -> None:
        if self._backtest_worker is not None and self._backtest_worker.isRunning():
            self._backtest_panel.append_log(
                "Stop requested (current backtest will run to completion)."
            )

    def _on_backtest_finished_single(
        self,
        artifacts: BacktestRunArtifacts,
    ) -> None:
        self._backtest_panel.show_single_artifacts(artifacts)
        self._backtest_panel.set_status(
            f"Single backtest complete: {artifacts.summary.verdict} "
            f"({artifacts.summary.trades} trades)"
        )
        # Chart タブ連携: 単発結果を渡す
        self._chart_tab.set_artifacts(artifacts)
        self._cleanup_backtest_worker()

    def _on_backtest_finished_all_months(self, result: AllMonthsResult) -> None:
        self._backtest_panel.show_aggregate(result.aggregate)
        self._backtest_panel.set_status(
            f"All months complete: {result.aggregate.month_count} months, "
            f"{result.aggregate.total_trades} trades, "
            f"{result.aggregate.total_pips:.2f} pips"
        )
        # Chart タブ連携: 連結モードなら単一 artifacts、月独立モードなら先頭月のみ
        # (月独立では artifact が 1 月分しか描画できないので暫定仕様)
        if result.monthly_artifacts:
            _, first_artifacts = result.monthly_artifacts[0]
            self._chart_tab.set_artifacts(first_artifacts)
        self._cleanup_backtest_worker()

    def _on_backtest_finished_error(self, message: str) -> None:
        self._backtest_panel.set_status(f"Backtest ERROR: {message}")
        QMessageBox.critical(self, "Backtest Error", message)
        self._cleanup_backtest_worker()

    def _cleanup_backtest_worker(self) -> None:
        self._backtest_panel.set_running(False)
        self._backtest_worker = None