# src/backtest_gui_app/views/compare_ab_tab.py
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from backtest.aggregate_stats import AggregateStats
from backtest.service import CompareABResult


class CompareABTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        top_bar = self._build_top_bar()
        layout.addWidget(top_bar)

        self.compare_table = self._build_compare_table()
        layout.addWidget(self.compare_table)

        layout.addStretch(1)

    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(8)

        bar_layout.addWidget(QLabel("CSV Directory:"))
        self.csv_dir_edit = QLineEdit()
        self.csv_dir_edit.setReadOnly(True)
        self.csv_dir_edit.setPlaceholderText(
            "Select a directory containing monthly CSV files"
        )
        bar_layout.addWidget(self.csv_dir_edit, stretch=1)

        self.browse_dir_button = QPushButton("Browse...")
        bar_layout.addWidget(self.browse_dir_button)

        self.run_button = QPushButton("Run Compare A/B")
        self.run_button.setMinimumHeight(36)
        self.run_button.setMinimumWidth(160)
        bar_layout.addWidget(self.run_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setMinimumHeight(36)
        self.cancel_button.setVisible(False)
        bar_layout.addWidget(self.cancel_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumWidth(200)
        bar_layout.addWidget(self.progress_bar)

        self.phase_label = QLabel("")
        self.phase_label.setVisible(False)
        bar_layout.addWidget(self.phase_label)

        return bar

    def _build_compare_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(10)
        table.setHorizontalHeaderLabels([
            "Pattern",
            "Strategy",
            "Trades",
            "Wins",
            "Losses",
            "Win Rate %",
            "Total Pips",
            "Profit Factor",
            "Max DD Pips",
            "Avg MFE/MAE",
        ])
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setStretchLastSection(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.setRowCount(0)
        return table

    def clear_results(self) -> None:
        self.compare_table.setRowCount(0)

    def display_result(self, result: CompareABResult) -> None:
        rows_data = [
            ("A only", result.lane_a_strategy, result.lane_a_result.aggregate),
            ("B only", result.lane_b_strategy, result.lane_b_result.aggregate),
            ("A+B combo", result.combo_strategy, result.combo_result.aggregate),
        ]

        self.compare_table.setUpdatesEnabled(False)
        try:
            self.compare_table.clearContents()
            self.compare_table.setRowCount(len(rows_data))

            for row_idx, (pattern, strategy, agg) in enumerate(rows_data):
                pf_text = self._format_pf(agg.overall_profit_factor)
                mfe_mae_text = (
                    f"{agg.avg_mfe_mae_ratio:.2f}"
                    if agg.avg_mfe_mae_ratio is not None
                    else "-"
                )

                values = [
                    pattern,
                    strategy,
                    str(agg.total_trades),
                    str(agg.total_wins),
                    str(agg.total_losses),
                    f"{agg.overall_win_rate:.1f}",
                    f"{agg.total_pips:.2f}",
                    pf_text,
                    f"{agg.max_drawdown_pips:.2f}",
                    mfe_mae_text,
                ]

                for col_idx, val in enumerate(values):
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignCenter)
                    if col_idx <= 1:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self.compare_table.setItem(row_idx, col_idx, item)
        finally:
            self.compare_table.setUpdatesEnabled(True)
            self.compare_table.viewport().update()

    def _format_pf(self, value: float | None) -> str:
        if value is None:
            return "-"
        if value == float("inf"):
            return "inf"
        return f"{value:.2f}"
