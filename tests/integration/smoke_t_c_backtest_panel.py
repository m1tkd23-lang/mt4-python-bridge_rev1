# TEST/smoke_t_c_backtest_panel.py
"""Offscreen smoke test for TASK-0139 T-C BacktestPanel.

Checks:
1. ExploreMainWindow constructs and event loop returns 0
2. Tab A <-> B <-> C switching does not crash
3. BacktestPanel programmatic single-CSV run shows the 11-field summary
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from explore_gui_app.views.backtest_panel import BacktestPanel
from explore_gui_app.views.main_window import ExploreMainWindow


def _switch_tabs(window: ExploreMainWindow) -> None:
    tab_widget = window._tab_widget
    assert tab_widget.count() == 3, f"expected 3 tabs, got {tab_widget.count()}"
    for index in (0, 1, 2, 1, 0):
        tab_widget.setCurrentIndex(index)
        QApplication.processEvents()


def _verify_panel_initial_state(window: ExploreMainWindow) -> None:
    panel: BacktestPanel = window._backtest_panel
    assert panel.get_candidate_strategy() is None
    assert panel.get_candidate_overrides() is None
    # All 11 summary fields default to "-"
    for key in (
        "total_pips",
        "win_rate_percent",
        "profit_factor",
        "max_drawdown_pips",
        "trades",
        "verdict",
        "wins",
        "losses",
        "average_pips",
        "max_consecutive_wins",
        "max_consecutive_losses",
    ):
        assert panel._summary_labels[key].text() == "-", (
            f"summary field {key} should start as '-'"
        )


def _run_single_backtest(window: ExploreMainWindow) -> None:
    panel: BacktestPanel = window._backtest_panel
    csv_path = (
        REPO_ROOT
        / "data"
        / "USDJPY-cd5_20250521_monthly"
        / "USDJPY-cd5_20250521_2025-05.csv"
    )
    assert csv_path.exists(), f"missing test CSV: {csv_path}"

    panel.set_candidate(
        strategy_name="bollinger_range_v4_4",
        param_overrides=None,
    )
    panel.set_csv_path(str(csv_path))
    panel.set_mode(BacktestPanel.MODE_SINGLE)

    window._on_backtest_run()

    worker = window._backtest_worker
    assert worker is not None, "backtest worker did not start"
    worker.wait(120_000)
    QApplication.processEvents()

    total_pips = panel._summary_labels["total_pips"].text()
    trades = panel._summary_labels["trades"].text()
    verdict = panel._summary_labels["verdict"].text()
    print(
        f"single-run summary: total_pips={total_pips}, "
        f"trades={trades}, verdict={verdict}"
    )
    assert total_pips != "-", "total_pips not populated after single run"
    assert trades != "-", "trades not populated after single run"
    assert verdict != "-", "verdict not populated after single run"


def main() -> int:
    app = QApplication(sys.argv)
    window = ExploreMainWindow()
    window.show()

    _verify_panel_initial_state(window)
    _switch_tabs(window)
    _run_single_backtest(window)
    _switch_tabs(window)

    QTimer.singleShot(50, app.quit)
    ret = app.exec()
    print(f"app.exec ret={ret}")
    return ret


if __name__ == "__main__":
    raise SystemExit(main())
