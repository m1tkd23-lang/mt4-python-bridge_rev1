# src\backtest_gui_app\widgets\chart_widget.py
# Re-export shim: canonical location is gui_common.widgets.chart_widget.
# See collapsible_section.py shim note for TASK-0141 / T-D context.
from __future__ import annotations

from gui_common.widgets.chart_widget import MatplotlibChart

__all__ = ["MatplotlibChart"]
