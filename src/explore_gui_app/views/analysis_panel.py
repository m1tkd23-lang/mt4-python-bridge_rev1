# src\explore_gui_app\views\analysis_panel.py
from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from backtest.mean_reversion_analysis import MeanReversionSummary
from gui_common.widgets.mean_reversion_summary_widget import (
    MeanReversionSummaryWidget,
)


class AnalysisPanel(QWidget):
    """Read-only view of the Phase 2 mean-reversion summary (11 fields).

    Delegates field layout and value formatting to the shared
    :class:`MeanReversionSummaryWidget` (TASK-0141 / S-3). ``set_summary(None)``
    resets all fields back to ``N/A``.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QLabel("<b>Phase 2 Mean Reversion Summary (all months)</b>")
        layout.addWidget(title)

        self._mr_widget = MeanReversionSummaryWidget()
        layout.addWidget(self._mr_widget)

        layout.addStretch(1)

    def set_summary(self, summary: MeanReversionSummary | None) -> None:
        self._mr_widget.set_summary(summary)
