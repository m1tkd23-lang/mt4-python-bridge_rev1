# src/backtest/evaluator.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from backtest.aggregate_stats import AggregateStats
from backtest.simulator import BacktestResult, BacktestStats

logger = logging.getLogger(__name__)


class EvaluationVerdict(str, Enum):
    ADOPT = "adopt"
    IMPROVE = "improve"
    DISCARD = "discard"


@dataclass(frozen=True)
class EvaluationThresholds:
    min_profit_factor_adopt: float = 1.1
    max_profit_factor_improve: float = 1.0
    max_drawdown_pips: float = 100.0
    min_total_pips_adopt: float = 0.0
    min_trades: int = 5

    @staticmethod
    def default() -> EvaluationThresholds:
        return EvaluationThresholds()


@dataclass(frozen=True)
class EvaluationResult:
    verdict: EvaluationVerdict
    reasons: list[str]
    stats_summary: dict[str, object]


def evaluate_backtest(
    stats: BacktestStats,
    thresholds: EvaluationThresholds | None = None,
) -> EvaluationResult:
    if thresholds is None:
        thresholds = EvaluationThresholds.default()

    reasons: list[str] = []

    stats_summary: dict[str, object] = {
        "strategy_name": stats.strategy_name,
        "total_pips": stats.total_pips,
        "profit_factor": stats.profit_factor,
        "max_drawdown_pips": stats.max_drawdown_pips,
        "win_rate": stats.win_rate,
        "trades": stats.trades,
    }

    if stats.trades < thresholds.min_trades:
        reasons.append(
            f"Insufficient trades ({stats.trades} < {thresholds.min_trades})"
        )
        return EvaluationResult(
            verdict=EvaluationVerdict.DISCARD,
            reasons=reasons,
            stats_summary=stats_summary,
        )

    if stats.max_drawdown_pips > thresholds.max_drawdown_pips:
        reasons.append(
            f"Excessive drawdown ({stats.max_drawdown_pips:.1f} pips "
            f"> {thresholds.max_drawdown_pips:.1f} pips threshold)"
        )
        return EvaluationResult(
            verdict=EvaluationVerdict.DISCARD,
            reasons=reasons,
            stats_summary=stats_summary,
        )

    pf = stats.profit_factor

    if pf is not None and pf > thresholds.min_profit_factor_adopt and stats.total_pips > thresholds.min_total_pips_adopt:
        reasons.append(
            f"PF {pf:.2f} > {thresholds.min_profit_factor_adopt}, "
            f"Total pips {stats.total_pips:.1f} positive"
        )
        return EvaluationResult(
            verdict=EvaluationVerdict.ADOPT,
            reasons=reasons,
            stats_summary=stats_summary,
        )

    if pf is None or pf < thresholds.max_profit_factor_improve or stats.total_pips < 0:
        if pf is None:
            reasons.append("No profit factor (no wins and no losses)")
        else:
            reasons.append(
                f"PF {pf:.2f} < {thresholds.max_profit_factor_improve} "
                f"or Total pips {stats.total_pips:.1f} negative"
            )
        return EvaluationResult(
            verdict=EvaluationVerdict.IMPROVE,
            reasons=reasons,
            stats_summary=stats_summary,
        )

    reasons.append(
        f"PF {pf:.2f} between {thresholds.max_profit_factor_improve} "
        f"and {thresholds.min_profit_factor_adopt}, needs improvement"
    )
    return EvaluationResult(
        verdict=EvaluationVerdict.IMPROVE,
        reasons=reasons,
        stats_summary=stats_summary,
    )


# --- Cross-month (all-months) evaluation ---


@dataclass(frozen=True)
class CrossMonthThresholds:
    min_avg_pips_per_month: float = 150.0
    target_avg_pips_per_month: float = 200.0
    max_deficit_month_ratio: float = 0.5
    max_consecutive_deficit_months: int = 2

    @staticmethod
    def default() -> CrossMonthThresholds:
        return CrossMonthThresholds()


@dataclass(frozen=True)
class CrossMonthEvaluationResult:
    verdict: EvaluationVerdict
    reasons: list[str]
    stats_summary: dict[str, object]


def evaluate_cross_month(
    agg: AggregateStats,
    thresholds: CrossMonthThresholds | None = None,
) -> CrossMonthEvaluationResult:
    """Evaluate aggregate stats across all months against monthly-average pips criteria."""
    if thresholds is None:
        thresholds = CrossMonthThresholds.default()

    reasons: list[str] = []
    stats_summary: dict[str, object] = {
        "month_count": agg.month_count,
        "average_pips_per_month": agg.average_pips_per_month,
        "total_pips": agg.total_pips,
        "deficit_month_count": agg.deficit_month_count,
        "max_consecutive_deficit_months": agg.max_consecutive_deficit_months,
        "monthly_pips_stddev": agg.monthly_pips_stddev,
    }

    if agg.month_count == 0:
        reasons.append("No monthly data available")
        return CrossMonthEvaluationResult(
            verdict=EvaluationVerdict.DISCARD,
            reasons=reasons,
            stats_summary=stats_summary,
        )

    # Check deficit month ratio
    deficit_ratio = agg.deficit_month_count / agg.month_count
    if deficit_ratio > thresholds.max_deficit_month_ratio:
        reasons.append(
            f"Too many deficit months ({agg.deficit_month_count}/{agg.month_count} "
            f"= {deficit_ratio:.0%} > {thresholds.max_deficit_month_ratio:.0%})"
        )

    # Check consecutive deficit months
    if agg.max_consecutive_deficit_months > thresholds.max_consecutive_deficit_months:
        reasons.append(
            f"Consecutive deficit months ({agg.max_consecutive_deficit_months}) "
            f"exceeds limit ({thresholds.max_consecutive_deficit_months})"
        )

    avg = agg.average_pips_per_month

    # Determine verdict based on average pips per month
    if avg >= thresholds.target_avg_pips_per_month and not reasons:
        reasons.append(
            f"Avg pips/month {avg:.1f} >= target {thresholds.target_avg_pips_per_month:.0f}"
        )
        return CrossMonthEvaluationResult(
            verdict=EvaluationVerdict.ADOPT,
            reasons=reasons,
            stats_summary=stats_summary,
        )

    if avg >= thresholds.min_avg_pips_per_month and not reasons:
        reasons.append(
            f"Avg pips/month {avg:.1f} >= minimum {thresholds.min_avg_pips_per_month:.0f} "
            f"but below target {thresholds.target_avg_pips_per_month:.0f}"
        )
        return CrossMonthEvaluationResult(
            verdict=EvaluationVerdict.ADOPT,
            reasons=reasons,
            stats_summary=stats_summary,
        )

    if avg >= thresholds.min_avg_pips_per_month and reasons:
        reasons.append(
            f"Avg pips/month {avg:.1f} meets minimum but stability issues detected"
        )
        return CrossMonthEvaluationResult(
            verdict=EvaluationVerdict.IMPROVE,
            reasons=reasons,
            stats_summary=stats_summary,
        )

    reasons.append(
        f"Avg pips/month {avg:.1f} below minimum {thresholds.min_avg_pips_per_month:.0f}"
    )
    if reasons and avg > 0:
        return CrossMonthEvaluationResult(
            verdict=EvaluationVerdict.IMPROVE,
            reasons=reasons,
            stats_summary=stats_summary,
        )

    return CrossMonthEvaluationResult(
        verdict=EvaluationVerdict.DISCARD,
        reasons=reasons,
        stats_summary=stats_summary,
    )


# --- Integrated (cross-month + aggregate performance) evaluation ---


@dataclass(frozen=True)
class IntegratedThresholds:
    """Thresholds for integrated adoption evaluation combining aggregate
    performance and monthly stability.

    Values tuned 2026-04-23 to align with the current production bollinger_range_A
    configuration (DUK 2024 + BRK 2025-26: total +1333 / worst -49 / deficit 3-4/12).
    The intent is that the current production params comfortably pass these gates,
    while clearly regressive candidates (e.g. total pips -59%, deficit 3→7) are
    DISCARDed up front. See docs/eval_criteria.md (if added later)."""

    # Aggregate performance
    min_total_pips: float = 1000.0
    min_profit_factor: float = 1.15
    max_drawdown_pips: float = 80.0

    # Monthly stability
    max_deficit_month_ratio: float = 0.30
    max_consecutive_deficit_months: int = 2
    max_monthly_pips_stddev: float = 300.0

    # Monthly average pips
    min_avg_pips_per_month: float = 40.0
    target_avg_pips_per_month: float = 80.0

    @staticmethod
    def default() -> IntegratedThresholds:
        return IntegratedThresholds()


@dataclass(frozen=True)
class IntegratedEvaluationResult:
    verdict: EvaluationVerdict
    reasons: list[str]
    stats_summary: dict[str, object]


def evaluate_integrated(
    agg: AggregateStats,
    thresholds: IntegratedThresholds | None = None,
) -> IntegratedEvaluationResult:
    """Evaluate strategy by combining aggregate performance and monthly stability.

    Returns ADOPT / IMPROVE / DISCARD based on completion_definition section 6:
    - Reject strategies that are strong only in a single month
    - Require both aggregate performance and monthly stability
    """
    if thresholds is None:
        thresholds = IntegratedThresholds.default()

    reasons: list[str] = []
    stats_summary: dict[str, object] = {
        "month_count": agg.month_count,
        "total_pips": agg.total_pips,
        "overall_profit_factor": agg.overall_profit_factor,
        "max_drawdown_pips": agg.max_drawdown_pips,
        "average_pips_per_month": agg.average_pips_per_month,
        "monthly_pips_stddev": agg.monthly_pips_stddev,
        "deficit_month_count": agg.deficit_month_count,
        "max_consecutive_deficit_months": agg.max_consecutive_deficit_months,
    }

    if agg.month_count == 0:
        reasons.append("No monthly data available")
        return IntegratedEvaluationResult(
            verdict=EvaluationVerdict.DISCARD,
            reasons=reasons,
            stats_summary=stats_summary,
        )

    # --- DISCARD checks (hard failures) ---

    if agg.total_pips <= thresholds.min_total_pips:
        reasons.append(
            f"Total pips {agg.total_pips:.1f} <= {thresholds.min_total_pips:.1f}"
        )

    if agg.max_drawdown_pips > thresholds.max_drawdown_pips:
        reasons.append(
            f"Max DD {agg.max_drawdown_pips:.1f} > {thresholds.max_drawdown_pips:.1f}"
        )

    deficit_ratio = agg.deficit_month_count / agg.month_count
    if deficit_ratio > thresholds.max_deficit_month_ratio:
        reasons.append(
            f"Deficit month ratio {deficit_ratio:.0%} "
            f"({agg.deficit_month_count}/{agg.month_count}) "
            f"> {thresholds.max_deficit_month_ratio:.0%}"
        )

    if agg.max_consecutive_deficit_months > thresholds.max_consecutive_deficit_months:
        reasons.append(
            f"Consecutive deficit months {agg.max_consecutive_deficit_months} "
            f"> {thresholds.max_consecutive_deficit_months}"
        )

    # If any hard failure, DISCARD
    if reasons:
        return IntegratedEvaluationResult(
            verdict=EvaluationVerdict.DISCARD,
            reasons=reasons,
            stats_summary=stats_summary,
        )

    # --- Stability checks (soft failures → IMPROVE) ---
    stability_issues: list[str] = []

    if (
        agg.monthly_pips_stddev is not None
        and agg.monthly_pips_stddev > thresholds.max_monthly_pips_stddev
    ):
        stability_issues.append(
            f"Monthly stddev {agg.monthly_pips_stddev:.1f} "
            f"> {thresholds.max_monthly_pips_stddev:.1f}"
        )

    pf = agg.overall_profit_factor
    if pf is not None and pf < thresholds.min_profit_factor:
        stability_issues.append(
            f"PF {pf:.2f} < {thresholds.min_profit_factor:.2f}"
        )

    avg = agg.average_pips_per_month
    if avg < thresholds.min_avg_pips_per_month:
        stability_issues.append(
            f"Avg pips/month {avg:.1f} < min {thresholds.min_avg_pips_per_month:.0f}"
        )

    # --- Verdict ---
    if stability_issues:
        reasons.extend(stability_issues)
        return IntegratedEvaluationResult(
            verdict=EvaluationVerdict.IMPROVE,
            reasons=reasons,
            stats_summary=stats_summary,
        )

    # All checks passed — determine ADOPT vs IMPROVE based on target
    if avg >= thresholds.target_avg_pips_per_month:
        reasons.append(
            f"Avg pips/month {avg:.1f} >= target {thresholds.target_avg_pips_per_month:.0f}; "
            f"all stability checks passed"
        )
        return IntegratedEvaluationResult(
            verdict=EvaluationVerdict.ADOPT,
            reasons=reasons,
            stats_summary=stats_summary,
        )

    reasons.append(
        f"Avg pips/month {avg:.1f} >= min {thresholds.min_avg_pips_per_month:.0f} "
        f"but < target {thresholds.target_avg_pips_per_month:.0f}; "
        f"stability OK"
    )
    return IntegratedEvaluationResult(
        verdict=EvaluationVerdict.ADOPT,
        reasons=reasons,
        stats_summary=stats_summary,
    )


# --- Baseline comparison evaluation ---


@dataclass(frozen=True)
class BaselineComparisonThresholds:
    """Thresholds for deciding whether a candidate is genuinely better than
    the baseline strategy parameters.

    The philosophy (project priority: "退場しない"):
    - worst month と deficit months の非悪化が絶対基準
    - その上で total_pips が baseline 比 +2% 以上なら ADOPT
    - baseline 比 -20% 以上悪化 or worst month が 10pips 以上深化 or
      deficit months が +2 以上増加 or 連続 deficit が +1 以上増加なら DISCARD
    - それ以外は IMPROVE (次イテレーションへ)
    """

    # ADOPT: すべて満たす必要あり
    min_total_pips_improvement_ratio: float = 0.02  # +2%
    max_worst_month_regression_pips: float = 3.0    # 3 pips 以内の深化は許容 (計測ノイズ)
    max_deficit_month_increase: int = 0              # deficit 月数は増やさない
    max_consecutive_deficit_increase: int = 0        # 連続 deficit も増やさない

    # DISCARD: どれか該当で即棄却
    max_total_pips_regression_ratio: float = 0.20    # -20% 以上悪化
    max_worst_month_deepening_pips: float = 10.0     # 10 pips 以上深化
    max_deficit_month_increase_discard: int = 2      # +2 以上増加
    max_consecutive_deficit_increase_discard: int = 1  # +1 以上増加

    @staticmethod
    def default() -> BaselineComparisonThresholds:
        return BaselineComparisonThresholds()


@dataclass(frozen=True)
class BaselineComparison:
    """Numeric deltas between candidate and baseline aggregate stats.

    Sign convention: positive = improvement.
    - total_pips_delta: candidate - baseline (positive = more pips)
    - worst_month_delta: positive = worst month got less negative (less deep loss)
    - deficit_month_delta: positive = fewer deficit months
    - consecutive_deficit_delta: positive = shorter worst streak
    """

    total_pips_delta: float
    total_pips_delta_ratio: float  # delta / abs(baseline). 0 when baseline is 0.
    worst_month_delta: float
    deficit_month_delta: int
    consecutive_deficit_delta: int


@dataclass(frozen=True)
class BaselineComparisonResult:
    verdict: EvaluationVerdict
    reasons: list[str]
    comparison: BaselineComparison
    baseline_summary: dict[str, object]
    candidate_summary: dict[str, object]


def _worst_month_pips(agg: AggregateStats) -> float:
    """Return the worst monthly pips (most negative), or 0.0 if no months."""
    if not agg.monthly_entries:
        return 0.0
    return min(entry.total_pips for entry in agg.monthly_entries)


def _agg_summary(agg: AggregateStats) -> dict[str, object]:
    return {
        "month_count": agg.month_count,
        "total_pips": agg.total_pips,
        "worst_month_pips": _worst_month_pips(agg),
        "deficit_month_count": agg.deficit_month_count,
        "max_consecutive_deficit_months": agg.max_consecutive_deficit_months,
        "overall_profit_factor": agg.overall_profit_factor,
    }


def compare_to_baseline(
    candidate: AggregateStats,
    baseline: AggregateStats,
    thresholds: BaselineComparisonThresholds | None = None,
) -> BaselineComparisonResult:
    """Judge whether *candidate* is genuinely better than *baseline*.

    The verdict prioritizes 崩壊月 (worst month) and deficit months over raw
    total pips, matching the project's "退場しない" policy.

    Returns ADOPT only when all four ADOPT criteria are met:
    - total_pips improved by >= 2%
    - worst month did not deepen by more than 3 pips
    - deficit months did not increase
    - max consecutive deficit months did not increase

    Returns DISCARD when any of the four DISCARD triggers fires:
    - total_pips regressed by >= 20%
    - worst month deepened by >= 10 pips
    - deficit months increased by >= 2
    - max consecutive deficit months increased by >= 1

    Otherwise returns IMPROVE (intermediate: next iteration should try again).
    """
    if thresholds is None:
        thresholds = BaselineComparisonThresholds.default()

    baseline_worst = _worst_month_pips(baseline)
    candidate_worst = _worst_month_pips(candidate)

    pips_delta = candidate.total_pips - baseline.total_pips
    baseline_abs = abs(baseline.total_pips)
    pips_delta_ratio = (pips_delta / baseline_abs) if baseline_abs > 0 else 0.0
    worst_delta = candidate_worst - baseline_worst  # positive = improvement
    deficit_delta_count = (
        baseline.deficit_month_count - candidate.deficit_month_count
    )  # positive = improvement (fewer deficit months)
    consecutive_delta = (
        baseline.max_consecutive_deficit_months
        - candidate.max_consecutive_deficit_months
    )  # positive = improvement

    comparison = BaselineComparison(
        total_pips_delta=pips_delta,
        total_pips_delta_ratio=pips_delta_ratio,
        worst_month_delta=worst_delta,
        deficit_month_delta=deficit_delta_count,
        consecutive_deficit_delta=consecutive_delta,
    )
    baseline_summary = _agg_summary(baseline)
    candidate_summary = _agg_summary(candidate)

    # --- DISCARD triggers (any one fires) ---
    discard_reasons: list[str] = []
    if pips_delta_ratio <= -thresholds.max_total_pips_regression_ratio:
        discard_reasons.append(
            f"total_pips regressed {pips_delta_ratio * 100:+.1f}% "
            f"(limit {-thresholds.max_total_pips_regression_ratio * 100:.0f}%)"
        )
    if worst_delta <= -thresholds.max_worst_month_deepening_pips:
        discard_reasons.append(
            f"worst month deepened by {-worst_delta:.1f} pips "
            f"(baseline {baseline_worst:+.1f} → {candidate_worst:+.1f}; "
            f"limit {thresholds.max_worst_month_deepening_pips})"
        )
    deficit_increase = -deficit_delta_count  # positive if deficit increased
    if deficit_increase >= thresholds.max_deficit_month_increase_discard:
        discard_reasons.append(
            f"deficit months increased by {deficit_increase} "
            f"(baseline {baseline.deficit_month_count} → "
            f"{candidate.deficit_month_count}; "
            f"limit +{thresholds.max_deficit_month_increase_discard - 1})"
        )
    consecutive_increase = -consecutive_delta
    if consecutive_increase >= thresholds.max_consecutive_deficit_increase_discard:
        discard_reasons.append(
            f"consecutive deficit months increased by {consecutive_increase} "
            f"(baseline {baseline.max_consecutive_deficit_months} → "
            f"{candidate.max_consecutive_deficit_months}; "
            f"limit 0)"
        )

    if discard_reasons:
        return BaselineComparisonResult(
            verdict=EvaluationVerdict.DISCARD,
            reasons=discard_reasons,
            comparison=comparison,
            baseline_summary=baseline_summary,
            candidate_summary=candidate_summary,
        )

    # --- ADOPT criteria (all must hold) ---
    adopt_checks: list[tuple[bool, str]] = [
        (
            pips_delta_ratio >= thresholds.min_total_pips_improvement_ratio,
            f"total_pips +{pips_delta_ratio * 100:.1f}% "
            f"(need +{thresholds.min_total_pips_improvement_ratio * 100:.0f}%)",
        ),
        (
            worst_delta >= -thresholds.max_worst_month_regression_pips,
            f"worst month delta {worst_delta:+.1f} pips "
            f"(need >= -{thresholds.max_worst_month_regression_pips})",
        ),
        (
            deficit_delta_count >= -thresholds.max_deficit_month_increase,
            f"deficit months {'same' if deficit_delta_count == 0 else (str(-deficit_delta_count) + ' more' if deficit_delta_count < 0 else str(deficit_delta_count) + ' fewer')}",
        ),
        (
            consecutive_delta >= -thresholds.max_consecutive_deficit_increase,
            f"consecutive deficit {'same' if consecutive_delta == 0 else (str(-consecutive_delta) + ' more' if consecutive_delta < 0 else str(consecutive_delta) + ' fewer')}",
        ),
    ]

    if all(passed for passed, _ in adopt_checks):
        reasons = ["ADOPT: all criteria met - " + "; ".join(msg for _, msg in adopt_checks)]
        return BaselineComparisonResult(
            verdict=EvaluationVerdict.ADOPT,
            reasons=reasons,
            comparison=comparison,
            baseline_summary=baseline_summary,
            candidate_summary=candidate_summary,
        )

    # --- IMPROVE (intermediate) ---
    improve_reasons = [
        "IMPROVE: no adopt criteria fail hard, but not all met - "
        + "; ".join(msg for passed, msg in adopt_checks if not passed)
    ]
    return BaselineComparisonResult(
        verdict=EvaluationVerdict.IMPROVE,
        reasons=improve_reasons,
        comparison=comparison,
        baseline_summary=baseline_summary,
        candidate_summary=candidate_summary,
    )


# --- Log quality gate ---

_LOG_REQUIRED_TRADE_FIELDS = ("trade_id", "lane", "exit_reason")


def check_log_quality(result: BacktestResult) -> tuple[bool, list[str]]:
    """Verify that a BacktestResult can produce valid structured log output.

    Returns (passed, issues). If passed is False, the result should be
    treated as DISCARD because structured logs cannot be generated.
    """
    issues: list[str] = []

    for i, trade in enumerate(result.trades):
        if not trade.trade_id:
            issues.append(f"trade[{i}]: missing trade_id")
        if not trade.lane:
            issues.append(f"trade[{i}]: missing lane (lane_id)")
        if not trade.exit_reason:
            issues.append(f"trade[{i}]: missing exit_reason (reason_code)")

    passed = len(issues) == 0
    if not passed:
        logger.warning(
            "Log quality check failed (%d issues): %s",
            len(issues),
            "; ".join(issues[:5]),
        )
    return passed, issues


def evaluate_backtest_with_log_guard(
    result: BacktestResult,
    thresholds: EvaluationThresholds | None = None,
) -> EvaluationResult:
    """Wrapper around evaluate_backtest that DISCARDs results lacking structured log output."""
    passed, issues = check_log_quality(result)
    if not passed:
        return EvaluationResult(
            verdict=EvaluationVerdict.DISCARD,
            reasons=[f"Structured log output unavailable: {'; '.join(issues[:3])}"],
            stats_summary={
                "strategy_name": result.stats.strategy_name,
                "total_pips": result.stats.total_pips,
                "trades": result.stats.trades,
                "log_quality_issues": len(issues),
            },
        )
    return evaluate_backtest(stats=result.stats, thresholds=thresholds)
