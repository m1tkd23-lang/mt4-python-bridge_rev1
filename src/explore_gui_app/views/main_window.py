# src\explore_gui_app\views\main_window.py
from __future__ import annotations

import copy
import logging

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
from gui_common.strategy_params import get_param_specs
from explore_gui_app.services.refinement import build_refinement_plan
from explore_gui_app.views.input_panel import ExploreInputPanel
from explore_gui_app.views.result_panel import ExploreResultPanel

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
            # Phase 2: use csv_dir for all CSVs (csv_paths=None)
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
                    csv_paths=None,  # Use csv_dir for all CSVs
                )
                result = run_bollinger_exploration(exploration_config)
                results.append(result)
                self.candidate_done.emit(idx, result)

            self.finished_ok.emit(results)
        except Exception as exc:
            logger.exception("Phase 2 worker failed")
            self.finished_error.emit(str(exc))


class ExploreMainWindow(QMainWindow):
    """Main window for the bollinger exploration GUI."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Bollinger Exploration - A Single Strategy")
        self.resize(1320, 760)

        self._worker: _ExplorationWorker | None = None
        self._phase2_worker: _Phase2Worker | None = None
        self._max_iterations: int = 0
        self._current_phase: int = 0  # 0=idle, 1=Phase1, 2=Phase2
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

        self._backtest_tab = QWidget()
        self._tab_widget.addTab(self._backtest_tab, "Backtest 単発")

        self._analysis_tab = QWidget()
        self._tab_widget.addTab(self._analysis_tab, "Analysis")

        self._input_panel.run_requested.connect(self._on_run)
        self._input_panel.refine_requested.connect(self._on_refine_from_trends)
        self._input_panel.stop_button.clicked.connect(self._on_stop)
        self._input_panel.confirm_all_requested.connect(self._on_confirm_all)

    def _on_run(self) -> None:
        csv_path = self._input_panel.get_csv_path()
        csv_paths = self._input_panel.get_csv_paths()

        # When csv_paths is available, csv_path is derived from csv_paths[-1]
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

        # Determine phase: Phase 1 if using selected CSV mode with csv_paths
        is_phase1 = csv_paths is not None and self._input_panel.get_csv_dir()
        self._current_phase = 1 if is_phase1 else 0

        self._result_panel.clear()
        self._result_panel.show_phase2_results(False)
        self._result_panel.clear_phase2_results()
        self._result_panel.hide_phase2_summary()
        self._result_panel.set_phase(self._current_phase)
        self._result_panel.set_status("Running...")
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

    def _on_iteration_done(self, iteration: int, result: BollingerExplorationResult) -> None:
        self._result_panel.set_status(
            f"Running... Iteration {iteration} / {self._max_iterations}"
        )
        self._result_panel.add_iteration_result(iteration, result)
        self._result_panel.append_log(
            f"Iteration {iteration}: verdict={result.verdict}, "
            f"overrides={result.param_overrides}"
        )

    def _on_finished_ok(self, loop_result: BollingerLoopResult) -> None:
        self._result_panel.show_final_result(loop_result)
        self._result_panel.append_log(
            f"Exploration complete: {loop_result.stopped_reason} "
            f"({loop_result.iterations} iterations)"
        )

        # Store Phase 1 results for potential Phase 2
        self._phase1_results = list(loop_result.results)

        # Enable "全期間で確認する" if Phase 1 with csv_dir available
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

    # ------------------------------------------------------------------
    # Phase 2: confirm all CSVs
    # ------------------------------------------------------------------

    def _get_top_candidates(self, max_candidates: int = 5) -> list[dict[str, float]]:
        """Extract unique top candidate param overrides from Phase 1 results."""
        if not self._phase1_results:
            return []

        # Score by aggregate average_pips_per_month if available, else single total_pips
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
        """Start Phase 2: re-evaluate top candidates with all CSVs."""
        csv_dir = self._input_panel.get_csv_dir()
        if not csv_dir:
            QMessageBox.warning(
                self, "Phase 2 Error", "CSV Dir is required for Phase 2."
            )
            return

        candidates = self._get_top_candidates()
        if not candidates:
            QMessageBox.warning(
                self, "Phase 2 Error",
                "No Phase 1 results available for confirmation."
            )
            return

        if not self._phase1_config:
            QMessageBox.warning(
                self, "Phase 2 Error", "Phase 1 config not available."
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
        self, index: int, result: BollingerExplorationResult
    ) -> None:
        self._result_panel.add_phase2_result(index, result)
        self._result_panel.show_monthly_breakdown(result)
        self._result_panel.set_status(
            f"Phase 2: candidate {index} evaluated"
        )
        self._result_panel.append_log(
            f"Phase 2 candidate {index}: verdict={result.verdict}, "
            f"avg_pips={result.aggregate_stats.average_pips_per_month:.1f}"
            if result.aggregate_stats
            else f"Phase 2 candidate {index}: verdict={result.verdict}"
        )

    def _on_phase2_finished_ok(
        self, results: list[BollingerExplorationResult]
    ) -> None:
        self._result_panel.set_status(
            f"Phase 2 complete: {len(results)} candidate(s) evaluated"
        )
        self._result_panel.append_log(
            f"Phase 2 finished: {len(results)} candidate(s) confirmed"
        )
        # Show monthly breakdown of the best Phase 2 result and summary
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
        self._cleanup_phase2_worker()

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