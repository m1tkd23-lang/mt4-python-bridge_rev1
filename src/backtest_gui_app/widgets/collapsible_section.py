# src\backtest_gui_app\widgets\collapsible_section.py
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QToolButton, QVBoxLayout, QWidget


class CollapsibleSection(QWidget):
    def __init__(
        self,
        title: str,
        content: QWidget,
        *,
        expanded: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._content = content
        self._toggle_button = QToolButton()
        self._toggle_button.setText(title)
        self._toggle_button.setCheckable(True)
        self._toggle_button.setChecked(expanded)
        self._toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._toggle_button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self._toggle_button.clicked.connect(self._on_toggled)

        header_line = QFrame()
        header_line.setFrameShape(QFrame.HLine)
        header_line.setFrameShadow(QFrame.Sunken)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        header_layout.addWidget(self._toggle_button, 0)
        header_layout.addWidget(header_line, 1)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(4)
        root_layout.addLayout(header_layout)
        root_layout.addWidget(self._content)

        self._content.setVisible(expanded)

    def setTitle(self, title: str) -> None:
        self._toggle_button.setText(title)

    def _on_toggled(self) -> None:
        expanded = self._toggle_button.isChecked()
        self._toggle_button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self._content.setVisible(expanded)