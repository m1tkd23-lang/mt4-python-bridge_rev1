# src\explore_gui_app\styles\terminal_dark_theme.py
from __future__ import annotations

from PySide6.QtWidgets import QApplication, QWidget


TERMINAL_DARK_QSS = """
QWidget {
    background-color: #000000;
    color: #f2f2f2;
    font-family: "JetBrains Mono", "Cascadia Code", Consolas, monospace;
    font-size: 13px;
}

QMainWindow, QDialog {
    background-color: #000000;
}

/* labels */
QLabel {
    background-color: transparent;
    color: #dcdcdc;
}

/* tabs */
QTabWidget::pane {
    border: 1px solid #dcdcdc;
    top: -1px;
    background-color: #000000;
}

QTabBar::tab {
    background-color: #000000;
    color: #d8d8d8;
    border: 1px solid #dcdcdc;
    padding: 6px 12px;
    min-width: 72px;
    margin-right: 4px;
    font-size: 12px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background-color: #151515;
    color: #ffffff;
}

QTabBar::tab:hover {
    background-color: #101010;
    color: #ffffff;
}

/* collapsible section header */
QToolButton[role="section-header"] {
    background-color: #000000;
    color: #ffffff;
    border: 1px solid #dcdcdc;
    padding: 4px 8px;
    font-weight: 600;
}

QToolButton[role="section-header"]:hover {
    background-color: #101010;
}

QToolButton[role="section-header"]:checked {
    background-color: #151515;
    color: #ffffff;
}

/* group box */
QGroupBox {
    border: 1px solid #dcdcdc;
    margin-top: 10px;
    padding-top: 10px;
    background-color: #000000;
    color: #ffffff;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px 0 4px;
    color: #ffffff;
}

/* line edit / combo / text */
QLineEdit,
QComboBox,
QTextEdit,
QPlainTextEdit,
QListWidget {
    background-color: #000000;
    color: #ffffff;
    border: 1px solid #dcdcdc;
    border-radius: 0px;
    padding: 4px 6px;
    selection-background-color: #ffffff;
    selection-color: #000000;
    font-family: "JetBrains Mono", "Cascadia Code", Consolas, monospace;
    font-size: 12px;
}

QLineEdit:focus,
QComboBox:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QListWidget:focus {
    border: 1px solid #ffffff;
}

QLineEdit[readOnly="true"],
QPlainTextEdit[readOnly="true"],
QTextEdit[readOnly="true"] {
    background-color: #050505;
    color: #dcdcdc;
}

/* spin box */
QSpinBox,
QDoubleSpinBox {
    background-color: #000000;
    color: #ffffff;
    border: 1px solid #dcdcdc;
    border-radius: 0px;
    padding-top: 4px;
    padding-bottom: 4px;
    padding-left: 6px;
    padding-right: 26px;
    min-height: 24px;
    selection-background-color: #ffffff;
    selection-color: #000000;
    font-family: "JetBrains Mono", "Cascadia Code", Consolas, monospace;
    font-size: 12px;
}

QSpinBox:focus,
QDoubleSpinBox:focus {
    border: 1px solid #ffffff;
}

QSpinBox::up-button,
QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    height: 12px;
    border-left: 1px solid #dcdcdc;
    border-bottom: 1px solid #dcdcdc;
    background-color: #000000;
}

QSpinBox::down-button,
QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    height: 12px;
    border-left: 1px solid #dcdcdc;
    background-color: #000000;
}

QSpinBox::up-button:hover,
QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover,
QDoubleSpinBox::down-button:hover {
    background-color: #161616;
}

QSpinBox::up-button:pressed,
QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed,
QDoubleSpinBox::down-button:pressed {
    background-color: #262626;
}

/* ここでは矢印を消さない */
QSpinBox::up-arrow,
QDoubleSpinBox::up-arrow,
QSpinBox::down-arrow,
QDoubleSpinBox::down-arrow {
    subcontrol-origin: padding;
    subcontrol-position: center;
}

/* combo */
QComboBox::drop-down {
    border: none;
    width: 18px;
    background-color: #000000;
}

QComboBox QAbstractItemView {
    background-color: #000000;
    color: #ffffff;
    border: 1px solid #dcdcdc;
    selection-background-color: #ffffff;
    selection-color: #000000;
}

/* buttons */
QPushButton,
QToolButton {
    background-color: #000000;
    color: #ffffff;
    border: 1px solid #dcdcdc;
    border-radius: 0px;
    padding: 4px 8px;
    min-height: 26px;
}

QPushButton:hover,
QToolButton:hover {
    background-color: #161616;
}

QPushButton:pressed,
QToolButton:pressed {
    background-color: #262626;
}

QPushButton:disabled,
QToolButton:disabled {
    color: #777777;
    border-color: #777777;
}

QPushButton[role="primary"] {
    color: #ffffff;
    border: 1px solid #ffffff;
}

QPushButton[role="danger"] {
    color: #ff7b72;
    border: 1px solid #dcdcdc;
}

/* checkbox / radio */
QRadioButton,
QCheckBox {
    spacing: 6px;
    color: #dcdcdc;
    background-color: transparent;
}

QRadioButton::indicator,
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #dcdcdc;
    background: #000000;
}

QRadioButton::indicator:checked,
QCheckBox::indicator:checked {
    background: #dcdcdc;
}

/* tables */
QTableWidget,
QTableView {
    background-color: #000000;
    alternate-background-color: #050505;
    color: #f2f2f2;
    gridline-color: #dcdcdc;
    selection-background-color: #ffffff;
    selection-color: #000000;
    border: 1px solid #dcdcdc;
    font-family: "JetBrains Mono", "Cascadia Code", Consolas, monospace;
    font-size: 12px;
}

QHeaderView::section {
    background-color: #000000;
    color: #ffffff;
    border: none;
    border-right: 1px solid #dcdcdc;
    border-bottom: 1px solid #dcdcdc;
    padding: 4px 6px;
    font-weight: 600;
}

QHeaderView::section:hover {
    background-color: #101010;
}

QTableCornerButton::section {
    background-color: #000000;
    border: 1px solid #dcdcdc;
}

/* splitter */
QSplitter::handle {
    background-color: #dcdcdc;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QSplitter::handle:vertical {
    height: 2px;
}

/* scrollbars */
QScrollBar:vertical,
QScrollBar:horizontal {
    background: #000000;
    border: 1px solid #dcdcdc;
    margin: 0px;
}

QScrollBar::handle:vertical,
QScrollBar::handle:horizontal {
    background: #d0d0d0;
    min-height: 24px;
    min-width: 24px;
}

QScrollBar::add-line,
QScrollBar::sub-line {
    background: #000000;
    border: none;
    height: 0;
    width: 0;
}

QScrollBar::add-page,
QScrollBar::sub-page {
    background: #000000;
}

/* scroll area */
QScrollArea {
    border: 1px solid #dcdcdc;
    background-color: #000000;
}

QScrollArea > QWidget > QWidget {
    background-color: #000000;
}

/* frame */
QFrame {
    background-color: transparent;
    color: #dcdcdc;
}

/* tooltips */
QToolTip {
    background-color: #111111;
    color: #ffffff;
    border: 1px solid #dcdcdc;
    padding: 4px;
}

/* status bar */
QStatusBar {
    background-color: #000000;
    color: #dcdcdc;
    border-top: 1px solid #dcdcdc;
}
"""


def apply_terminal_dark_theme(target: QApplication | QWidget) -> None:
    target.setStyleSheet(TERMINAL_DARK_QSS)