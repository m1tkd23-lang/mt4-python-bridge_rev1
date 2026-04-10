# src/explore_gui_app/views/input_panel.py
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from backtest.exploration_loop import BOLLINGER_PARAM_VARIATION_RANGES
from backtest_gui_app.services.strategy_params import StrategyParamSpec, get_param_specs
from backtest_gui_app.widgets.collapsible_section import CollapsibleSection

# Initial scope: A single exploration only
_STRATEGY_NAME = "bollinger_range_v4_4"


class _ParamRangeRow:
    """Holds widgets for one parameter's exploration range (min/max/step + enable checkbox)."""

    def __init__(
        self,
        spec: StrategyParamSpec,
        default_range: tuple[float, float, float] | None,
    ) -> None:
        self.spec = spec
        self.enabled = QCheckBox()
        self.enabled.setChecked(default_range is not None)

        is_int = spec.param_type == "int"
        decimals = 0 if is_int else spec.decimals

        if default_range is not None:
            lo, hi, step = default_range
        else:
            lo, hi, step = spec.min_val, spec.max_val, spec.step

        if is_int:
            self.min_spin = QSpinBox()
            self.max_spin = QSpinBox()
            self.step_spin = QSpinBox()
            for sb in (self.min_spin, self.max_spin, self.step_spin):
                sb.setRange(int(spec.min_val), int(spec.max_val))
            self.min_spin.setValue(int(lo))
            self.max_spin.setValue(int(hi))
            self.step_spin.setRange(1, int(spec.max_val))
            self.step_spin.setValue(int(step))
        else:
            self.min_spin = QDoubleSpinBox()
            self.max_spin = QDoubleSpinBox()
            self.step_spin = QDoubleSpinBox()
            for sb in (self.min_spin, self.max_spin, self.step_spin):
                sb.setDecimals(decimals)
                sb.setRange(spec.min_val, spec.max_val)
            self.min_spin.setValue(lo)
            self.max_spin.setValue(hi)
            self.step_spin.setDecimals(decimals)
            self.step_spin.setRange(0.0, spec.max_val)
            self.step_spin.setValue(step)

        self.enabled.toggled.connect(self._on_toggle)
        self._on_toggle(self.enabled.isChecked())

    def _on_toggle(self, checked: bool) -> None:
        for w in (self.min_spin, self.max_spin, self.step_spin):
            w.setEnabled(checked)


class ExploreInputPanel(QWidget):
    """Input panel for bollinger exploration configuration."""

    run_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._param_rows: list[_ParamRangeRow] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        csv_section = self._build_csv_section()
        loop_section = self._build_loop_config_section()
        param_range_section = self._build_param_range_section()

        layout.addWidget(csv_section)
        layout.addWidget(loop_section)
        layout.addWidget(param_range_section)

        # Run / Stop buttons
        btn_row = QHBoxLayout()
        self.run_button = QPushButton("Run Exploration")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        btn_row.addWidget(self.run_button)
        btn_row.addWidget(self.stop_button)
        layout.addLayout(btn_row)

        layout.addStretch(1)

        self.run_button.clicked.connect(self.run_requested.emit)

    # ------------------------------------------------------------------
    # CSV section
    # ------------------------------------------------------------------

    def _build_csv_section(self) -> QWidget:
        box = QWidget()
        form = QFormLayout(box)
        form.setContentsMargins(4, 4, 4, 4)

        # Single CSV (csv_path)
        csv_row = QHBoxLayout()
        self.csv_path_edit = QLineEdit()
        self.csv_path_edit.setPlaceholderText("Single CSV file for primary evaluation")
        browse_csv = QPushButton("Browse...")
        browse_csv.clicked.connect(self._browse_csv)
        csv_row.addWidget(self.csv_path_edit, 1)
        csv_row.addWidget(browse_csv)
        form.addRow("CSV File:", csv_row)

        # CSV directory (csv_dir)
        dir_row = QHBoxLayout()
        self.csv_dir_edit = QLineEdit()
        self.csv_dir_edit.setPlaceholderText("Directory with monthly CSVs (optional, for cross-month eval)")
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
    # Parameter range section
    # ------------------------------------------------------------------

    def _build_param_range_section(self) -> QWidget:
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(4, 4, 4, 4)

        # Headers
        for col, header in enumerate(["Enable", "Parameter", "Min", "Max", "Step"]):
            lbl = QLabel(f"<b>{header}</b>")
            grid.addWidget(lbl, 0, col)

        specs = get_param_specs(_STRATEGY_NAME)
        variation_ranges = BOLLINGER_PARAM_VARIATION_RANGES.get(_STRATEGY_NAME, {})

        for row_idx, spec in enumerate(specs, start=1):
            qualified_key = f"{spec.module_path}::{spec.name}"
            default_range = variation_ranges.get(qualified_key)

            param_row = _ParamRangeRow(spec, default_range)
            self._param_rows.append(param_row)

            grid.addWidget(param_row.enabled, row_idx, 0)
            grid.addWidget(QLabel(spec.label), row_idx, 1)
            grid.addWidget(param_row.min_spin, row_idx, 2)
            grid.addWidget(param_row.max_spin, row_idx, 3)
            grid.addWidget(param_row.step_spin, row_idx, 4)

        return CollapsibleSection("Exploration Parameters (bollinger_range_v4_4)", box, expanded=True)

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
        """Return enabled parameter ranges as {qualified_key: (min, max, step)}."""
        ranges: dict[str, tuple[float, float, float]] = {}
        for row in self._param_rows:
            if not row.enabled.isChecked():
                continue
            qualified_key = f"{row.spec.module_path}::{row.spec.name}"
            lo = row.min_spin.value()
            hi = row.max_spin.value()
            step = row.step_spin.value()
            ranges[qualified_key] = (lo, hi, step)
        return ranges

    def get_strategy_name(self) -> str:
        return _STRATEGY_NAME
