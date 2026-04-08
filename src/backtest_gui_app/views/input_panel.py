# src/backtest_gui_app/views/input_panel.py
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from backtest.simulator import IntrabarFillPolicy
from backtest_gui_app.widgets.collapsible_section import CollapsibleSection


class InputPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        source_section = self._build_source_section()
        params_section = self._build_parameters_section()
        status_section = self._build_status_section()

        layout.addWidget(source_section)
        layout.addWidget(params_section)
        layout.addWidget(status_section)
        layout.addStretch(1)

    def _build_source_section(self) -> QWidget:
        source_box = QWidget()
        source_layout = QGridLayout(source_box)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.setHorizontalSpacing(8)
        source_layout.setVerticalSpacing(6)

        self.strategy_combo = QComboBox()
        self.refresh_strategy_button = QPushButton("Refresh strategies")

        self.csv_combo = QComboBox()
        self.refresh_csv_button = QPushButton("Refresh CSVs")
        self.browse_csv_button = QPushButton("Browse CSV...")

        source_layout.addWidget(QLabel("Strategy"), 0, 0)
        source_layout.addWidget(self.strategy_combo, 0, 1)
        source_layout.addWidget(self.refresh_strategy_button, 0, 2)

        source_layout.addWidget(QLabel("CSV"), 1, 0)
        source_layout.addWidget(self.csv_combo, 1, 1)
        source_layout.addWidget(self.refresh_csv_button, 1, 2)
        source_layout.addWidget(self.browse_csv_button, 1, 3)

        return CollapsibleSection("Source", source_box, expanded=True)

    def _build_parameters_section(self) -> QWidget:
        params_box = QWidget()
        params_layout = QGridLayout(params_box)
        params_layout.setContentsMargins(0, 0, 0, 0)
        params_layout.setHorizontalSpacing(12)
        params_layout.setVerticalSpacing(6)

        self.symbol_edit = QLineEdit()
        self.timeframe_edit = QLineEdit()
        self.pip_size_edit = QLineEdit()
        self.sl_pips_edit = QLineEdit()
        self.tp_pips_edit = QLineEdit()
        self.initial_balance_edit = QLineEdit()
        self.risk_percent_edit = QLineEdit()

        self.intrabar_policy_combo = QComboBox()
        self.intrabar_policy_combo.addItem(IntrabarFillPolicy.CONSERVATIVE.value)
        self.intrabar_policy_combo.addItem(IntrabarFillPolicy.OPTIMISTIC.value)

        self.close_position_checkbox = QCheckBox(
            "Force-close open position at end of data"
        )
        self.close_position_checkbox.setChecked(True)

        left_form = QFormLayout()
        left_form.setContentsMargins(0, 0, 0, 0)
        left_form.setSpacing(6)
        left_form.addRow("Symbol", self.symbol_edit)
        left_form.addRow("Timeframe", self.timeframe_edit)
        left_form.addRow("Pip size", self.pip_size_edit)
        left_form.addRow("Intrabar policy", self.intrabar_policy_combo)

        middle_form = QFormLayout()
        middle_form.setContentsMargins(0, 0, 0, 0)
        middle_form.setSpacing(6)
        middle_form.addRow("SL pips", self.sl_pips_edit)
        middle_form.addRow("TP pips", self.tp_pips_edit)
        middle_form.addRow("Initial balance", self.initial_balance_edit)
        middle_form.addRow("Risk %", self.risk_percent_edit)

        action_box = QWidget()
        action_layout = QVBoxLayout(action_box)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)

        self.run_button = QPushButton("Run backtest")
        self.run_button.setMinimumHeight(36)

        self.clear_button = QPushButton("Clear result")
        self.export_trades_csv_button = QPushButton("Export Trades CSV")

        action_layout.addWidget(self.close_position_checkbox)
        action_layout.addSpacing(4)
        action_layout.addWidget(self.run_button)
        action_layout.addWidget(self.clear_button)
        action_layout.addWidget(self.export_trades_csv_button)
        action_layout.addStretch(1)

        params_layout.addLayout(left_form, 0, 0)
        params_layout.addLayout(middle_form, 0, 1)
        params_layout.addWidget(action_box, 0, 2)

        return CollapsibleSection("Parameters", params_box, expanded=True)

    def _build_status_section(self) -> QWidget:
        status_box = QWidget()
        status_layout = QVBoxLayout(status_box)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(4)

        self.notes_text = QTextEdit()
        self.notes_text.setReadOnly(True)
        self.notes_text.setMinimumHeight(90)
        self.notes_text.setMaximumHeight(140)
        self.notes_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        status_layout.addWidget(self.notes_text)

        return CollapsibleSection("Status / Notes", status_box, expanded=True)