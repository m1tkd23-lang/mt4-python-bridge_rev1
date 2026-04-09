# src/backtest/simulator/stats.py
from __future__ import annotations

from backtest.simulator.models import BacktestStats, ExecutedTrade


class StatsMixin:
    def _build_stats(
        self,
        total_bars: int,
        processed_bars: int,
        executed_trades: list[ExecutedTrade],
        final_open_position_type: str | None,
    ) -> BacktestStats:
        wins = sum(1 for trade in executed_trades if trade.pips > 0)
        losses = sum(1 for trade in executed_trades if trade.pips < 0)
        total_pips = sum(trade.pips for trade in executed_trades)
        average_pips = total_pips / len(executed_trades) if executed_trades else 0.0

        win_pips = [trade.pips for trade in executed_trades if trade.pips > 0]
        loss_pips = [trade.pips for trade in executed_trades if trade.pips < 0]

        average_win_pips = sum(win_pips) / len(win_pips) if win_pips else 0.0
        average_loss_pips = sum(loss_pips) / len(loss_pips) if loss_pips else 0.0

        gross_profit = sum(win_pips)
        gross_loss = abs(sum(loss_pips))
        if gross_loss == 0:
            profit_factor = None if gross_profit == 0 else float("inf")
        else:
            profit_factor = gross_profit / gross_loss

        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for trade in executed_trades:
            equity += trade.pips
            if equity > peak:
                peak = equity
            drawdown = peak - equity
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        mfe_mae_ratios = []
        for trade in executed_trades:
            if trade.mfe_pips is not None and trade.mae_pips is not None:
                if trade.mae_pips != 0:
                    mfe_mae_ratios.append(trade.mfe_pips / trade.mae_pips)
        avg_mfe_mae_ratio = (
            sum(mfe_mae_ratios) / len(mfe_mae_ratios)
            if mfe_mae_ratios
            else None
        )

        trades = len(executed_trades)
        win_rate = (wins / trades * 100.0) if trades else 0.0

        return BacktestStats(
            strategy_name=self._strategy_name,
            symbol=self._symbol,
            timeframe=self._timeframe,
            intrabar_fill_policy=self._intrabar_fill_policy.value,
            sl_pips=self._sl_pips,
            tp_pips=self._tp_pips,
            total_bars=total_bars,
            processed_bars=processed_bars,
            trades=trades,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            total_pips=total_pips,
            average_pips=average_pips,
            average_win_pips=average_win_pips,
            average_loss_pips=average_loss_pips,
            profit_factor=profit_factor,
            max_drawdown_pips=max_drawdown,
            gross_profit_pips=gross_profit,
            gross_loss_pips=gross_loss,
            final_open_position_type=final_open_position_type,
            avg_mfe_mae_ratio=avg_mfe_mae_ratio,
        )