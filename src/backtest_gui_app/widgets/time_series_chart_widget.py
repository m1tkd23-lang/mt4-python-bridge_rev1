# src\backtest_gui_app\widgets\time_series_chart_widget.py
from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QVBoxLayout, QWidget
from matplotlib import dates as mdates
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from backtest_gui_app.styles import DARK_THEME_COLORS, style_matplotlib_figure


class TimeSeriesChartWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._figure = Figure(figsize=(8, 3))
        self._canvas = FigureCanvas(self._figure)
        self._canvas.setStyleSheet(f"background-color: {DARK_THEME_COLORS['panel']};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

    def _apply_default_layout(self) -> None:
        self._figure.subplots_adjust(left=0.08, right=0.99, top=0.90, bottom=0.14)

    def clear_chart(self, title: str = "No data") -> None:
        self._figure.clear()
        ax = self._figure.add_subplot(111)
        ax.set_title(title)
        style_matplotlib_figure(self._figure, axes=[ax])
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
            style_matplotlib_figure(self._figure, axes=[ax])
            self._apply_default_layout()
            self._canvas.draw_idle()
            return

        ax.plot(x_values, y_values, color=DARK_THEME_COLORS["accent"], linewidth=1.4)
        ax.set_title(title)
        ax.set_ylabel(y_label)

        if x_range is not None:
            ax.set_xlim(x_range[0], x_range[1])

        locator = mdates.AutoDateLocator()
        formatter = mdates.ConciseDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)

        style_matplotlib_figure(self._figure, axes=[ax])
        self._apply_default_layout()
        self._canvas.draw_idle()

    def plot_series_with_vlines(
        self,
        x_values: list[datetime],
        y_values: list[float],
        title: str,
        y_label: str,
        vline_positions: list[datetime] | None = None,
    ) -> None:
        self._figure.clear()
        ax = self._figure.add_subplot(111)

        if not x_values or not y_values:
            ax.set_title(f"{title} (no data)")
            style_matplotlib_figure(self._figure, axes=[ax])
            self._apply_default_layout()
            self._canvas.draw_idle()
            return

        ax.plot(x_values, y_values, color=DARK_THEME_COLORS["accent"], linewidth=1.4)
        ax.set_title(title)
        ax.set_ylabel(y_label)

        if vline_positions:
            for vx in vline_positions:
                ax.axvline(
                    x=vx,
                    color=DARK_THEME_COLORS["text_dim"],
                    linestyle="--",
                    linewidth=0.6,
                    alpha=0.7,
                )

        ax.axhline(y=0, color=DARK_THEME_COLORS["text_muted"], linewidth=0.5)

        locator = mdates.AutoDateLocator()
        formatter = mdates.ConciseDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)

        style_matplotlib_figure(self._figure, axes=[ax])
        self._apply_default_layout()
        self._canvas.draw_idle()
