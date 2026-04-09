# src/backtest_gui_app/views/main_window.py
from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from backtest.csv_loader import CsvLoadError
from backtest.service import (
    AllMonthsResult,
    BacktestRunArtifacts,
    BacktestRunConfig,
    CompareABResult,
    _resolve_lane_strategies,
    run_all_months,
    run_backtest,
)
from backtest.simulator import BacktestSimulationError, IntrabarFillPolicy
from backtest_gui_app.constants import DEFAULT_DATA_DIR, DEFAULT_STRATEGIES_DIR, REPO_ROOT
from backtest_gui_app.helpers import list_csv_paths, list_strategy_names
from backtest_gui_app.presenters.result_presenter import BacktestResultPresenter
from backtest_gui_app.services.run_config_builder import build_run_config
from backtest_gui_app.views.all_months_tab import AllMonthsTab
from backtest_gui_app.views.chart_overview_tab import ChartOverviewTab
from backtest_gui_app.views.compare_ab_tab import CompareABTab
from backtest_gui_app.views.input_panel import InputPanel
from backtest_gui_app.views.result_tabs import ResultTabs
from backtest_gui_app.views.summary_panel import SummaryPanel


class _AllMonthsCancelled(Exception):
    """Raised inside progress_callback to abort run_all_months loop."""


class AllMonthsWorker(QThread):
    """Worker thread that runs backtest for each month and emits progress."""

    progress = Signal(int, int)  # (completed_count, total_count)
    finished_ok = Signal(object)  # AllMonthsResult
    finished_error = Signal(str)  # error message
    finished_cancelled = Signal()  # cancelled by user

    def __init__(
        self,
        csv_dir: Path,
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
        strategy_params: dict[str, float] | None = None,
        trade_log_dir: Path | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._csv_dir = csv_dir
        self._strategy_name = strategy_name
        self._symbol = symbol
        self._timeframe = timeframe
        self._pip_size = pip_size
        self._sl_pips = sl_pips
        self._tp_pips = tp_pips
        self._intrabar_fill_policy = intrabar_fill_policy
        self._close_open_position_at_end = close_open_position_at_end
        self._initial_balance = initial_balance
        self._money_per_pip = money_per_pip
        self._strategy_params = strategy_params
        self._trade_log_dir = trade_log_dir

    def _progress_with_cancel_check(self, completed: int, total: int) -> None:
        if self.isInterruptionRequested():
            raise _AllMonthsCancelled()
        self.progress.emit(completed, total)

    def run(self) -> None:
        try:
            result = run_all_months(
                csv_dir=self._csv_dir,
                strategy_name=self._strategy_name,
                symbol=self._symbol,
                timeframe=self._timeframe,
                pip_size=self._pip_size,
                sl_pips=self._sl_pips,
                tp_pips=self._tp_pips,
                intrabar_fill_policy=self._intrabar_fill_policy,
                close_open_position_at_end=self._close_open_position_at_end,
                initial_balance=self._initial_balance,
                money_per_pip=self._money_per_pip,
                progress_callback=self._progress_with_cancel_check,
                strategy_params=self._strategy_params,
                trade_log_dir=self._trade_log_dir,
            )
            self.finished_ok.emit(result)
        except _AllMonthsCancelled:
            self.finished_cancelled.emit()
        except Exception as exc:
            self.finished_error.emit(str(exc))


class CompareABWorker(QThread):
    """Worker thread that runs A/B comparison (3 phases: A, B, combo)."""

    phase_changed = Signal(str)  # phase label ("Lane A", "Lane B", "Combo")
    progress = Signal(int, int)  # (completed_months_in_phase, total_months)
    finished_ok = Signal(object)  # CompareABResult
    finished_error = Signal(str)
    finished_cancelled = Signal()

    def __init__(
        self,
        csv_dir: Path,
        combo_strategy_name: str,
        symbol: str,
        timeframe: str,
        pip_size: float,
        sl_pips: float,
        tp_pips: float,
        intrabar_fill_policy: IntrabarFillPolicy,
        close_open_position_at_end: bool,
        initial_balance: float,
        money_per_pip: float,
        strategy_params: dict[str, float] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._csv_dir = csv_dir
        self._combo_strategy_name = combo_strategy_name
        self._symbol = symbol
        self._timeframe = timeframe
        self._pip_size = pip_size
        self._sl_pips = sl_pips
        self._tp_pips = tp_pips
        self._intrabar_fill_policy = intrabar_fill_policy
        self._close_open_position_at_end = close_open_position_at_end
        self._initial_balance = initial_balance
        self._money_per_pip = money_per_pip
        self._strategy_params = strategy_params

    def _progress_with_cancel_check(self, completed: int, total: int) -> None:
        if self.isInterruptionRequested():
            raise _AllMonthsCancelled()
        self.progress.emit(completed, total)

    def run(self) -> None:
        try:
            lane_a_name, lane_b_name = _resolve_lane_strategies(
                self._combo_strategy_name
            )

            common_kwargs = dict(
                csv_dir=self._csv_dir,
                symbol=self._symbol,
                timeframe=self._timeframe,
                pip_size=self._pip_size,
                sl_pips=self._sl_pips,
                tp_pips=self._tp_pips,
                intrabar_fill_policy=self._intrabar_fill_policy,
                close_open_position_at_end=self._close_open_position_at_end,
                initial_balance=self._initial_balance,
                money_per_pip=self._money_per_pip,
                progress_callback=self._progress_with_cancel_check,
                strategy_params=self._strategy_params,
            )

            self.phase_changed.emit("Lane A")
            lane_a_result = run_all_months(
                strategy_name=lane_a_name, **common_kwargs
            )
            if self.isInterruptionRequested():
                raise _AllMonthsCancelled()

            self.phase_changed.emit("Lane B")
            lane_b_result = run_all_months(
                strategy_name=lane_b_name, **common_kwargs
            )
            if self.isInterruptionRequested():
                raise _AllMonthsCancelled()

            self.phase_changed.emit("Combo")
            combo_result = run_all_months(
                strategy_name=self._combo_strategy_name, **common_kwargs
            )

            result = CompareABResult(
                lane_a_strategy=lane_a_name,
                lane_b_strategy=lane_b_name,
                combo_strategy=self._combo_strategy_name,
                lane_a_result=lane_a_result,
                lane_b_result=lane_b_result,
                combo_result=combo_result,
            )
            self.finished_ok.emit(result)
        except _AllMonthsCancelled:
            self.finished_cancelled.emit()
        except Exception as exc:
            self.finished_error.emit(str(exc))


class BacktestMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MT4 Backtest GUI")
        self.resize(1520, 920)

        self._latest_artifacts: BacktestRunArtifacts | None = None
        self._syncing_trade_selection = False
        self._all_months_worker: AllMonthsWorker | None = None
        self._compare_ab_worker: CompareABWorker | None = None

        self.input_panel = InputPanel()
        self.summary_panel = SummaryPanel()
        self.result_tabs_panel = ResultTabs()
        self.chart_overview_tab = ChartOverviewTab()
        self.all_months_tab = AllMonthsTab()
        self.compare_ab_tab = CompareABTab()

        self._presenter = BacktestResultPresenter(
            summary_panel=self.summary_panel,
            result_tabs=self.result_tabs_panel,
            input_panel=self.input_panel,
            chart_overview_tab=self.chart_overview_tab,
        )

        self._build_layout()
        self._connect_signals()

        self._refresh_strategy_list()
        self._refresh_csv_list()
        self._apply_default_values()
        self._on_strategy_changed(
            self.input_panel.strategy_combo.currentText()
        )
        self._clear_result_views()

    def _build_layout(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        self.page_tabs = QTabWidget()
        self.page_tabs.addTab(self._build_standard_page(), "Standard")
        self.page_tabs.addTab(self.chart_overview_tab, "Chart view")
        self.page_tabs.addTab(self.all_months_tab, "All Months")
        self.page_tabs.addTab(self.compare_ab_tab, "Compare A/B")

        root_layout.addWidget(self.page_tabs)

    def _build_standard_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        upper_container = self._build_upper_area()
        lower_container = self._build_lower_area()

        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.addWidget(upper_container)
        main_splitter.addWidget(lower_container)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([300, 620])

        layout.addWidget(main_splitter)
        return page

    def _build_upper_area(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        top_splitter = QSplitter(Qt.Horizontal)
        top_splitter.addWidget(self.input_panel)
        top_splitter.addWidget(self.summary_panel)
        top_splitter.setStretchFactor(0, 3)
        top_splitter.setStretchFactor(1, 2)
        top_splitter.setSizes([950, 520])

        layout.addWidget(top_splitter)
        return container

    def _build_lower_area(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.result_tabs_panel)
        return container

    def _connect_signals(self) -> None:
        self.input_panel.refresh_strategy_button.clicked.connect(
            self._refresh_strategy_list
        )
        self.input_panel.refresh_csv_button.clicked.connect(self._refresh_csv_list)
        self.input_panel.browse_csv_button.clicked.connect(self._browse_csv_file)
        self.input_panel.run_button.clicked.connect(self._run_backtest)
        self.input_panel.clear_button.clicked.connect(self._clear_result_views)
        self.input_panel.export_trades_csv_button.clicked.connect(
            self._export_trades_csv
        )
        self.input_panel.strategy_combo.currentTextChanged.connect(
            self._on_strategy_changed
        )

        self.all_months_tab.browse_dir_button.clicked.connect(
            self._browse_csv_directory
        )
        self.all_months_tab.run_all_button.clicked.connect(self._run_all_months)
        self.all_months_tab.cancel_button.clicked.connect(self._cancel_all_months)

        self.compare_ab_tab.browse_dir_button.clicked.connect(
            self._browse_compare_ab_directory
        )
        self.compare_ab_tab.run_button.clicked.connect(self._run_compare_ab)
        self.compare_ab_tab.cancel_button.clicked.connect(self._cancel_compare_ab)

        self.result_tabs_panel.trades_table.itemSelectionChanged.connect(
            self._on_primary_trade_selection_changed
        )
        self.chart_overview_tab.detail_tabs.trades_table.itemSelectionChanged.connect(
            self._on_chart_trade_selection_changed
        )

    def _apply_default_values(self) -> None:
        self.input_panel.symbol_edit.setText("BACKTEST")
        self.input_panel.timeframe_edit.setText("M1")
        self.input_panel.pip_size_edit.setText("0.01")
        self.input_panel.sl_pips_edit.setText("10")
        self.input_panel.tp_pips_edit.setText("10")
        self.input_panel.initial_balance_edit.setText("1000000")
        self.input_panel.risk_percent_edit.setText("1.0")

    def _refresh_strategy_list(self) -> None:
        current = self.input_panel.strategy_combo.currentText().strip()
        names = list_strategy_names(DEFAULT_STRATEGIES_DIR)

        self.input_panel.strategy_combo.clear()
        self.input_panel.strategy_combo.addItems(names)

        if current:
            index = self.input_panel.strategy_combo.findText(current)
            if index >= 0:
                self.input_panel.strategy_combo.setCurrentIndex(index)

        if self.input_panel.strategy_combo.count() == 0:
            self.input_panel.notes_text.setPlainText(
                f"Strategy directory not found or empty:\n{DEFAULT_STRATEGIES_DIR}"
            )

    def _refresh_csv_list(self) -> None:
        current_data = self.input_panel.csv_combo.currentData()
        csv_paths = list_csv_paths(DEFAULT_DATA_DIR)

        self.input_panel.csv_combo.clear()
        for path in csv_paths:
            display_text = str(path.relative_to(REPO_ROOT))
            self.input_panel.csv_combo.addItem(display_text, str(path))

        if current_data:
            index = self._find_csv_combo_index_by_path(str(current_data))
            if index >= 0:
                self.input_panel.csv_combo.setCurrentIndex(index)

        if self.input_panel.csv_combo.count() == 0:
            self.input_panel.notes_text.setPlainText(
                f"CSV files not found under:\n{DEFAULT_DATA_DIR}"
            )

    def _browse_csv_file(self) -> None:
        start_dir = str(DEFAULT_DATA_DIR if DEFAULT_DATA_DIR.exists() else REPO_ROOT)
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Select CSV file",
            start_dir,
            "CSV Files (*.csv);;All Files (*)",
        )
        if not selected:
            return

        index = self._find_csv_combo_index_by_path(selected)
        if index >= 0:
            self.input_panel.csv_combo.setCurrentIndex(index)
            return

        display_text = self._display_path_for_combo(Path(selected))
        self.input_panel.csv_combo.addItem(display_text, selected)
        self.input_panel.csv_combo.setCurrentIndex(
            self.input_panel.csv_combo.count() - 1
        )

    def _find_csv_combo_index_by_path(self, path_text: str) -> int:
        for index in range(self.input_panel.csv_combo.count()):
            if self.input_panel.csv_combo.itemData(index) == path_text:
                return index
        return -1

    def _display_path_for_combo(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(REPO_ROOT.resolve()))
        except ValueError:
            return str(path)

    def _clear_result_views(self) -> None:
        self._latest_artifacts = None
        self._clear_trade_table_selection(self.result_tabs_panel.trades_table)
        self._clear_trade_table_selection(
            self.chart_overview_tab.detail_tabs.trades_table
        )
        self.chart_overview_tab.linked_chart.clear_highlight()
        self._presenter.clear_result_views()

    def _run_backtest(self) -> None:
        try:
            config = build_run_config(self.input_panel)
            artifacts = run_backtest(config)
        except (ValueError, CsvLoadError, BacktestSimulationError) as exc:
            self._show_error(str(exc))
            return
        except Exception as exc:
            self._show_error(f"Unexpected error: {exc}")
            return

        self._latest_artifacts = artifacts
        self._presenter.apply_artifacts_to_ui(artifacts)
        self._clear_trade_table_selection(self.result_tabs_panel.trades_table)
        self._clear_trade_table_selection(
            self.chart_overview_tab.detail_tabs.trades_table
        )
        self.chart_overview_tab.linked_chart.clear_highlight()

    def _browse_csv_directory(self) -> None:
        start_dir = str(DEFAULT_DATA_DIR if DEFAULT_DATA_DIR.exists() else REPO_ROOT)
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select CSV Directory",
            start_dir,
        )
        if selected:
            self.all_months_tab.csv_dir_edit.setText(selected)

    def _run_all_months(self) -> None:
        if self._all_months_worker is not None and self._all_months_worker.isRunning():
            return

        csv_dir_text = self.all_months_tab.csv_dir_edit.text().strip()
        if not csv_dir_text:
            self._show_error("CSV directory is not selected.")
            return

        csv_dir = Path(csv_dir_text)
        if not csv_dir.is_dir():
            self._show_error(f"Directory not found: {csv_dir}")
            return

        strategy_name = self.input_panel.strategy_combo.currentText().strip()
        if not strategy_name:
            self._show_error("Strategy is not selected.")
            return

        try:
            pip_size = float(self.input_panel.pip_size_edit.text().strip() or "0.01")
            sl_pips = float(self.input_panel.sl_pips_edit.text().strip() or "10")
            tp_pips = float(self.input_panel.tp_pips_edit.text().strip() or "10")
            initial_balance = float(
                self.input_panel.initial_balance_edit.text().strip() or "1000000"
            )
            risk_percent = float(
                self.input_panel.risk_percent_edit.text().strip() or "1.0"
            )
            money_per_pip = (initial_balance * risk_percent / 100.0) / sl_pips

            policy_text = self.input_panel.intrabar_policy_combo.currentText().strip()
            policy = IntrabarFillPolicy(policy_text)
        except ValueError as exc:
            self._show_error(str(exc))
            return

        self.all_months_tab.run_all_button.setEnabled(False)
        self.all_months_tab.cancel_button.setVisible(True)
        self.all_months_tab.progress_bar.setValue(0)
        self.all_months_tab.progress_bar.setVisible(True)
        self.all_months_tab.clear_results()
        self.input_panel.notes_text.setPlainText("Running all months...")

        strategy_params = self.input_panel.get_strategy_param_overrides() or None

        trade_log_dir: Path | None = None
        if self.all_months_tab.trade_log_checkbox.isChecked():
            trade_log_dir = Path("logs/trade_logs")

        self._all_months_worker = AllMonthsWorker(
            csv_dir=csv_dir,
            strategy_name=strategy_name,
            symbol=self.input_panel.symbol_edit.text().strip() or "BACKTEST",
            timeframe=self.input_panel.timeframe_edit.text().strip() or "M1",
            pip_size=pip_size,
            sl_pips=sl_pips,
            tp_pips=tp_pips,
            intrabar_fill_policy=policy,
            close_open_position_at_end=self.input_panel.close_position_checkbox.isChecked(),
            initial_balance=initial_balance,
            money_per_pip=money_per_pip,
            strategy_params=strategy_params,
            trade_log_dir=trade_log_dir,
            parent=self,
        )
        self._all_months_worker.progress.connect(self._on_all_months_progress)
        self._all_months_worker.finished_ok.connect(self._on_all_months_finished)
        self._all_months_worker.finished_error.connect(self._on_all_months_error)
        self._all_months_worker.finished_cancelled.connect(self._on_all_months_cancelled)
        self._all_months_worker.start()

    def _on_all_months_progress(self, completed: int, total: int) -> None:
        percent = int(completed / total * 100) if total > 0 else 0
        self.all_months_tab.progress_bar.setValue(percent)
        self.input_panel.notes_text.setPlainText(
            f"Running all months... ({completed}/{total})"
        )

    def _cancel_all_months(self) -> None:
        if self._all_months_worker is not None and self._all_months_worker.isRunning():
            self._all_months_worker.requestInterruption()
            self.all_months_tab.cancel_button.setEnabled(False)

    def _reset_all_months_ui(self) -> None:
        self.all_months_tab.run_all_button.setEnabled(True)
        self.all_months_tab.cancel_button.setVisible(False)
        self.all_months_tab.cancel_button.setEnabled(True)
        self.all_months_tab.progress_bar.setVisible(False)
        self.all_months_tab.progress_bar.setValue(0)
        self._all_months_worker = None

    def _on_all_months_finished(self, result: AllMonthsResult) -> None:
        self._reset_all_months_ui()

        self.all_months_tab.display_result(result)
        self.input_panel.notes_text.setPlainText(
            f"All months completed.\n"
            f"Months: {result.aggregate.month_count}\n"
            f"Total trades: {result.aggregate.total_trades}\n"
            f"Total pips: {result.aggregate.total_pips:.2f}\n"
            f"Win rate: {result.aggregate.overall_win_rate:.2f}%"
        )

    def _on_all_months_error(self, message: str) -> None:
        self._reset_all_months_ui()
        self._show_error(message)

    def _on_all_months_cancelled(self) -> None:
        self._reset_all_months_ui()
        self.input_panel.notes_text.setPlainText("All months execution cancelled.")

    # --- Compare A/B ---

    def _browse_compare_ab_directory(self) -> None:
        start_dir = str(DEFAULT_DATA_DIR if DEFAULT_DATA_DIR.exists() else REPO_ROOT)
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select CSV Directory",
            start_dir,
        )
        if selected:
            self.compare_ab_tab.csv_dir_edit.setText(selected)

    def _run_compare_ab(self) -> None:
        if self._compare_ab_worker is not None and self._compare_ab_worker.isRunning():
            return

        csv_dir_text = self.compare_ab_tab.csv_dir_edit.text().strip()
        if not csv_dir_text:
            self._show_error("CSV directory is not selected.")
            return

        csv_dir = Path(csv_dir_text)
        if not csv_dir.is_dir():
            self._show_error(f"Directory not found: {csv_dir}")
            return

        strategy_name = self.input_panel.strategy_combo.currentText().strip()
        if not strategy_name:
            self._show_error("Strategy is not selected.")
            return

        try:
            pip_size = float(self.input_panel.pip_size_edit.text().strip() or "0.01")
            sl_pips = float(self.input_panel.sl_pips_edit.text().strip() or "10")
            tp_pips = float(self.input_panel.tp_pips_edit.text().strip() or "10")
            initial_balance = float(
                self.input_panel.initial_balance_edit.text().strip() or "1000000"
            )
            risk_percent = float(
                self.input_panel.risk_percent_edit.text().strip() or "1.0"
            )
            money_per_pip = (initial_balance * risk_percent / 100.0) / sl_pips

            policy_text = self.input_panel.intrabar_policy_combo.currentText().strip()
            policy = IntrabarFillPolicy(policy_text)
        except ValueError as exc:
            self._show_error(str(exc))
            return

        self.compare_ab_tab.run_button.setEnabled(False)
        self.compare_ab_tab.cancel_button.setVisible(True)
        self.compare_ab_tab.progress_bar.setValue(0)
        self.compare_ab_tab.progress_bar.setVisible(True)
        self.compare_ab_tab.phase_label.setVisible(True)
        self.compare_ab_tab.phase_label.setText("")
        self.compare_ab_tab.clear_results()
        self.input_panel.notes_text.setPlainText("Running Compare A/B...")

        strategy_params = self.input_panel.get_strategy_param_overrides() or None

        self._compare_ab_worker = CompareABWorker(
            csv_dir=csv_dir,
            combo_strategy_name=strategy_name,
            symbol=self.input_panel.symbol_edit.text().strip() or "BACKTEST",
            timeframe=self.input_panel.timeframe_edit.text().strip() or "M1",
            pip_size=pip_size,
            sl_pips=sl_pips,
            tp_pips=tp_pips,
            intrabar_fill_policy=policy,
            close_open_position_at_end=self.input_panel.close_position_checkbox.isChecked(),
            initial_balance=initial_balance,
            money_per_pip=money_per_pip,
            strategy_params=strategy_params,
            parent=self,
        )
        self._compare_ab_worker.phase_changed.connect(self._on_compare_ab_phase)
        self._compare_ab_worker.progress.connect(self._on_compare_ab_progress)
        self._compare_ab_worker.finished_ok.connect(self._on_compare_ab_finished)
        self._compare_ab_worker.finished_error.connect(self._on_compare_ab_error)
        self._compare_ab_worker.finished_cancelled.connect(self._on_compare_ab_cancelled)
        self._compare_ab_worker.start()

    def _on_compare_ab_phase(self, phase: str) -> None:
        self.compare_ab_tab.phase_label.setText(phase)
        self.compare_ab_tab.progress_bar.setValue(0)
        self.input_panel.notes_text.setPlainText(f"Running Compare A/B... ({phase})")

    def _on_compare_ab_progress(self, completed: int, total: int) -> None:
        percent = int(completed / total * 100) if total > 0 else 0
        self.compare_ab_tab.progress_bar.setValue(percent)

    def _cancel_compare_ab(self) -> None:
        if self._compare_ab_worker is not None and self._compare_ab_worker.isRunning():
            self._compare_ab_worker.requestInterruption()
            self.compare_ab_tab.cancel_button.setEnabled(False)

    def _reset_compare_ab_ui(self) -> None:
        self.compare_ab_tab.run_button.setEnabled(True)
        self.compare_ab_tab.cancel_button.setVisible(False)
        self.compare_ab_tab.cancel_button.setEnabled(True)
        self.compare_ab_tab.progress_bar.setVisible(False)
        self.compare_ab_tab.progress_bar.setValue(0)
        self.compare_ab_tab.phase_label.setVisible(False)
        self._compare_ab_worker = None

    def _on_compare_ab_finished(self, result: CompareABResult) -> None:
        self._reset_compare_ab_ui()
        self.compare_ab_tab.display_result(result)

        combo_agg = result.combo_result.aggregate
        self.input_panel.notes_text.setPlainText(
            f"Compare A/B completed.\n"
            f"A: {result.lane_a_result.aggregate.total_pips:.2f} pips\n"
            f"B: {result.lane_b_result.aggregate.total_pips:.2f} pips\n"
            f"A+B: {combo_agg.total_pips:.2f} pips"
        )

    def _on_compare_ab_error(self, message: str) -> None:
        self._reset_compare_ab_ui()
        self._show_error(message)

    def _on_compare_ab_cancelled(self) -> None:
        self._reset_compare_ab_ui()
        self.input_panel.notes_text.setPlainText("Compare A/B execution cancelled.")

    def _export_trades_csv(self) -> None:
        if self._latest_artifacts is None or not self._latest_artifacts.trade_rows:
            self._show_error("No trades to export.")
            return

        strategy_name = self.input_panel.strategy_combo.currentText().strip() or "trades"
        csv_data = self.input_panel.csv_combo.currentData()
        csv_path = Path(csv_data) if csv_data else None
        stem = csv_path.stem if csv_path is not None else "output"
        default_filename = f"{strategy_name}__{stem}__trades.csv"

        start_dir = str(DEFAULT_DATA_DIR if DEFAULT_DATA_DIR.exists() else REPO_ROOT)
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Trades CSV",
            str(Path(start_dir) / default_filename),
            "CSV Files (*.csv)",
        )
        if not selected_path:
            return

        try:
            self._write_trade_rows_to_csv(
                trade_rows=self._latest_artifacts.trade_rows,
                path=Path(selected_path),
            )
        except Exception as exc:
            self._show_error(f"Failed to export CSV: {exc}")
            return

        self.input_panel.notes_text.append(f"Trades CSV exported:\n{selected_path}")

    def _write_trade_rows_to_csv(self, *, trade_rows, path: Path) -> None:
        headers = [
            "trade_no",
            "lane",
            "entry_subtype",
            "entry_time",
            "exit_time",
            "position_type",
            "entry_price",
            "exit_price",
            "pips",
            "cumulative_pips",
            "trade_profit_amount",
            "balance_after_trade",
            "result_label",
            "consecutive_wins",
            "consecutive_losses",
            "exit_reason",
            "entry_market_state",
            "exit_market_state",
            "entry_detected_market_state",
            "entry_candidate_market_state",
            "entry_state_transition_event",
            "entry_state_age",
            "entry_candidate_age",
            "entry_detector_reason",
            "entry_range_score",
            "entry_transition_up_score",
            "entry_transition_down_score",
            "entry_trend_up_score",
            "entry_trend_down_score",
            "exit_detected_market_state",
            "exit_candidate_market_state",
            "exit_state_transition_event",
            "exit_state_age",
            "exit_candidate_age",
            "exit_detector_reason",
            "exit_range_score",
            "exit_transition_up_score",
            "exit_transition_down_score",
            "exit_trend_up_score",
            "exit_trend_down_score",
            "entry_signal_reason",
            "exit_signal_reason",
            "entry_middle_band",
            "entry_upper_band",
            "entry_lower_band",
            "entry_normalized_band_width",
            "entry_range_slope",
            "entry_trend_slope",
            "entry_trend_current_ma",
            "entry_distance_from_middle",
            "exit_middle_band",
            "exit_upper_band",
            "exit_lower_band",
            "exit_normalized_band_width",
            "exit_range_slope",
            "exit_trend_slope",
            "exit_trend_current_ma",
            "exit_distance_from_middle",
            "entry_risk_score",
            "entry_upper_band_walk",
            "entry_lower_band_walk",
            "entry_upper_band_walk_hits",
            "entry_lower_band_walk_hits",
            "entry_dangerous_for_buy",
            "entry_dangerous_for_sell",
            "entry_strong_up_slope",
            "entry_strong_down_slope",
            "entry_latest_slope",
            "entry_prev_slope",
            "entry_latest_band_width",
            "entry_prev_band_width",
            "entry_latest_distance",
            "entry_prev_distance",
        ]

        with path.open("w", newline="", encoding="utf-8-sig") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(headers)

            for row in trade_rows:
                writer.writerow(
                    [
                        row.trade_no,
                        row.lane,
                        self._csv_text(row.entry_subtype),
                        self._csv_text(row.entry_time),
                        self._csv_text(row.exit_time),
                        row.position_type,
                        row.entry_price,
                        row.exit_price,
                        row.pips,
                        row.cumulative_pips,
                        row.trade_profit_amount,
                        row.balance_after_trade,
                        row.result_label,
                        row.consecutive_wins,
                        row.consecutive_losses,
                        row.exit_reason,
                        self._csv_text(row.entry_market_state),
                        self._csv_text(row.exit_market_state),
                        self._csv_text(row.entry_detected_market_state),
                        self._csv_text(row.entry_candidate_market_state),
                        self._csv_text(row.entry_state_transition_event),
                        self._csv_text(row.entry_state_age),
                        self._csv_text(row.entry_candidate_age),
                        self._csv_text(row.entry_detector_reason),
                        self._csv_text(row.entry_range_score),
                        self._csv_text(row.entry_transition_up_score),
                        self._csv_text(row.entry_transition_down_score),
                        self._csv_text(row.entry_trend_up_score),
                        self._csv_text(row.entry_trend_down_score),
                        self._csv_text(row.exit_detected_market_state),
                        self._csv_text(row.exit_candidate_market_state),
                        self._csv_text(row.exit_state_transition_event),
                        self._csv_text(row.exit_state_age),
                        self._csv_text(row.exit_candidate_age),
                        self._csv_text(row.exit_detector_reason),
                        self._csv_text(row.exit_range_score),
                        self._csv_text(row.exit_transition_up_score),
                        self._csv_text(row.exit_transition_down_score),
                        self._csv_text(row.exit_trend_up_score),
                        self._csv_text(row.exit_trend_down_score),
                        self._csv_text(row.entry_signal_reason),
                        self._csv_text(row.exit_signal_reason),
                        self._csv_text(row.entry_middle_band),
                        self._csv_text(row.entry_upper_band),
                        self._csv_text(row.entry_lower_band),
                        self._csv_text(row.entry_normalized_band_width),
                        self._csv_text(row.entry_range_slope),
                        self._csv_text(row.entry_trend_slope),
                        self._csv_text(row.entry_trend_current_ma),
                        self._csv_text(row.entry_distance_from_middle),
                        self._csv_text(row.exit_middle_band),
                        self._csv_text(row.exit_upper_band),
                        self._csv_text(row.exit_lower_band),
                        self._csv_text(row.exit_normalized_band_width),
                        self._csv_text(row.exit_range_slope),
                        self._csv_text(row.exit_trend_slope),
                        self._csv_text(row.exit_trend_current_ma),
                        self._csv_text(row.exit_distance_from_middle),
                        self._csv_text(row.entry_risk_score),
                        self._csv_text(row.entry_upper_band_walk),
                        self._csv_text(row.entry_lower_band_walk),
                        self._csv_text(row.entry_upper_band_walk_hits),
                        self._csv_text(row.entry_lower_band_walk_hits),
                        self._csv_text(row.entry_dangerous_for_buy),
                        self._csv_text(row.entry_dangerous_for_sell),
                        self._csv_text(row.entry_strong_up_slope),
                        self._csv_text(row.entry_strong_down_slope),
                        self._csv_text(row.entry_latest_slope),
                        self._csv_text(row.entry_prev_slope),
                        self._csv_text(row.entry_latest_band_width),
                        self._csv_text(row.entry_prev_band_width),
                        self._csv_text(row.entry_latest_distance),
                        self._csv_text(row.entry_prev_distance),
                    ]
                )

    def _csv_text(self, value) -> str:
        if value is None:
            return ""
        return str(value)

    def _clear_trade_table_selection(self, table) -> None:
        table.blockSignals(True)
        try:
            table.clearSelection()
            table.setCurrentCell(-1, -1)
        finally:
            table.blockSignals(False)

    def _on_primary_trade_selection_changed(self) -> None:
        self._handle_trade_selection_change(
            selected_row=self.result_tabs_panel.trades_table.currentRow(),
            source="primary",
        )

    def _on_chart_trade_selection_changed(self) -> None:
        self._handle_trade_selection_change(
            selected_row=self.chart_overview_tab.detail_tabs.trades_table.currentRow(),
            source="chart",
        )

    def _handle_trade_selection_change(
        self,
        *,
        selected_row: int,
        source: str,
    ) -> None:
        if self._syncing_trade_selection:
            return

        if self._latest_artifacts is None:
            return

        trade_rows = self._latest_artifacts.trade_rows
        if selected_row < 0 or selected_row >= len(trade_rows):
            self.chart_overview_tab.linked_chart.clear_highlight()
            return

        self._syncing_trade_selection = True
        try:
            if source == "primary":
                self._select_row_without_signal(
                    self.chart_overview_tab.detail_tabs.trades_table,
                    selected_row,
                )
            else:
                self._select_row_without_signal(
                    self.result_tabs_panel.trades_table,
                    selected_row,
                )
        finally:
            self._syncing_trade_selection = False

        self.chart_overview_tab.linked_chart.highlight_trade(trade_rows[selected_row])

    def _select_row_without_signal(self, table, row_index: int) -> None:
        table.blockSignals(True)
        try:
            table.selectRow(row_index)
            table.setCurrentCell(row_index, 0)
        finally:
            table.blockSignals(False)

    def _on_strategy_changed(self, strategy_name: str) -> None:
        self.input_panel.load_strategy_params(strategy_name.strip())

    def _show_error(self, message: str) -> None:
        self.input_panel.notes_text.setPlainText(f"Error:\n{message}")
        QMessageBox.critical(self, "Backtest error", message)