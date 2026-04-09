# src/backtest/simulator/__init__.py
from backtest.simulator.engine import BacktestSimulator
from backtest.simulator.models import (
    BacktestDecisionLog,
    BacktestResult,
    BacktestSimulationError,
    BacktestStats,
    ExecutedTrade,
    IntrabarFillPolicy,
    SimulatedPosition,
    StateSegment,
)
from backtest.simulator.trade_logger import (
    build_trade_lifecycle_events,
    write_trade_log_jsonl,
)

__all__ = [
    "BacktestSimulator",
    "BacktestDecisionLog",
    "BacktestResult",
    "BacktestSimulationError",
    "BacktestStats",
    "ExecutedTrade",
    "IntrabarFillPolicy",
    "SimulatedPosition",
    "StateSegment",
    "build_trade_lifecycle_events",
    "write_trade_log_jsonl",
]