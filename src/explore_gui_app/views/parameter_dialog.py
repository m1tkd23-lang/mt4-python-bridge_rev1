# src\explore_gui_app\views\parameter_dialog.py
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QDoubleValidator, QIntValidator, QPainter, QPen, QPolygon
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStyle,
    QStyleOptionButton,
    QVBoxLayout,
    QWidget,
)

from backtest.exploration_loop import BOLLINGER_PARAM_VARIATION_RANGES
from gui_common.strategy_params import StrategyParamSpec, get_param_specs


class ArrowButton(QPushButton):
    """SpinBox風の矢印ボタン。"""

    def __init__(
        self,
        direction: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("", parent)

        if direction not in {"up", "down"}:
            raise ValueError("direction must be 'up' or 'down'")

        self._direction = direction
        self._triangle_offset_y = -2

        self.setCursor(Qt.PointingHandCursor)

        self.setStyleSheet(
            """
            QPushButton {
                padding: 0px;
                margin: 0px;
                border-top: 1px solid #b8b8b8;
                border-right: 1px solid #8c8c8c;
                border-bottom: 1px solid #6a6a6a;
                border-left: none;
                border-radius: 0px;
                background-color: #050505;
            }
            QPushButton:hover {
                background-color: #101010;
                border-top: 1px solid #d0d0d0;
                border-right: 1px solid #a8a8a8;
                border-bottom: 1px solid #7a7a7a;
            }
            QPushButton:pressed {
                background-color: #1a1a1a;
                border-top: 1px solid #5a5a5a;
                border-right: 1px solid #7a7a7a;
                border-bottom: 1px solid #b8b8b8;
            }
            QPushButton:disabled {
                background-color: #080808;
                border-top: 1px solid #4a4a4a;
                border-right: 1px solid #4a4a4a;
                border-bottom: 1px solid #4a4a4a;
            }
            """
        )

    def paintEvent(self, event) -> None:
        option = QStyleOptionButton()
        option.initFrom(self)
        if self.isDown():
            option.state |= QStyle.State_Sunken

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        self.style().drawControl(QStyle.CE_PushButtonBevel, option, painter, self)

        rect = self.rect()
        press_shift_y = 1 if self.isDown() else 0

        cx = int(rect.center().x())
        cy = int(rect.center().y() + self._triangle_offset_y + press_shift_y)

        tri_w = max(8, min(12, rect.width() - 8))
        tri_h = max(5, min(8, rect.height() - 6))
        half_w = tri_w // 2
        half_h = tri_h // 2

        if self._direction == "up":
            points = [
                QPoint(cx, cy - half_h),
                QPoint(cx - half_w, cy + half_h),
                QPoint(cx + half_w, cy + half_h),
            ]
        else:
            points = [
                QPoint(cx - half_w, cy - half_h),
                QPoint(cx + half_w, cy - half_h),
                QPoint(cx, cy + half_h),
            ]

        polygon = QPolygon(points)

        arrow_color = Qt.white if self.isEnabled() else Qt.gray
        pen = QPen(arrow_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(arrow_color)
        painter.drawPolygon(polygon)

    def set_triangle_offset_y(self, offset_y: int) -> None:
        self._triangle_offset_y = int(offset_y)
        self.update()


class _BaseStepper(QWidget):
    """独自の stepper ベース。"""

    _CONTROL_HEIGHT = 34
    _BUTTON_WIDTH = 26

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setFixedHeight(self._CONTROL_HEIGHT)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._line_edit = QLineEdit()
        self._line_edit.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._line_edit.setFixedHeight(self._CONTROL_HEIGHT)
        self._line_edit.setStyleSheet(
            """
            QLineEdit {
                background-color: #000000;
                color: #ffffff;
                border: 1px solid #b8b8b8;
                padding-left: 6px;
                padding-right: 4px;
            }
            QLineEdit:disabled {
                color: #6f6f6f;
                border: 1px solid #4a4a4a;
                background-color: #080808;
            }
            """
        )
        self._line_edit.editingFinished.connect(self._on_editing_finished)

        self._button_container = QWidget()
        self._button_container.setFixedSize(self._BUTTON_WIDTH, self._CONTROL_HEIGHT)

        button_col = QVBoxLayout(self._button_container)
        button_col.setContentsMargins(0, 0, 0, 0)
        button_col.setSpacing(0)

        self._up_button = ArrowButton("up")
        self._down_button = ArrowButton("down")

        button_height_top = self._CONTROL_HEIGHT // 2
        button_height_bottom = self._CONTROL_HEIGHT - button_height_top

        self._up_button.setFixedSize(self._BUTTON_WIDTH, button_height_top)
        self._down_button.setFixedSize(self._BUTTON_WIDTH, button_height_bottom)

        self._up_button.set_triangle_offset_y(-3)
        self._down_button.set_triangle_offset_y(-2)

        self._up_button.clicked.connect(self.step_up)
        self._down_button.clicked.connect(self.step_down)

        button_col.addWidget(self._up_button)
        button_col.addWidget(self._down_button)

        root.addWidget(self._line_edit, 1)
        root.addWidget(self._button_container, 0)

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        self._line_edit.setEnabled(enabled)
        self._up_button.setEnabled(enabled)
        self._down_button.setEnabled(enabled)

    def _on_editing_finished(self) -> None:
        raise NotImplementedError

    def step_up(self) -> None:
        raise NotImplementedError

    def step_down(self) -> None:
        raise NotImplementedError


class IntStepper(_BaseStepper):
    def __init__(
        self,
        minimum: int,
        maximum: int,
        value: int,
        step: int = 1,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._minimum = int(minimum)
        self._maximum = int(maximum)
        self._single_step = max(1, int(step))
        self._value = self._clamp(value)

        self._line_edit.setValidator(QIntValidator(self._minimum, self._maximum, self))
        self._line_edit.setText(str(self._value))

    def _clamp(self, value: int) -> int:
        return max(self._minimum, min(self._maximum, int(value)))

    def _on_editing_finished(self) -> None:
        text = self._line_edit.text().strip()
        try:
            parsed = int(text)
        except ValueError:
            parsed = self._value
        self.setValue(parsed)

    def setRange(self, minimum: int, maximum: int) -> None:
        self._minimum = int(minimum)
        self._maximum = int(maximum)
        self._line_edit.setValidator(QIntValidator(self._minimum, self._maximum, self))
        self.setValue(self._value)

    def setSingleStep(self, step: int) -> None:
        self._single_step = max(1, int(step))

    def setValue(self, value: int) -> None:
        self._value = self._clamp(value)
        self._line_edit.setText(str(self._value))

    def value(self) -> int:
        return self._value

    def step_up(self) -> None:
        self.setValue(self._value + self._single_step)

    def step_down(self) -> None:
        self.setValue(self._value - self._single_step)


class DoubleStepper(_BaseStepper):
    def __init__(
        self,
        minimum: float,
        maximum: float,
        value: float,
        step: float = 0.1,
        decimals: int = 2,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._minimum = float(minimum)
        self._maximum = float(maximum)
        self._single_step = max(10 ** (-decimals), float(step))
        self._decimals = max(0, int(decimals))
        self._value = self._clamp(value)

        validator = QDoubleValidator(self._minimum, self._maximum, self._decimals, self)
        validator.setNotation(QDoubleValidator.StandardNotation)
        self._line_edit.setValidator(validator)
        self._line_edit.setText(self._format_value(self._value))

    def _format_value(self, value: float) -> str:
        return f"{value:.{self._decimals}f}"

    def _clamp(self, value: float) -> float:
        return max(self._minimum, min(self._maximum, float(value)))

    def _on_editing_finished(self) -> None:
        text = self._line_edit.text().strip()
        try:
            parsed = float(text)
        except ValueError:
            parsed = self._value
        self.setValue(parsed)

    def setRange(self, minimum: float, maximum: float) -> None:
        self._minimum = float(minimum)
        self._maximum = float(maximum)
        validator = QDoubleValidator(
            self._minimum,
            self._maximum,
            self._decimals,
            self,
        )
        validator.setNotation(QDoubleValidator.StandardNotation)
        self._line_edit.setValidator(validator)
        self.setValue(self._value)

    def setSingleStep(self, step: float) -> None:
        self._single_step = max(10 ** (-self._decimals), float(step))

    def setDecimals(self, decimals: int) -> None:
        self._decimals = max(0, int(decimals))
        validator = QDoubleValidator(
            self._minimum,
            self._maximum,
            self._decimals,
            self,
        )
        validator.setNotation(QDoubleValidator.StandardNotation)
        self._line_edit.setValidator(validator)
        self._line_edit.setText(self._format_value(self._value))

    def setValue(self, value: float) -> None:
        self._value = self._clamp(value)
        self._line_edit.setText(self._format_value(self._value))

    def value(self) -> float:
        return self._value

    def step_up(self) -> None:
        self.setValue(self._value + self._single_step)

    def step_down(self) -> None:
        self.setValue(self._value - self._single_step)


@dataclass
class _EditableParamRow:
    spec: StrategyParamSpec
    enabled: QCheckBox
    min_spin: IntStepper | DoubleStepper
    max_spin: IntStepper | DoubleStepper
    step_spin: IntStepper | DoubleStepper


class ParameterDialog(QDialog):
    """Popup dialog for editing exploration parameter ranges."""

    def __init__(
        self,
        parent: QWidget | None = None,
        strategy_name: str = "bollinger_range_v4_4",
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
            min_spin = IntStepper(
                minimum=int(spec.min_val),
                maximum=int(spec.max_val),
                value=int(lo),
                step=1,
            )
            max_spin = IntStepper(
                minimum=int(spec.min_val),
                maximum=int(spec.max_val),
                value=int(hi),
                step=1,
            )
            step_spin = IntStepper(
                minimum=1,
                maximum=max(1, int(spec.max_val)),
                value=max(1, int(step)),
                step=1,
            )
        else:
            min_step = 10 ** (-decimals)
            min_spin = DoubleStepper(
                minimum=spec.min_val,
                maximum=spec.max_val,
                value=float(lo),
                step=min_step,
                decimals=decimals,
            )
            max_spin = DoubleStepper(
                minimum=spec.min_val,
                maximum=spec.max_val,
                value=float(hi),
                step=min_step,
                decimals=decimals,
            )
            step_spin = DoubleStepper(
                minimum=min_step,
                maximum=spec.max_val,
                value=max(min_step, float(step)),
                step=min_step,
                decimals=decimals,
            )

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