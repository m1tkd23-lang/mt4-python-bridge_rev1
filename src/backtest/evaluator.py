# src/backtest/evaluator.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backtest.aggregate_stats import AggregateStats
from backtest.simulator import BacktestStats


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
    performance and monthly stability.  Values are based on
    completion_definition section 6."""

    # Aggregate performance
    min_total_pips: float = 0.0
    min_profit_factor: float = 1.0
    max_drawdown_pips: float = 200.0

    # Monthly stability
    max_deficit_month_ratio: float = 0.5
    max_consecutive_deficit_months: int = 2
    max_monthly_pips_stddev: float = 300.0

    # Monthly average pips (section 6: 150-200 pips target)
    min_avg_pips_per_month: float = 150.0
    target_avg_pips_per_month: float = 200.0

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
