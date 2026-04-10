# src\explore_gui_app\views\parameter_dialog.py
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from backtest.exploration_loop import BOLLINGER_PARAM_VARIATION_RANGES
from backtest_gui_app.services.strategy_params import StrategyParamSpec, get_param_specs


_STRATEGY_NAME = "bollinger_range_v4_4"


@dataclass
class _EditableParamRow:
    spec: StrategyParamSpec
    enabled: QCheckBox
    min_spin: QSpinBox | QDoubleSpinBox
    max_spin: QSpinBox | QDoubleSpinBox
    step_spin: QSpinBox | QDoubleSpinBox


class ParameterDialog(QDialog):
    """Popup dialog for editing exploration parameter ranges."""

    def __init__(
        self,
        parent: QWidget | None = None,
        strategy_name: str = _STRATEGY_NAME,
        current_ranges: dict[str, tuple[float, float, float]] | None = None,
    ) -> None:
        super().__init__(parent)
        self._strategy_name = strategy_name
        self._rows: list[_EditableParamRow] = []

        self.setWindowTitle(f"Exploration Parameters - {strategy_name}")
        self.resize(900, 520)

        root = QVBoxLayout(self)

        desc = QLabel(
            "Configure which parameters are explored and their Min / Max / Step ranges."
        )
        root.addWidget(desc)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)

        grid = QGridLayout(container)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        headers = ["Enable", "Parameter", "Min", "Max", "Step"]
        for col, header in enumerate(headers):
            lbl = QLabel(f"<b>{header}</b>")
            grid.addWidget(lbl, 0, col)

        specs = get_param_specs(strategy_name)
        default_ranges = BOLLINGER_PARAM_VARIATION_RANGES.get(strategy_name, {})
        effective_ranges = current_ranges if current_ranges is not None else default_ranges

        for row_idx, spec in enumerate(specs, start=1):
            qualified_key = f"{spec.module_path}::{spec.name}"
            saved_range = effective_ranges.get(qualified_key)
            row = self._build_row(spec, saved_range, enabled=saved_range is not None)
            self._rows.append(row)

            grid.addWidget(row.enabled, row_idx, 0)
            grid.addWidget(QLabel(spec.label), row_idx, 1)
            grid.addWidget(row.min_spin, row_idx, 2)
            grid.addWidget(row.max_spin, row_idx, 3)
            grid.addWidget(row.step_spin, row_idx, 4)

        btn_row = QHBoxLayout()
        self.reset_button = QPushButton("Reset to Defaults")
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        btn_row.addWidget(self.reset_button)
        btn_row.addStretch(1)
        btn_row.addWidget(self.ok_button)
        btn_row.addWidget(self.cancel_button)
        root.addLayout(btn_row)

        self.reset_button.clicked.connect(self._reset_to_defaults)
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def _build_row(
        self,
        spec: StrategyParamSpec,
        saved_range: tuple[float, float, float] | None,
        *,
        enabled: bool,
    ) -> _EditableParamRow:
        is_int = spec.param_type == "int"
        decimals = 0 if is_int else spec.decimals

        if saved_range is not None:
            lo, hi, step = saved_range
        else:
            lo, hi, step = spec.min_val, spec.max_val, spec.step

        enabled_check = QCheckBox()
        enabled_check.setChecked(enabled)

        if is_int:
            min_spin = QSpinBox()
            max_spin = QSpinBox()
            step_spin = QSpinBox()

            for sb in (min_spin, max_spin):
                sb.setRange(int(spec.min_val), int(spec.max_val))
            min_spin.setValue(int(lo))
            max_spin.setValue(int(hi))

            step_spin.setRange(1, max(1, int(spec.max_val)))
            step_spin.setValue(max(1, int(step)))
        else:
            min_spin = QDoubleSpinBox()
            max_spin = QDoubleSpinBox()
            step_spin = QDoubleSpinBox()

            for sb in (min_spin, max_spin, step_spin):
                sb.setDecimals(decimals)

            min_spin.setRange(spec.min_val, spec.max_val)
            max_spin.setRange(spec.min_val, spec.max_val)
            step_spin.setRange(10 ** (-decimals), spec.max_val)

            min_spin.setValue(float(lo))
            max_spin.setValue(float(hi))
            step_spin.setValue(max(10 ** (-decimals), float(step)))

        row = _EditableParamRow(
            spec=spec,
            enabled=enabled_check,
            min_spin=min_spin,
            max_spin=max_spin,
            step_spin=step_spin,
        )

        enabled_check.toggled.connect(
            lambda checked, r=row: self._set_row_enabled(r, checked)
        )
        self._set_row_enabled(row, enabled)
        return row

    def _set_row_enabled(self, row: _EditableParamRow, enabled: bool) -> None:
        row.min_spin.setEnabled(enabled)
        row.max_spin.setEnabled(enabled)
        row.step_spin.setEnabled(enabled)

    def _reset_to_defaults(self) -> None:
        default_ranges = BOLLINGER_PARAM_VARIATION_RANGES.get(self._strategy_name, {})
        for row in self._rows:
            qualified_key = f"{row.spec.module_path}::{row.spec.name}"
            default_range = default_ranges.get(qualified_key)
            row.enabled.setChecked(default_range is not None)

            if default_range is None:
                lo, hi, step = row.spec.min_val, row.spec.max_val, row.spec.step
            else:
                lo, hi, step = default_range

            row.min_spin.setValue(lo)
            row.max_spin.setValue(hi)
            row.step_spin.setValue(step)

    def get_ranges(self) -> dict[str, tuple[float, float, float]]:
        ranges: dict[str, tuple[float, float, float]] = {}
        for row in self._rows:
            if not row.enabled.isChecked():
                continue

            lo = float(row.min_spin.value())
            hi = float(row.max_spin.value())
            step = float(row.step_spin.value())

            if lo > hi:
                lo, hi = hi, lo

            qualified_key = f"{row.spec.module_path}::{row.spec.name}"
            ranges[qualified_key] = (lo, hi, step)

        return ranges