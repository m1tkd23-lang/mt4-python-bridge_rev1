# src\backtest_gui_app\widgets\price_chart_widget.py
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget
from matplotlib import dates as mdates
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from backtest.csv_loader import HistoricalBarDataset
from backtest.view_models import TradeViewRow


class PriceChartWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._figure = Figure(figsize=(8, 4))
        self._canvas = FigureCanvas(self._figure)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

    def _apply_default_layout(self) -> None:
        self._figure.subplots_adjust(left=0.08, right=0.99, top=0.92, bottom=0.12)

    def clear_chart(self, title: str = "Price chart") -> None:
        self._figure.clear()
        ax = self._figure.add_subplot(111)
        ax.set_title(title)
        ax.grid(True)
        self._apply_default_layout()
        self._canvas.draw_idle()

    def plot_dataset_with_trades(
        self,
        dataset: HistoricalBarDataset,
        trade_rows: list[TradeViewRow],
        title: str,
    ) -> None:
        self._figure.clear()
        ax = self._figure.add_subplot(111)

        if not dataset.rows:
            ax.set_title(f"{title} (no bars)")
            ax.grid(True)
            self._apply_default_layout()
            self._canvas.draw_idle()
            return

        x_values = [mdates.date2num(row.time) for row in dataset.rows]
        if len(x_values) >= 2:
            deltas = [
                next_value - current_value
                for current_value, next_value in zip(x_values[:-1], x_values[1:])
                if next_value > current_value
            ]
            min_delta = min(deltas) if deltas else (1.0 / 288.0)
            candle_width = min_delta * 0.72 if min_delta > 0 else (1.0 / 288.0) * 0.72
        else:
            candle_width = (1.0 / 288.0) * 0.72

        for x_value, row in zip(x_values, dataset.rows):
            ax.vlines(
                x_value,
                row.low,
                row.high,
                color="black",
                linewidth=0.8,
                zorder=1,
            )

            body_low = min(row.open, row.close)
            body_high = max(row.open, row.close)
            body_height = body_high - body_low

            if row.close >= row.open:
                face_color = "black"
            else:
                face_color = "white"

            if body_height == 0:
                ax.hlines(
                    row.open,
                    x_value - (candle_width / 2.0),
                    x_value + (candle_width / 2.0),
                    color="black",
                    linewidth=1.1,
                    zorder=2,
                )
            else:
                rectangle = Rectangle(
                    (x_value - (candle_width / 2.0), body_low),
                    candle_width,
                    body_height,
                    facecolor=face_color,
                    edgecolor="black",
                    linewidth=0.9,
                    zorder=2,
                )
                ax.add_patch(rectangle)

        self._plot_trade_markers(ax=ax, trade_rows=trade_rows)

        min_price = min(row.low for row in dataset.rows)
        max_price = max(row.high for row in dataset.rows)
        price_range = max_price - min_price
        padding = price_range * 0.03 if price_range > 0 else max_price * 0.001 or 0.001

        ax.set_title(title)
        ax.set_ylabel("Price")
        ax.set_xlim(x_values[0], x_values[-1])
        ax.set_ylim(min_price - padding, max_price + padding)
        ax.grid(True, linewidth=0.4)

        locator = mdates.AutoDateLocator()
        formatter = mdates.ConciseDateFormatter(locator)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(formatter)

        self._apply_default_layout()
        self._canvas.draw_idle()

    def _plot_trade_markers(self, ax, trade_rows: list[TradeViewRow]) -> None:
        if not trade_rows:
            return

        entry_buy_x: list[float] = []
        entry_buy_y: list[float] = []
        entry_sell_x: list[float] = []
        entry_sell_y: list[float] = []
        exit_x: list[float] = []
        exit_y: list[float] = []

        for row in trade_rows:
            entry_num = mdates.date2num(row.entry_time)
            exit_num = mdates.date2num(row.exit_time)

            if row.position_type.lower() == "buy":
                entry_buy_x.append(entry_num)
                entry_buy_y.append(row.entry_price)
            else:
                entry_sell_x.append(entry_num)
                entry_sell_y.append(row.entry_price)

            exit_x.append(exit_num)
            exit_y.append(row.exit_price)

        if entry_buy_x:
            ax.scatter(
                entry_buy_x,
                entry_buy_y,
                marker="^",
                s=42,
                color="tab:blue",
                label="Buy entry",
                zorder=3,
            )

        if entry_sell_x:
            ax.scatter(
                entry_sell_x,
                entry_sell_y,
                marker="v",
                s=42,
                color="tab:orange",
                label="Sell entry",
                zorder=3,
            )

        if exit_x:
            ax.scatter(
                exit_x,
                exit_y,
                marker="o",
                s=28,
                color="tab:red",
                label="Exit",
                zorder=3,
            )

        handles, labels = ax.get_legend_handles_labels()
        if handles:
            unique: dict[str, object] = {}
            for handle, label in zip(handles, labels):
                if label not in unique:
                    unique[label] = handle
            ax.legend(
                unique.values(),
                unique.keys(),
                loc="upper left",
                fontsize=8,
            )