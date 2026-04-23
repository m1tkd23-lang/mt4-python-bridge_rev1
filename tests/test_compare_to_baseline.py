# tests/test_compare_to_baseline.py
"""Unit tests for compare_to_baseline verdict logic (Stage B)."""
from __future__ import annotations

from backtest.aggregate_stats import AggregateStats, MonthlyPipsEntry
from backtest.evaluator import (
    BaselineComparisonThresholds,
    EvaluationVerdict,
    compare_to_baseline,
)


def _make_agg(
    monthly_pips: list[float],
    *,
    max_consecutive_deficit: int | None = None,
) -> AggregateStats:
    total = sum(monthly_pips)
    deficit_count = sum(1 for p in monthly_pips if p < 0)
    if max_consecutive_deficit is None:
        max_consecutive_deficit = 0
        current = 0
        for p in monthly_pips:
            if p < 0:
                current += 1
                if current > max_consecutive_deficit:
                    max_consecutive_deficit = current
            else:
                current = 0
    entries = [
        MonthlyPipsEntry(label=f"m{i + 1:02d}", total_pips=p)
        for i, p in enumerate(monthly_pips)
    ]
    return AggregateStats(
        month_count=len(monthly_pips),
        total_trades=len(monthly_pips) * 50,
        total_wins=len(monthly_pips) * 30,
        total_losses=len(monthly_pips) * 20,
        total_pips=total,
        overall_win_rate=60.0,
        overall_profit_factor=1.2,
        max_drawdown_pips=abs(min(monthly_pips)) if monthly_pips else 0.0,
        average_pips_per_month=total / len(monthly_pips) if monthly_pips else 0.0,
        monthly_pips_stddev=100.0,
        deficit_month_count=deficit_count,
        max_consecutive_deficit_months=max_consecutive_deficit,
        monthly_entries=entries,
    )


BASELINE_MONTHLY = [
    100, 120, 80, 110, -20, 90, -30, 140, 75, 105, -45, 95  # 12 months, +820 total, worst -45
]


def _baseline() -> AggregateStats:
    return _make_agg(BASELINE_MONTHLY)


def test_adopt_when_all_criteria_met():
    """All four ADOPT criteria met: +5% pips, worst improved, no new deficit, no new consec."""
    candidate_monthly = [
        120, 130, 90, 115, -15, 100, -25, 150, 85, 110, -40, 100
    ]
    # total: +920 (+12%), worst -40 (improved +5), deficit 3 (same), consec 1 (same)
    result = compare_to_baseline(_make_agg(candidate_monthly), _baseline())
    assert result.verdict == EvaluationVerdict.ADOPT
    assert result.comparison.total_pips_delta > 0
    assert result.comparison.worst_month_delta >= 0


def test_discard_on_large_pips_regression():
    """Iter1-like scenario: pips -59%, deficit +4."""
    candidate_monthly = [
        5, 20, -10, 15, -30, -20, -60, 20, -15, 30, -80, -15
    ]
    # total much less than baseline's 820, multiple deficits
    result = compare_to_baseline(_make_agg(candidate_monthly), _baseline())
    assert result.verdict == EvaluationVerdict.DISCARD
    # Expect pips regression reason
    assert any("regressed" in r for r in result.reasons)


def test_discard_on_worst_month_deepening():
    """Worst month goes from -45 to -60 (15 pips deeper, exceeds 10 pip limit)."""
    candidate_monthly = [
        100, 120, 80, 110, -20, 90, -30, 140, 75, 105, -60, 95
    ]
    result = compare_to_baseline(_make_agg(candidate_monthly), _baseline())
    assert result.verdict == EvaluationVerdict.DISCARD
    assert any("worst month deepened" in r for r in result.reasons)


def test_discard_on_deficit_months_increase_by_two():
    """Deficit months 3 -> 5 (+2) should DISCARD."""
    candidate_monthly = [
        100, 120, -5, 110, -20, 90, -30, -10, 75, 105, -45, 95
    ]
    # deficits: -5, -20, -30, -10, -45 = 5 deficits (baseline has 3)
    result = compare_to_baseline(_make_agg(candidate_monthly), _baseline())
    assert result.verdict == EvaluationVerdict.DISCARD
    assert any("deficit months increased" in r for r in result.reasons)


def test_discard_on_consecutive_deficit_increase():
    """Max consecutive deficit months 1 -> 2 (+1) should DISCARD."""
    candidate_monthly = [
        100, 120, 80, 110, -20, -15, 50, 140, 75, 105, -45, 95
    ]
    # baseline max consec = 1; candidate has -20,-15 consecutive = 2
    cand = _make_agg(candidate_monthly)
    base = _baseline()
    assert cand.max_consecutive_deficit_months == 2
    assert base.max_consecutive_deficit_months == 1
    result = compare_to_baseline(cand, base)
    assert result.verdict == EvaluationVerdict.DISCARD
    assert any("consecutive deficit" in r for r in result.reasons)


def test_improve_when_small_pips_gain_but_worst_slightly_deeper():
    """Small +1% pips gain (below +2% threshold) with worst ok — IMPROVE."""
    # baseline total 820, candidate total 828 (+1%), worst slightly improved
    candidate_monthly = [
        100, 120, 80, 110, -20, 92, -30, 142, 75, 105, -43, 97
    ]
    cand = _make_agg(candidate_monthly)
    base = _baseline()
    assert abs(cand.total_pips - 828) < 1e-6
    result = compare_to_baseline(cand, base)
    assert result.verdict == EvaluationVerdict.IMPROVE


def test_improve_when_worst_slightly_deeper_within_discard_limit():
    """Worst month -45 -> -52 (-7 pips, within 10 pip discard limit) — IMPROVE."""
    candidate_monthly = [
        100, 120, 80, 110, -20, 90, -30, 140, 75, 105, -52, 95
    ]
    result = compare_to_baseline(_make_agg(candidate_monthly), _baseline())
    assert result.verdict == EvaluationVerdict.IMPROVE


def test_adopt_with_custom_stricter_thresholds():
    """When thresholds are stricter, fewer candidates ADOPT."""
    # +12% pips gain
    candidate_monthly = [
        120, 130, 90, 115, -15, 100, -25, 150, 85, 110, -40, 100
    ]
    strict = BaselineComparisonThresholds(
        min_total_pips_improvement_ratio=0.30,  # require +30%
    )
    # With relaxed default, ADOPT. With strict, only IMPROVE.
    default_result = compare_to_baseline(_make_agg(candidate_monthly), _baseline())
    strict_result = compare_to_baseline(
        _make_agg(candidate_monthly), _baseline(), thresholds=strict,
    )
    assert default_result.verdict == EvaluationVerdict.ADOPT
    assert strict_result.verdict == EvaluationVerdict.IMPROVE


def test_same_stats_returns_improve():
    """Baseline vs itself should be IMPROVE (not ADOPT; no +2% gain)."""
    result = compare_to_baseline(_baseline(), _baseline())
    assert result.verdict == EvaluationVerdict.IMPROVE
    assert abs(result.comparison.total_pips_delta) < 1e-6


def test_comparison_numbers_make_sense():
    """The comparison numeric fields should reflect signed deltas correctly."""
    candidate_monthly = [
        150, 130, 90, 115, -15, 100, -25, 150, 85, 110, -40, 100
    ]
    cand = _make_agg(candidate_monthly)
    base = _baseline()
    result = compare_to_baseline(cand, base)
    c = result.comparison
    assert abs(c.total_pips_delta - (cand.total_pips - base.total_pips)) < 1e-6
    # candidate worst = -40, baseline worst = -45 → worst delta = +5 (improvement)
    assert abs(c.worst_month_delta - 5.0) < 1e-6
    # deficit count same (3 -> 3)
    assert c.deficit_month_delta == 0
