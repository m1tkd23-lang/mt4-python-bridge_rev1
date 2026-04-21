# src/gui_common/widgets/trades_table_widget.py
"""Trades table widget: コア列常時表示 + 詳細列折り畳み + フィルター + 色分け。

設計意図:
- backtest_gui_app の 33 列表を「コア 11 + 詳細 22」に整理
- pips 列は正負で text color を緑/赤、崩壊級(pips <= -20)は背景も赤
- Lane / Position / Pips フィルタで in-memory 絞り込み
- 詳細列は default 非表示、"Show details" チェックボックスで一括 show/hide
- 行選択で trade_selected(TradeViewRow) シグナルを emit (chart 連動用)
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from backtest.view_models import TradeViewRow


# ---------------------------------------------------------------------------
# 列定義
# ---------------------------------------------------------------------------
# 各エントリ: (label, category) — category は "core" か "detail"
# コアは常時表示、詳細は default hidden
_COLUMNS: list[tuple[str, str]] = [
    ("No", "core"),
    ("Lane", "core"),
    ("Type", "core"),
    ("Entry time", "core"),
    ("Exit time", "core"),
    ("Entry", "core"),
    ("Exit", "core"),
    ("Pips", "core"),
    ("Cum pips", "core"),
    ("Exit reason", "core"),
    ("Exit subtype", "core"),
    # ---- 以下 detail ----
    ("Entry subtype", "detail"),
    ("Profit amount", "detail"),
    ("Balance after", "detail"),
    ("Entry state", "detail"),
    ("Exit state", "detail"),
    ("Entry detected state", "detail"),
    ("Entry candidate state", "detail"),
    ("Entry event", "detail"),
    ("Entry state age", "detail"),
    ("Entry candidate age", "detail"),
    ("Entry range score", "detail"),
    ("Entry trans up score", "detail"),
    ("Entry trans down score", "detail"),
    ("Entry trend up score", "detail"),
    ("Entry trend down score", "detail"),
    ("Exit detected state", "detail"),
    ("Exit candidate state", "detail"),
    ("Exit event", "detail"),
    ("Exit state age", "detail"),
    ("Exit candidate age", "detail"),
    ("Entry signal reason", "detail"),
    ("Exit signal reason", "detail"),
]

# 色
_WIN_COLOR = QColor("#7BD88F")
_LOSS_COLOR = QColor("#FF7B72")
_CRASH_BG_COLOR = QColor(80, 30, 30)  # 暗赤背景(崩壊 pips <= -20)
_FLAT_COLOR = QColor("#dcdcdc")

_CRASH_PIPS_THRESHOLD = -20.0


class TradesTableWidget(QWidget):
    """Trades 表示 widget: フィルター + table + 詳細 toggle。"""

    trade_selected = Signal(object)  # TradeViewRow

    # フィルター選択肢
    _LANE_ALL = "All lanes"
    _LANE_RANGE = "range"
    _LANE_TREND = "trend"
    _LANE_LEGACY = "legacy"

    _POS_ALL = "All"
    _POS_BUY = "buy"
    _POS_SELL = "sell"

    _PIPS_ALL = "All trades"
    _PIPS_WIN = "Win only (pips > 0)"
    _PIPS_LOSS = "Loss only (pips < 0)"
    _PIPS_CRASH = f"Crash only (pips <= {int(_CRASH_PIPS_THRESHOLD)})"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._all_rows: list[TradeViewRow] = []
        self._filtered_rows: list[TradeViewRow] = []  # 表示順に並ぶ

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._build_filter_bar())
        layout.addWidget(self._build_table(), 1)

    # ------------------------------------------------------------------
    # UI builders
    # ------------------------------------------------------------------

    def _build_filter_bar(self) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(4, 2, 4, 2)
        row.setSpacing(8)

        self.lane_combo = QComboBox()
        self.lane_combo.addItems(
            [self._LANE_ALL, self._LANE_RANGE, self._LANE_TREND, self._LANE_LEGACY]
        )
        self.lane_combo.currentTextChanged.connect(self._apply_filters)

        self.position_combo = QComboBox()
        self.position_combo.addItems([self._POS_ALL, self._POS_BUY, self._POS_SELL])
        self.position_combo.currentTextChanged.connect(self._apply_filters)

        self.pips_combo = QComboBox()
        self.pips_combo.addItems(
            [self._PIPS_ALL, self._PIPS_WIN, self._PIPS_LOSS, self._PIPS_CRASH]
        )
        self.pips_combo.currentTextChanged.connect(self._apply_filters)

        self.details_checkbox = QCheckBox("Show details")
        self.details_checkbox.setChecked(False)
        self.details_checkbox.toggled.connect(self._apply_detail_visibility)

        self.count_label = QLabel("0 / 0 trades")
        self.count_label.setStyleSheet("color: #9aa;")

        row.addWidget(QLabel("Lane:"))
        row.addWidget(self.lane_combo)
        row.addSpacing(8)
        row.addWidget(QLabel("Position:"))
        row.addWidget(self.position_combo)
        row.addSpacing(8)
        row.addWidget(QLabel("Result:"))
        row.addWidget(self.pips_combo)
        row.addSpacing(16)
        row.addWidget(self.details_checkbox)
        row.addStretch(1)
        row.addWidget(self.count_label)
        return box

    def _build_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(_COLUMNS))
        table.setHorizontalHeaderLabels([label for label, _ in _COLUMNS])
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)

        table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table = table
        self._apply_detail_visibility(False)
        return table

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_rows(self, rows: list[TradeViewRow]) -> None:
        self._all_rows = list(rows)
        self._apply_filters()

    def clear(self) -> None:
        self._all_rows = []
        self._filtered_rows = []
        self.table.setRowCount(0)
        self._update_count_label()

    def selected_row(self) -> TradeViewRow | None:
        current = self.table.currentRow()
        if current < 0 or current >= len(self._filtered_rows):
            return None
        return self._filtered_rows[current]

    def select_row_by_trade_no(self, trade_no: int) -> None:
        """trade_no を持つ行を選択。フィルターで非表示ならスキップ。"""
        for idx, row in enumerate(self._filtered_rows):
            if row.trade_no == trade_no:
                self.table.selectRow(idx)
                return

    # ------------------------------------------------------------------
    # Filter / rendering
    # ------------------------------------------------------------------

    def _apply_filters(self) -> None:
        lane = self.lane_combo.currentText()
        position = self.position_combo.currentText()
        pips_mode = self.pips_combo.currentText()

        def _accept(row: TradeViewRow) -> bool:
            row_lane = (row.lane or "legacy").strip().lower()
            if lane != self._LANE_ALL and row_lane != lane:
                return False
            row_pos = (row.position_type or "").strip().lower()
            if position != self._POS_ALL and row_pos != position:
                return False
            if pips_mode == self._PIPS_WIN and row.pips <= 0:
                return False
            if pips_mode == self._PIPS_LOSS and row.pips >= 0:
                return False
            if pips_mode == self._PIPS_CRASH and row.pips > _CRASH_PIPS_THRESHOLD:
                return False
            return True

        self._filtered_rows = [row for row in self._all_rows if _accept(row)]
        self._render_rows()
        self._update_count_label()

    def _render_rows(self) -> None:
        self.table.setUpdatesEnabled(False)
        try:
            self.table.clearContents()
            self.table.setRowCount(len(self._filtered_rows))
            for row_index, row in enumerate(self._filtered_rows):
                values = self._build_row_values(row)
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setTextAlignment(Qt.AlignCenter)

                    label = _COLUMNS[col][0]
                    if label == "Pips":
                        self._apply_pips_style(item, row.pips)
                    elif label == "Cum pips":
                        self._apply_pips_text_color(item, row.pips)
                    elif label in {"Entry signal reason", "Exit signal reason", "Exit reason"}:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                        if value:
                            item.setToolTip(value)
                    self.table.setItem(row_index, col, item)
        finally:
            self.table.setUpdatesEnabled(True)
            self.table.viewport().update()

    def _apply_pips_style(self, item: QTableWidgetItem, pips: float) -> None:
        self._apply_pips_text_color(item, pips)
        if pips <= _CRASH_PIPS_THRESHOLD:
            item.setBackground(QBrush(_CRASH_BG_COLOR))

    @staticmethod
    def _apply_pips_text_color(item: QTableWidgetItem, pips: float) -> None:
        if pips > 0:
            item.setForeground(QBrush(_WIN_COLOR))
        elif pips < 0:
            item.setForeground(QBrush(_LOSS_COLOR))
        else:
            item.setForeground(QBrush(_FLAT_COLOR))

    def _build_row_values(self, row: TradeViewRow) -> list[str]:
        """_COLUMNS と同順の表示値。"""
        return [
            str(row.trade_no),
            row.lane or "-",
            row.position_type or "-",
            row.entry_time.strftime("%Y-%m-%d %H:%M:%S"),
            row.exit_time.strftime("%Y-%m-%d %H:%M:%S"),
            f"{row.entry_price:.5f}",
            f"{row.exit_price:.5f}",
            f"{row.pips:.2f}",
            f"{row.cumulative_pips:.2f}",
            row.exit_reason or "-",
            _safe_str(getattr(row, "exit_subtype", None)),
            _safe_str(row.entry_subtype),
            f"{row.trade_profit_amount:,.2f}",
            f"{row.balance_after_trade:,.2f}",
            _safe_str(row.entry_market_state),
            _safe_str(row.exit_market_state),
            _safe_str(row.entry_detected_market_state),
            _safe_str(row.entry_candidate_market_state),
            _safe_str(row.entry_state_transition_event),
            _safe_int(row.entry_state_age),
            _safe_int(row.entry_candidate_age),
            _safe_float(row.entry_range_score, digits=0),
            _safe_float(row.entry_transition_up_score, digits=0),
            _safe_float(row.entry_transition_down_score, digits=0),
            _safe_float(row.entry_trend_up_score, digits=0),
            _safe_float(row.entry_trend_down_score, digits=0),
            _safe_str(row.exit_detected_market_state),
            _safe_str(row.exit_candidate_market_state),
            _safe_str(row.exit_state_transition_event),
            _safe_int(row.exit_state_age),
            _safe_int(row.exit_candidate_age),
            _shorten(_safe_str(row.entry_signal_reason), 120),
            _shorten(_safe_str(row.exit_signal_reason), 120),
        ]

    def _apply_detail_visibility(self, show: bool) -> None:
        for col, (_label, category) in enumerate(_COLUMNS):
            if category == "detail":
                self.table.setColumnHidden(col, not show)

    def _update_count_label(self) -> None:
        total = len(self._all_rows)
        shown = len(self._filtered_rows)
        self.count_label.setText(f"{shown} / {total} trades")

    def _on_selection_changed(self) -> None:
        row = self.selected_row()
        if row is not None:
            self.trade_selected.emit(row)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_str(value) -> str:
    if value is None or value == "":
        return "-"
    return str(value)


def _safe_int(value) -> str:
    if value is None:
        return "-"
    return str(value)


def _safe_float(value, *, digits: int) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "-"


def _shorten(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
