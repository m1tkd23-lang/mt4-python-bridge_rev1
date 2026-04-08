# src/backtest/aggregate_stats.py
from __future__ import annotations

import statistics
from dataclasses import dataclass

from backtest.simulator.models import BacktestStats  # direct import to avoid engine chain


@dataclass(frozen=True)
class MonthlyPipsEntry:
    label: str
    total_pips: float


@dataclass(frozen=True)
class AggregateStats:
    month_count: int
    total_trades: int
    total_wins: int
    total_losses: int
    total_pips: float
    overall_win_rate: float
    overall_profit_factor: float | None
    max_drawdown_pips: float
    average_pips_per_month: float
    monthly_pips_stddev: float | None
    deficit_month_count: int
    max_consecutive_deficit_months: int
    monthly_entries: list[MonthlyPipsEntry]


def aggregate_monthly_stats(
    monthly_stats: list[tuple[str, BacktestStats]],
) -> AggregateStats:
    """Aggregate multiple monthly BacktestStats into overall statistics.

    Args:
        monthly_stats: List of (month_label, BacktestStats) tuples.

    Returns:
        AggregateStats with overall and variance metrics.
    """
    if not monthly_stats:
        return AggregateStats(
            month_count=0,
            total_trades=0,
            total_wins=0,
            total_losses=0,
            total_pips=0.0,
            overall_win_rate=0.0,
            overall_profit_factor=None,
            max_drawdown_pips=0.0,
            average_pips_per_month=0.0,
            monthly_pips_stddev=None,
            deficit_month_count=0,
            max_consecutive_deficit_months=0,
            monthly_entries=[],
        )

    month_count = len(monthly_stats)
    total_trades = sum(s.trades for _, s in monthly_stats)
    total_wins = sum(s.wins for _, s in monthly_stats)
    total_losses = sum(s.losses for _, s in monthly_stats)
    total_pips = sum(s.total_pips for _, s in monthly_stats)

    overall_win_rate = (total_wins / total_trades * 100.0) if total_trades > 0 else 0.0

    gross_profit = 0.0
    gross_loss = 0.0
    for _, s in monthly_stats:
        # Use per-trade level gross profit/loss for accurate PF
        # Approximate from win/loss counts and averages
        gross_profit += s.average_win_pips * s.wins if s.wins > 0 else 0.0
        gross_loss += abs(s.average_loss_pips) * s.losses if s.losses > 0 else 0.0

    if gross_loss == 0:
        overall_profit_factor = None if gross_profit == 0 else float("inf")
    else:
        overall_profit_factor = gross_profit / gross_loss

    max_drawdown_pips = max(s.max_drawdown_pips for _, s in monthly_stats)

    monthly_pips_list = [s.total_pips for _, s in monthly_stats]
    average_pips_per_month = total_pips / month_count

    if month_count >= 2:
        monthly_pips_stddev = statistics.stdev(monthly_pips_list)
    else:
        monthly_pips_stddev = None

    deficit_month_count = sum(1 for p in monthly_pips_list if p < 0)

    max_consecutive_deficit = 0
    current_consecutive = 0
    for p in monthly_pips_list:
        if p < 0:
            current_consecutive += 1
            if current_consecutive > max_consecutive_deficit:
                max_consecutive_deficit = current_consecutive
        else:
            current_consecutive = 0

    monthly_entries = [
        MonthlyPipsEntry(label=label, total_pips=s.total_pips)
        for label, s in monthly_stats
    ]

    return AggregateStats(
        month_count=month_count,
        total_trades=total_trades,
        total_wins=total_wins,
        total_losses=total_losses,
        total_pips=total_pips,
        overall_win_rate=overall_win_rate,
        overall_profit_factor=overall_profit_factor,
        max_drawdown_pips=max_drawdown_pips,
        average_pips_per_month=average_pips_per_month,
        monthly_pips_stddev=monthly_pips_stddev,
        deficit_month_count=deficit_month_count,
        max_consecutive_deficit_months=max_consecutive_deficit,
        monthly_entries=monthly_entries,
    )
