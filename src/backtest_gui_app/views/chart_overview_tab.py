# src\backtest_gui_app\views\chart_overview_tab.py
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from backtest_gui_app.views.result_tabs import ResultTabs
from gui_common.widgets.collapsible_section import CollapsibleSection
from backtest_gui_app.widgets.linked_trade_chart_widget import LinkedTradeChartWidget


class ChartOverviewTab(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.strategy_value_label = QLabel("-")
        self.strategy_value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.csv_value_label = QLabel("-")
        self.csv_value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.linked_chart = LinkedTradeChartWidget()
        self.detail_tabs = ResultTabs(include_pips_tab=False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(self._build_source_section())
        layout.addWidget(self._build_chart_splitter())

    def _build_source_section(self) -> QWidget:
        content = QWidget()
        form = QFormLayout(content)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        form.addRow("Strategy", self.strategy_value_label)
        form.addRow("CSV", self.csv_value_label)
        return CollapsibleSection("Source overview", content, expanded=True)

    def _build_chart_splitter(self) -> QWidget:
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.linked_chart)
        splitter.addWidget(self.detail_tabs)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([700, 260])
        return splitter