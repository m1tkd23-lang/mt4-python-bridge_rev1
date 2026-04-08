# src\backtest_gui_app\widgets\chart_widget.py
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class MatplotlibChart(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._figure = Figure(figsize=(6, 4))
        self._canvas = FigureCanvas(self._figure)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

    def _apply_default_layout(self) -> None:
        self._figure.subplots_adjust(left=0.10, right=0.98, top=0.92, bottom=0.12)

    def plot_series(
        self,
        x_values: list[int],
        y_values: list[float],
        title: str,
        x_label: str,
        y_label: str,
    ) -> None:
        self._figure.clear()
        ax = self._figure.add_subplot(111)
        ax.plot(x_values, y_values)
        ax.set_title(title)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.grid(True)
        self._apply_default_layout()
        self._canvas.draw_idle()

    def clear_chart(self, title: str = "No data") -> None:
        self._figure.clear()
        ax = self._figure.add_subplot(111)
        ax.set_title(title)
        ax.grid(True)
        self._apply_default_layout()
        self._canvas.draw_idle()