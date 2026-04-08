# src\linked_trade_chart_widget.py
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget
from matplotlib import dates as mdates
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from backtest.csv_loader import HistoricalBarDataset
from backtest.view_models import EquityPoint, TradeViewRow
from mt4_bridge.models import Bar, MarketSnapshot
from mt4_bridge.strategies.v7_state_detector import detect_v7_market_state
from mt4_bridge.strategies.v7_state_models import V7_DEFAULT_PARAMS


class LinkedTradeChartWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._figure = Figure(figsize=(10, 7))
        self._canvas = FigureCanvas(self._figure)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

        self._price_ax = None
        self._pips_ax = None

        self._is_panning = False
        self._last_pan_xdata: float | None = None
        self._syncing_limits = False

        self._dataset: HistoricalBarDataset | None = None
        self._trade_rows: list[TradeViewRow] = []
        self._equity_points: list[EquityPoint] = []

        self._x_values_num: list[float] = []
        self._lows: list[float] = []
        self._highs: list[float] = []
        self._dataset_start_num: float | None = None
        self._dataset_end_num: float | None = None

        self._highlight_price_span = None
        self._highlight_pips_span = None
        self._highlight_entry_artist = None
        self._highlight_exit_artist = None
        self._highlight_pips_start_line = None
        self._highlight_pips_end_line = None
        self._highlight_pips_points = None
        self._highlighted_trade: TradeViewRow | None = None

        self._canvas.mpl_connect("button_press_event", self._on_button_press)
        self._canvas.mpl_connect("button_release_event", self._on_button_release)
        self._canvas.mpl_connect("motion_notify_event", self._on_mouse_move)
        self._canvas.mpl_connect("scroll_event", self._on_scroll)

        self.clear_chart()

    def _build_state_segments_from_bars(self, dataset: HistoricalBarDataset):
        segments = []
        bars = dataset.rows

        if not bars:
            return segments

        bar_objects = []
        prev_state = None
        segment_start_time = bars[0].time

        for row in bars:
            bar_objects.append(
                Bar(
                    time=row.time,
                    open=row.open,
                    high=row.high,
                    low=row.low,
                    close=row.close,
                    tick_volume=row.tick_volume,
                    spread=0,
                )
            )

            snapshot = MarketSnapshot(
                schema_version="gui-1.0",
                generated_at=row.time,
                symbol=dataset.symbol,
                timeframe=dataset.timeframe,
                bars_requested=len(bar_objects),
                bars_copied=len(bar_objects),
                bid=row.close,
                ask=row.close,
                spread_points=0,
                digits=dataset.digits,
                point=dataset.point,
                last_tick_time=row.time,
                bars=bar_objects,
            )

            state = detect_v7_market_state(
                snapshot,
                V7_DEFAULT_PARAMS,
            ).confirmed_state.value

            if prev_state is None:
                prev_state = state
                segment_start_time = row.time
                continue

            if state != prev_state:
                segments.append((segment_start_time, row.time, prev_state))
                segment_start_time = row.time
                prev_state = state

        segments.append((segment_start_time, bars[-1].time, prev_state))
        return segments

    def _draw_state_background(self, ax, segments) -> None:
        for start, end, state in segments:
            x_start = mdates.date2num(start)
            x_end = mdates.date2num(end)

            if state == "trend_up":
                color = "green"
            elif state == "trend_down":
                color = "red"
            elif state == "range":
                color = "blue"
            else:
                continue

            ax.axvspan(x_start, x_end, color=color, alpha=0.08, zorder=0)

    def _apply_default_layout(self) -> None:
        self._figure.subplots_adjust(
            left=0.07,
            right=0.99,
            top=0.94,
            bottom=0.08,
            hspace=0.20,
        )

    def clear_chart(self, title: str = "Linked trade chart") -> None:
        self._dataset = None
        self._trade_rows = []
        self._equity_points = []

        self._x_values_num = []
        self._lows = []
        self._highs = []
        self._dataset_start_num = None
        self._dataset_end_num = None
        self._highlighted_trade = None

        self._figure.clear()
        self._price_ax = self._figure.add_subplot(211)
        self._pips_ax = self._figure.add_subplot(212, sharex=self._price_ax)

        self._reset_highlight_refs()

        self._price_ax.set_title(title)
        self._price_ax.set_ylabel("Price")
        self._price_ax.grid(True, linewidth=0.4)

        self._pips_ax.set_title("Cumulative pips by time")
        self._pips_ax.set_ylabel("Pips")
        self._pips_ax.grid(True, linewidth=0.4)

        locator = mdates.AutoDateLocator()
        formatter = mdates.ConciseDateFormatter(locator)
        self._pips_ax.xaxis.set_major_locator(locator)
        self._pips_ax.xaxis.set_major_formatter(formatter)

        self._register_xlim_sync()
        self._apply_default_layout()
        self._canvas.draw()

    def plot_dataset_with_equity(
        self,
        dataset: HistoricalBarDataset,
        trade_rows: list[TradeViewRow],
        equity_points: list[EquityPoint],
        *,
        price_title: str = "Price chart with entry / exit",
    ) -> None:
        self._dataset = dataset
        self._trade_rows = list(trade_rows)
        self._equity_points = list(equity_points)
        self._highlighted_trade = None

        self._figure.clear()
        self._price_ax = self._figure.add_subplot(211)
        self._pips_ax = self._figure.add_subplot(212, sharex=self._price_ax)

        self._reset_highlight_refs()

        self._draw_price_chart(
            dataset=dataset,
            trade_rows=trade_rows,
            title=price_title,
        )
        self._draw_pips_chart(
            dataset=dataset,
            equity_points=equity_points,
        )

        self._register_xlim_sync()
        self._apply_default_layout()
        self._canvas.draw()

    def clear_highlight(self) -> None:
        self._highlighted_trade = None
        self._remove_highlight_artists()
        self._canvas.draw_idle()

    def highlight_trade(self, trade_row: TradeViewRow) -> None:
        if self._price_ax is None or self._pips_ax is None:
            return

        self._highlighted_trade = trade_row
        self._remove_highlight_artists()

        entry_x = mdates.date2num(trade_row.entry_time)
        exit_x = mdates.date2num(trade_row.exit_time)
        left_x = min(entry_x, exit_x)
        right_x = max(entry_x, exit_x)

        self._highlight_price_span = self._price_ax.axvspan(
            left_x,
            right_x,
            alpha=0.18,
            zorder=4,
        )
        self._highlight_pips_span = self._pips_ax.axvspan(
            left_x,
            right_x,
            alpha=0.18,
            zorder=4,
        )

        self._highlight_entry_artist = self._price_ax.scatter(
            [trade_row.entry_time],
            [trade_row.entry_price],
            marker="o",
            s=70,
            zorder=5,
        )
        self._highlight_exit_artist = self._price_ax.scatter(
            [trade_row.exit_time],
            [trade_row.exit_price],
            marker="o",
            s=70,
            zorder=5,
        )

        start_pips = self._cumulative_pips_before_trade(trade_row)
        end_pips = start_pips + float(trade_row.pips)

        self._highlight_pips_start_line = self._pips_ax.axvline(
            entry_x,
            linewidth=1.2,
            zorder=5,
        )
        self._highlight_pips_end_line = self._pips_ax.axvline(
            exit_x,
            linewidth=1.2,
            zorder=5,
        )
        self._highlight_pips_points = self._pips_ax.scatter(
            [trade_row.entry_time, trade_row.exit_time],
            [start_pips, end_pips],
            marker="o",
            s=40,
            zorder=6,
        )

        self._ensure_trade_visible(left_x=left_x, right_x=right_x)
        self._canvas.draw_idle()

    def _remove_highlight_artists(self) -> None:
        for attr_name in (
            "_highlight_price_span",
            "_highlight_pips_span",
            "_highlight_entry_artist",
            "_highlight_exit_artist",
            "_highlight_pips_start_line",
            "_highlight_pips_end_line",
            "_highlight_pips_points",
        ):
            artist = getattr(self, attr_name)
            if artist is None:
                continue
            try:
                artist.remove()
            except (ValueError, AttributeError):
                pass
            setattr(self, attr_name, None)

    def _reset_highlight_refs(self) -> None:
        self._highlight_price_span = None
        self._highlight_pips_span = None
        self._highlight_entry_artist = None
        self._highlight_exit_artist = None
        self._highlight_pips_start_line = None
        self._highlight_pips_end_line = None
        self._highlight_pips_points = None

    def _cumulative_pips_before_trade(self, target_trade: TradeViewRow) -> float:
        cumulative = 0.0
        for row in self._trade_rows:
            if row is target_trade:
                break
            cumulative += float(row.pips)
        return cumulative

    def _ensure_trade_visible(self, *, left_x: float, right_x: float) -> None:
        if self._price_ax is None or self._pips_ax is None:
            return

        current_left, current_right = self._price_ax.get_xlim()
        if left_x >= current_left and right_x <= current_right:
            return

        span = right_x - left_x
        padding = span * 1.5 if span > 0 else (current_right - current_left) * 0.1
        if padding <= 0:
            padding = 0.001

        new_left = left_x - padding
        new_right = right_x + padding

        if self._dataset_start_num is not None:
            new_left = max(new_left, self._dataset_start_num)
        if self._dataset_end_num is not None:
            new_right = min(new_right, self._dataset_end_num)

        if new_right <= new_left:
            return

        self._price_ax.set_xlim(new_left, new_right)
        self._pips_ax.set_xlim(new_left, new_right)

    def _draw_price_chart(
        self,
        dataset: HistoricalBarDataset,
        trade_rows: list[TradeViewRow],
        title: str,
    ) -> None:
        ax = self._price_ax
        if ax is None:
            return

        if not dataset.rows:
            ax.set_title(f"{title} (no bars)")
            ax.set_ylabel("Price")
            ax.grid(True, linewidth=0.4)
            return

        self._x_values_num = [mdates.date2num(row.time) for row in dataset.rows]
        self._lows = [row.low for row in dataset.rows]
        self._highs = [row.high for row in dataset.rows]
        self._dataset_start_num = self._x_values_num[0]
        self._dataset_end_num = self._x_values_num[-1]

        segments = self._build_state_segments_from_bars(dataset)
        self._draw_state_background(ax, segments)

        candle_width = self._compute_candle_width(self._x_values_num)

        for x_value, row in zip(self._x_values_num, dataset.rows):
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
            face_color = "black" if row.close >= row.open else "white"

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

        min_price = min(self._lows)
        max_price = max(self._highs)
        padding = (max_price - min_price) * 0.03 if max_price > min_price else 0.001

        ax.set_title(title)
        ax.set_ylabel("Price")
        ax.set_xlim(self._x_values_num[0], self._x_values_num[-1])
        ax.set_ylim(min_price - padding, max_price + padding)
        ax.grid(True, linewidth=0.4)

    def _draw_pips_chart(
        self,
        dataset: HistoricalBarDataset,
        equity_points: list[EquityPoint],
    ) -> None:
        ax = self._pips_ax
        if ax is None:
            return

        if not dataset.rows:
            return

        x = [dataset.rows[0].time]
        y = [0.0]

        for p in equity_points:
            x.append(p.exit_time)
            y.append(p.cumulative_pips)

        if x[-1] != dataset.rows[-1].time:
            x.append(dataset.rows[-1].time)
            y.append(y[-1])

        ax.plot(x, y)
        ax.set_xlim(dataset.rows[0].time, dataset.rows[-1].time)

    def _compute_candle_width(self, x_values: list[float]) -> float:
        if len(x_values) < 2:
            return 1.0 / 288.0 * 0.72
        deltas = [b - a for a, b in zip(x_values[:-1], x_values[1:]) if b > a]
        return min(deltas) * 0.72 if deltas else 1.0 / 288.0 * 0.72

    def _plot_trade_markers(self, ax, trade_rows: list[TradeViewRow]) -> None:
        if not trade_rows:
            return

        for row in trade_rows:
            x_entry = mdates.date2num(row.entry_time)
            x_exit = mdates.date2num(row.exit_time)

            if row.position_type == "buy":
                ax.scatter(
                    [x_entry],
                    [row.entry_price],
                    marker="^",
                    color="blue",
                    zorder=3,
                )
            else:
                ax.scatter(
                    [x_entry],
                    [row.entry_price],
                    marker="v",
                    color="orange",
                    zorder=3,
                )

            ax.scatter(
                [x_exit],
                [row.exit_price],
                marker="o",
                color="red",
                zorder=3,
            )

    def _register_xlim_sync(self) -> None:
        if self._price_ax and self._pips_ax:
            self._price_ax.callbacks.connect("xlim_changed", self._sync_from_price_ax)
            self._pips_ax.callbacks.connect("xlim_changed", self._sync_from_pips_ax)

    def _sync_from_price_ax(self, ax) -> None:
        if self._syncing_limits:
            return
        self._syncing_limits = True
        self._pips_ax.set_xlim(self._price_ax.get_xlim())
        self._syncing_limits = False

    def _sync_from_pips_ax(self, ax) -> None:
        if self._syncing_limits:
            return
        self._syncing_limits = True
        self._price_ax.set_xlim(self._pips_ax.get_xlim())
        self._syncing_limits = False

    def _on_button_press(self, event) -> None:
        if event.button == 1 and event.xdata is not None:
            self._is_panning = True
            self._last_pan_xdata = event.xdata

    def _on_button_release(self, event) -> None:
        self._is_panning = False
        self._last_pan_xdata = None

    def _on_mouse_move(self, event) -> None:
        if not self._is_panning or event.xdata is None:
            return

        delta = self._last_pan_xdata - event.xdata
        left, right = self._price_ax.get_xlim()
        self._price_ax.set_xlim(left + delta, right + delta)
        self._pips_ax.set_xlim(left + delta, right + delta)
        self._last_pan_xdata = event.xdata
        self._canvas.draw_idle()

    def _on_scroll(self, event) -> None:
        if event.xdata is None:
            return

        left, right = self._price_ax.get_xlim()
        span = right - left
        factor = 0.8 if event.button == "up" else 1.25

        new_span = span * factor
        center = event.xdata

        new_left = center - new_span / 2
        new_right = center + new_span / 2

        if self._dataset_start_num is not None:
            new_left = max(new_left, self._dataset_start_num)
        if self._dataset_end_num is not None:
            new_right = min(new_right, self._dataset_end_num)

        if new_right <= new_left:
            return

        self._price_ax.set_xlim(new_left, new_right)
        self._pips_ax.set_xlim(new_left, new_right)
        self._canvas.draw_idle()