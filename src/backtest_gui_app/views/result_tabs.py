# src/backtest_gui_app/views/result_tabs.py
from __future__ import annotations

from PySide6.QtWidgets import (
    QHeaderView,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gui_common.widgets.chart_widget import MatplotlibChart


class ResultTabs(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        include_pips_tab: bool = True,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.result_tabs = QTabWidget()

        self.pips_chart = MatplotlibChart() if include_pips_tab else None
        self.balance_chart = MatplotlibChart()
        self.trades_table = self._build_trades_table()

        if self.pips_chart is not None:
            self.result_tabs.addTab(self.pips_chart, "Cumulative pips")
        self.result_tabs.addTab(self.balance_chart, "Converted balance")
        self.result_tabs.addTab(self.trades_table, "Trades")

        layout.addWidget(self.result_tabs)

    def _build_trades_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(33)
        table.setHorizontalHeaderLabels(
            [
                "No",
                "Lane",
                "Entry subtype",
                "Entry time",
                "Exit time",
                "Type",
                "Entry",
                "Exit",
                "Pips",
                "Cum pips",
                "Profit amount",
                "Balance after",
                "Exit reason",
                "Entry state",
                "Exit state",
                "Entry detected state",
                "Entry candidate state",
                "Entry event",
                "Entry state age",
                "Entry candidate age",
                "Entry range score",
                "Entry trans up score",
                "Entry trans down score",
                "Entry trend up score",
                "Entry trend down score",
                "Exit detected state",
                "Exit candidate state",
                "Exit event",
                "Exit state age",
                "Exit candidate age",
                "Exit scores",
                "Entry signal reason",
                "Exit signal reason",
            ]
        )
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)
        return table