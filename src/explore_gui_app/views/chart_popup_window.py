# src/explore_gui_app/views/chart_popup_window.py
"""Chart をモードレスで別ウィンドウ表示するためのダイアログ。

- 同時に開けるのは 1 枚(ChartTab 側で管理)
- 起動時は全期間表示、Trades table 選択で特定 trade にズーム&ハイライト
- Reset zoom / State background トグル / Clear highlight などのコントロールを上部に配置
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from backtest.service import BacktestRunArtifacts
from backtest.view_models import TradeViewRow
from explore_gui_app.styles.terminal_dark_theme import apply_terminal_dark_theme
from gui_common.widgets.linked_trade_chart_widget import LinkedTradeChartWidget


class ChartPopupWindow(QDialog):
    """モードレスな trade chart ウィンドウ。"""

    closed = Signal()

    def __init__(
        self,
        *,
        artifacts: BacktestRunArtifacts,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        # モードレス + 最大化/最小化可能 + 閉じる
        self.setWindowModality(Qt.NonModal)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, True)
        self.setWindowFlag(Qt.WindowCloseButtonHint, True)

        strategy = artifacts.config.strategy_name
        csv_name = "(connected)"
        try:
            csv_name = str(artifacts.config.csv_path.name)
        except AttributeError:
            csv_name = str(artifacts.config.csv_path)
        self.setWindowTitle(f"Trade chart - {strategy} - {csv_name}")
        self.resize(1400, 820)

        self._artifacts = artifacts
        self._chart = LinkedTradeChartWidget()

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        root.addLayout(self._build_controls())
        root.addWidget(self._chart, 1)

        apply_terminal_dark_theme(self)

        # 初期描画 (全期間)
        self._chart.plot_dataset_with_equity(
            dataset=artifacts.dataset,
            trade_rows=artifacts.trade_rows,
            equity_points=artifacts.equity_points,
            state_segments=artifacts.backtest_result.state_segments,
            price_title=f"Price with entry / exit  [{strategy}]",
        )

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------

    def _build_controls(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._reset_button = QPushButton("Reset zoom")
        self._reset_button.clicked.connect(self._chart.reset_zoom)

        self._clear_highlight_button = QPushButton("Clear highlight")
        self._clear_highlight_button.clicked.connect(self._chart.clear_highlight)

        self._state_bg_checkbox = QCheckBox("State background")
        self._state_bg_checkbox.setChecked(False)
        self._state_bg_checkbox.toggled.connect(
            self._chart.set_state_background_visible
        )

        self._info_label = QLabel("Scroll to zoom. Drag to pan.")
        self._info_label.setStyleSheet("color: #9aa;")

        row.addWidget(self._reset_button)
        row.addWidget(self._clear_highlight_button)
        row.addSpacing(8)
        row.addWidget(self._state_bg_checkbox)
        row.addStretch(1)
        row.addWidget(self._info_label)
        return row

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def focus_trade(self, trade_row: TradeViewRow) -> None:
        """外部から trade 選択を反映(テーブル→チャート連動)。"""
        self._chart.highlight_trade(trade_row)

    def reset_zoom(self) -> None:
        self._chart.reset_zoom()

    def clear_highlight(self) -> None:
        self._chart.clear_highlight()

    # ------------------------------------------------------------------
    # Close handling
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.closed.emit()
        super().closeEvent(event)
