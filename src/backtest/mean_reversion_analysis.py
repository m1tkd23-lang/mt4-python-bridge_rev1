# src/backtest/mean_reversion_analysis.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from backtest.csv_loader import HistoricalBarDataset
from backtest.simulator.models import BacktestResult, ExecutedTrade

if TYPE_CHECKING:
    from backtest.service import BacktestRunArtifacts


@dataclass(frozen=True)
class MeanReversionRecord:
    """Per-trade mean reversion analysis for a range-lane entry."""

    trade_id: str
    entry_time: object
    exit_time: object
    position_type: str
    entry_price: float
    entry_middle_band: float

    bars_to_mean_reversion: int | None
    success_within_3: bool
    success_within_5: bool
    success_within_8: bool
    success_within_12: bool
    max_progress_to_middle_ratio: float | None
    max_adverse_excursion_from_entry: float | None

    holding_bars: int | None
    pips: float
    exit_reason: str


@dataclass(frozen=True)
class MeanReversionSummary:
    """Aggregated mean reversion statistics across range-lane trades."""

    total_range_trades: int
    reversion_success_count: int
    reversion_failure_count: int
    success_rate: float | None

    success_within_3_count: int
    success_within_5_count: int
    success_within_8_count: int
    success_within_12_count: int

    success_within_3_rate: float | None
    success_within_5_rate: float | None
    success_within_8_rate: float | None
    success_within_12_rate: float | None

    avg_bars_to_reversion: float | None
    avg_max_progress_ratio: float | None
    avg_max_adverse_excursion: float | None


def _build_time_index(dataset: HistoricalBarDataset) -> dict[datetime, int]:
    return {row.time: i for i, row in enumerate(dataset.rows)}


def _is_range_lane_trade(trade: ExecutedTrade) -> bool:
    lane = trade.lane.strip().lower()
    return lane in ("range", "legacy")

def _analyze_single_trade(
    trade: ExecutedTrade,
    dataset: HistoricalBarDataset,
    time_index: dict[datetime, int],
) -> MeanReversionRecord | None:
    if trade.entry_middle_band is None:
        return None

    entry_bar_idx = time_index.get(trade.entry_time)
    exit_bar_idx = time_index.get(trade.exit_time)
    if entry_bar_idx is None or exit_bar_idx is None:
        return None

    rows = dataset.rows
    middle = trade.entry_middle_band
    entry_price = trade.entry_price
    is_buy = trade.position_type == "buy"

    bars_to_reversion: int | None = None
    max_progress_ratio: float | None = None
    max_adverse: float | None = None

    entry_to_middle = middle - entry_price if is_buy else entry_price - middle

    for offset in range(1, exit_bar_idx - entry_bar_idx + 1):
        bar_idx = entry_bar_idx + offset
        if bar_idx >= len(rows):
            break

        bar = rows[bar_idx]
        close = bar.close

        if is_buy:
            reached = close >= middle
            progress = (close - entry_price) / entry_to_middle if entry_to_middle != 0 else 0.0
            adverse = max(0.0, entry_price - bar.low)
        else:
            reached = close <= middle
            progress = (entry_price - close) / entry_to_middle if entry_to_middle != 0 else 0.0
            adverse = max(0.0, bar.high - entry_price)

        if max_progress_ratio is None or progress > max_progress_ratio:
            max_progress_ratio = progress
        if max_adverse is None or adverse > max_adverse:
            max_adverse = adverse

        if reached and bars_to_reversion is None:
            bars_to_reversion = offset

    success_3 = bars_to_reversion is not None and bars_to_reversion <= 3
    success_5 = bars_to_reversion is not None and bars_to_reversion <= 5
    success_8 = bars_to_reversion is not None and bars_to_reversion <= 8
    success_12 = bars_to_reversion is not None and bars_to_reversion <= 12

    return MeanReversionRecord(
        trade_id=trade.trade_id,
        entry_time=trade.entry_time,
        exit_time=trade.exit_time,
        position_type=trade.position_type,
        entry_price=entry_price,
        entry_middle_band=middle,
        bars_to_mean_reversion=bars_to_reversion,
        success_within_3=success_3,
        success_within_5=success_5,
        success_within_8=success_8,
        success_within_12=success_12,
        max_progress_to_middle_ratio=max_progress_ratio,
        max_adverse_excursion_from_entry=max_adverse,
        holding_bars=trade.holding_bars,
        pips=trade.pips,
        exit_reason=trade.exit_reason,
    )


def analyze_mean_reversion(
    result: BacktestResult,
    dataset: HistoricalBarDataset,
) -> list[MeanReversionRecord]:
    """Analyze mean reversion success/failure for all range-lane trades."""
    time_index = _build_time_index(dataset)
    records: list[MeanReversionRecord] = []

    for trade in result.trades:
        if not _is_range_lane_trade(trade):
            continue
        record = _analyze_single_trade(trade, dataset, time_index)
        if record is not None:
            records.append(record)

    return records


def summarize_mean_reversion(
    records: list[MeanReversionRecord],
) -> MeanReversionSummary:
    """Aggregate mean reversion records into summary statistics."""
    total = len(records)
    if total == 0:
        return MeanReversionSummary(
            total_range_trades=0,
            reversion_success_count=0,
            reversion_failure_count=0,
            success_rate=None,
            success_within_3_count=0,
            success_within_5_count=0,
            success_within_8_count=0,
            success_within_12_count=0,
            success_within_3_rate=None,
            success_within_5_rate=None,
            success_within_8_rate=None,
            success_within_12_rate=None,
            avg_bars_to_reversion=None,
            avg_max_progress_ratio=None,
            avg_max_adverse_excursion=None,
        )

    success_count = sum(1 for r in records if r.bars_to_mean_reversion is not None)
    failure_count = total - success_count

    s3 = sum(1 for r in records if r.success_within_3)
    s5 = sum(1 for r in records if r.success_within_5)
    s8 = sum(1 for r in records if r.success_within_8)
    s12 = sum(1 for r in records if r.success_within_12)

    bars_values = [
        r.bars_to_mean_reversion
        for r in records
        if r.bars_to_mean_reversion is not None
    ]
    avg_bars = sum(bars_values) / len(bars_values) if bars_values else None

    progress_values = [
        r.max_progress_to_middle_ratio
        for r in records
        if r.max_progress_to_middle_ratio is not None
    ]
    avg_progress = (
        sum(progress_values) / len(progress_values) if progress_values else None
    )

    adverse_values = [
        r.max_adverse_excursion_from_entry
        for r in records
        if r.max_adverse_excursion_from_entry is not None
    ]
    avg_adverse = (
        sum(adverse_values) / len(adverse_values) if adverse_values else None
    )

    return MeanReversionSummary(
        total_range_trades=total,
        reversion_success_count=success_count,
        reversion_failure_count=failure_count,
        success_rate=success_count / total * 100.0,
        success_within_3_count=s3,
        success_within_5_count=s5,
        success_within_8_count=s8,
        success_within_12_count=s12,
        success_within_3_rate=s3 / total * 100.0,
        success_within_5_rate=s5 / total * 100.0,
        success_within_8_rate=s8 / total * 100.0,
        success_within_12_rate=s12 / total * 100.0,
        avg_bars_to_reversion=avg_bars,
        avg_max_progress_ratio=avg_progress,
        avg_max_adverse_excursion=avg_adverse,
    )


@dataclass(frozen=True)
class AllMonthsMeanReversionSummary:
    """Mean reversion summaries across months and over the full period."""

    monthly: list[tuple[str, MeanReversionSummary]]
    all_period: MeanReversionSummary


def analyze_all_months_mean_reversion(
    monthly_artifacts: list[tuple[str, "BacktestRunArtifacts"]],
) -> AllMonthsMeanReversionSummary:
    """Compute per-month and full-period MeanReversionSummary from monthly artifacts.

    Each entry of ``monthly_artifacts`` is ``(label, BacktestRunArtifacts)``;
    the artifact's ``backtest_result`` and ``dataset`` are used as inputs.
    Months with zero range-lane trades produce an empty ``MeanReversionSummary``.
    The all-period summary is built by re-aggregating every record across all
    months so averages reflect the true full-period distribution.
    """
    monthly_summaries: list[tuple[str, MeanReversionSummary]] = []
    all_records: list[MeanReversionRecord] = []

    for label, artifacts in monthly_artifacts:
        records = analyze_mean_reversion(
            result=artifacts.backtest_result,
            dataset=artifacts.dataset,
        )
        monthly_summaries.append((label, summarize_mean_reversion(records)))
        all_records.extend(records)

    return AllMonthsMeanReversionSummary(
        monthly=monthly_summaries,
        all_period=summarize_mean_reversion(all_records),
    )
