# src/gui_common/widgets/linked_trade_chart_widget.py
"""ローソク足 + トレードマーカー + 累積 pips の連動チャート widget。

backtest_gui_app/widgets/linked_trade_chart_widget.py をベースに、
explore_gui の terminal dark theme への配色統一・lane 別マーカー・
描画間引きを組み込んだ共通版。chart タブ / ポップアップウィンドウから共有される。

重要:
- matplotlib のデフォルト RGB 背景(white)を無効化し、theme に合わせて黒背景で描画する
- ローソクは陽線 green / 陰線 red の塗りつぶし、ヒゲは薄グレーで視認性確保
- エントリーマーカーは lane ごとに色を変えるため、trade_row.lane が "range"/"trend" の場合に使い分ける
- 全期間表示時 (可視本数 >= CANDLE_DECIMATION_THRESHOLD) はローソク body 描画をスキップして
  close 価格の折れ線で代替 → ズームすると自動的にローソクに切り替わる
"""
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget
from matplotlib import dates as mdates
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from backtest.csv_loader import HistoricalBarDataset
from backtest.simulator import StateSegment
from backtest.view_models import EquityPoint, TradeViewRow


# ---------------------------------------------------------------------------
# Terminal dark theme カラーパレット
# ---------------------------------------------------------------------------
_BG = "#000000"
_FG = "#dcdcdc"
_GRID = "#333333"

_CANDLE_UP = "#7BD88F"
_CANDLE_DOWN = "#FF7B72"
_CANDLE_WICK = "#dcdcdc"

_EQUITY_LINE = "#6FA8FF"

# lane 別エントリーマーカー
_MARKER_RANGE_BUY = "#6FA8FF"
_MARKER_RANGE_SELL = "#B084EB"
_MARKER_TREND_BUY = "#7BD88F"
_MARKER_TREND_SELL = "#F0A050"
_MARKER_LEGACY_BUY = "#6FA8FF"
_MARKER_LEGACY_SELL = "#F0A050"
_MARKER_EXIT = "#F0C674"

_HIGHLIGHT_SPAN = "#F0C674"
_HIGHLIGHT_ENTRY = "#F0C674"
_HIGHLIGHT_EXIT = "#FFFFFF"
_HIGHLIGHT_PIPS = "#F0C674"

# state 背景 (default OFF、ユーザ切替で ON)
_STATE_BG_COLORS = {
    "trend_up": "#7BD88F",
    "trend_down": "#FF7B72",
    "range": "#6FA8FF",
}
_STATE_BG_ALPHA = 0.12

# 描画間引き閾値: 可視範囲 bar 数がこれ以上なら candle body を省略して線描画
CANDLE_DECIMATION_THRESHOLD = 2000


def _apply_dark_style(ax) -> None:
    ax.set_facecolor(_BG)
    for spine in ax.spines.values():
        spine.set_edgecolor(_FG)
    ax.tick_params(colors=_FG, which="both")
    ax.xaxis.label.set_color(_FG)
    ax.yaxis.label.set_color(_FG)
    ax.title.set_color(_FG)
    ax.grid(True, color=_GRID, linewidth=0.4)


class LinkedTradeChartWidget(QWidget):
    """価格 + 累積 pips の 2 軸連動チャート。ズーム/パン/ハイライト対応。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._figure = Figure(figsize=(12, 7), facecolor=_BG)
        self._canvas = FigureCanvas(self._figure)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

        self._price_ax = None
        self._pips_ax = None

        self._is_panning = False
        self._last_pan_xdata: float | None = None
        self._syncing_limits = False
        self._show_state_bg = False

        self._dataset: HistoricalBarDataset | None = None
        self._trade_rows: list[TradeViewRow] = []
        self._equity_points: list[EquityPoint] = []
        self._state_segments: list[StateSegment] = []

        self._x_values_num: list[float] = []
        self._lows: list[float] = []
        self._highs: list[float] = []
        self._closes: list[float] = []
        self._dataset_start_num: float | None = None
        self._dataset_end_num: float | None = None

        # ローソク描画用の patches ( 全本描画済み、_refresh_candles でズームに応じて visibility 切替 )
        self._candle_patches: list = []
        self._close_line = None  # decimation 時の折れ線
        self._last_decimation_state: bool | None = None

        # ハイライト artifacts
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clear_chart(self, title: str = "Trade chart") -> None:
        self._dataset = None
        self._trade_rows = []
        self._equity_points = []
        self._state_segments = []

        self._x_values_num = []
        self._lows = []
        self._highs = []
        self._closes = []
        self._dataset_start_num = None
        self._dataset_end_num = None
        self._highlighted_trade = None
        self._candle_patches = []
        self._close_line = None
        self._last_decimation_state = None

        self._figure.clear()
        self._figure.patch.set_facecolor(_BG)
        self._price_ax = self._figure.add_subplot(211)
        self._pips_ax = self._figure.add_subplot(212, sharex=self._price_ax)

        self._reset_highlight_refs()

        self._price_ax.set_title(title, color=_FG)
        self._price_ax.set_ylabel("Price")
        _apply_dark_style(self._price_ax)

        self._pips_ax.set_title("Cumulative pips by time", color=_FG)
        self._pips_ax.set_ylabel("Pips")
        _apply_dark_style(self._pips_ax)

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
        state_segments: list[StateSegment],
        *,
        price_title: str = "Price with entry / exit",
    ) -> None:
        self._dataset = dataset
        self._trade_rows = list(trade_rows)
        self._equity_points = list(equity_points)
        self._state_segments = list(state_segments)
        self._highlighted_trade = None
        self._candle_patches = []
        self._close_line = None
        self._last_decimation_state = None

        self._figure.clear()
        self._figure.patch.set_facecolor(_BG)
        self._price_ax = self._figure.add_subplot(211)
        self._pips_ax = self._figure.add_subplot(212, sharex=self._price_ax)

        self._reset_highlight_refs()

        self._draw_price_chart(
            dataset=dataset,
            trade_rows=trade_rows,
            state_segments=state_segments,
            title=price_title,
        )
        self._draw_pips_chart(dataset=dataset, equity_points=equity_points)

        self._register_xlim_sync()
        self._apply_default_layout()
        self._refresh_candles_visibility()
        self._canvas.draw()

    def reset_zoom(self) -> None:
        """全期間表示に戻す。"""
        if (
            self._price_ax is None
            or self._dataset_start_num is None
            or self._dataset_end_num is None
        ):
            return
        self._price_ax.set_xlim(self._dataset_start_num, self._dataset_end_num)
        if self._lows and self._highs:
            min_price = min(self._lows)
            max_price = max(self._highs)
            padding = (
                (max_price - min_price) * 0.03 if max_price > min_price else 0.001
            )
            self._price_ax.set_ylim(min_price - padding, max_price + padding)
        self._refresh_candles_visibility()
        self._canvas.draw_idle()

    def set_state_background_visible(self, visible: bool) -> None:
        """state 背景 tint の表示切替。再描画が必要。"""
        if self._show_state_bg == visible:
            return
        self._show_state_bg = visible
        if self._dataset is None:
            return
        # 背景再描画のため全プロットやり直し(state 以外の artifacts はそのまま)
        self.plot_dataset_with_equity(
            dataset=self._dataset,
            trade_rows=self._trade_rows,
            equity_points=self._equity_points,
            state_segments=self._state_segments,
        )
        if self._highlighted_trade is not None:
            self.highlight_trade(self._highlighted_trade)

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
            color=_HIGHLIGHT_SPAN,
            alpha=0.18,
            zorder=4,
        )
        self._highlight_pips_span = self._pips_ax.axvspan(
            left_x,
            right_x,
            color=_HIGHLIGHT_SPAN,
            alpha=0.18,
            zorder=4,
        )

        self._highlight_entry_artist = self._price_ax.scatter(
            [trade_row.entry_time],
            [trade_row.entry_price],
            marker="o",
            s=90,
            facecolors="none",
            edgecolors=_HIGHLIGHT_ENTRY,
            linewidths=2.0,
            zorder=5,
        )
        self._highlight_exit_artist = self._price_ax.scatter(
            [trade_row.exit_time],
            [trade_row.exit_price],
            marker="o",
            s=90,
            facecolors="none",
            edgecolors=_HIGHLIGHT_EXIT,
            linewidths=2.0,
            zorder=5,
        )

        start_pips = self._cumulative_pips_before_trade(trade_row)
        end_pips = start_pips + float(trade_row.pips)

        self._highlight_pips_start_line = self._pips_ax.axvline(
            entry_x,
            linewidth=1.2,
            color=_HIGHLIGHT_PIPS,
            zorder=5,
        )
        self._highlight_pips_end_line = self._pips_ax.axvline(
            exit_x,
            linewidth=1.2,
            color=_HIGHLIGHT_PIPS,
            zorder=5,
        )
        self._highlight_pips_points = self._pips_ax.scatter(
            [trade_row.entry_time, trade_row.exit_time],
            [start_pips, end_pips],
            marker="o",
            s=40,
            color=_HIGHLIGHT_PIPS,
            zorder=6,
        )

        self._ensure_trade_visible(left_x=left_x, right_x=right_x)
        # y 軸を可視範囲の価格にフィットさせる (選択トレードの価格も確実に含める)
        self._adjust_y_to_visible_range(
            extra_y_values=[trade_row.entry_price, trade_row.exit_price],
        )
        self._refresh_candles_visibility()
        self._canvas.draw_idle()

    # ------------------------------------------------------------------
    # Highlight helpers
    # ------------------------------------------------------------------

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

        span = right_x - left_x
        if span <= 0:
            span = 1.0 / 288.0  # 5 分足 1 本分
        padding = span * 2.5

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

    def _adjust_y_to_visible_range(
        self,
        *,
        extra_y_values: list[float] | None = None,
        padding_ratio: float = 0.12,
    ) -> None:
        """現在の x 範囲に含まれる bars の low/high から price 軸 ylim を再計算する。

        extra_y_values に entry/exit 価格を渡すと、bar 範囲外にはみ出る価格でも
        必ず視野に含めるようにする。
        """
        if self._price_ax is None or not self._x_values_num:
            return
        left, right = self._price_ax.get_xlim()
        lows: list[float] = []
        highs: list[float] = []
        for x, low, high in zip(self._x_values_num, self._lows, self._highs):
            if left <= x <= right:
                lows.append(low)
                highs.append(high)
        if extra_y_values:
            lows.extend(extra_y_values)
            highs.extend(extra_y_values)
        if not lows or not highs:
            return
        min_price = min(lows)
        max_price = max(highs)
        span = max_price - min_price
        if span <= 0:
            span = max(abs(max_price) * 0.0005, 0.01)
        padding = span * padding_ratio
        self._price_ax.set_ylim(min_price - padding, max_price + padding)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw_price_chart(
        self,
        dataset: HistoricalBarDataset,
        trade_rows: list[TradeViewRow],
        state_segments: list[StateSegment],
        title: str,
    ) -> None:
        ax = self._price_ax
        if ax is None:
            return

        if not dataset.rows:
            ax.set_title(f"{title} (no bars)", color=_FG)
            ax.set_ylabel("Price")
            _apply_dark_style(ax)
            return

        self._x_values_num = [mdates.date2num(row.time) for row in dataset.rows]
        self._lows = [row.low for row in dataset.rows]
        self._highs = [row.high for row in dataset.rows]
        self._closes = [row.close for row in dataset.rows]
        self._dataset_start_num = self._x_values_num[0]
        self._dataset_end_num = self._x_values_num[-1]

        if self._show_state_bg:
            self._draw_state_background(ax, state_segments)

        candle_width = self._compute_candle_width(self._x_values_num)

        self._candle_patches = []
        for x_value, row in zip(self._x_values_num, dataset.rows):
            wick = ax.vlines(
                x_value,
                row.low,
                row.high,
                color=_CANDLE_WICK,
                linewidth=0.7,
                zorder=1,
            )
            body_low = min(row.open, row.close)
            body_high = max(row.open, row.close)
            body_height = body_high - body_low
            face_color = _CANDLE_UP if row.close >= row.open else _CANDLE_DOWN

            if body_height == 0:
                body = ax.hlines(
                    row.open,
                    x_value - (candle_width / 2.0),
                    x_value + (candle_width / 2.0),
                    color=face_color,
                    linewidth=1.1,
                    zorder=2,
                )
            else:
                body = Rectangle(
                    (x_value - (candle_width / 2.0), body_low),
                    candle_width,
                    body_height,
                    facecolor=face_color,
                    edgecolor=face_color,
                    linewidth=0.6,
                    zorder=2,
                )
                ax.add_patch(body)
            self._candle_patches.append((wick, body))

        # decimation 用の close line (初期は invisible)
        self._close_line, = ax.plot(
            self._x_values_num,
            self._closes,
            color=_FG,
            linewidth=0.6,
            zorder=2,
            visible=False,
        )

        self._plot_trade_markers(ax=ax, trade_rows=trade_rows)

        min_price = min(self._lows)
        max_price = max(self._highs)
        padding = (max_price - min_price) * 0.03 if max_price > min_price else 0.001

        ax.set_title(title, color=_FG)
        ax.set_ylabel("Price")
        ax.set_xlim(self._x_values_num[0], self._x_values_num[-1])
        ax.set_ylim(min_price - padding, max_price + padding)
        _apply_dark_style(ax)

    def _draw_state_background(
        self, ax, state_segments: list[StateSegment]
    ) -> None:
        for segment in state_segments:
            color = _STATE_BG_COLORS.get(segment.state)
            if color is None:
                continue
            x_start = mdates.date2num(segment.start_time)
            x_end = mdates.date2num(segment.end_time)
            ax.axvspan(
                x_start, x_end, color=color, alpha=_STATE_BG_ALPHA, zorder=0
            )

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

        for point in equity_points:
            x.append(point.exit_time)
            y.append(point.cumulative_pips)

        if x[-1] != dataset.rows[-1].time:
            x.append(dataset.rows[-1].time)
            y.append(y[-1])

        ax.plot(x, y, color=_EQUITY_LINE, linewidth=1.2)
        ax.set_title("Cumulative pips by time", color=_FG)
        ax.set_ylabel("Pips")
        ax.set_xlim(dataset.rows[0].time, dataset.rows[-1].time)
        _apply_dark_style(ax)

    def _compute_candle_width(self, x_values: list[float]) -> float:
        if len(x_values) < 2:
            return 1.0 / 288.0 * 0.72
        deltas = [
            current_value - previous_value
            for previous_value, current_value in zip(x_values[:-1], x_values[1:])
            if current_value > previous_value
        ]
        if not deltas:
            return 1.0 / 288.0 * 0.72
        return min(deltas) * 0.72

    def _plot_trade_markers(
        self, ax, trade_rows: list[TradeViewRow]
    ) -> None:
        if not trade_rows:
            return

        # lane × direction ごとに分類して scatter を 1 回で呼ぶ
        buckets: dict[tuple[str, str], tuple[list[float], list[float]]] = {}
        exits_x: list[float] = []
        exits_y: list[float] = []

        for row in trade_rows:
            lane = (row.lane or "legacy").strip().lower()
            direction = row.position_type.lower()
            key = (lane, direction)
            buckets.setdefault(key, ([], []))
            xs, ys = buckets[key]
            xs.append(mdates.date2num(row.entry_time))
            ys.append(row.entry_price)

            exits_x.append(mdates.date2num(row.exit_time))
            exits_y.append(row.exit_price)

        def _pick_color_marker(key: tuple[str, str]) -> tuple[str, str, str]:
            lane, direction = key
            if lane == "range":
                if direction == "buy":
                    return _MARKER_RANGE_BUY, "^", "range buy"
                return _MARKER_RANGE_SELL, "v", "range sell"
            if lane == "trend":
                if direction == "buy":
                    return _MARKER_TREND_BUY, "^", "trend buy"
                return _MARKER_TREND_SELL, "v", "trend sell"
            if direction == "buy":
                return _MARKER_LEGACY_BUY, "^", "buy"
            return _MARKER_LEGACY_SELL, "v", "sell"

        for key, (xs, ys) in buckets.items():
            color, marker, label = _pick_color_marker(key)
            ax.scatter(
                xs,
                ys,
                marker=marker,
                s=34,
                color=color,
                label=label,
                zorder=3,
                edgecolors="none",
            )

        if exits_x:
            ax.scatter(
                exits_x,
                exits_y,
                marker="o",
                s=18,
                color=_MARKER_EXIT,
                label="exit",
                zorder=3,
                edgecolors="none",
            )

        handles, labels = ax.get_legend_handles_labels()
        if handles:
            unique: dict[str, object] = {}
            for handle, label in zip(handles, labels):
                if label not in unique:
                    unique[label] = handle
            legend = ax.legend(
                unique.values(),
                unique.keys(),
                loc="upper left",
                fontsize=8,
                facecolor=_BG,
                edgecolor=_FG,
                labelcolor=_FG,
            )
            if legend is not None:
                for text in legend.get_texts():
                    text.set_color(_FG)

    # ------------------------------------------------------------------
    # Decimation: ズーム状態に応じて candle / line 表示を切替
    # ------------------------------------------------------------------

    def _refresh_candles_visibility(self) -> None:
        if self._price_ax is None or self._close_line is None:
            return
        if not self._x_values_num:
            return
        left, right = self._price_ax.get_xlim()
        visible_count = sum(1 for x in self._x_values_num if left <= x <= right)
        decimate = visible_count >= CANDLE_DECIMATION_THRESHOLD
        if decimate == self._last_decimation_state:
            return
        self._last_decimation_state = decimate
        # candle patches を visible 切替
        show_candles = not decimate
        for wick, body in self._candle_patches:
            try:
                wick.set_visible(show_candles)
                body.set_visible(show_candles)
            except AttributeError:
                pass
        self._close_line.set_visible(decimate)

    # ------------------------------------------------------------------
    # Layout / sync / mouse handling
    # ------------------------------------------------------------------

    def _apply_default_layout(self) -> None:
        self._figure.subplots_adjust(
            left=0.07,
            right=0.99,
            top=0.94,
            bottom=0.08,
            hspace=0.22,
        )

    def _register_xlim_sync(self) -> None:
        if self._price_ax and self._pips_ax:
            self._price_ax.callbacks.connect(
                "xlim_changed", self._sync_from_price_ax
            )
            self._pips_ax.callbacks.connect(
                "xlim_changed", self._sync_from_pips_ax
            )

    def _sync_from_price_ax(self, ax) -> None:
        del ax
        if self._syncing_limits:
            return
        self._syncing_limits = True
        self._pips_ax.set_xlim(self._price_ax.get_xlim())
        self._syncing_limits = False
        self._refresh_candles_visibility()

    def _sync_from_pips_ax(self, ax) -> None:
        del ax
        if self._syncing_limits:
            return
        self._syncing_limits = True
        self._price_ax.set_xlim(self._pips_ax.get_xlim())
        self._syncing_limits = False
        self._refresh_candles_visibility()

    def _on_button_press(self, event) -> None:
        if event.button == 1 and event.xdata is not None:
            self._is_panning = True
            self._last_pan_xdata = event.xdata

    def _on_button_release(self, event) -> None:
        del event
        self._is_panning = False
        self._last_pan_xdata = None

    def _on_mouse_move(self, event) -> None:
        if not self._is_panning or event.xdata is None:
            return
        delta = self._last_pan_xdata - event.xdata
        left, right = self._price_ax.get_xlim()
        new_left = left + delta
        new_right = right + delta
        if self._dataset_start_num is not None:
            new_left = max(new_left, self._dataset_start_num)
            new_right = max(new_right, self._dataset_start_num + (right - left))
        if self._dataset_end_num is not None:
            new_right = min(new_right, self._dataset_end_num)
            new_left = min(new_left, self._dataset_end_num - (right - left))
        self._price_ax.set_xlim(new_left, new_right)
        self._pips_ax.set_xlim(new_left, new_right)
        self._last_pan_xdata = event.xdata
        self._refresh_candles_visibility()
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
        # scroll zoom では price 軸の y も可視範囲にフィット
        self._adjust_y_to_visible_range()
        self._refresh_candles_visibility()
        self._canvas.draw_idle()
