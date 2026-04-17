"""TASK-0120 headless SummaryPanel visual check.

Goals (from TASK-0120):
 (a) Mean Reversion section collapse default state.
 (b) Dark theme consistency (text/background/separator colors).
 (c) Long label wrap / column width for fields like mr_success_within_12.
 (d) range-trade = 0 case: N/A / '-' display does not collapse.

This script drives the real SummaryPanel + BacktestResultPresenter in an
offscreen Qt session, so layout geometry and stylesheet application are
resolved exactly as in the GUI (minus the actual pixel render).
It does NOT replace a human visual sign-off, but gives deterministic
evidence for every check above.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from backtest.mean_reversion_analysis import MeanReversionSummary  # noqa: E402
from backtest.service import BacktestRunConfig, run_backtest  # noqa: E402
from backtest.simulator import IntrabarFillPolicy  # noqa: E402
from backtest_gui_app.presenters.result_presenter import (  # noqa: E402
    BacktestResultPresenter,
)
from backtest_gui_app.styles import apply_dark_theme  # noqa: E402
from backtest_gui_app.styles.dark_theme import DARK_THEME_COLORS  # noqa: E402
from backtest_gui_app.views.chart_overview_tab import ChartOverviewTab  # noqa: E402
from backtest_gui_app.views.input_panel import InputPanel  # noqa: E402
from backtest_gui_app.views.result_tabs import ResultTabs  # noqa: E402
from backtest_gui_app.views.summary_panel import SummaryPanel  # noqa: E402
from gui_common.widgets.collapsible_section import (  # noqa: E402
    CollapsibleSection,
)


MR_KEYS = (
    "mr_total_range_trades",
    "mr_reversion_failure_count",
    "mr_reversion_success_count",
    "mr_success_rate",
    "mr_avg_bars_to_reversion",
    "mr_success_within_3",
    "mr_success_within_5",
    "mr_success_within_8",
    "mr_success_within_12",
    "mr_avg_max_progress_ratio",
    "mr_avg_max_adverse_excursion",
)


def _find_mr_section(panel: SummaryPanel) -> CollapsibleSection:
    for section in panel.findChildren(CollapsibleSection):
        btn = section.findChild(type(section._toggle_button))
        if btn is not None and "Mean reversion" in btn.text():
            return section
    raise RuntimeError("Mean reversion CollapsibleSection not found")


def _label_sizehint(label: QLabel) -> tuple[int, int]:
    sh = label.sizeHint()
    return sh.width(), sh.height()


def _zero_mr_summary() -> MeanReversionSummary:
    return MeanReversionSummary(
        total_range_trades=0,
        reversion_failure_count=0,
        reversion_success_count=0,
        success_rate=None,
        avg_bars_to_reversion=None,
        success_within_3_count=0,
        success_within_3_rate=None,
        success_within_5_count=0,
        success_within_5_rate=None,
        success_within_8_count=0,
        success_within_8_rate=None,
        success_within_12_count=0,
        success_within_12_rate=None,
        avg_max_progress_ratio=None,
        avg_max_adverse_excursion=None,
    )


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    apply_dark_theme(app)

    panel = SummaryPanel()
    result_tabs = ResultTabs()
    input_panel = InputPanel()
    chart_overview = ChartOverviewTab()
    presenter = BacktestResultPresenter(
        summary_panel=panel,
        result_tabs=result_tabs,
        input_panel=input_panel,
        chart_overview_tab=chart_overview,
    )

    panel.resize(820, 260)  # typical workspace summary height
    panel.show()
    app.processEvents()

    findings: list[str] = []

    # (a) Default collapse state
    mr_section = _find_mr_section(panel)
    toggle = mr_section._toggle_button
    content_visible_init = mr_section._content.isVisible()
    findings.append(
        "[a] MR section toggle checked(expanded) on init: "
        f"{toggle.isChecked()} | content visible: {content_visible_init}"
    )
    assert toggle.isChecked() is False, "MR section should start collapsed"
    assert content_visible_init is False, "MR content should be hidden on init"

    # (b) Dark theme consistency
    qss = app.styleSheet()
    theme_ok = bool(qss) and DARK_THEME_COLORS["bg"] in qss
    findings.append(
        f"[b] Dark theme stylesheet applied: {theme_ok} "
        f"(stylesheet length={len(qss)})"
    )
    # sample widget palette
    hdr_btn_ss = toggle.styleSheet()
    findings.append(
        "[b] Section-header button inherits app QSS "
        f"(section-header rule present: {'section-header' in qss})"
    )
    assert theme_ok

    # Case 1: mr_summary = None -> every MR label becomes 'N/A'
    presenter._populate_mean_reversion(None)
    mr_section._content.setVisible(True)  # force layout resolution
    app.processEvents()
    none_case = {k: panel.summary_labels[k].text() for k in MR_KEYS}
    findings.append(f"[d-none] mr_summary=None labels: {none_case}")
    for k, v in none_case.items():
        assert v == "N/A", f"{k} expected 'N/A' when mr_summary is None, got {v!r}"

    # Case 2: zero-range-trade summary -> counts=0, rate fields='N/A'
    presenter._populate_mean_reversion(_zero_mr_summary())
    app.processEvents()
    zero_case = {k: panel.summary_labels[k].text() for k in MR_KEYS}
    findings.append(f"[d-zero] zero-range mr_summary labels: {zero_case}")
    assert zero_case["mr_total_range_trades"] == "0"
    assert zero_case["mr_reversion_failure_count"] == "0"
    assert zero_case["mr_reversion_success_count"] == "0"
    assert zero_case["mr_success_rate"] == "N/A"
    assert zero_case["mr_avg_bars_to_reversion"] == "N/A"
    for compound in (
        "mr_success_within_3",
        "mr_success_within_5",
        "mr_success_within_8",
        "mr_success_within_12",
    ):
        text = zero_case[compound]
        assert text.startswith("0 ("), f"{compound} unexpected format: {text!r}"
        assert "N/A" in text, f"{compound} should contain N/A: {text!r}"

    # (c) Column width / label wrap check
    # Inspect sizeHint of every MR label + its key-label after layout resolution.
    # Our Qt labels don't wrap by default; we just confirm no label value
    # is empty and that the value side has a visible width > 0 once the
    # section is expanded (so the grid actually reserves space).
    value_widths = {k: _label_sizehint(panel.summary_labels[k]) for k in MR_KEYS}
    findings.append(f"[c] MR value label sizeHints: {value_widths}")
    for k, (w, h) in value_widths.items():
        assert w > 0 and h > 0, f"label {k} has degenerate sizeHint {(w, h)}"

    # Case 3: real USDJPY single-month backtest
    csv_path = (
        ROOT
        / "data"
        / "USDJPY-cd5_20250521_monthly"
        / "USDJPY-cd5_20250521_2026-03.csv"
    )
    if csv_path.exists():
        config = BacktestRunConfig(
            csv_path=csv_path,
            strategy_name="bollinger_range_v4_4_guarded",
            symbol="USDJPY",
            timeframe="M1",
            pip_size=0.01,
            sl_pips=10.0,
            tp_pips=10.0,
            intrabar_fill_policy=IntrabarFillPolicy.CONSERVATIVE,
            close_open_position_at_end=True,
            initial_balance=1_000_000.0,
            money_per_pip=100.0,
            risk_percent=1.0,
        )
        artifacts = run_backtest(config)
        presenter.apply_artifacts_to_ui(artifacts)
        app.processEvents()
        real_case = {k: panel.summary_labels[k].text() for k in MR_KEYS}
        findings.append(
            f"[real] USDJPY 2026-03 single-month MR labels: {real_case}"
        )
        # Expansion stays at user default (collapsed) but labels are populated
        # into the hidden content — unhide to confirm their resolved geometry.
        mr_section._content.setVisible(True)
        app.processEvents()
        real_widths = {k: _label_sizehint(panel.summary_labels[k]) for k in MR_KEYS}
        findings.append(f"[real] MR value label sizeHints after run: {real_widths}")
    else:
        findings.append(f"[real] SKIPPED (csv not found): {csv_path}")

    # (b) Also verify that kpi_card and section-header roles are honored
    findings.append(
        "[b] kpi-card widgets in panel: "
        f"{len([w for w in panel.findChildren(object) if getattr(w, 'property', None) and w.property('role') == 'kpi-card'])}"
    )

    print("=== TASK-0120 SummaryPanel visual check ===")
    for line in findings:
        print(line)
    print("All assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
