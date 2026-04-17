# src\explore_gui_app\views\analysis_panel.py
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from backtest.mean_reversion_analysis import MeanReversionSummary


_MR_FIELDS_LEFT: list[tuple[str, str]] = [
    ("mr_total_range_trades", "Total range trades"),
    ("mr_reversion_failure_count", "Reversion fail"),
    ("mr_reversion_success_count", "Reversion success"),
    ("mr_success_rate", "Success rate"),
    ("mr_avg_bars_to_reversion", "Avg bars to reversion"),
]

_MR_FIELDS_RIGHT: list[tuple[str, str]] = [
    ("mr_success_within_3", "Success <=3"),
    ("mr_success_within_5", "Success <=5"),
    ("mr_success_within_8", "Success <=8"),
    ("mr_success_within_12", "Success <=12"),
    ("mr_avg_max_progress_ratio", "Avg max progress"),
    ("mr_avg_max_adverse_excursion", "Avg max adverse"),
]

_MR_KEYS: tuple[str, ...] = tuple(
    key for key, _ in (*_MR_FIELDS_LEFT, *_MR_FIELDS_RIGHT)
)


class AnalysisPanel(QWidget):
    """Read-only view of the Phase 2 mean-reversion summary (11 fields).

    Displays the full-period mean-reversion summary produced by Phase 2 of the
    exploration flow. Fields default to ``N/A`` until a summary is supplied via
    :meth:`set_summary`; ``set_summary(None)`` resets all fields back to N/A.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QLabel("<b>Phase 2 Mean Reversion Summary (all months)</b>")
        layout.addWidget(title)

        self._labels: dict[str, QLabel] = {}

        grid_box = QWidget()
        grid = QGridLayout(grid_box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(3)
        self._populate_grid(grid, _MR_FIELDS_LEFT, col_offset=0)
        self._populate_grid(grid, _MR_FIELDS_RIGHT, col_offset=2)
        layout.addWidget(grid_box)

        layout.addStretch(1)

        self.set_summary(None)

    def _populate_grid(
        self,
        grid: QGridLayout,
        fields: list[tuple[str, str]],
        *,
        col_offset: int,
    ) -> None:
        for row, (key, label_text) in enumerate(fields):
            label = QLabel(label_text)
            value_label = QLabel("-")
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._labels[key] = value_label
            grid.addWidget(label, row, col_offset)
            grid.addWidget(value_label, row, col_offset + 1)

    def set_summary(self, summary: MeanReversionSummary | None) -> None:
        if summary is None:
            for key in _MR_KEYS:
                self._labels[key].setText("N/A")
            return

        self._labels["mr_total_range_trades"].setText(
            str(summary.total_range_trades)
        )
        self._labels["mr_reversion_failure_count"].setText(
            str(summary.reversion_failure_count)
        )
        self._labels["mr_reversion_success_count"].setText(
            str(summary.reversion_success_count)
        )
        self._labels["mr_success_rate"].setText(
            self._format_optional_percent(summary.success_rate)
        )
        self._labels["mr_avg_bars_to_reversion"].setText(
            self._format_optional_number(summary.avg_bars_to_reversion)
        )
        self._labels["mr_success_within_3"].setText(
            f"{summary.success_within_3_count} "
            f"({self._format_optional_percent(summary.success_within_3_rate)})"
        )
        self._labels["mr_success_within_5"].setText(
            f"{summary.success_within_5_count} "
            f"({self._format_optional_percent(summary.success_within_5_rate)})"
        )
        self._labels["mr_success_within_8"].setText(
            f"{summary.success_within_8_count} "
            f"({self._format_optional_percent(summary.success_within_8_rate)})"
        )
        self._labels["mr_success_within_12"].setText(
            f"{summary.success_within_12_count} "
            f"({self._format_optional_percent(summary.success_within_12_rate)})"
        )
        self._labels["mr_avg_max_progress_ratio"].setText(
            self._format_optional_number(summary.avg_max_progress_ratio)
        )
        self._labels["mr_avg_max_adverse_excursion"].setText(
            self._format_optional_number(summary.avg_max_adverse_excursion)
        )

    @staticmethod
    def _format_optional_percent(value: float | None) -> str:
        if value is None:
            return "N/A"
        return f"{value:.2f}%"

    @staticmethod
    def _format_optional_number(value: float | None) -> str:
        if value is None:
            return "N/A"
        return f"{value:.2f}"
