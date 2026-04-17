# src/backtest_gui_app/styles/dark_theme.py
from __future__ import annotations

from PySide6.QtWidgets import QApplication, QWidget


DARK_THEME_COLORS: dict[str, str] = {
    "bg": "#1e1f29",
    "bg_alt": "#252731",
    "panel": "#2a2c39",
    "panel_alt": "#30323f",
    "border": "#3a3d4d",
    "border_strong": "#4a4d5e",
    "text": "#e0e3eb",
    "text_muted": "#9aa0b4",
    "text_dim": "#6b7088",
    "accent": "#4a90e2",
    "accent_pressed": "#3978c1",
    "warning": "#f0a050",
    "success": "#4caf50",
    "danger": "#ef4f4f",
    "selection_bg": "#3b5374",
    "selection_text": "#ffffff",
    "header_bg": "#2f3242",
}


def _qss(colors: dict[str, str]) -> str:
    c = colors
    return f"""
/* === root === */
QWidget {{
    background-color: {c['bg']};
    color: {c['text']};
    font-size: 12px;
}}

QMainWindow, QDialog {{
    background-color: {c['bg']};
}}

/* === labels === */
QLabel {{
    background-color: transparent;
    color: {c['text']};
}}

QLabel[role="kpi-title"] {{
    color: {c['text_muted']};
    font-size: 11px;
    letter-spacing: 0.4px;
}}

QLabel[role="kpi-value"] {{
    color: {c['text']};
    font-size: 16px;
    font-weight: 600;
}}

QLabel[role="kpi-subvalue"] {{
    color: {c['text_muted']};
    font-size: 11px;
}}

QLabel[role="section-title"] {{
    color: {c['text']};
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.4px;
}}

/* === inputs === */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {c['bg_alt']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: 3px;
    padding: 3px 6px;
    selection-background-color: {c['selection_bg']};
    selection-color: {c['selection_text']};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {c['accent']};
}}

QLineEdit:disabled, QTextEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QComboBox:disabled {{
    color: {c['text_dim']};
    background-color: {c['panel']};
}}

QComboBox::drop-down {{
    border: none;
    width: 18px;
}}

QComboBox QAbstractItemView {{
    background-color: {c['bg_alt']};
    color: {c['text']};
    border: 1px solid {c['border']};
    selection-background-color: {c['selection_bg']};
    selection-color: {c['selection_text']};
}}

/* === buttons === */
QPushButton {{
    background-color: {c['panel']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: 3px;
    padding: 5px 12px;
}}

QPushButton:hover {{
    background-color: {c['panel_alt']};
    border-color: {c['border_strong']};
}}

QPushButton:pressed {{
    background-color: {c['accent_pressed']};
    border-color: {c['accent']};
    color: {c['selection_text']};
}}

QPushButton:disabled {{
    color: {c['text_dim']};
    background-color: {c['panel']};
    border-color: {c['border']};
}}

QPushButton[role="primary"] {{
    background-color: {c['accent']};
    color: {c['selection_text']};
    border: 1px solid {c['accent']};
    font-weight: 600;
}}

QPushButton[role="primary"]:hover {{
    background-color: {c['accent_pressed']};
}}

QPushButton[role="primary"]:pressed {{
    background-color: {c['accent_pressed']};
}}

QPushButton[role="primary"]:disabled {{
    background-color: {c['panel']};
    color: {c['text_dim']};
    border-color: {c['border']};
}}

QPushButton[role="danger"] {{
    background-color: {c['panel']};
    color: {c['danger']};
    border: 1px solid {c['border']};
}}

QPushButton[role="danger"]:hover {{
    background-color: {c['panel_alt']};
    border-color: {c['danger']};
}}

QToolButton {{
    background-color: transparent;
    color: {c['text']};
    border: none;
    padding: 3px 6px;
}}

QToolButton:hover {{
    background-color: {c['panel_alt']};
    border-radius: 3px;
}}

QToolButton:checked {{
    color: {c['text']};
}}

/* CollapsibleSection header (uses QToolButton) */
QToolButton[role="section-header"] {{
    color: {c['text']};
    font-weight: 600;
    padding: 4px 4px;
    background-color: transparent;
}}

/* === checkbox === */
QCheckBox {{
    color: {c['text']};
    spacing: 6px;
    background-color: transparent;
}}

QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {c['border_strong']};
    border-radius: 2px;
    background-color: {c['bg_alt']};
}}

QCheckBox::indicator:checked {{
    background-color: {c['accent']};
    border-color: {c['accent']};
}}

QCheckBox::indicator:hover {{
    border-color: {c['accent']};
}}

/* === group box === */
QGroupBox {{
    background-color: {c['panel']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    margin-top: 12px;
    padding: 8px;
    color: {c['text']};
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    padding: 0 4px;
    color: {c['text_muted']};
}}

/* === frame (used as horizontal lines / panels) === */
QFrame {{
    background-color: transparent;
    color: {c['text']};
}}

QFrame[frameShape="4"] /* HLine */, QFrame[frameShape="5"] /* VLine */ {{
    background-color: {c['border']};
    color: {c['border']};
    border: none;
}}

QFrame[role="card"] {{
    background-color: {c['panel']};
    border: 1px solid {c['border']};
    border-radius: 4px;
}}

QFrame[role="kpi-card"] {{
    background-color: {c['panel']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    padding: 6px;
}}

/* === tabs === */
QTabWidget::pane {{
    border: 1px solid {c['border']};
    border-radius: 3px;
    background-color: {c['bg_alt']};
    top: -1px;
}}

QTabBar::tab {{
    background-color: {c['panel']};
    color: {c['text_muted']};
    border: 1px solid {c['border']};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 6px 14px;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    background-color: {c['bg_alt']};
    color: {c['text']};
    border-color: {c['border_strong']};
}}

QTabBar::tab:hover:!selected {{
    color: {c['text']};
}}

/* === table === */
QTableWidget, QTableView {{
    background-color: {c['bg_alt']};
    alternate-background-color: {c['panel']};
    color: {c['text']};
    gridline-color: {c['border']};
    selection-background-color: {c['selection_bg']};
    selection-color: {c['selection_text']};
    border: 1px solid {c['border']};
}}

QHeaderView::section {{
    background-color: {c['header_bg']};
    color: {c['text']};
    border: none;
    border-right: 1px solid {c['border']};
    border-bottom: 1px solid {c['border']};
    padding: 4px 6px;
    font-weight: 600;
}}

QHeaderView::section:hover {{
    background-color: {c['panel_alt']};
}}

QTableCornerButton::section {{
    background-color: {c['header_bg']};
    border: 1px solid {c['border']};
}}

/* === splitter === */
QSplitter::handle {{
    background-color: {c['border']};
}}

QSplitter::handle:horizontal {{
    width: 3px;
}}

QSplitter::handle:vertical {{
    height: 3px;
}}

QSplitter::handle:hover {{
    background-color: {c['accent']};
}}

/* === progress bar === */
QProgressBar {{
    background-color: {c['bg_alt']};
    border: 1px solid {c['border']};
    border-radius: 3px;
    color: {c['text']};
    text-align: center;
    height: 18px;
}}

QProgressBar::chunk {{
    background-color: {c['accent']};
    border-radius: 2px;
}}

/* === scrollbars === */
QScrollBar:vertical {{
    background-color: {c['bg']};
    width: 12px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {c['border_strong']};
    border-radius: 4px;
    min-height: 24px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {c['accent']};
}}

QScrollBar:horizontal {{
    background-color: {c['bg']};
    height: 12px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {c['border_strong']};
    border-radius: 4px;
    min-width: 24px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {c['accent']};
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    background: none;
    border: none;
    height: 0;
    width: 0;
}}

QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
}}

/* === menu / tooltip === */
QMenu {{
    background-color: {c['bg_alt']};
    color: {c['text']};
    border: 1px solid {c['border']};
}}

QMenu::item:selected {{
    background-color: {c['selection_bg']};
    color: {c['selection_text']};
}}

QToolTip {{
    background-color: {c['panel']};
    color: {c['text']};
    border: 1px solid {c['border_strong']};
    padding: 4px 6px;
}}

/* === status bar === */
QStatusBar {{
    background-color: {c['bg_alt']};
    color: {c['text_muted']};
    border-top: 1px solid {c['border']};
}}
"""


DARK_THEME_QSS: str = _qss(DARK_THEME_COLORS)


def apply_dark_theme(target: QApplication | QWidget) -> None:
    """Apply the dark theme stylesheet to a QApplication or root QWidget."""
    target.setStyleSheet(DARK_THEME_QSS)


def style_matplotlib_figure(figure, *, axes=None) -> None:
    """Apply dark theme colors to a matplotlib Figure (and optional axes list).

    Call this each time before drawing if the figure is cleared, since
    matplotlib resets axis-level colors on clear().
    """
    c = DARK_THEME_COLORS
    figure.patch.set_facecolor(c["panel"])
    target_axes = axes if axes is not None else figure.get_axes()
    for ax in target_axes:
        ax.set_facecolor(c["bg_alt"])
        for spine in ax.spines.values():
            spine.set_edgecolor(c["border_strong"])
        ax.tick_params(colors=c["text_muted"], which="both")
        ax.xaxis.label.set_color(c["text"])
        ax.yaxis.label.set_color(c["text"])
        ax.title.set_color(c["text"])
        ax.grid(True, color=c["border"], linewidth=0.4, alpha=0.6)
