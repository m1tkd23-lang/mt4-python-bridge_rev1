# src/backtest_gui_app/presenters/result_presenter.py
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from backtest.service import BacktestRunArtifacts
from backtest.view_models import DecisionLogViewRow, EquityPoint, TradeViewRow
from backtest_gui_app.views.chart_overview_tab import ChartOverviewTab
from backtest_gui_app.views.input_panel import InputPanel
from backtest_gui_app.views.result_tabs import ResultTabs
from backtest_gui_app.views.summary_panel import SummaryPanel


class BacktestResultPresenter:
    def __init__(
        self,
        summary_panel: SummaryPanel,
        result_tabs: ResultTabs,
        input_panel: InputPanel,
        chart_overview_tab: ChartOverviewTab,
    ) -> None:
        self._summary_panel = summary_panel
        self._result_tabs = result_tabs
        self._input_panel = input_panel
        self._chart_overview_tab = chart_overview_tab

    def clear_result_views(self) -> None:
        for label in self._summary_panel.summary_labels.values():
            label.setText("-")
        self._summary_panel.reasons_text.clear()

        self._clear_result_tabs(self._result_tabs)
        self._clear_result_tabs(self._chart_overview_tab.detail_tabs)

        self._chart_overview_tab.strategy_value_label.setText("-")
        self._chart_overview_tab.csv_value_label.setText("-")
        self._chart_overview_tab.linked_chart.clear_chart("Linked trade chart")

        self._input_panel.notes_text.setPlainText(
            "Ready.\n"
            "- Select a strategy.\n"
            "- Select a CSV.\n"
            "- Set pip size / SL / TP / initial balance / risk %.\n"
            "- Risk model: fixed initial balance basis.\n"
            "- USDJPY only: 1.0 lot = about 1000 yen/pip.\n"
            "- Run backtest."
        )

    def apply_artifacts_to_ui(self, artifacts: BacktestRunArtifacts) -> None:
        self._populate_summary(artifacts)
        self._populate_primary_tabs(artifacts)
        self._populate_chart_overview_tab(artifacts)
        self._populate_notes(artifacts)

    def _clear_result_tabs(self, result_tabs: ResultTabs) -> None:
        result_tabs.trades_table.setRowCount(0)
        if result_tabs.pips_chart is not None:
            result_tabs.pips_chart.clear_chart("Cumulative pips")
        result_tabs.balance_chart.clear_chart("Converted balance")

    def _populate_primary_tabs(self, artifacts: BacktestRunArtifacts) -> None:
        self._populate_reasons(artifacts)
        self._populate_trades_table(
            table=self._result_tabs.trades_table,
            rows=artifacts.trade_rows,
        )
        if self._result_tabs.pips_chart is not None:
            self._populate_trade_number_pips_chart(
                chart=self._result_tabs.pips_chart,
                points=artifacts.equity_points,
            )
        self._populate_trade_number_balance_chart(
            chart=self._result_tabs.balance_chart,
            points=artifacts.equity_points,
        )

    def _populate_chart_overview_tab(self, artifacts: BacktestRunArtifacts) -> None:
        self._chart_overview_tab.strategy_value_label.setText(
            artifacts.config.strategy_name
        )
        self._chart_overview_tab.csv_value_label.setText(str(artifacts.config.csv_path))

        self._chart_overview_tab.linked_chart.plot_dataset_with_equity(
            dataset=artifacts.dataset,
            trade_rows=artifacts.trade_rows,
            equity_points=artifacts.equity_points,
            state_segments=artifacts.backtest_result.state_segments,
            price_title="Price chart with entry / exit",
        )

        self._populate_trades_table(
            table=self._chart_overview_tab.detail_tabs.trades_table,
            rows=artifacts.trade_rows,
        )
        self._populate_trade_number_balance_chart(
            chart=self._chart_overview_tab.detail_tabs.balance_chart,
            points=artifacts.equity_points,
        )

    def _populate_summary(self, artifacts: BacktestRunArtifacts) -> None:
        summary = artifacts.summary
        config = artifacts.config
        labels = self._summary_panel.summary_labels

        labels["strategy_name"].setText(summary.strategy_name)
        labels["symbol"].setText(summary.symbol)
        labels["timeframe"].setText(summary.timeframe)
        labels["intrabar_fill_policy"].setText(summary.intrabar_fill_policy)
        labels["trades"].setText(str(summary.trades))
        labels["wins"].setText(str(summary.wins))
        labels["losses"].setText(str(summary.losses))
        labels["win_rate_percent"].setText(f"{summary.win_rate_percent:.2f}%")
        labels["total_pips"].setText(f"{summary.total_pips:.2f}")
        labels["average_pips"].setText(f"{summary.average_pips:.2f}")
        labels["average_win_pips"].setText(f"{summary.average_win_pips:.2f}")
        labels["average_loss_pips"].setText(f"{summary.average_loss_pips:.2f}")
        labels["profit_factor"].setText(
            self._format_profit_factor(summary.profit_factor)
        )
        labels["max_drawdown_pips"].setText(f"{summary.max_drawdown_pips:.2f}")
        labels["initial_balance"].setText(f"{summary.initial_balance:,.2f}")
        labels["risk_percent"].setText(
            f"{config.risk_percent:.2f}%" if config.risk_percent is not None else "-"
        )
        labels["lot_size"].setText(
            f"{config.lot_size:.4f}" if config.lot_size is not None else "-"
        )
        labels["money_per_pip"].setText(f"{config.money_per_pip:,.2f}")
        labels["final_balance"].setText(f"{summary.final_balance:,.2f}")
        labels["total_profit_amount"].setText(f"{summary.total_profit_amount:,.2f}")
        labels["return_rate_percent"].setText(f"{summary.return_rate_percent:.2f}%")
        labels["max_drawdown_amount"].setText(f"{summary.max_drawdown_amount:,.2f}")
        labels["max_consecutive_wins"].setText(str(summary.max_consecutive_wins))
        labels["max_consecutive_losses"].setText(str(summary.max_consecutive_losses))
        labels["verdict"].setText(summary.verdict)
        labels["final_open_position_type"].setText(
            summary.final_open_position_type
            if summary.final_open_position_type is not None
            else "none"
        )

    def _populate_reasons(self, artifacts: BacktestRunArtifacts) -> None:
        reasons = artifacts.summary.verdict_reasons
        if not reasons:
            self._summary_panel.reasons_text.setPlainText("none")
            return
        self._summary_panel.reasons_text.setPlainText(
            "\n".join(f"- {reason}" for reason in reasons)
        )

    def _prepare_table_for_bulk_update(self, table: QTableWidget) -> None:
        table.setUpdatesEnabled(False)
        table.setSortingEnabled(False)
        table.setWordWrap(False)
        table.verticalHeader().setDefaultSectionSize(22)

    def _finish_table_bulk_update(self, table: QTableWidget) -> None:
        table.setUpdatesEnabled(True)
        table.viewport().update()

    def _populate_trades_table(
        self,
        table: QTableWidget,
        rows: list[TradeViewRow],
    ) -> None:
        self._prepare_table_for_bulk_update(table)
        try:
            table.clearContents()
            table.setRowCount(len(rows))

            for row_index, row in enumerate(rows):
                exit_scores_text = self._build_exit_scores_text(row)

                values = [
                    str(row.trade_no),
                    row.lane,
                    self._safe_text(row.entry_subtype),
                    row.entry_time.strftime("%Y-%m-%d %H:%M:%S"),
                    row.exit_time.strftime("%Y-%m-%d %H:%M:%S"),
                    row.position_type,
                    f"{row.entry_price:.5f}",
                    f"{row.exit_price:.5f}",
                    f"{row.pips:.2f}",
                    f"{row.cumulative_pips:.2f}",
                    f"{row.trade_profit_amount:,.2f}",
                    f"{row.balance_after_trade:,.2f}",
                    row.exit_reason,
                    self._safe_text(row.entry_market_state),
                    self._safe_text(row.exit_market_state),
                    self._safe_text(row.entry_detected_market_state),
                    self._safe_text(row.entry_candidate_market_state),
                    self._safe_text(row.entry_state_transition_event),
                    self._format_optional_int(row.entry_state_age),
                    self._format_optional_int(row.entry_candidate_age),
                    self._format_optional_float(row.entry_range_score, digits=0),
                    self._format_optional_float(row.entry_transition_up_score, digits=0),
                    self._format_optional_float(
                        row.entry_transition_down_score,
                        digits=0,
                    ),
                    self._format_optional_float(row.entry_trend_up_score, digits=0),
                    self._format_optional_float(row.entry_trend_down_score, digits=0),
                    self._safe_text(row.exit_detected_market_state),
                    self._safe_text(row.exit_candidate_market_state),
                    self._safe_text(row.exit_state_transition_event),
                    self._format_optional_int(row.exit_state_age),
                    self._format_optional_int(row.exit_candidate_age),
                    exit_scores_text,
                    self._shorten_text(
                        self._safe_text(row.entry_signal_reason),
                        max_length=120,
                    ),
                    self._shorten_text(
                        self._safe_text(row.exit_signal_reason),
                        max_length=120,
                    ),
                ]

                for column_index, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setTextAlignment(Qt.AlignCenter)

                    if column_index in {12, 30, 31, 32}:
                        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                    if column_index == 30:
                        full_scores = self._build_exit_scores_tooltip(row)
                        if full_scores != "-":
                            item.setToolTip(full_scores)

                    if column_index == 31:
                        full_reason = self._safe_text(row.entry_signal_reason)
                        if full_reason != "-":
                            item.setToolTip(full_reason)

                    if column_index == 32:
                        full_reason = self._safe_text(row.exit_signal_reason)
                        if full_reason != "-":
                            item.setToolTip(full_reason)

                    table.setItem(row_index, column_index, item)
        finally:
            self._finish_table_bulk_update(table)

    def _populate_trade_number_pips_chart(
        self,
        chart,
        points: list[EquityPoint],
    ) -> None:
        if not points:
            chart.clear_chart("Cumulative pips (no trades)")
            return

        x_values = [point.trade_no for point in points]
        cumulative_pips = [point.cumulative_pips for point in points]
        chart.plot_series(
            x_values=x_values,
            y_values=cumulative_pips,
            title="Cumulative pips by trade",
            x_label="Trade no",
            y_label="Pips",
        )

    def _populate_trade_number_balance_chart(
        self,
        chart,
        points: list[EquityPoint],
    ) -> None:
        if not points:
            chart.clear_chart("Converted balance (no trades)")
            return

        x_values = [point.trade_no for point in points]
        balances = [point.balance for point in points]
        chart.plot_series(
            x_values=x_values,
            y_values=balances,
            title="Converted balance by trade",
            x_label="Trade no",
            y_label="Balance",
        )

    def _populate_notes(self, artifacts: BacktestRunArtifacts) -> None:
        config = artifacts.config
        dataset = artifacts.dataset
        summary = artifacts.summary
        decision_summary_lines = self._build_decision_log_summary_lines(
            artifacts.decision_log_rows
        )

        note_lines = [
            "Completed.",
            f"Strategy: {config.strategy_name}",
            f"CSV: {config.csv_path}",
            f"Loaded bars: {len(dataset.rows)}",
            f"Detected digits: {dataset.digits}",
            f"Detected point: {dataset.point}",
            f"Initial balance: {config.initial_balance:,.2f}",
            (
                f"Risk %: {config.risk_percent:.2f}%"
                if config.risk_percent is not None
                else "Risk %: -"
            ),
            (
                f"Calculated lot size: {config.lot_size:.4f}"
                if config.lot_size is not None
                else "Calculated lot size: -"
            ),
            f"Calculated yen/pip: {config.money_per_pip:,.2f}",
            f"Converted final balance: {summary.final_balance:,.2f}",
            f"Converted return rate: {summary.return_rate_percent:.2f}%",
            "",
            "[Decision log summary]",
            *decision_summary_lines,
        ]
        self._input_panel.notes_text.setPlainText("\n".join(note_lines))

    def _build_decision_log_summary_lines(
        self,
        rows: list[DecisionLogViewRow],
    ) -> list[str]:
        if not rows:
            return ["No decision logs."]

        trend_up_count = self._count_market_state(rows, "trend_up")
        trend_down_count = self._count_market_state(rows, "trend_down")
        weak_trend_up_count = self._count_market_state(rows, "weak_trend_up")
        weak_trend_down_count = self._count_market_state(rows, "weak_trend_down")
        range_count = self._count_market_state(rows, "range")
        neutral_count = self._count_market_state(rows, "neutral")
        other_state_count = self._count_other_market_states(
            rows,
            known_states={
                "trend_up",
                "trend_down",
                "weak_trend_up",
                "weak_trend_down",
                "range",
                "neutral",
            },
        )

        strong_trend_buy_count = self._count_action_with_reason_keywords(
            rows=rows,
            action="buy",
            keywords=(
                "trend-follow buy confirmed",
                "trend-continuation buy confirmed",
            ),
        )
        strong_trend_sell_count = self._count_action_with_reason_keywords(
            rows=rows,
            action="sell",
            keywords=(
                "trend-follow sell confirmed",
                "trend-continuation sell confirmed",
            ),
        )
        weak_trend_buy_entry_count = self._count_action_with_reason_keywords(
            rows=rows,
            action="buy",
            keywords=("weak-trend continuation buy confirmed",),
        )
        weak_trend_sell_entry_count = self._count_action_with_reason_keywords(
            rows=rows,
            action="sell",
            keywords=("weak-trend continuation sell confirmed",),
        )
        total_trend_buy_count = strong_trend_buy_count + weak_trend_buy_entry_count
        total_trend_sell_count = strong_trend_sell_count + weak_trend_sell_entry_count

        trend_hold_count = self._count_action_in_market_states(
            rows=rows,
            action="hold",
            states={
                "trend_up",
                "trend_down",
                "weak_trend_up",
                "weak_trend_down",
            },
        )

        debug_trend_up_slope_blocked = self._count_entry_subtype(
            rows,
            "debug_trend_up_slope_blocked",
        )
        debug_trend_down_slope_blocked = self._count_entry_subtype(
            rows,
            "debug_trend_down_slope_blocked",
        )
        debug_trend_up_price_filter_blocked = self._count_entry_subtype(
            rows,
            "debug_trend_up_price_filter_blocked",
        )
        debug_trend_down_price_filter_blocked = self._count_entry_subtype(
            rows,
            "debug_trend_down_price_filter_blocked",
        )
        debug_trend_up_breakout_miss = self._count_entry_subtype(
            rows,
            "debug_trend_up_breakout_miss",
        )
        debug_trend_down_breakout_miss = self._count_entry_subtype(
            rows,
            "debug_trend_down_breakout_miss",
        )
        debug_flat_slope = self._count_entry_subtype(
            rows,
            "debug_flat_slope",
        )
        hold_existing_count = self._count_entry_subtype(
            rows,
            "hold_existing",
        )

        upper_break_miss_rows = self._find_entry_subtype(
            rows,
            "debug_trend_up_breakout_miss",
        )
        lower_break_miss_rows = self._find_entry_subtype(
            rows,
            "debug_trend_down_breakout_miss",
        )
        up_slope_blocked_rows = self._find_entry_subtype(
            rows,
            "debug_trend_up_slope_blocked",
        )
        down_slope_blocked_rows = self._find_entry_subtype(
            rows,
            "debug_trend_down_slope_blocked",
        )
        up_price_blocked_rows = self._find_entry_subtype(
            rows,
            "debug_trend_up_price_filter_blocked",
        )
        down_price_blocked_rows = self._find_entry_subtype(
            rows,
            "debug_trend_down_price_filter_blocked",
        )

        lines = [
            f"Decision rows: {len(rows)}",
            (
                "Market state counts: "
                f"trend_up={trend_up_count}, "
                f"trend_down={trend_down_count}, "
                f"weak_trend_up={weak_trend_up_count}, "
                f"weak_trend_down={weak_trend_down_count}, "
                f"range={range_count}, "
                f"neutral={neutral_count}, "
                f"other={other_state_count}"
            ),
            (
                "Trend entry counts: "
                f"trend_buy={total_trend_buy_count}, "
                f"trend_sell={total_trend_sell_count}, "
                f"strong_trend_buy={strong_trend_buy_count}, "
                f"strong_trend_sell={strong_trend_sell_count}, "
                f"weak_trend_buy={weak_trend_buy_entry_count}, "
                f"weak_trend_sell={weak_trend_sell_entry_count}"
            ),
            (
                "Trend HOLD rows: "
                f"total={trend_hold_count}, "
                f"hold_existing={hold_existing_count}"
            ),
            (
                "Trend debug counts: "
                f"up_slope_blocked={debug_trend_up_slope_blocked}, "
                f"down_slope_blocked={debug_trend_down_slope_blocked}, "
                f"up_price_blocked={debug_trend_up_price_filter_blocked}, "
                f"down_price_blocked={debug_trend_down_price_filter_blocked}, "
                f"up_breakout_miss={debug_trend_up_breakout_miss}, "
                f"down_breakout_miss={debug_trend_down_breakout_miss}, "
                f"flat_slope={debug_flat_slope}"
            ),
        ]

        lines.extend(
            self._build_sample_lines(
                title="Sample upper breakout misses",
                rows=upper_break_miss_rows,
                max_items=3,
            )
        )
        lines.extend(
            self._build_sample_lines(
                title="Sample lower breakout misses",
                rows=lower_break_miss_rows,
                max_items=3,
            )
        )
        lines.extend(
            self._build_sample_lines(
                title="Sample up slope blocked",
                rows=up_slope_blocked_rows,
                max_items=3,
            )
        )
        lines.extend(
            self._build_sample_lines(
                title="Sample down slope blocked",
                rows=down_slope_blocked_rows,
                max_items=3,
            )
        )
        lines.extend(
            self._build_sample_lines(
                title="Sample up price filter blocked",
                rows=up_price_blocked_rows,
                max_items=3,
            )
        )
        lines.extend(
            self._build_sample_lines(
                title="Sample down price filter blocked",
                rows=down_price_blocked_rows,
                max_items=3,
            )
        )

        return lines

    def _count_market_state(
        self,
        rows: list[DecisionLogViewRow],
        state: str,
    ) -> int:
        return sum(1 for row in rows if row.market_state == state)

    def _count_other_market_states(
        self,
        rows: list[DecisionLogViewRow],
        known_states: set[str],
    ) -> int:
        return sum(
            1
            for row in rows
            if (row.market_state or "") not in known_states
        )

    def _count_action_with_lane(
        self,
        *,
        rows: list[DecisionLogViewRow],
        action: str,
        lane: str,
    ) -> int:
        return sum(
            1
            for row in rows
            if row.action == action and (row.entry_lane or "") == lane
        )

    def _count_action_in_market_states(
        self,
        *,
        rows: list[DecisionLogViewRow],
        action: str,
        states: set[str],
    ) -> int:
        return sum(
            1
            for row in rows
            if row.action == action and (row.market_state or "") in states
        )

    def _count_action_with_reason_keywords(
        self,
        *,
        rows: list[DecisionLogViewRow],
        action: str,
        keywords: tuple[str, ...],
    ) -> int:
        lowered_keywords = tuple(keyword.lower() for keyword in keywords)
        return sum(
            1
            for row in rows
            if row.action == action
            and any(keyword in row.reason.lower() for keyword in lowered_keywords)
        )

    def _count_entry_subtype(
        self,
        rows: list[DecisionLogViewRow],
        entry_subtype: str,
    ) -> int:
        return sum(
            1
            for row in rows
            if (row.entry_subtype or "") == entry_subtype
        )

    def _find_reason_contains(
        self,
        rows: list[DecisionLogViewRow],
        keyword: str,
    ) -> list[DecisionLogViewRow]:
        lowered_keyword = keyword.lower()
        return [
            row
            for row in rows
            if lowered_keyword in row.reason.lower()
        ]

    def _find_entry_subtype(
        self,
        rows: list[DecisionLogViewRow],
        entry_subtype: str,
    ) -> list[DecisionLogViewRow]:
        return [
            row
            for row in rows
            if (row.entry_subtype or "") == entry_subtype
        ]

    def _build_sample_lines(
        self,
        *,
        title: str,
        rows: list[DecisionLogViewRow],
        max_items: int,
    ) -> list[str]:
        if not rows:
            return [f"{title}: none"]

        lines = [f"{title}:"]
        for row in rows[:max_items]:
            lines.append(
                "  - "
                f"{row.bar_time.strftime('%Y-%m-%d %H:%M:%S')} | "
                f"state={self._safe_text(row.market_state)} | "
                f"lane={self._safe_text(row.entry_lane)} | "
                f"subtype={self._safe_text(row.entry_subtype)} | "
                f"action={row.action} | "
                f"prev={row.previous_close:.5f} | "
                f"latest={row.latest_close:.5f}"
            )
        return lines

    def _format_profit_factor(self, value: float | None) -> str:
        if value is None:
            return "None"
        if value == float("inf"):
            return "inf"
        return f"{value:.2f}"

    def _format_optional_float(
        self,
        value: float | None,
        *,
        digits: int = 2,
    ) -> str:
        if value is None:
            return "-"
        return f"{value:.{digits}f}"

    def _format_optional_int(self, value: int | None) -> str:
        if value is None:
            return "-"
        return str(value)

    def _safe_text(self, value: str | None) -> str:
        if value is None or value == "":
            return "-"
        return value

    def _shorten_text(self, value: str, *, max_length: int) -> str:
        if len(value) <= max_length:
            return value
        return value[: max_length - 3] + "..."

    def _build_exit_scores_text(self, row: TradeViewRow) -> str:
        if (
            row.exit_range_score is None
            and row.exit_transition_up_score is None
            and row.exit_transition_down_score is None
            and row.exit_trend_up_score is None
            and row.exit_trend_down_score is None
        ):
            return "-"
        return (
            f"r={self._format_optional_float(row.exit_range_score, digits=0)} "
            f"tu={self._format_optional_float(row.exit_transition_up_score, digits=0)} "
            f"td={self._format_optional_float(row.exit_transition_down_score, digits=0)} "
            f"u={self._format_optional_float(row.exit_trend_up_score, digits=0)} "
            f"d={self._format_optional_float(row.exit_trend_down_score, digits=0)}"
        )

    def _build_exit_scores_tooltip(self, row: TradeViewRow) -> str:
        if (
            row.exit_range_score is None
            and row.exit_transition_up_score is None
            and row.exit_transition_down_score is None
            and row.exit_trend_up_score is None
            and row.exit_trend_down_score is None
        ):
            return "-"
        return (
            "exit scores\n"
            f"range={self._format_optional_float(row.exit_range_score, digits=0)}\n"
            f"transition_up={self._format_optional_float(row.exit_transition_up_score, digits=0)}\n"
            f"transition_down={self._format_optional_float(row.exit_transition_down_score, digits=0)}\n"
            f"trend_up={self._format_optional_float(row.exit_trend_up_score, digits=0)}\n"
            f"trend_down={self._format_optional_float(row.exit_trend_down_score, digits=0)}"
        )