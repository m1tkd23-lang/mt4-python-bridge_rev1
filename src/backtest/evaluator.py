# src/backtest/evaluator.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

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
