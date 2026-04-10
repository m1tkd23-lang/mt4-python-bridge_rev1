# src/explore_gui_app/views/main_window.py
from __future__ import annotations

import copy
import logging

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QWidget,
)

from backtest.exploration_loop import (
    BollingerExplorationResult,
    BollingerLoopConfig,
    BollingerLoopResult,
    BOLLINGER_PARAM_VARIATION_RANGES,
    run_bollinger_exploration_loop,
)

from explore_gui_app.views.input_panel import ExploreInputPanel
from explore_gui_app.views.result_panel import ExploreResultPanel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------


class ExploreMainWindow(QMainWindow):
    """Main window for the bollinger exploration GUI."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Bollinger Exploration - A Single Strategy")
        self.resize(1200, 700)

        self._worker: _ExplorationWorker | None = None
        self._max_iterations: int = 0

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)

        # Left: input panel
        self._input_panel = ExploreInputPanel()
        self._input_panel.setFixedWidth(420)
        root_layout.addWidget(self._input_panel)

        # Right: result panel
        self._result_panel = ExploreResultPanel()
        root_layout.addWidget(self._result_panel, 1)

        # Signals
        self._input_panel.run_requested.connect(self._on_run)
        self._input_panel.stop_button.clicked.connect(self._on_stop)

    # ------------------------------------------------------------------
    # Run / Stop
    # ------------------------------------------------------------------

    def _on_run(self) -> None:
        csv_path = self._input_panel.get_csv_path()
        if not csv_path:
            QMessageBox.warning(self, "Input Error", "Please select a CSV file.")
            return

        strategy_name = self._input_panel.get_strategy_name()

        # Build param_overrides from enabled ranges
        # (use None to let the loop generate random variations from BOLLINGER_PARAM_VARIATION_RANGES)
        param_overrides: dict[str, float] | None = None

        # Build local variation ranges — never mutate the module-level dict
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
            max_iterations=self._input_panel.get_max_iterations(),
            max_improve_retries=self._input_panel.get_max_improve_retries(),
            max_param_variations=self._input_panel.get_max_param_variations(),
            random_seed=self._input_panel.get_random_seed(),
            param_overrides=param_overrides,
            param_variation_ranges=param_variation_ranges,
        )

        self._max_iterations = config.max_iterations

        self._result_panel.clear()
        self._result_panel.set_status("Running...")
        self._input_panel.run_button.setEnabled(False)
        self._input_panel.stop_button.setEnabled(True)

        self._worker = _ExplorationWorker(config)
        self._worker.iteration_done.connect(self._on_iteration_done)
        self._worker.finished_ok.connect(self._on_finished_ok)
        self._worker.finished_error.connect(self._on_finished_error)
        self._worker.log_message.connect(self._result_panel.append_log)
        self._worker.start()

    def _on_stop(self) -> None:
        if self._worker and self._worker.isRunning():
            self._result_panel.append_log("Stop requested (will finish current iteration)...")
            self._worker.requestInterruption()

    def _on_iteration_done(self, iteration: int, result: BollingerExplorationResult) -> None:
        self._result_panel.set_status(f"Running... Iteration {iteration} / {self._max_iterations}")
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
        self._cleanup_worker()

    def _on_finished_error(self, error_msg: str) -> None:
        self._result_panel.set_status(f"Error: {error_msg}")
        self._result_panel.append_log(f"ERROR: {error_msg}")
        QMessageBox.critical(self, "Exploration Error", error_msg)
        self._cleanup_worker()

    def _cleanup_worker(self) -> None:
        self._input_panel.run_button.setEnabled(True)
        self._input_panel.stop_button.setEnabled(False)
        self._worker = None
