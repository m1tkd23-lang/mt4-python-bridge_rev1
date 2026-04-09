# src/backtest_gui_app/views/all_months_tab.py
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from backtest.aggregate_stats import AggregateStats
from backtest.service import AllMonthsResult
from backtest_gui_app.widgets.time_series_chart_widget import TimeSeriesChartWidget


class AllMonthsTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        top_bar = self._build_top_bar()
        layout.addWidget(top_bar)

        splitter = QSplitter(Qt.Vertical)
        self.monthly_table = self._build_monthly_table()
        self.aggregate_group = self._build_aggregate_panel()
        self.cumulative_chart = TimeSeriesChartWidget()
        self.cumulative_chart.clear_chart("Cumulative Pips (all months)")

        splitter.addWidget(self.monthly_table)
        splitter.addWidget(self.aggregate_group)
        splitter.addWidget(self.cumulative_chart)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 2)

        layout.addWidget(splitter)

    def _build_top_bar(self) -> QWidget:
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(8)

        bar_layout.addWidget(QLabel("CSV Directory:"))
        self.csv_dir_edit = QLineEdit()
        self.csv_dir_edit.setReadOnly(True)
        self.csv_dir_edit.setPlaceholderText("Select a directory containing monthly CSV files")
        bar_layout.addWidget(self.csv_dir_edit, stretch=1)

        self.browse_dir_button = QPushButton("Browse...")
        bar_layout.addWidget(self.browse_dir_button)

        self.trade_log_checkbox = QCheckBox("Trade Log")
        self.trade_log_checkbox.setToolTip("Output structured trade log (JSONL) for each month")
        bar_layout.addWidget(self.trade_log_checkbox)

        self.run_all_button = QPushButton("Run All Months")
        self.run_all_button.setMinimumHeight(36)
        self.run_all_button.setMinimumWidth(140)
        bar_layout.addWidget(self.run_all_button)

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

        return bar

    def _build_monthly_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels([
            "Month",
            "Trades",
            "Wins",
            "Losses",
            "Win Rate %",
            "Total Pips",
            "Profit Factor",
            "Max DD Pips",
        ])
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setStretchLastSection(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.verticalHeader().setVisible(False)
        return table

    def _build_aggregate_panel(self) -> QGroupBox:
        group = QGroupBox("All Months Aggregate")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(4)

        self.agg_labels: dict[str, QLabel] = {}

        fields_left = [
            ("total_pips", "Total Pips"),
            ("overall_win_rate", "Win Rate %"),
            ("overall_profit_factor", "Profit Factor"),
            ("max_drawdown_pips", "Max DD Pips"),
            ("total_trades", "Total Trades"),
        ]
        fields_right = [
            ("month_count", "Month Count"),
            ("average_pips_per_month", "Avg Pips/Month"),
            ("monthly_pips_stddev", "Monthly Stddev"),
            ("deficit_month_count", "Deficit Months"),
            ("max_consecutive_deficit", "Max Consecutive Deficit"),
        ]

        for row, (key, label_text) in enumerate(fields_left):
            label = QLabel(label_text)
            value_label = QLabel("-")
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.agg_labels[key] = value_label
            grid.addWidget(label, row, 0)
            grid.addWidget(value_label, row, 1)

        for row, (key, label_text) in enumerate(fields_right):
            label = QLabel(label_text)
            value_label = QLabel("-")
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.agg_labels[key] = value_label
            grid.addWidget(label, row, 2)
            grid.addWidget(value_label, row, 3)

        return group

    def clear_results(self) -> None:
        self.monthly_table.setRowCount(0)
        for label in self.agg_labels.values():
            label.setText("-")
        self.cumulative_chart.clear_chart("Cumulative Pips (all months)")

    def display_result(self, result: AllMonthsResult) -> None:
        self._populate_monthly_table(result)
        self._populate_aggregate(result.aggregate)
        self._populate_cumulative_chart(result)

    def _populate_monthly_table(self, result: AllMonthsResult) -> None:
        artifacts_list = result.monthly_artifacts
        self.monthly_table.setUpdatesEnabled(False)
        try:
            self.monthly_table.clearContents()
            self.monthly_table.setRowCount(len(artifacts_list))

            for row_idx, (label, artifacts) in enumerate(artifacts_list):
                stats = artifacts.backtest_result.stats

                win_rate = (stats.wins / stats.trades * 100.0) if stats.trades > 0 else 0.0
                pf_text = self._format_pf(
                    stats.gross_profit_pips, stats.gross_loss_pips
                )

                values = [
                    label,
                    str(stats.trades),
                    str(stats.wins),
                    str(stats.losses),
                    f"{win_rate:.1f}",
                    f"{stats.total_pips:.2f}",
                    pf_text,
                    f"{stats.max_drawdown_pips:.2f}",
                ]

                for col_idx, val in enumerate(values):
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignCenter)
                    if col_idx == 0:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self.monthly_table.setItem(row_idx, col_idx, item)
        finally:
            self.monthly_table.setUpdatesEnabled(True)
            self.monthly_table.viewport().update()

    def _populate_aggregate(self, agg: AggregateStats) -> None:
        labels = self.agg_labels
        labels["total_pips"].setText(f"{agg.total_pips:.2f}")
        labels["overall_win_rate"].setText(f"{agg.overall_win_rate:.2f}%")
        labels["overall_profit_factor"].setText(self._format_pf_value(agg.overall_profit_factor))
        labels["max_drawdown_pips"].setText(f"{agg.max_drawdown_pips:.2f}")
        labels["total_trades"].setText(str(agg.total_trades))
        labels["month_count"].setText(str(agg.month_count))
        labels["average_pips_per_month"].setText(f"{agg.average_pips_per_month:.2f}")
        labels["monthly_pips_stddev"].setText(
            f"{agg.monthly_pips_stddev:.2f}" if agg.monthly_pips_stddev is not None else "-"
        )
        labels["deficit_month_count"].setText(str(agg.deficit_month_count))
        labels["max_consecutive_deficit"].setText(str(agg.max_consecutive_deficit_months))

    def _format_pf(self, gross_profit: float, gross_loss: float) -> str:
        if gross_loss == 0:
            return "inf" if gross_profit > 0 else "-"
        return f"{gross_profit / gross_loss:.2f}"

    def _format_pf_value(self, value: float | None) -> str:
        if value is None:
            return "-"
        if value == float("inf"):
            return "inf"
        return f"{value:.2f}"

    def _populate_cumulative_chart(self, result: AllMonthsResult) -> None:
        x_values: list[datetime] = []
        y_values: list[float] = []
        month_boundaries: list[datetime] = []

        cumulative = 0.0
        num_months = len(result.monthly_artifacts)

        for month_idx, (_label, artifacts) in enumerate(result.monthly_artifacts):
            trades = artifacts.backtest_result.trades
            for trade in trades:
                exit_time = trade.exit_time
                if isinstance(exit_time, datetime):
                    cumulative += trade.pips
                    x_values.append(exit_time)
                    y_values.append(cumulative)

            if month_idx < num_months - 1 and x_values:
                month_boundaries.append(x_values[-1])

        self.cumulative_chart.plot_series_with_vlines(
            x_values=x_values,
            y_values=y_values,
            title="Cumulative Pips (all months)",
            y_label="Cumulative Pips",
            vline_positions=month_boundaries,
        )
