# src/mt4_bridge/signal_engine.py
from __future__ import annotations

import importlib

from mt4_bridge.models import MarketSnapshot, PositionSnapshot, SignalDecision
from mt4_bridge.signal_exceptions import SignalEngineError
from mt4_bridge.strategies.close_compare_v1 import (
    evaluate_close_compare_v1,
    required_bars as close_compare_v1_required_bars,
)
from mt4_bridge.strategies.ma_cross_v1 import (
    evaluate_ma_cross_v1,
    required_bars as ma_cross_v1_required_bars,
)

_MULTI_DECISION_STRATEGIES = {
    "bollinger_range_v4_6_1",
    "bollinger_combo_AB",
    "bollinger_combo_AB_v1",
}


def _load_dynamic_strategy(strategy_name: str) -> tuple:
    module_path = f"mt4_bridge.strategies.{strategy_name}"
    try:
        mod = importlib.import_module(module_path)
    except ImportError as e:
        raise SignalEngineError(f"Unsupported strategy: {strategy_name}") from e

    evaluate_fn = getattr(mod, f"evaluate_{strategy_name}", None)
    required_bars_fn = getattr(mod, "required_bars", None)

    if evaluate_fn is None:
        raise SignalEngineError(
            f"Strategy module '{strategy_name}' missing evaluate_{strategy_name}()"
        )
    if required_bars_fn is None:
        raise SignalEngineError(
            f"Strategy module '{strategy_name}' missing required_bars()"
        )

    return evaluate_fn, required_bars_fn


def _load_dynamic_multi_decision_strategy(strategy_name: str):
    module_path = f"mt4_bridge.strategies.{strategy_name}"
    try:
        mod = importlib.import_module(module_path)
    except ImportError as e:
        raise SignalEngineError(f"Unsupported strategy: {strategy_name}") from e

    evaluate_signals_fn = getattr(mod, f"evaluate_{strategy_name}_signals", None)
    required_bars_fn = getattr(mod, "required_bars", None)

    if evaluate_signals_fn is None:
        raise SignalEngineError(
            f"Strategy module '{strategy_name}' missing evaluate_{strategy_name}_signals()"
        )
    if required_bars_fn is None:
        raise SignalEngineError(
            f"Strategy module '{strategy_name}' missing required_bars()"
        )

    return evaluate_signals_fn, required_bars_fn


def get_required_bars(strategy_name: str) -> int:
    normalized_name = strategy_name.strip()

    if normalized_name == "close_compare_v1":
        return close_compare_v1_required_bars()

    if normalized_name == "ma_cross_v1":
        return ma_cross_v1_required_bars()

    if normalized_name in _MULTI_DECISION_STRATEGIES:
        _, required_bars_fn = _load_dynamic_multi_decision_strategy(normalized_name)
        return required_bars_fn()

    _, required_bars_fn = _load_dynamic_strategy(normalized_name)
    return required_bars_fn()


def evaluate_signals(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str,
) -> list[SignalDecision]:
    normalized_name = strategy_name.strip()

    if normalized_name in _MULTI_DECISION_STRATEGIES:
        evaluate_signals_fn, _ = _load_dynamic_multi_decision_strategy(normalized_name)
        decisions = evaluate_signals_fn(
            market_snapshot=market_snapshot,
            position_snapshot=position_snapshot,
            strategy_name=normalized_name,
        )
        if not isinstance(decisions, list):
            raise SignalEngineError(
                f"Strategy '{normalized_name}' returned non-list from multi decision evaluation"
            )
        return decisions

    return [
        evaluate_signal(
            market_snapshot=market_snapshot,
            position_snapshot=position_snapshot,
            strategy_name=normalized_name,
        )
    ]


def evaluate_signal(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str,
) -> SignalDecision:
    normalized_name = strategy_name.strip()

    if normalized_name == "close_compare_v1":
        return evaluate_close_compare_v1(
            market_snapshot=market_snapshot,
            position_snapshot=position_snapshot,
            strategy_name=normalized_name,
        )

    if normalized_name == "ma_cross_v1":
        return evaluate_ma_cross_v1(
            market_snapshot=market_snapshot,
            position_snapshot=position_snapshot,
            strategy_name=normalized_name,
        )

    if normalized_name in _MULTI_DECISION_STRATEGIES:
        decisions = evaluate_signals(
            market_snapshot=market_snapshot,
            position_snapshot=position_snapshot,
            strategy_name=normalized_name,
        )
        if not decisions:
            raise SignalEngineError(
                f"Strategy '{normalized_name}' returned no decisions"
            )
        return decisions[0]

    evaluate_fn, _ = _load_dynamic_strategy(normalized_name)
    return evaluate_fn(
        market_snapshot=market_snapshot,
        position_snapshot=position_snapshot,
        strategy_name=normalized_name,
    )


def evaluate_close_compare_signal(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "close_compare_v1",
) -> SignalDecision:
    return evaluate_signal(
        market_snapshot=market_snapshot,
        position_snapshot=position_snapshot,
        strategy_name=strategy_name,
    )