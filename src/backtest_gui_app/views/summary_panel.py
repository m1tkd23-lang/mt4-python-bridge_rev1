# src\backtest_gui_app\views\summary_panel.py
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QSizePolicy, QTextEdit, QVBoxLayout, QWidget

from backtest_gui_app.widgets.collapsible_section import CollapsibleSection


class SummaryPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.summary_labels: dict[str, QLabel] = {}

        summary_section = self._build_summary_section()
        reasons_section = self._build_reasons_section()

        layout.addWidget(summary_section)
        layout.addWidget(reasons_section)
        layout.addStretch(1)

    def _build_summary_section(self) -> QWidget:
        summary_content = QWidget()
        summary_grid = QGridLayout(summary_content)
        summary_grid.setContentsMargins(0, 0, 0, 0)
        summary_grid.setHorizontalSpacing(16)
        summary_grid.setVerticalSpacing(4)

        summary_fields = [
            ("strategy_name", "Strategy"),
            ("symbol", "Symbol"),
            ("timeframe", "Timeframe"),
            ("intrabar_fill_policy", "Intrabar policy"),
            ("trades", "Trades"),
            ("wins", "Wins"),
            ("losses", "Losses"),
            ("win_rate_percent", "Win rate"),
            ("total_pips", "Total pips"),
            ("average_pips", "Average pips"),
            ("average_win_pips", "Average win pips"),
            ("average_loss_pips", "Average loss pips"),
            ("profit_factor", "Profit factor"),
            ("max_drawdown_pips", "Max DD pips"),
            ("initial_balance", "Initial balance"),
            ("risk_percent", "Risk %"),
            ("lot_size", "Calculated lot"),
            ("money_per_pip", "Calculated yen/pip"),
            ("final_balance", "Final balance"),
            ("total_profit_amount", "Total profit amount"),
            ("return_rate_percent", "Converted return rate"),
            ("max_drawdown_amount", "Converted max DD"),
            ("max_consecutive_wins", "Max consecutive wins"),
            ("max_consecutive_losses", "Max consecutive losses"),
            ("verdict", "Verdict"),
            ("final_open_position_type", "Final open position"),
        ]

        midpoint = (len(summary_fields) + 1) // 2
        left_fields = summary_fields[:midpoint]
        right_fields = summary_fields[midpoint:]

        for row, (key, label_text) in enumerate(left_fields):
            label = QLabel(label_text)
            value_label = QLabel("-")
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.summary_labels[key] = value_label
            summary_grid.addWidget(label, row, 0)
            summary_grid.addWidget(value_label, row, 1)

        for row, (key, label_text) in enumerate(right_fields):
            label = QLabel(label_text)
            value_label = QLabel("-")
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.summary_labels[key] = value_label
            summary_grid.addWidget(label, row, 2)
            summary_grid.addWidget(value_label, row, 3)

        return CollapsibleSection("Summary", summary_content, expanded=True)

    def _build_reasons_section(self) -> QWidget:
        reasons_box = QWidget()
        reasons_layout = QVBoxLayout(reasons_box)
        reasons_layout.setContentsMargins(0, 0, 0, 0)
        reasons_layout.setSpacing(4)

        self.reasons_text = QTextEdit()
        self.reasons_text.setReadOnly(True)
        self.reasons_text.setMinimumHeight(80)
        self.reasons_text.setMaximumHeight(140)
        self.reasons_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        reasons_layout.addWidget(self.reasons_text)

        return CollapsibleSection("Verdict reasons", reasons_box, expanded=True)