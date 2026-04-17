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
from backtest.evaluator import evaluate_cross_month, evaluate_integrated
from backtest.mean_reversion_analysis import (
    AllMonthsMeanReversionSummary,
    MeanReversionSummary,
)
from backtest.service import AllMonthsResult
from gui_common.widgets.time_series_chart_widget import TimeSeriesChartWidget


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
        self.mr_group = self._build_mean_reversion_panel()
        self.cumulative_chart = TimeSeriesChartWidget()
        self.cumulative_chart.clear_chart("Cumulative Pips (all months)")

        splitter.addWidget(self.monthly_table)
        splitter.addWidget(self.aggregate_group)
        splitter.addWidget(self.mr_group)
        splitter.addWidget(self.cumulative_chart)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)
        splitter.setStretchFactor(3, 2)

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
        table.setColumnCount(14)
        table.setHorizontalHeaderLabels([
            "Month",
            "Trades",
            "Wins",
            "Losses",
            "Win Rate %",
            "Total Pips",
            "Profit Factor",
            "Max DD Pips",
            "Avg MFE/MAE",
            "MR Trades",
            "MR Fail",
            "MR Succ<=5",
            "MR Rate<=5 %",
            "MR Avg Bars",
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
            ("avg_mfe_mae_ratio", "Avg MFE/MAE"),
            ("cross_month_verdict", "Cross-Month Verdict"),
            ("cross_month_reasons", "Cross-Month Reasons"),
            ("integrated_verdict", "Integrated Verdict"),
            ("integrated_reasons", "Integrated Reasons"),
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

    def _build_mean_reversion_panel(self) -> QGroupBox:
        group = QGroupBox("Mean Reversion (range lane, all period)")
        grid = QGridLayout(group)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(4)

        self.mr_labels: dict[str, QLabel] = {}

        fields_left = [
            ("total_range_trades", "Total Range Trades"),
            ("reversion_failure_count", "Reversion Fail (skip)"),
            ("reversion_success_count", "Reversion Success"),
            ("success_rate", "Success Rate"),
            ("avg_bars_to_reversion", "Avg Bars to Reversion"),
        ]
        fields_right = [
            ("success_within_3", "Success <=3"),
            ("success_within_5", "Success <=5"),
            ("success_within_8", "Success <=8"),
            ("success_within_12", "Success <=12"),
            ("avg_max_progress_ratio", "Avg Max Progress"),
            ("avg_max_adverse_excursion", "Avg Max Adverse"),
        ]

        for row, (key, label_text) in enumerate(fields_left):
            label = QLabel(label_text)
            value_label = QLabel("-")
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.mr_labels[key] = value_label
            grid.addWidget(label, row, 0)
            grid.addWidget(value_label, row, 1)

        for row, (key, label_text) in enumerate(fields_right):
            label = QLabel(label_text)
            value_label = QLabel("-")
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.mr_labels[key] = value_label
            grid.addWidget(label, row, 2)
            grid.addWidget(value_label, row, 3)

        return group

    def clear_results(self) -> None:
        self.monthly_table.setRowCount(0)
        for label in self.agg_labels.values():
            label.setText("-")
        for label in self.mr_labels.values():
            label.setText("-")
        self.cumulative_chart.clear_chart("Cumulative Pips (all months)")

    def display_result(
        self,
        result: AllMonthsResult,
        mr_summary: AllMonthsMeanReversionSummary | None = None,
    ) -> None:
        self._populate_monthly_table(result, mr_summary)
        self._populate_aggregate(result.aggregate)
        self._populate_mean_reversion_panel(mr_summary)
        self._populate_cumulative_chart(result)

    def _populate_monthly_table(
        self,
        result: AllMonthsResult,
        mr_summary: AllMonthsMeanReversionSummary | None = None,
    ) -> None:
        artifacts_list = result.monthly_artifacts
        mr_by_label: dict[str, MeanReversionSummary] = {}
        if mr_summary is not None:
            mr_by_label = {label: summary for label, summary in mr_summary.monthly}

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

                mfe_mae_text = (
                    f"{stats.avg_mfe_mae_ratio:.2f}"
                    if stats.avg_mfe_mae_ratio is not None
                    else "-"
                )

                mr = mr_by_label.get(label)
                mr_trades = str(mr.total_range_trades) if mr is not None else "N/A"
                mr_fail = str(mr.reversion_failure_count) if mr is not None else "N/A"
                mr_succ5 = str(mr.success_within_5_count) if mr is not None else "N/A"
                mr_rate5 = (
                    self._format_optional_percent(mr.success_within_5_rate)
                    if mr is not None
                    else "N/A"
                )
                mr_avg_bars = (
                    self._format_optional_number(mr.avg_bars_to_reversion)
                    if mr is not None
                    else "N/A"
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
                    mfe_mae_text,
                    mr_trades,
                    mr_fail,
                    mr_succ5,
                    mr_rate5,
                    mr_avg_bars,
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
        labels["avg_mfe_mae_ratio"].setText(
            f"{agg.avg_mfe_mae_ratio:.2f}" if agg.avg_mfe_mae_ratio is not None else "-"
        )

        cross_eval = evaluate_cross_month(agg)
        labels["cross_month_verdict"].setText(cross_eval.verdict.value.upper())
        labels["cross_month_reasons"].setText("; ".join(cross_eval.reasons) if cross_eval.reasons else "-")

        integrated_eval = evaluate_integrated(agg)
        labels["integrated_verdict"].setText(integrated_eval.verdict.value.upper())
        labels["integrated_reasons"].setText("; ".join(integrated_eval.reasons) if integrated_eval.reasons else "-")

    def _populate_mean_reversion_panel(
        self,
        mr_summary: AllMonthsMeanReversionSummary | None,
    ) -> None:
        if mr_summary is None:
            for label in self.mr_labels.values():
                label.setText("N/A")
            return

        agg = mr_summary.all_period
        labels = self.mr_labels
        labels["total_range_trades"].setText(str(agg.total_range_trades))
        labels["reversion_failure_count"].setText(str(agg.reversion_failure_count))
        labels["reversion_success_count"].setText(str(agg.reversion_success_count))
        labels["success_rate"].setText(
            self._format_optional_percent(agg.success_rate)
        )
        labels["avg_bars_to_reversion"].setText(
            self._format_optional_number(agg.avg_bars_to_reversion)
        )

        labels["success_within_3"].setText(
            f"{agg.success_within_3_count} "
            f"({self._format_optional_percent(agg.success_within_3_rate)})"
        )
        labels["success_within_5"].setText(
            f"{agg.success_within_5_count} "
            f"({self._format_optional_percent(agg.success_within_5_rate)})"
        )
        labels["success_within_8"].setText(
            f"{agg.success_within_8_count} "
            f"({self._format_optional_percent(agg.success_within_8_rate)})"
        )
        labels["success_within_12"].setText(
            f"{agg.success_within_12_count} "
            f"({self._format_optional_percent(agg.success_within_12_rate)})"
        )
        labels["avg_max_progress_ratio"].setText(
            self._format_optional_number(agg.avg_max_progress_ratio)
        )
        labels["avg_max_adverse_excursion"].setText(
            self._format_optional_number(agg.avg_max_adverse_excursion)
        )

    def _format_optional_percent(self, value: float | None) -> str:
        if value is None:
            return "N/A"
        return f"{value:.2f}%"

    def _format_optional_number(self, value: float | None) -> str:
        if value is None:
            return "N/A"
        return f"{value:.2f}"

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
