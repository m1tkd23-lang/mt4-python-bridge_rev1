# src\explore_gui_app\views\result_panel.py
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
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

    # Phase 2 table sizing constants
    _P2_ROW_HEIGHT = 30
    _P2_HEADER_HEIGHT = 30
    _P2_MARGIN = 6
    _P2_MAX_HEIGHT = 200

    # Foreground-only status colors for dark theme
    _PHASE1_COLOR = "#6FA8FF"
    _PHASE2_COLOR = "#F0A050"
    _ADOPT_COLOR = "#7BD88F"
    _IMPROVE_COLOR = "#F0C674"
    _DISCARD_COLOR = "#FF7B72"
    _DEFAULT_TEXT_COLOR = "#E0E3EB"

    # 月別 breakdown の崩壊月判定閾値 (本筋 §3.2 基準)
    _CRASH_PIPS_THRESHOLD = -30.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._results: list[BollingerExplorationResult] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Phase display label
        self._phase_label = QLabel("")
        self._phase_label.setStyleSheet(
            "font-size: 13px; font-weight: bold; padding: 4px;"
        )
        self._phase_label.setVisible(False)
        layout.addWidget(self._phase_label)

        splitter = QSplitter(Qt.Vertical)

        # Upper: results table
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(4, 4, 4, 4)
        table_layout.addWidget(QLabel("<b>Iteration Results</b>"))

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["#", "Verdict", "Total Pips", "Win Rate", "PF", "Overrides"]
        )
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
        log_container.setMinimumHeight(120)
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(4, 4, 4, 4)
        log_layout.addWidget(QLabel("<b>Exploration Log</b>"))

        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setFontFamily("Consolas")
        log_layout.addWidget(self._log_text)
        splitter.addWidget(log_container)

        # Monthly breakdown table (for Phase 2 / aggregate results)
        monthly_container = QWidget()
        monthly_layout = QVBoxLayout(monthly_container)
        monthly_layout.setContentsMargins(4, 4, 4, 4)
        monthly_layout.addWidget(QLabel("<b>Monthly Breakdown</b>"))

        self._monthly_table = QTableWidget()
        self._monthly_table.setColumnCount(2)
        self._monthly_table.setHorizontalHeaderLabels(["Month", "Total Pips"])
        self._monthly_table.horizontalHeader().setStretchLastSection(True)
        self._monthly_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self._monthly_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._monthly_table.setSelectionBehavior(QTableWidget.SelectRows)
        monthly_layout.addWidget(self._monthly_table)
        splitter.addWidget(monthly_container)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 2)
        layout.addWidget(splitter)

        # Phase 2 results table
        self._phase2_label = QLabel("<b>Phase 2: All-Period Confirmation Results</b>")
        self._phase2_label.setVisible(False)
        layout.addWidget(self._phase2_label)

        self._phase2_table = QTableWidget()
        self._phase2_table.setColumnCount(5)
        self._phase2_table.setHorizontalHeaderLabels(
            ["#", "Avg Pips/Month", "Win Rate", "PF", "Overrides"]
        )
        self._phase2_table.horizontalHeader().setStretchLastSection(True)
        self._phase2_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self._phase2_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._phase2_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._phase2_table.setVisible(False)
        layout.addWidget(self._phase2_table)

        # Phase 2 summary panel (adoption assessment)
        self._summary_box = QGroupBox("Phase 2 Summary: Adoption Assessment")
        self._summary_box.setStyleSheet(
            "QGroupBox { font-weight: bold; border: 2px solid #9E9E9E; "
            "border-radius: 4px; margin-top: 8px; padding-top: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; }"
        )
        self._summary_box.setVisible(False)
        summary_layout = QVBoxLayout(self._summary_box)

        self._summary_labels: dict[str, QLabel] = {}
        summary_fields = [
            ("total_pips", "Total Pips"),
            ("avg_pips", "Avg Pips/Month"),
            ("pf", "Profit Factor"),
            ("win_rate", "Win Rate"),
            ("stddev", "Monthly Pips StdDev"),
            ("deficit_months", "Deficit Months"),
            ("mfe_mae", "Avg MFE/MAE Ratio"),
            ("assessment", "Assessment"),
        ]

        # 2-column grid layout
        row_widget = None
        row_layout = None
        for i, (key, label_text) in enumerate(summary_fields):
            if key == "assessment":
                lbl = QLabel(f"{label_text}: -")
                lbl.setStyleSheet(
                    f"font-size: 13px; font-weight: bold; padding: 2px; "
                    f"color: {self._DEFAULT_TEXT_COLOR};"
                )
                self._summary_labels[key] = lbl
                summary_layout.addWidget(lbl)
                continue

            if i % 2 == 0:
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)
                summary_layout.addWidget(row_widget)

            lbl = QLabel(f"{label_text}: -")
            lbl.setStyleSheet(
                f"font-size: 12px; padding: 2px; color: {self._DEFAULT_TEXT_COLOR};"
            )
            self._summary_labels[key] = lbl
            row_layout.addWidget(lbl)

        layout.addWidget(self._summary_box)

        # Status label
        self._status_label = QLabel("Ready")
        layout.addWidget(self._status_label)

    def clear(self) -> None:
        self._results.clear()
        self._table.setRowCount(0)
        self._log_text.clear()
        self._status_label.setText("Ready")
        self.hide_phase2_summary()

    def append_log(self, text: str) -> None:
        self._log_text.append(text)

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def add_iteration_result(
        self, iteration: int, result: BollingerExplorationResult
    ) -> None:
        self._results.append(result)

        row = self._table.rowCount()
        self._table.insertRow(row)

        ss = result.evaluation.stats_summary
        total_pips = (
            f"{ss['total_pips']:.1f}" if ss.get("total_pips") is not None else "-"
        )
        win_rate_val = ss.get("win_rate")
        win_rate = f"{win_rate_val:.1f}%" if win_rate_val is not None else "-"
        pf_val = ss.get("profit_factor")
        pf = f"{pf_val:.2f}" if pf_val is not None else "-"

        overrides_str = (
            ", ".join(
                f"{k.split('::')[-1]}={v}"
                for k, v in sorted(result.param_overrides.items())
            )
            if result.param_overrides
            else "(default)"
        )

        items = [
            str(iteration),
            result.verdict.upper(),
            total_pips,
            win_rate,
            pf,
            overrides_str,
        ]

        verdict_color = self._verdict_text_color(result.verdict)
        for col, text in enumerate(items):
            item = QTableWidgetItem(text)
            if col < 5:
                item.setTextAlignment(Qt.AlignCenter)

            # Foreground-only emphasis for dark theme
            item.setForeground(QColor(self._DEFAULT_TEXT_COLOR))
            if col == 1:
                item.setForeground(verdict_color)

            self._table.setItem(row, col, item)

    def get_all_iteration_results(self) -> list[BollingerExplorationResult]:
        return list(self._results)

    def show_final_result(self, loop_result: BollingerLoopResult) -> None:
        if loop_result.adopted:
            r = loop_result.adopted
            overrides_str = (
                ", ".join(
                    f"{k.split('::')[-1]}={v}"
                    for k, v in sorted(r.param_overrides.items())
                )
                if r.param_overrides
                else "(default)"
            )
            self.set_status(
                f"ADOPTED after {loop_result.iterations} iterations: {overrides_str}"
            )
        else:
            self.set_status(
                f"Stopped: {loop_result.stopped_reason} "
                f"({loop_result.iterations} iterations, no adoption)"
            )

    # ------------------------------------------------------------------
    # Phase display
    # ------------------------------------------------------------------

    def set_phase(self, phase: int) -> None:
        """Set the current phase display. 0=hidden, 1=探索中, 2=確認中."""
        if phase == 0:
            self._phase_label.setVisible(False)
        elif phase == 1:
            self._phase_label.setText("Phase 1: 探索中 (Selected 3 months)")
            self._phase_label.setStyleSheet(
                "font-size: 13px; font-weight: bold; padding: 4px; "
                f"color: {self._PHASE1_COLOR};"
            )
            self._phase_label.setVisible(True)
        elif phase == 2:
            self._phase_label.setText("Phase 2: 確認中 (All CSVs)")
            self._phase_label.setStyleSheet(
                "font-size: 13px; font-weight: bold; padding: 4px; "
                f"color: {self._PHASE2_COLOR};"
            )
            self._phase_label.setVisible(True)

    # ------------------------------------------------------------------
    # Monthly breakdown
    # ------------------------------------------------------------------

    def show_monthly_breakdown(self, result: BollingerExplorationResult) -> None:
        """Show monthly pips breakdown from aggregate_stats.

        崩壊月 (pips < -30) を赤でハイライト、負の軽微月を黄、正を緑寄りの
        デフォルト色で出す。本筋 §3.2 の「月別崩壊ゼロ」基準を目視で判別しやすくする。
        """
        self._monthly_table.setRowCount(0)
        if result.aggregate_stats is None:
            return

        entries = result.aggregate_stats.monthly_entries
        for entry in entries:
            row = self._monthly_table.rowCount()
            self._monthly_table.insertRow(row)

            color = self._monthly_pips_color(entry.total_pips)

            month_item = QTableWidgetItem(entry.label)
            month_item.setForeground(color)
            self._monthly_table.setItem(row, 0, month_item)

            pips_item = QTableWidgetItem(f"{entry.total_pips:.1f}")
            pips_item.setTextAlignment(Qt.AlignCenter)
            pips_item.setForeground(color)
            self._monthly_table.setItem(row, 1, pips_item)

    def _monthly_pips_color(self, pips: float) -> QColor:
        """月別 pips 値から表示色を決める。
        - pips < -30 (崩壊月): 赤 (_DISCARD_COLOR)
        - -30 <= pips < 0   : 黄 (_IMPROVE_COLOR)
        - pips >= 0          : 緑 (_ADOPT_COLOR)
        """
        if pips < self._CRASH_PIPS_THRESHOLD:
            return QColor(self._DISCARD_COLOR)
        if pips < 0:
            return QColor(self._IMPROVE_COLOR)
        return QColor(self._ADOPT_COLOR)

    # ------------------------------------------------------------------
    # Phase 2 results
    # ------------------------------------------------------------------

    def show_phase2_results(self, visible: bool) -> None:
        """Toggle Phase 2 results table visibility."""
        self._phase2_label.setVisible(visible)
        self._phase2_table.setVisible(visible)

    def clear_phase2_results(self) -> None:
        """Clear Phase 2 results table."""
        self._phase2_table.setRowCount(0)
        self._adjust_phase2_table_height()

    def add_phase2_result(
        self, index: int, result: BollingerExplorationResult
    ) -> None:
        """Add a Phase 2 confirmation result to the table."""
        row = self._phase2_table.rowCount()
        self._phase2_table.insertRow(row)

        agg = result.aggregate_stats
        avg_pips = f"{agg.average_pips_per_month:.1f}" if agg else "-"
        win_rate = f"{agg.overall_win_rate:.1f}%" if agg else "-"
        pf = (
            f"{agg.overall_profit_factor:.2f}"
            if agg and agg.overall_profit_factor is not None
            else "-"
        )

        overrides_str = (
            ", ".join(
                f"{k.split('::')[-1]}={v}"
                for k, v in sorted(result.param_overrides.items())
            )
            if result.param_overrides
            else "(default)"
        )

        items = [str(index), avg_pips, win_rate, pf, overrides_str]
        verdict_color = self._verdict_text_color(result.verdict)
        for col, text in enumerate(items):
            item = QTableWidgetItem(text)
            if col < 4:
                item.setTextAlignment(Qt.AlignCenter)

            item.setForeground(QColor(self._DEFAULT_TEXT_COLOR))
            if col == 0:
                item.setForeground(verdict_color)

            self._phase2_table.setItem(row, col, item)

        self._adjust_phase2_table_height()

    # ------------------------------------------------------------------
    # Phase 2 summary (adoption assessment)
    # ------------------------------------------------------------------

    def show_phase2_summary(
        self, results: list[BollingerExplorationResult]
    ) -> None:
        """Show aggregate summary of Phase 2 results for adoption assessment."""
        if not results:
            self._summary_box.setVisible(False)
            return

        best = max(
            results,
            key=lambda r: (
                r.aggregate_stats.average_pips_per_month if r.aggregate_stats else 0.0
            ),
        )
        agg = best.aggregate_stats
        if agg is None:
            self._summary_box.setVisible(False)
            return

        self._summary_labels["total_pips"].setText(f"Total Pips: {agg.total_pips:.1f}")
        self._summary_labels["avg_pips"].setText(
            f"Avg Pips/Month: {agg.average_pips_per_month:.1f}"
        )

        pf_str = (
            f"{agg.overall_profit_factor:.2f}"
            if agg.overall_profit_factor is not None
            else "-"
        )
        self._summary_labels["pf"].setText(f"Profit Factor: {pf_str}")
        self._summary_labels["win_rate"].setText(
            f"Win Rate: {agg.overall_win_rate:.1f}%"
        )

        stddev_str = (
            f"{agg.monthly_pips_stddev:.1f}"
            if agg.monthly_pips_stddev is not None
            else "-"
        )
        self._summary_labels["stddev"].setText(f"Monthly Pips StdDev: {stddev_str}")
        self._summary_labels["deficit_months"].setText(
            f"Deficit Months: {agg.deficit_month_count} / {agg.month_count}"
        )

        mfe_str = (
            f"{agg.avg_mfe_mae_ratio:.2f}" if agg.avg_mfe_mae_ratio is not None else "-"
        )
        self._summary_labels["mfe_mae"].setText(f"Avg MFE/MAE Ratio: {mfe_str}")

        issues: list[str] = []
        if agg.average_pips_per_month < 0:
            issues.append("negative avg pips")
        if agg.overall_profit_factor is not None and agg.overall_profit_factor < 1.0:
            issues.append("PF < 1.0")
        if agg.deficit_month_count > agg.month_count // 2:
            issues.append(f">{agg.month_count // 2} deficit months")

        if not issues:
            assessment_text = "CANDIDATE - viable for adoption"
            color = self._ADOPT_COLOR
        elif len(issues) <= 1:
            assessment_text = f"MARGINAL - {', '.join(issues)}"
            color = self._IMPROVE_COLOR
        else:
            assessment_text = f"WEAK - {', '.join(issues)}"
            color = self._DISCARD_COLOR

        self._summary_labels["assessment"].setText(f"Assessment: {assessment_text}")
        self._summary_labels["assessment"].setStyleSheet(
            "font-size: 13px; font-weight: bold; padding: 4px; "
            f"color: {color};"
        )
        self._summary_box.setVisible(True)

    def hide_phase2_summary(self) -> None:
        """Hide the Phase 2 summary panel."""
        self._summary_box.setVisible(False)
        self._summary_labels["assessment"].setStyleSheet(
            f"font-size: 13px; font-weight: bold; padding: 4px; "
            f"color: {self._DEFAULT_TEXT_COLOR};"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _adjust_phase2_table_height(self) -> None:
        """Adjust Phase 2 table height based on row count."""
        row_count = self._phase2_table.rowCount()
        if row_count == 0:
            self._phase2_table.setMinimumHeight(0)
            self._phase2_table.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
            return

        desired = (
            self._P2_HEADER_HEIGHT + row_count * self._P2_ROW_HEIGHT + self._P2_MARGIN
        )
        clamped = min(desired, self._P2_MAX_HEIGHT)
        self._phase2_table.setMinimumHeight(clamped)
        if desired <= self._P2_MAX_HEIGHT:
            self._phase2_table.setMaximumHeight(desired)
        else:
            self._phase2_table.setMaximumHeight(self._P2_MAX_HEIGHT)

    def _verdict_text_color(self, verdict: str) -> QColor:
        """Return a foreground color for a verdict cell."""
        v = (verdict or "").lower()
        if v == "adopt":
            return QColor(self._ADOPT_COLOR)
        if v == "improve":
            return QColor(self._IMPROVE_COLOR)
        if v == "discard":
            return QColor(self._DISCARD_COLOR)
        return QColor(self._DEFAULT_TEXT_COLOR)