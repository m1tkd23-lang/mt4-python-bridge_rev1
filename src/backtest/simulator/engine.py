# src/backtest/simulator/engine.py
from __future__ import annotations

from backtest.csv_loader import HistoricalBarDataset
from backtest.simulator.decision_log import DecisionLogMixin
from backtest.simulator.generic_runner import GenericRunnerMixin
from backtest.simulator.intrabar import IntrabarMixin
from backtest.simulator.models import (
    BacktestResult,
    BacktestSimulationError,
    IntrabarFillPolicy,
)
from backtest.simulator.position_manager import PositionManagerMixin
from backtest.simulator.snapshots import SnapshotBuilderMixin
from backtest.simulator.stats import StatsMixin
from backtest.simulator.v7_runner import V7RunnerMixin


class BacktestSimulator(
    DecisionLogMixin,
    SnapshotBuilderMixin,
    IntrabarMixin,
    PositionManagerMixin,
    StatsMixin,
    GenericRunnerMixin,
    V7RunnerMixin,
):
    def __init__(
        self,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        pip_size: float,
        sl_pips: float,
        tp_pips: float,
        intrabar_fill_policy: IntrabarFillPolicy = IntrabarFillPolicy.CONSERVATIVE,
    ) -> None:
        self._strategy_name = strategy_name
        self._symbol = symbol
        self._timeframe = timeframe
        self._pip_size = pip_size
        self._sl_pips = sl_pips
        self._tp_pips = tp_pips
        self._intrabar_fill_policy = intrabar_fill_policy

    def run(
        self,
        dataset: HistoricalBarDataset,
        close_open_position_at_end: bool = True,
    ) -> BacktestResult:
        if self._pip_size <= 0:
            raise BacktestSimulationError("pip_size must be greater than zero")
        if self._sl_pips <= 0:
            raise BacktestSimulationError("sl_pips must be greater than zero")
        if self._tp_pips <= 0:
            raise BacktestSimulationError("tp_pips must be greater than zero")

        if self._is_v7_strategy():
            return self._run_v7_fast_path(
                dataset=dataset,
                close_open_position_at_end=close_open_position_at_end,
            )

        return self._run_generic_path(
            dataset=dataset,
            close_open_position_at_end=close_open_position_at_end,
        )

    def _is_v7_strategy(self) -> bool:
        return self._strategy_name in {
            "bollinger_range_v7",
            "bollinger_range_v7_1",
        }

    def _is_multi_lane_strategy(self) -> bool:
        return self._strategy_name in {
            "bollinger_range_v4_6",
            "bollinger_range_v4_6_1",
            "bollinger_combo_AB",
            "bollinger_combo_AB_v1",
        }