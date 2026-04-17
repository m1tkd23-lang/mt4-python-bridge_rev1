# src\backtest_gui_app\widgets\collapsible_section.py
# Re-export shim: canonical location is gui_common.widgets.collapsible_section.
# Physical move (TASK-0141 / T-D §12-2 第1段) kept this module as a thin
# re-export so legacy import paths continue to resolve. Shim deletion is a
# follow-up task (T-D §12-2 第2段, F6).
from __future__ import annotations

from gui_common.widgets.collapsible_section import CollapsibleSection

__all__ = ["CollapsibleSection"]
