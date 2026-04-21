# src/explore_gui_app/views/chart_tab.py
"""Chart タブ: BT 単発の結果を Trades table で表示し、チャートをポップアップで起動する。

設計(合意事項):
- タブ内には実チャートを持たない。Open Chart Window ボタン+ Trades table のみ。
- Chart はモードレスダイアログ (ChartPopupWindow) で別ウィンドウ表示。
- 同時に開けるのは 1 枚。2 枚目を開こうとすると既存を閉じて新規作成。
- Trades table は gui_common の TradesTableWidget を使用 (コア 11 列 + 詳細折り畳み)。
- Trade 選択 → 開いているポップアップに連動してハイライト&ズーム。
  ポップアップが開いていない場合は自動で開く。
- 使うデータは BT 単発タブ (BacktestPanel) で直前に実行した BacktestRunArtifacts。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from backtest.service import BacktestRunArtifacts
from backtest.view_models import TradeViewRow
from explore_gui_app.views.chart_popup_window import ChartPopupWindow
from gui_common.widgets.trades_table_widget import TradesTableWidget


class ChartTab(QWidget):
    """BT 結果の Trades + Chart コントロールタブ。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._artifacts: BacktestRunArtifacts | None = None
        self._popup: ChartPopupWindow | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_table_section(), 1)

    # ------------------------------------------------------------------
    # UI builders
    # ------------------------------------------------------------------

    def _build_header(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 実行元情報 (strategy / csv / trades 数)
        info_form = QFormLayout()
        info_form.setContentsMargins(0, 0, 0, 0)
        info_form.setSpacing(4)

        self._strategy_label = QLabel("-")
        self._strategy_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._csv_label = QLabel("-")
        self._csv_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._trades_label = QLabel("-")

        info_form.addRow("Strategy:", self._strategy_label)
        info_form.addRow("CSV source:", self._csv_label)
        info_form.addRow("Total trades:", self._trades_label)
        layout.addLayout(info_form)

        # コントロールボタン
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)

        self._open_chart_button = QPushButton("Open chart window")
        self._open_chart_button.setEnabled(False)
        self._open_chart_button.clicked.connect(self._open_chart_popup)

        self._close_chart_button = QPushButton("Close chart window")
        self._close_chart_button.setEnabled(False)
        self._close_chart_button.clicked.connect(self._close_chart_popup)

        hint = QLabel(
            "Trade 行を選択すると、チャートウィンドウが自動的に開いて該当トレードへズームします。"
        )
        hint.setStyleSheet("font-size: 11px; color: #9aa;")
        hint.setWordWrap(True)

        btn_row.addWidget(self._open_chart_button)
        btn_row.addWidget(self._close_chart_button)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        layout.addWidget(hint)
        return box

    def _build_table_section(self) -> QWidget:
        self._trades_widget = TradesTableWidget()
        self._trades_widget.trade_selected.connect(self._on_trade_selected)
        return self._trades_widget

    # ------------------------------------------------------------------
    # Public API (called from main_window)
    # ------------------------------------------------------------------

    def set_artifacts(self, artifacts: BacktestRunArtifacts | None) -> None:
        """BT 完了後に呼ばれる。None はクリア。"""
        self._artifacts = artifacts
        if artifacts is None:
            self._strategy_label.setText("-")
            self._csv_label.setText("-")
            self._trades_label.setText("-")
            self._trades_widget.clear()
            self._open_chart_button.setEnabled(False)
            self._close_chart_popup()
            return

        self._strategy_label.setText(artifacts.config.strategy_name)
        self._csv_label.setText(str(artifacts.config.csv_path))
        self._trades_label.setText(str(len(artifacts.trade_rows)))
        self._trades_widget.set_rows(artifacts.trade_rows)
        self._open_chart_button.setEnabled(True)

        # 既に開いているポップアップがあれば、新しい artifacts で再生成
        if self._popup is not None:
            self._close_chart_popup()

    # ------------------------------------------------------------------
    # Popup management (同時 1 枚ガード)
    # ------------------------------------------------------------------

    def _open_chart_popup(self) -> ChartPopupWindow | None:
        if self._artifacts is None:
            return None
        if self._popup is not None:
            # 既に開いている -> 前面へ
            self._popup.raise_()
            self._popup.activateWindow()
            return self._popup

        self._popup = ChartPopupWindow(artifacts=self._artifacts, parent=self)
        self._popup.closed.connect(self._on_popup_closed)
        self._popup.show()
        self._close_chart_button.setEnabled(True)
        return self._popup

    def _close_chart_popup(self) -> None:
        if self._popup is None:
            return
        popup = self._popup
        self._popup = None
        self._close_chart_button.setEnabled(False)
        try:
            popup.close()
        except RuntimeError:
            pass

    def _on_popup_closed(self) -> None:
        self._popup = None
        self._close_chart_button.setEnabled(False)

    # ------------------------------------------------------------------
    # Table -> chart 連動
    # ------------------------------------------------------------------

    def _on_trade_selected(self, row: TradeViewRow) -> None:
        popup = self._popup if self._popup is not None else self._open_chart_popup()
        if popup is None:
            return
        popup.focus_trade(row)
