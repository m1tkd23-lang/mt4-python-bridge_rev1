# src\explore_gui_app\views\input_panel.py
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from backtest.exploration_loop import BOLLINGER_PARAM_VARIATION_RANGES
from backtest_gui_app.widgets.collapsible_section import CollapsibleSection
from explore_gui_app.views.parameter_dialog import ParameterDialog

_AVAILABLE_STRATEGIES = [
    "bollinger_range_v4_4",
    "bollinger_trend_B",
]


class ExploreInputPanel(QWidget):
    """Input panel for bollinger exploration configuration."""

    run_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._param_ranges: dict[str, tuple[float, float, float]] = dict(
            BOLLINGER_PARAM_VARIATION_RANGES.get(_AVAILABLE_STRATEGIES[0], {})
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        strategy_section = self._build_strategy_section()
        csv_section = self._build_csv_section()
        loop_section = self._build_loop_config_section()
        param_section = self._build_param_section()

        layout.addWidget(strategy_section)
        layout.addWidget(csv_section)
        layout.addWidget(loop_section)
        layout.addWidget(param_section)

        btn_row = QHBoxLayout()
        self.run_button = QPushButton("Run Exploration")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        btn_row.addWidget(self.run_button)
        btn_row.addWidget(self.stop_button)
        layout.addLayout(btn_row)

        layout.addStretch(1)

        self.run_button.clicked.connect(self.run_requested.emit)
        self._refresh_param_summary()

    # ------------------------------------------------------------------
    # Strategy section
    # ------------------------------------------------------------------

    def _build_strategy_section(self) -> QWidget:
        box = QWidget()
        form = QFormLayout(box)
        form.setContentsMargins(4, 4, 4, 4)

        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(_AVAILABLE_STRATEGIES)
        self.strategy_combo.currentTextChanged.connect(self._on_strategy_changed)
        form.addRow("Strategy:", self.strategy_combo)

        return CollapsibleSection("Strategy Selection", box, expanded=True)

    def _on_strategy_changed(self, strategy_name: str) -> None:
        self._param_ranges = dict(
            BOLLINGER_PARAM_VARIATION_RANGES.get(strategy_name, {})
        )
        self._param_section.setTitle(f"Exploration Parameters ({strategy_name})")
        self._refresh_param_summary()

    # ------------------------------------------------------------------
    # CSV section
    # ------------------------------------------------------------------

    def _build_csv_section(self) -> QWidget:
        box = QWidget()
        form = QFormLayout(box)
        form.setContentsMargins(4, 4, 4, 4)

        csv_row = QHBoxLayout()
        self.csv_path_edit = QLineEdit()
        self.csv_path_edit.setPlaceholderText("Single CSV file for primary evaluation")
        browse_csv = QPushButton("Browse...")
        browse_csv.clicked.connect(self._browse_csv)
        csv_row.addWidget(self.csv_path_edit, 1)
        csv_row.addWidget(browse_csv)
        form.addRow("CSV File:", csv_row)

        dir_row = QHBoxLayout()
        self.csv_dir_edit = QLineEdit()
        self.csv_dir_edit.setPlaceholderText(
            "Directory with monthly CSVs (optional, for cross-month eval)"
        )
        browse_dir = QPushButton("Browse...")
        browse_dir.clicked.connect(self._browse_csv_dir)
        dir_row.addWidget(self.csv_dir_edit, 1)
        dir_row.addWidget(browse_dir)
        form.addRow("CSV Dir:", dir_row)

        return CollapsibleSection("Data Source", box, expanded=True)

    def _browse_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV file", "", "CSV Files (*.csv)"
        )
        if path:
            self.csv_path_edit.setText(path)

    def _browse_csv_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select CSV directory")
        if path:
            self.csv_dir_edit.setText(path)

    # ------------------------------------------------------------------
    # Loop config section
    # ------------------------------------------------------------------

    def _build_loop_config_section(self) -> QWidget:
        box = QWidget()
        form = QFormLayout(box)
        form.setContentsMargins(4, 4, 4, 4)

        self.max_iterations_spin = QSpinBox()
        self.max_iterations_spin.setRange(1, 1000)
        self.max_iterations_spin.setValue(10)
        form.addRow("Max Iterations:", self.max_iterations_spin)

        self.max_improve_retries_spin = QSpinBox()
        self.max_improve_retries_spin.setRange(0, 100)
        self.max_improve_retries_spin.setValue(1)
        form.addRow("Improve Retries:", self.max_improve_retries_spin)

        self.max_param_variations_spin = QSpinBox()
        self.max_param_variations_spin.setRange(1, 100)
        self.max_param_variations_spin.setValue(3)
        form.addRow("Param Variations:", self.max_param_variations_spin)

        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 999999)
        self.seed_spin.setValue(42)
        form.addRow("Random Seed:", self.seed_spin)

        return CollapsibleSection("Loop Config", box, expanded=True)

    # ------------------------------------------------------------------
    # Parameter section
    # ------------------------------------------------------------------

    def _build_param_section(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        self.param_summary_label = QLabel()
        self.edit_params_button = QPushButton("Edit Parameters...")
        self.edit_params_button.clicked.connect(self._open_param_dialog)
        top_row.addWidget(self.param_summary_label, 1)
        top_row.addWidget(self.edit_params_button)
        layout.addLayout(top_row)

        self.param_detail_label = QLabel()
        self.param_detail_label.setWordWrap(True)
        layout.addWidget(self.param_detail_label)

        strategy_name = self.strategy_combo.currentText()
        self._param_section = CollapsibleSection(
            f"Exploration Parameters ({strategy_name})",
            box,
            expanded=True,
        )
        return self._param_section

    def _open_param_dialog(self) -> None:
        dialog = ParameterDialog(
            parent=self,
            strategy_name=self.strategy_combo.currentText(),
            current_ranges=self._param_ranges,
        )
        if dialog.exec():
            self._param_ranges = dialog.get_ranges()
            self._refresh_param_summary()

    def _refresh_param_summary(self) -> None:
        count = len(self._param_ranges)
        self.param_summary_label.setText(f"{count} parameter(s) enabled")

        if not self._param_ranges:
            self.param_detail_label.setText("No exploration parameters enabled.")
            return

        lines: list[str] = []
        for qualified_key, (lo, hi, step) in self._param_ranges.items():
            name = qualified_key.split("::", 1)[1]
            lines.append(f"{name}: {lo} .. {hi} (step {step})")

        self.param_detail_label.setText("\n".join(lines))

    # ------------------------------------------------------------------
    # Public getters
    # ------------------------------------------------------------------

    def get_csv_path(self) -> str:
        return self.csv_path_edit.text().strip()

    def get_csv_dir(self) -> str | None:
        text = self.csv_dir_edit.text().strip()
        return text if text else None

    def get_max_iterations(self) -> int:
        return self.max_iterations_spin.value()

    def get_max_improve_retries(self) -> int:
        return self.max_improve_retries_spin.value()

    def get_max_param_variations(self) -> int:
        return self.max_param_variations_spin.value()

    def get_random_seed(self) -> int:
        return self.seed_spin.value()

    def get_param_override_ranges(self) -> dict[str, tuple[float, float, float]]:
        return dict(self._param_ranges)

    def get_strategy_name(self) -> str:
        return self.strategy_combo.currentText()