# src\backtest_gui_app\widgets\time_series_chart_widget.py
from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QVBoxLayout, QWidget
from matplotlib import dates as mdates
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class TimeSeriesChartWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._figure = Figure(figsize=(8, 3))
        self._canvas = FigureCanvas(self._figure)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

    def _apply_default_layout(self) -> None:
        self._figure.subplots_adjust(left=0.08, right=0.99, top=0.90, bottom=0.14)

    def clear_chart(self, title: str = "No data") -> None:
        self._figure.clear()
        ax = self._figure.add_subplot(111)
        ax.set_title(title)
        ax.grid(True)
        self._apply_default_layout()
        self._canvas.draw_idle()

    def plot_series(
        self,
        x_values: list[datetime],
        y_values: list[float],
        title: str,
        y_label: str,
        x_range: tuple[datetime, datetime] | None = None,
    ) -> None:
        self._figure.clear()
        ax = self._figure.add_subplot(111)

        if not x_values or not y_values:
            ax.set_title(f"{title} (no data)")
            ax.grid(True)
            self._apply_default_layout()
            self._canvas.draw_idle()
            return

        ax.plot(x_values, y_values)
        ax.set_title(title)
        ax.set_ylabel(y_label)
        ax.grid(True, linewidth=0.4)

        if x_range is not None:
            ax.set_xlim(x_range[0], x_range[1])

        locator = mdates.AutoDateLocator()
        formatter = mdates.ConciseDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)

        self._apply_default_layout()
        self._canvas.draw_idle()