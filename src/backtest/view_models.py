# src/backtest/view_models.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backtest.evaluator import EvaluationResult
from backtest.simulator import (
    BacktestDecisionLog,
    BacktestStats,
    ExecutedTrade,
)


@dataclass(frozen=True)
class TradeViewRow:
    trade_no: int
    lane: str
    entry_subtype: str | None

    entry_time: datetime
    exit_time: datetime
    position_type: str
    entry_price: float
    exit_price: float
    pips: float
    exit_reason: str
    cumulative_pips: float
    trade_profit_amount: float
    balance_after_trade: float
    result_label: str
    consecutive_wins: int
    consecutive_losses: int

    entry_signal_reason: str | None
    entry_market_state: str | None
    entry_middle_band: float | None
    entry_upper_band: float | None
    entry_lower_band: float | None
    entry_normalized_band_width: float | None
    entry_range_slope: float | None
    entry_trend_slope: float | None
    entry_trend_current_ma: float | None
    entry_distance_from_middle: float | None

    exit_signal_reason: str | None
    exit_market_state: str | None
    exit_middle_band: float | None
    exit_upper_band: float | None
    exit_lower_band: float | None
    exit_normalized_band_width: float | None
    exit_range_slope: float | None
    exit_trend_slope: float | None
    exit_trend_current_ma: float | None
    exit_distance_from_middle: float | None

    entry_detected_market_state: str | None
    entry_candidate_market_state: str | None
    entry_state_transition_event: str | None
    entry_state_age: int | None
    entry_candidate_age: int | None
    entry_detector_reason: str | None
    entry_range_score: float | None
    entry_transition_up_score: float | None
    entry_transition_down_score: float | None
    entry_trend_up_score: float | None
    entry_trend_down_score: float | None

    exit_detected_market_state: str | None
    exit_candidate_market_state: str | None
    exit_state_transition_event: str | None
    exit_state_age: int | None
    exit_candidate_age: int | None
    exit_detector_reason: str | None
    exit_range_score: float | None
    exit_transition_up_score: float | None
    exit_transition_down_score: float | None
    exit_trend_up_score: float | None
    exit_trend_down_score: float | None

    entry_risk_score: int | None
    entry_upper_band_walk: bool | None
    entry_lower_band_walk: bool | None
    entry_upper_band_walk_hits: int | None
    entry_lower_band_walk_hits: int | None
    entry_dangerous_for_buy: bool | None
    entry_dangerous_for_sell: bool | None
    entry_strong_up_slope: bool | None
    entry_strong_down_slope: bool | None
    entry_latest_slope: float | None
    entry_prev_slope: float | None
    entry_latest_band_width: float | None
    entry_prev_band_width: float | None
    entry_latest_distance: float | None
    entry_prev_distance: float | None


@dataclass(frozen=True)
class EquityPoint:
    trade_no: int
    exit_time: datetime
    cumulative_pips: float
    balance: float


@dataclass(frozen=True)
class DecisionLogViewRow:
    row_no: int
    bar_time: datetime
    action: str
    market_state: str | None
    entry_lane: str | None
    entry_subtype: str | None

    previous_close: float
    latest_close: float

    middle_band: float | None
    upper_band: float | None
    lower_band: float | None
    normalized_band_width: float | None
    range_slope: float | None
    trend_slope: float | None
    trend_current_ma: float | None
    distance_from_middle: float | None

    current_position_ticket: int | None
    current_position_type: str | None

    has_range_position: bool
    has_trend_position: bool
    has_legacy_position: bool

    reason: str


@dataclass(frozen=True)
class BacktestDisplaySummary:
    strategy_name: str
    symbol: str
    timeframe: str
    intrabar_fill_policy: str
    sl_pips: float
    tp_pips: float
    total_bars: int
    processed_bars: int
    trades: int
    wins: int
    losses: int
    win_rate_percent: float
    total_pips: float
    average_pips: float
    average_win_pips: float
    average_loss_pips: float
    profit_factor: float | None
    max_drawdown_pips: float
    initial_balance: float
    final_balance: float
    total_profit_amount: float
    return_rate_percent: float
    max_drawdown_amount: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    verdict: str
    verdict_reasons: list[str]
    final_open_position_type: str | None
    avg_mfe_mae_ratio: float | None = None


def build_trade_view_rows(
    trades: list[ExecutedTrade],
    initial_balance: float,
    money_per_pip: float,
) -> list[TradeViewRow]:
    rows: list[TradeViewRow] = []
    cumulative_pips = 0.0
    balance = initial_balance
    consecutive_wins = 0
    consecutive_losses = 0

    for index, trade in enumerate(trades, start=1):
        cumulative_pips += trade.pips
        trade_profit_amount = trade.pips * money_per_pip
        balance += trade_profit_amount

        if trade.pips > 0:
            result_label = "win"
            consecutive_wins += 1
            consecutive_losses = 0
        elif trade.pips < 0:
            result_label = "loss"
            consecutive_losses += 1
            consecutive_wins = 0
        else:
            result_label = "flat"
            consecutive_wins = 0
            consecutive_losses = 0

        rows.append(
            TradeViewRow(
                trade_no=index,
                lane=trade.lane,
                entry_subtype=trade.entry_subtype,
                entry_time=trade.entry_time,
                exit_time=trade.exit_time,
                position_type=trade.position_type,
                entry_price=trade.entry_price,
                exit_price=trade.exit_price,
                pips=trade.pips,
                exit_reason=trade.exit_reason,
                cumulative_pips=cumulative_pips,
                trade_profit_amount=trade_profit_amount,
                balance_after_trade=balance,
                result_label=result_label,
                consecutive_wins=consecutive_wins,
                consecutive_losses=consecutive_losses,
                entry_signal_reason=trade.entry_signal_reason,
                entry_market_state=trade.entry_market_state,
                entry_middle_band=trade.entry_middle_band,
                entry_upper_band=trade.entry_upper_band,
                entry_lower_band=trade.entry_lower_band,
                entry_normalized_band_width=trade.entry_normalized_band_width,
                entry_range_slope=trade.entry_range_slope,
                entry_trend_slope=trade.entry_trend_slope,
                entry_trend_current_ma=trade.entry_trend_current_ma,
                entry_distance_from_middle=trade.entry_distance_from_middle,
                exit_signal_reason=trade.exit_signal_reason,
                exit_market_state=trade.exit_market_state,
                exit_middle_band=trade.exit_middle_band,
                exit_upper_band=trade.exit_upper_band,
                exit_lower_band=trade.exit_lower_band,
                exit_normalized_band_width=trade.exit_normalized_band_width,
                exit_range_slope=trade.exit_range_slope,
                exit_trend_slope=trade.exit_trend_slope,
                exit_trend_current_ma=trade.exit_trend_current_ma,
                exit_distance_from_middle=trade.exit_distance_from_middle,
                entry_detected_market_state=trade.entry_detected_market_state,
                entry_candidate_market_state=trade.entry_candidate_market_state,
                entry_state_transition_event=trade.entry_state_transition_event,
                entry_state_age=trade.entry_state_age,
                entry_candidate_age=trade.entry_candidate_age,
                entry_detector_reason=trade.entry_detector_reason,
                entry_range_score=trade.entry_range_score,
                entry_transition_up_score=trade.entry_transition_up_score,
                entry_transition_down_score=trade.entry_transition_down_score,
                entry_trend_up_score=trade.entry_trend_up_score,
                entry_trend_down_score=trade.entry_trend_down_score,
                exit_detected_market_state=trade.exit_detected_market_state,
                exit_candidate_market_state=trade.exit_candidate_market_state,
                exit_state_transition_event=trade.exit_state_transition_event,
                exit_state_age=trade.exit_state_age,
                exit_candidate_age=trade.exit_candidate_age,
                exit_detector_reason=trade.exit_detector_reason,
                exit_range_score=trade.exit_range_score,
                exit_transition_up_score=trade.exit_transition_up_score,
                exit_transition_down_score=trade.exit_transition_down_score,
                exit_trend_up_score=trade.exit_trend_up_score,
                exit_trend_down_score=trade.exit_trend_down_score,
                entry_risk_score=trade.entry_risk_score,
                entry_upper_band_walk=trade.entry_upper_band_walk,
                entry_lower_band_walk=trade.entry_lower_band_walk,
                entry_upper_band_walk_hits=trade.entry_upper_band_walk_hits,
                entry_lower_band_walk_hits=trade.entry_lower_band_walk_hits,
                entry_dangerous_for_buy=trade.entry_dangerous_for_buy,
                entry_dangerous_for_sell=trade.entry_dangerous_for_sell,
                entry_strong_up_slope=trade.entry_strong_up_slope,
                entry_strong_down_slope=trade.entry_strong_down_slope,
                entry_latest_slope=trade.entry_latest_slope,
                entry_prev_slope=trade.entry_prev_slope,
                entry_latest_band_width=trade.entry_latest_band_width,
                entry_prev_band_width=trade.entry_prev_band_width,
                entry_latest_distance=trade.entry_latest_distance,
                entry_prev_distance=trade.entry_prev_distance,
            )
        )

    return rows


def build_equity_points(
    trade_rows: list[TradeViewRow],
) -> list[EquityPoint]:
    return [
        EquityPoint(
            trade_no=row.trade_no,
            exit_time=row.exit_time,
            cumulative_pips=row.cumulative_pips,
            balance=row.balance_after_trade,
        )
        for row in trade_rows
    ]


def build_decision_log_view_rows(
    decision_logs: list[BacktestDecisionLog],
) -> list[DecisionLogViewRow]:
    rows: list[DecisionLogViewRow] = []

    for index, log in enumerate(decision_logs, start=1):
        rows.append(
            DecisionLogViewRow(
                row_no=index,
                bar_time=log.bar_time,
                action=log.action,
                market_state=log.market_state,
                entry_lane=log.entry_lane,
                entry_subtype=log.entry_subtype,
                previous_close=log.previous_close,
                latest_close=log.latest_close,
                middle_band=log.middle_band,
                upper_band=log.upper_band,
                lower_band=log.lower_band,
                normalized_band_width=log.normalized_band_width,
                range_slope=log.range_slope,
                trend_slope=log.trend_slope,
                trend_current_ma=log.trend_current_ma,
                distance_from_middle=log.distance_from_middle,
                current_position_ticket=log.current_position_ticket,
                current_position_type=log.current_position_type,
                has_range_position=log.has_range_position,
                has_trend_position=log.has_trend_position,
                has_legacy_position=log.has_legacy_position,
                reason=log.reason,
            )
        )

    return rows


def build_display_summary(
    stats: BacktestStats,
    evaluation: EvaluationResult,
    initial_balance: float,
    money_per_pip: float,
    trade_rows: list[TradeViewRow],
) -> BacktestDisplaySummary:
    total_profit_amount = stats.total_pips * money_per_pip
    final_balance = initial_balance + total_profit_amount
    return_rate_percent = (
        (total_profit_amount / initial_balance) * 100.0
        if initial_balance != 0
        else 0.0
    )
    max_drawdown_amount = stats.max_drawdown_pips * money_per_pip

    max_consecutive_wins = 0
    max_consecutive_losses = 0
    for row in trade_rows:
        if row.consecutive_wins > max_consecutive_wins:
            max_consecutive_wins = row.consecutive_wins
        if row.consecutive_losses > max_consecutive_losses:
            max_consecutive_losses = row.consecutive_losses

    return BacktestDisplaySummary(
        strategy_name=stats.strategy_name,
        symbol=stats.symbol,
        timeframe=stats.timeframe,
        intrabar_fill_policy=stats.intrabar_fill_policy,
        sl_pips=stats.sl_pips,
        tp_pips=stats.tp_pips,
        total_bars=stats.total_bars,
        processed_bars=stats.processed_bars,
        trades=stats.trades,
        wins=stats.wins,
        losses=stats.losses,
        win_rate_percent=stats.win_rate,
        total_pips=stats.total_pips,
        average_pips=stats.average_pips,
        average_win_pips=stats.average_win_pips,
        average_loss_pips=stats.average_loss_pips,
        profit_factor=stats.profit_factor,
        max_drawdown_pips=stats.max_drawdown_pips,
        initial_balance=initial_balance,
        final_balance=final_balance,
        total_profit_amount=total_profit_amount,
        return_rate_percent=return_rate_percent,
        max_drawdown_amount=max_drawdown_amount,
        max_consecutive_wins=max_consecutive_wins,
        max_consecutive_losses=max_consecutive_losses,
        verdict=evaluation.verdict.value,
        verdict_reasons=list(evaluation.reasons),
        final_open_position_type=stats.final_open_position_type,
        avg_mfe_mae_ratio=stats.avg_mfe_mae_ratio,
    )