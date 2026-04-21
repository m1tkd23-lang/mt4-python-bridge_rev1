# src/backtest/simulator/intrabar.py
from __future__ import annotations

from backtest.csv_loader import HistoricalBarRow
from backtest.simulator.models import (
    BacktestSimulationError,
    ExecutedTrade,
    IntrabarFillPolicy,
    SimulatedPosition,
)


class IntrabarMixin:
    def _check_intrabar_exit(
        self,
        simulated_position: SimulatedPosition,
        current_row: HistoricalBarRow,
        current_bar_index: int | None = None,
    ) -> ExecutedTrade | None:
        if simulated_position.sl_price is None or simulated_position.tp_price is None:
            return None

        if simulated_position.position_type == "buy":
            sl_hit = current_row.low <= simulated_position.sl_price
            tp_hit = current_row.high >= simulated_position.tp_price

            if not sl_hit and not tp_hit:
                return None

            if sl_hit and tp_hit:
                exit_reason = self._resolve_same_bar_conflict_reason(
                    unfavorable_reason="sl_same_bar_conflict",
                    favorable_reason="tp_same_bar_conflict",
                )
                exit_price = (
                    simulated_position.sl_price
                    if exit_reason.startswith("sl")
                    else simulated_position.tp_price
                )
                return self._close_position(
                    simulated_position=simulated_position,
                    exit_time=current_row.time,
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                    exit_decision=None,
                    exit_absolute_bar_index=current_bar_index,
                )

            if sl_hit:
                return self._close_position(
                    simulated_position=simulated_position,
                    exit_time=current_row.time,
                    exit_price=simulated_position.sl_price,
                    exit_reason="sl_hit",
                    exit_decision=None,
                    exit_absolute_bar_index=current_bar_index,
                )

            return self._close_position(
                simulated_position=simulated_position,
                exit_time=current_row.time,
                exit_price=simulated_position.tp_price,
                exit_reason="tp_hit",
                exit_decision=None,
                exit_absolute_bar_index=current_bar_index,
            )

        if simulated_position.position_type == "sell":
            sl_hit = current_row.high >= simulated_position.sl_price
            tp_hit = current_row.low <= simulated_position.tp_price

            if not sl_hit and not tp_hit:
                return None

            if sl_hit and tp_hit:
                exit_reason = self._resolve_same_bar_conflict_reason(
                    unfavorable_reason="sl_same_bar_conflict",
                    favorable_reason="tp_same_bar_conflict",
                )
                exit_price = (
                    simulated_position.sl_price
                    if exit_reason.startswith("sl")
                    else simulated_position.tp_price
                )
                return self._close_position(
                    simulated_position=simulated_position,
                    exit_time=current_row.time,
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                    exit_decision=None,
                    exit_absolute_bar_index=current_bar_index,
                )

            if sl_hit:
                return self._close_position(
                    simulated_position=simulated_position,
                    exit_time=current_row.time,
                    exit_price=simulated_position.sl_price,
                    exit_reason="sl_hit",
                    exit_decision=None,
                    exit_absolute_bar_index=current_bar_index,
                )

            return self._close_position(
                simulated_position=simulated_position,
                exit_time=current_row.time,
                exit_price=simulated_position.tp_price,
                exit_reason="tp_hit",
                exit_decision=None,
                exit_absolute_bar_index=current_bar_index,
            )

        raise BacktestSimulationError(
            f"Unsupported simulated position type: {simulated_position.position_type}"
        )

    def _resolve_same_bar_conflict_reason(
        self,
        unfavorable_reason: str,
        favorable_reason: str,
    ) -> str:
        if self._intrabar_fill_policy == IntrabarFillPolicy.CONSERVATIVE:
            return unfavorable_reason
        if self._intrabar_fill_policy == IntrabarFillPolicy.OPTIMISTIC:
            return favorable_reason
        raise BacktestSimulationError(
            f"Unsupported intrabar fill policy: {self._intrabar_fill_policy}"
        )