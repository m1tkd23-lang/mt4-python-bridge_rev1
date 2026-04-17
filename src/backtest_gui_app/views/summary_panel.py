# src\backtest_gui_app\views\summary_panel.py
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui_common.widgets.collapsible_section import CollapsibleSection
from gui_common.widgets.mean_reversion_summary_widget import (
    MeanReversionSummaryWidget,
)


# Headline KPIs displayed as large cards at the top of the panel.
_KPI_CARDS: list[tuple[str, str]] = [
    ("total_pips", "Total pips"),
    ("win_rate_percent", "Win rate"),
    ("profit_factor", "Profit factor"),
    ("max_drawdown_pips", "Max DD pips"),
    ("trades", "Trades"),
    ("verdict", "Verdict"),
]

# Secondary fields displayed as compact label/value rows below the KPI strip.
_DETAIL_FIELDS_LEFT: list[tuple[str, str]] = [
    ("strategy_name", "Strategy"),
    ("symbol", "Symbol"),
    ("timeframe", "Timeframe"),
    ("intrabar_fill_policy", "Intrabar policy"),
    ("wins", "Wins"),
    ("losses", "Losses"),
    ("average_pips", "Avg pips"),
    ("average_win_pips", "Avg win pips"),
    ("average_loss_pips", "Avg loss pips"),
    ("avg_mfe_mae_ratio", "Avg MFE/MAE"),
    ("max_consecutive_wins", "Max consec wins"),
    ("max_consecutive_losses", "Max consec losses"),
]

_DETAIL_FIELDS_RIGHT: list[tuple[str, str]] = [
    ("initial_balance", "Initial balance"),
    ("risk_percent", "Risk %"),
    ("lot_size", "Calculated lot"),
    ("money_per_pip", "Yen / pip"),
    ("final_balance", "Final balance"),
    ("total_profit_amount", "Total profit"),
    ("return_rate_percent", "Return rate"),
    ("max_drawdown_amount", "Max DD amount"),
    ("final_open_position_type", "Final open position"),
]


class SummaryPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.summary_labels: dict[str, QLabel] = {}

        kpi_strip = self._build_kpi_strip()
        details_section = self._build_details_section()
        mean_reversion_section = self._build_mean_reversion_section()
        reasons_section = self._build_reasons_section()

        layout.addWidget(kpi_strip)
        layout.addWidget(details_section)
        layout.addWidget(mean_reversion_section)
        layout.addWidget(reasons_section)
        layout.addStretch(1)

    def _build_kpi_strip(self) -> QWidget:
        strip = QWidget()
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(8)

        for key, title in _KPI_CARDS:
            card = self._build_kpi_card(key, title)
            strip_layout.addWidget(card, 1)

        return strip

    def _build_kpi_card(self, key: str, title: str) -> QFrame:
        card = QFrame()
        card.setProperty("role", "kpi-card")
        card.setFrameShape(QFrame.StyledPanel)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(2)

        title_label = QLabel(title.upper())
        title_label.setProperty("role", "kpi-title")

        value_label = QLabel("-")
        value_label.setProperty("role", "kpi-value")
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.summary_labels[key] = value_label

        card_layout.addWidget(title_label)
        card_layout.addWidget(value_label)
        return card

    def _build_details_section(self) -> QWidget:
        details_box = QWidget()
        grid = QGridLayout(details_box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(3)

        self._populate_detail_grid(grid, _DETAIL_FIELDS_LEFT, col_offset=0)
        self._populate_detail_grid(grid, _DETAIL_FIELDS_RIGHT, col_offset=2)

        return CollapsibleSection("Details", details_box, expanded=True)

    def _populate_detail_grid(
        self,
        grid: QGridLayout,
        fields: list[tuple[str, str]],
        *,
        col_offset: int,
    ) -> None:
        for row, (key, label_text) in enumerate(fields):
            label = QLabel(label_text)
            label.setProperty("role", "kpi-subvalue")
            value_label = QLabel("-")
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.summary_labels[key] = value_label
            grid.addWidget(label, row, col_offset)
            grid.addWidget(value_label, row, col_offset + 1)

    def _build_mean_reversion_section(self) -> QWidget:
        self.mean_reversion_widget = MeanReversionSummaryWidget()
        return CollapsibleSection(
            "Mean reversion (range lane)",
            self.mean_reversion_widget,
            expanded=False,
        )

    def _build_reasons_section(self) -> QWidget:
        reasons_box = QWidget()
        reasons_layout = QVBoxLayout(reasons_box)
        reasons_layout.setContentsMargins(0, 0, 0, 0)
        reasons_layout.setSpacing(4)

        self.reasons_text = QTextEdit()
        self.reasons_text.setReadOnly(True)
        self.reasons_text.setMinimumHeight(70)
        self.reasons_text.setMaximumHeight(120)
        self.reasons_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        reasons_layout.addWidget(self.reasons_text)

        return CollapsibleSection("Verdict reasons", reasons_box, expanded=True)
