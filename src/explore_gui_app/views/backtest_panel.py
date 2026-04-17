# src\explore_gui_app\views\backtest_panel.py
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from backtest.aggregate_stats import AggregateStats
from backtest.service import BacktestRunArtifacts


_KPI_FIELDS: list[tuple[str, str]] = [
    ("total_pips", "Total pips"),
    ("win_rate_percent", "Win rate"),
    ("profit_factor", "Profit factor"),
    ("max_drawdown_pips", "Max DD pips"),
    ("trades", "Trades"),
    ("verdict", "Verdict"),
]

_DETAIL_FIELDS: list[tuple[str, str]] = [
    ("wins", "Wins"),
    ("losses", "Losses"),
    ("average_pips", "Avg pips"),
    ("max_consecutive_wins", "Max consec wins"),
    ("max_consecutive_losses", "Max consec losses"),
]

_SUMMARY_KEYS: tuple[str, ...] = tuple(
    key for key, _ in (*_KPI_FIELDS, *_DETAIL_FIELDS)
)


class BacktestPanel(QWidget):
    """Minimal Backtest 単発 panel for the explore_gui タブ B.

    Runs ``backtest.service.run_backtest`` (single CSV) or
    ``backtest.service.run_all_months`` (CSV dir) for the most recently
    accepted exploration candidate (strategy + param overrides) and
    displays an 11-field summary (6 KPI + 5 details).

    Behavior intentionally duplicates the backtest_gui_app InputPanel /
    SummaryPanel field set per TASK-0131 / TASK-0136 / TASK-0139 (重複許容).
    Common-widget extraction is deferred to T-D.
    """

    MODE_SINGLE = "single"
    MODE_ALL_MONTHS = "all_months"

    run_requested = Signal()
    stop_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._summary_labels: dict[str, QLabel] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(self._build_candidate_section())
        layout.addWidget(self._build_source_section())
        layout.addWidget(self._build_market_section())
        layout.addWidget(self._build_action_section())
        layout.addWidget(self._build_kpi_strip())
        layout.addWidget(self._build_details_section())
        layout.addWidget(self._build_notes_section())
        layout.addStretch(1)

        self.set_candidate(strategy_name=None, param_overrides=None)
        self.clear_summary()

    # ------------------------------------------------------------------
    # UI builders
    # ------------------------------------------------------------------

    def _build_candidate_section(self) -> QWidget:
        box = QFrame()
        box.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        title = QLabel("<b>探索結果 1 候補（最終採択 A+B パラメータ）</b>")
        layout.addWidget(title)

        self.strategy_value_label = QLabel("-")
        self.strategy_value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.params_value_label = QLabel("-")
        self.params_value_label.setWordWrap(True)
        self.params_value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)
        form.addRow("Strategy:", self.strategy_value_label)
        form.addRow("Param overrides:", self.params_value_label)
        layout.addLayout(form)

        return box

    def _build_source_section(self) -> QWidget:
        box = QFrame()
        box.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        layout.addWidget(QLabel("<b>Run mode / Data source</b>"))

        self._mode_group = QButtonGroup(self)
        self._radio_single = QRadioButton("Single CSV")
        self._radio_all = QRadioButton("All months in CSV Dir")
        self._radio_single.setChecked(True)
        self._mode_group.addButton(self._radio_single)
        self._mode_group.addButton(self._radio_all)

        mode_row = QHBoxLayout()
        mode_row.addWidget(self._radio_single)
        mode_row.addWidget(self._radio_all)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        single_row = QHBoxLayout()
        self.csv_path_edit = QLineEdit()
        self.csv_path_edit.setPlaceholderText("Single CSV path")
        single_browse = QPushButton("Browse...")
        single_browse.clicked.connect(self._browse_csv)
        single_row.addWidget(QLabel("CSV File:"))
        single_row.addWidget(self.csv_path_edit, 1)
        single_row.addWidget(single_browse)
        layout.addLayout(single_row)

        dir_row = QHBoxLayout()
        self.csv_dir_edit = QLineEdit()
        self.csv_dir_edit.setPlaceholderText("CSV directory (used in All months mode)")
        dir_browse = QPushButton("Browse...")
        dir_browse.clicked.connect(self._browse_csv_dir)
        dir_row.addWidget(QLabel("CSV Dir:"))
        dir_row.addWidget(self.csv_dir_edit, 1)
        dir_row.addWidget(dir_browse)
        layout.addLayout(dir_row)

        return box

    def _build_market_section(self) -> QWidget:
        box = QFrame()
        box.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)
        layout.addWidget(QLabel("<b>Market parameters</b>"))

        self.symbol_edit = QLineEdit("BACKTEST")
        self.timeframe_edit = QLineEdit("M1")
        self.pip_size_edit = QLineEdit("0.01")
        self.sl_pips_edit = QLineEdit("10")
        self.tp_pips_edit = QLineEdit("10")

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(4)
        form.addRow("Symbol", self.symbol_edit)
        form.addRow("Timeframe", self.timeframe_edit)
        form.addRow("Pip size", self.pip_size_edit)
        form.addRow("SL pips", self.sl_pips_edit)
        form.addRow("TP pips", self.tp_pips_edit)
        layout.addLayout(form)
        return box

    def _build_action_section(self) -> QWidget:
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.run_button = QPushButton("Run backtest")
        self.run_button.setMinimumHeight(32)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)

        self.run_button.clicked.connect(self.run_requested.emit)
        self.stop_button.clicked.connect(self.stop_requested.emit)

        layout.addWidget(self.run_button)
        layout.addWidget(self.stop_button)
        layout.addStretch(1)
        return box

    def _build_kpi_strip(self) -> QWidget:
        strip = QWidget()
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(6)
        for key, title in _KPI_FIELDS:
            strip_layout.addWidget(self._build_kpi_card(key, title), 1)
        return strip

    def _build_kpi_card(self, key: str, title: str) -> QFrame:
        card = QFrame()
        card.setFrameShape(QFrame.StyledPanel)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(2)

        title_label = QLabel(title.upper())
        title_label.setStyleSheet("font-size: 10px; color: gray;")

        value_label = QLabel("-")
        value_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._summary_labels[key] = value_label

        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        return card

    def _build_details_section(self) -> QWidget:
        box = QFrame()
        box.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.addWidget(QLabel("<b>Details</b>"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(3)
        for row, (key, label_text) in enumerate(_DETAIL_FIELDS):
            label = QLabel(label_text)
            value = QLabel("-")
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._summary_labels[key] = value
            grid.addWidget(label, row, 0)
            grid.addWidget(value, row, 1)
        layout.addLayout(grid)
        return box

    def _build_notes_section(self) -> QWidget:
        box = QFrame()
        box.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.addWidget(QLabel("<b>Status / Notes</b>"))

        self.notes_text = QTextEdit()
        self.notes_text.setReadOnly(True)
        self.notes_text.setMinimumHeight(80)
        self.notes_text.setMaximumHeight(160)
        layout.addWidget(self.notes_text)
        return box

    # ------------------------------------------------------------------
    # File dialogs
    # ------------------------------------------------------------------

    def _browse_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV file", "", "CSV Files (*.csv)"
        )
        if path:
            self.csv_path_edit.setText(path)

    def _browse_csv_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select CSV directory")
        if path:
            self.csv_dir_edit.setText(path)

    # ------------------------------------------------------------------
    # Public getters / setters
    # ------------------------------------------------------------------

    def get_mode(self) -> str:
        if self._radio_all.isChecked():
            return self.MODE_ALL_MONTHS
        return self.MODE_SINGLE

    def set_mode(self, mode: str) -> None:
        if mode == self.MODE_ALL_MONTHS:
            self._radio_all.setChecked(True)
        else:
            self._radio_single.setChecked(True)

    def get_csv_path(self) -> str:
        return self.csv_path_edit.text().strip()

    def set_csv_path(self, path: str | None) -> None:
        self.csv_path_edit.setText(path or "")

    def get_csv_dir(self) -> str:
        return self.csv_dir_edit.text().strip()

    def set_csv_dir(self, path: str | None) -> None:
        self.csv_dir_edit.setText(path or "")

    def get_symbol(self) -> str:
        return self.symbol_edit.text().strip() or "BACKTEST"

    def get_timeframe(self) -> str:
        return self.timeframe_edit.text().strip() or "M1"

    def get_pip_size(self) -> float:
        return float(self.pip_size_edit.text().strip() or "0.01")

    def get_sl_pips(self) -> float:
        return float(self.sl_pips_edit.text().strip() or "10")

    def get_tp_pips(self) -> float:
        return float(self.tp_pips_edit.text().strip() or "10")

    def set_market_defaults(
        self,
        *,
        symbol: str | None = None,
        timeframe: str | None = None,
        pip_size: float | None = None,
        sl_pips: float | None = None,
        tp_pips: float | None = None,
    ) -> None:
        if symbol is not None:
            self.symbol_edit.setText(symbol)
        if timeframe is not None:
            self.timeframe_edit.setText(timeframe)
        if pip_size is not None:
            self.pip_size_edit.setText(str(pip_size))
        if sl_pips is not None:
            self.sl_pips_edit.setText(str(sl_pips))
        if tp_pips is not None:
            self.tp_pips_edit.setText(str(tp_pips))

    def set_candidate(
        self,
        *,
        strategy_name: str | None,
        param_overrides: dict[str, float] | None,
    ) -> None:
        self._candidate_strategy = strategy_name
        self._candidate_overrides = (
            dict(param_overrides) if param_overrides else None
        )

        self.strategy_value_label.setText(strategy_name or "-")
        if not param_overrides:
            self.params_value_label.setText("(default)")
            return

        lines = [
            f"{k.split('::')[-1]} = {v}"
            for k, v in sorted(param_overrides.items())
        ]
        self.params_value_label.setText("\n".join(lines))

    def get_candidate_strategy(self) -> str | None:
        return getattr(self, "_candidate_strategy", None)

    def get_candidate_overrides(self) -> dict[str, float] | None:
        overrides = getattr(self, "_candidate_overrides", None)
        return dict(overrides) if overrides else None

    def set_running(self, running: bool) -> None:
        self.run_button.setEnabled(not running)
        self.stop_button.setEnabled(running)

    def set_status(self, text: str) -> None:
        self.notes_text.setPlainText(text)

    def append_log(self, text: str) -> None:
        self.notes_text.append(text)

    # ------------------------------------------------------------------
    # Summary display
    # ------------------------------------------------------------------

    def clear_summary(self) -> None:
        for key in _SUMMARY_KEYS:
            self._summary_labels[key].setText("-")

    def show_single_artifacts(self, artifacts: BacktestRunArtifacts) -> None:
        summary = artifacts.summary
        labels = self._summary_labels
        labels["total_pips"].setText(f"{summary.total_pips:.2f}")
        labels["win_rate_percent"].setText(f"{summary.win_rate_percent:.2f}%")
        labels["profit_factor"].setText(
            self._format_profit_factor(summary.profit_factor)
        )
        labels["max_drawdown_pips"].setText(f"{summary.max_drawdown_pips:.2f}")
        labels["trades"].setText(str(summary.trades))
        labels["verdict"].setText(summary.verdict or "-")
        labels["wins"].setText(str(summary.wins))
        labels["losses"].setText(str(summary.losses))
        labels["average_pips"].setText(f"{summary.average_pips:.2f}")
        labels["max_consecutive_wins"].setText(str(summary.max_consecutive_wins))
        labels["max_consecutive_losses"].setText(
            str(summary.max_consecutive_losses)
        )

    def show_aggregate(self, aggregate: AggregateStats) -> None:
        labels = self._summary_labels
        labels["total_pips"].setText(f"{aggregate.total_pips:.2f}")
        labels["win_rate_percent"].setText(
            f"{aggregate.overall_win_rate:.2f}%"
        )
        labels["profit_factor"].setText(
            self._format_profit_factor(aggregate.overall_profit_factor)
        )
        labels["max_drawdown_pips"].setText(
            f"{aggregate.max_drawdown_pips:.2f}"
        )
        labels["trades"].setText(str(aggregate.total_trades))
        labels["verdict"].setText(f"{aggregate.month_count} months")
        labels["wins"].setText(str(aggregate.total_wins))
        labels["losses"].setText(str(aggregate.total_losses))
        labels["average_pips"].setText(
            f"{aggregate.average_pips_per_month:.2f}"
        )
        labels["max_consecutive_wins"].setText("-")
        labels["max_consecutive_losses"].setText(
            f"deficit streak: {aggregate.max_consecutive_deficit_months}"
        )

    @staticmethod
    def _format_profit_factor(value: float | None) -> str:
        if value is None:
            return "None"
        if value == float("inf"):
            return "inf"
        return f"{value:.2f}"
