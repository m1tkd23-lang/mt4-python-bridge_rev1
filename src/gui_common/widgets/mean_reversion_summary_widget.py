# src\gui_common\widgets\mean_reversion_summary_widget.py
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

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


class MeanReversionSummaryWidget(QWidget):
    """Shared read-only display of 11 Phase 2 mean-reversion summary fields.

    Consumed directly as a :class:`MeanReversionSummary` dataclass; no dict
    translation is introduced. ``set_summary(None)`` resets every field to
    ``N/A`` and matches the prior AnalysisPanel / result_presenter None-branch
    behavior.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._labels: dict[str, QLabel] = {}

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(3)

        self._populate_grid(grid, _MR_FIELDS_LEFT, col_offset=0)
        self._populate_grid(grid, _MR_FIELDS_RIGHT, col_offset=2)

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
            label.setProperty("role", "kpi-subvalue")
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
            _format_optional_percent(summary.success_rate)
        )
        self._labels["mr_avg_bars_to_reversion"].setText(
            _format_optional_number(summary.avg_bars_to_reversion)
        )
        self._labels["mr_success_within_3"].setText(
            f"{summary.success_within_3_count} "
            f"({_format_optional_percent(summary.success_within_3_rate)})"
        )
        self._labels["mr_success_within_5"].setText(
            f"{summary.success_within_5_count} "
            f"({_format_optional_percent(summary.success_within_5_rate)})"
        )
        self._labels["mr_success_within_8"].setText(
            f"{summary.success_within_8_count} "
            f"({_format_optional_percent(summary.success_within_8_rate)})"
        )
        self._labels["mr_success_within_12"].setText(
            f"{summary.success_within_12_count} "
            f"({_format_optional_percent(summary.success_within_12_rate)})"
        )
        self._labels["mr_avg_max_progress_ratio"].setText(
            _format_optional_number(summary.avg_max_progress_ratio)
        )
        self._labels["mr_avg_max_adverse_excursion"].setText(
            _format_optional_number(summary.avg_max_adverse_excursion)
        )


def _format_optional_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}%"


def _format_optional_number(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}"
