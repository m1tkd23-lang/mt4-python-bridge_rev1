# src\backtest_gui_app\services\run_config_builder.py
from __future__ import annotations

from pathlib import Path

from backtest.service import BacktestRunConfig
from backtest.simulator import IntrabarFillPolicy
from backtest_gui_app.constants import USDJPY_YEN_PER_PIP_PER_1LOT
from backtest_gui_app.views.input_panel import InputPanel


def build_run_config(input_panel: InputPanel) -> BacktestRunConfig:
    strategy_name = input_panel.strategy_combo.currentText().strip()
    if not strategy_name:
        raise ValueError("Strategy is not selected.")

    csv_path_text = input_panel.csv_combo.currentData()
    if not csv_path_text:
        raise ValueError("CSV file is not selected.")

    csv_path = Path(str(csv_path_text))
    if not csv_path.exists():
        raise ValueError(f"CSV file not found: {csv_path}")

    symbol = input_panel.symbol_edit.text().strip() or "BACKTEST"
    timeframe = input_panel.timeframe_edit.text().strip() or "M1"

    pip_size = _parse_positive_float(input_panel.pip_size_edit.text(), "Pip size")
    sl_pips = _parse_positive_float(input_panel.sl_pips_edit.text(), "SL pips")
    tp_pips = _parse_positive_float(input_panel.tp_pips_edit.text(), "TP pips")
    initial_balance = _parse_positive_float(
        input_panel.initial_balance_edit.text(),
        "Initial balance",
    )
    risk_percent = _parse_positive_float(
        input_panel.risk_percent_edit.text(),
        "Risk %",
    )

    policy_text = input_panel.intrabar_policy_combo.currentText().strip()
    try:
        policy = IntrabarFillPolicy(policy_text)
    except ValueError as exc:
        raise ValueError(f"Intrabar policy is invalid: {policy_text}") from exc

    if sl_pips <= 0:
        raise ValueError("SL pips must be greater than zero for risk-based sizing.")

    risk_amount = initial_balance * (risk_percent / 100.0)
    money_per_pip = risk_amount / sl_pips
    lot_size = money_per_pip / USDJPY_YEN_PER_PIP_PER_1LOT

    strategy_params = input_panel.get_strategy_param_overrides() or None

    return BacktestRunConfig(
        csv_path=csv_path,
        strategy_name=strategy_name,
        symbol=symbol,
        timeframe=timeframe,
        pip_size=pip_size,
        sl_pips=sl_pips,
        tp_pips=tp_pips,
        intrabar_fill_policy=policy,
        close_open_position_at_end=input_panel.close_position_checkbox.isChecked(),
        initial_balance=initial_balance,
        money_per_pip=money_per_pip,
        risk_percent=risk_percent,
        lot_size=lot_size,
        strategy_params=strategy_params,
    )


def _parse_float(text: str, field_name: str) -> float:
    stripped = text.strip()
    if not stripped:
        raise ValueError(f"{field_name} is required.")
    try:
        return float(stripped)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a number.") from exc


def _parse_positive_float(text: str, field_name: str) -> float:
    value = _parse_float(text, field_name)
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")
    return value