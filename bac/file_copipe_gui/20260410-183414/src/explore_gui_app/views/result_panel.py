# src/explore_gui_app/views/result_panel.py
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from backtest.exploration_loop import BollingerExplorationResult, BollingerLoopResult


class ExploreResultPanel(QWidget):
    """Panel showing exploration results: iteration table + log display."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Vertical)

        # Upper: results table
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(4, 4, 4, 4)
        table_layout.addWidget(QLabel("<b>Iteration Results</b>"))

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            "#", "Verdict", "Total Pips", "Win Rate", "PF", "Overrides",
        ])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        table_layout.addWidget(self._table)
        splitter.addWidget(table_container)

        # Lower: log display
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(4, 4, 4, 4)
        log_layout.addWidget(QLabel("<b>Exploration Log</b>"))

        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setFontFamily("Consolas")
        log_layout.addWidget(self._log_text)
        splitter.addWidget(log_container)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        # Status label
        self._status_label = QLabel("Ready")
        layout.addWidget(self._status_label)

    def clear(self) -> None:
        self._table.setRowCount(0)
        self._log_text.clear()
        self._status_label.setText("Ready")

    def append_log(self, text: str) -> None:
        self._log_text.append(text)

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def add_iteration_result(
        self, iteration: int, result: BollingerExplorationResult
    ) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)

        ss = result.evaluation.stats_summary
        total_pips = f"{ss['total_pips']:.1f}" if ss.get("total_pips") is not None else "-"
        win_rate_val = ss.get("win_rate")
        win_rate = f"{win_rate_val:.1f}%" if win_rate_val is not None else "-"
        pf_val = ss.get("profit_factor")
        pf = f"{pf_val:.2f}" if pf_val is not None else "-"

        overrides_str = ", ".join(
            f"{k.split('::')[-1]}={v}"
            for k, v in sorted(result.param_overrides.items())
        ) if result.param_overrides else "(default)"

        items = [
            str(iteration),
            result.verdict.upper(),
            total_pips,
            win_rate,
            pf,
            overrides_str,
        ]
        for col, text in enumerate(items):
            item = QTableWidgetItem(text)
            if col < 5:
                item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, col, item)

    def show_final_result(self, loop_result: BollingerLoopResult) -> None:
        if loop_result.adopted:
            r = loop_result.adopted
            overrides_str = ", ".join(
                f"{k.split('::')[-1]}={v}"
                for k, v in sorted(r.param_overrides.items())
            ) if r.param_overrides else "(default)"
            self.set_status(
                f"ADOPTED after {loop_result.iterations} iterations: {overrides_str}"
            )
        else:
            self.set_status(
                f"Stopped: {loop_result.stopped_reason} "
                f"({loop_result.iterations} iterations, no adoption)"
            )
