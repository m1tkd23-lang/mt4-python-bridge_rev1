# src/backtest/simulator/models.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IntrabarFillPolicy(str, Enum):
    CONSERVATIVE = "conservative"
    OPTIMISTIC = "optimistic"


@dataclass(frozen=True)
class SimulatedPosition:
    lane: str
    entry_subtype: str | None
    position_type: str
    entry_price: float
    entry_time: object
    ticket: int
    sl_price: float | None
    tp_price: float | None
    trade_id: str
    entry_bar_index: int = 0

    entry_signal_reason: str | None = None
    entry_market_state: str | None = None
    entry_middle_band: float | None = None
    entry_upper_band: float | None = None
    entry_lower_band: float | None = None
    entry_normalized_band_width: float | None = None
    entry_range_slope: float | None = None
    entry_trend_slope: float | None = None
    entry_trend_current_ma: float | None = None
    entry_distance_from_middle: float | None = None

    entry_detected_market_state: str | None = None
    entry_candidate_market_state: str | None = None
    entry_state_transition_event: str | None = None
    entry_state_age: int | None = None
    entry_candidate_age: int | None = None
    entry_detector_reason: str | None = None
    entry_range_score: float | None = None
    entry_transition_up_score: float | None = None
    entry_transition_down_score: float | None = None
    entry_trend_up_score: float | None = None
    entry_trend_down_score: float | None = None

    entry_risk_score: int | None = None
    entry_upper_band_walk: bool | None = None
    entry_lower_band_walk: bool | None = None
    entry_upper_band_walk_hits: int | None = None
    entry_lower_band_walk_hits: int | None = None
    entry_dangerous_for_buy: bool | None = None
    entry_dangerous_for_sell: bool | None = None
    entry_strong_up_slope: bool | None = None
    entry_strong_down_slope: bool | None = None
    entry_latest_slope: float | None = None
    entry_prev_slope: float | None = None
    entry_latest_band_width: float | None = None
    entry_prev_band_width: float | None = None
    entry_latest_distance: float | None = None
    entry_prev_distance: float | None = None

    max_favorable_price: float | None = None
    max_adverse_price: float | None = None


@dataclass(frozen=True)
class ExecutedTrade:
    lane: str
    entry_subtype: str | None

    entry_time: object
    exit_time: object
    position_type: str
    entry_price: float
    exit_price: float
    pips: float
    exit_reason: str
    trade_id: str

    entry_signal_reason: str | None = None
    entry_market_state: str | None = None
    entry_middle_band: float | None = None
    entry_upper_band: float | None = None
    entry_lower_band: float | None = None
    entry_normalized_band_width: float | None = None
    entry_range_slope: float | None = None
    entry_trend_slope: float | None = None
    entry_trend_current_ma: float | None = None
    entry_distance_from_middle: float | None = None

    exit_signal_reason: str | None = None
    exit_market_state: str | None = None
    exit_middle_band: float | None = None
    exit_upper_band: float | None = None
    exit_lower_band: float | None = None
    exit_normalized_band_width: float | None = None
    exit_range_slope: float | None = None
    exit_trend_slope: float | None = None
    exit_trend_current_ma: float | None = None
    exit_distance_from_middle: float | None = None

    entry_detected_market_state: str | None = None
    entry_candidate_market_state: str | None = None
    entry_state_transition_event: str | None = None
    entry_state_age: int | None = None
    entry_candidate_age: int | None = None
    entry_detector_reason: str | None = None
    entry_range_score: float | None = None
    entry_transition_up_score: float | None = None
    entry_transition_down_score: float | None = None
    entry_trend_up_score: float | None = None
    entry_trend_down_score: float | None = None

    exit_detected_market_state: str | None = None
    exit_candidate_market_state: str | None = None
    exit_state_transition_event: str | None = None
    exit_state_age: int | None = None
    exit_candidate_age: int | None = None
    exit_detector_reason: str | None = None
    exit_range_score: float | None = None
    exit_transition_up_score: float | None = None
    exit_transition_down_score: float | None = None
    exit_trend_up_score: float | None = None
    exit_trend_down_score: float | None = None

    entry_risk_score: int | None = None
    entry_upper_band_walk: bool | None = None
    entry_lower_band_walk: bool | None = None
    entry_upper_band_walk_hits: int | None = None
    entry_lower_band_walk_hits: int | None = None
    entry_dangerous_for_buy: bool | None = None
    entry_dangerous_for_sell: bool | None = None
    entry_strong_up_slope: bool | None = None
    entry_strong_down_slope: bool | None = None
    entry_latest_slope: float | None = None
    entry_prev_slope: float | None = None
    entry_latest_band_width: float | None = None
    entry_prev_band_width: float | None = None
    entry_latest_distance: float | None = None
    entry_prev_distance: float | None = None

    mfe_pips: float | None = None
    mae_pips: float | None = None
    holding_bars: int | None = None


@dataclass(frozen=True)
class StateSegment:
    start_time: object
    end_time: object
    state: str


@dataclass(frozen=True)
class BacktestDecisionLog:
    bar_time: object
    action: str
    reason: str
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


@dataclass(frozen=True)
class BacktestStats:
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
    win_rate: float
    total_pips: float
    average_pips: float
    average_win_pips: float
    average_loss_pips: float
    profit_factor: float | None
    max_drawdown_pips: float
    gross_profit_pips: float
    gross_loss_pips: float
    final_open_position_type: str | None
    avg_mfe_mae_ratio: float | None = None


@dataclass(frozen=True)
class BacktestResult:
    stats: BacktestStats
    trades: list[ExecutedTrade]
    state_segments: list[StateSegment]
    decision_logs: list[BacktestDecisionLog]


class BacktestSimulationError(Exception):
    pass