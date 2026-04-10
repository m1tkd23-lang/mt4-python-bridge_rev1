# src/backtest_gui_app/services/strategy_params.py
"""Strategy-specific parameter definitions and runtime override utilities."""
from __future__ import annotations

import importlib
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyParamSpec:
    """Specification for a single strategy parameter exposed in the GUI."""

    name: str  # module-level constant name (e.g. "BOLLINGER_PERIOD")
    label: str  # display label in the GUI
    param_type: str  # "int" or "float"
    default: float  # default value from the strategy module
    min_val: float
    max_val: float
    step: float
    decimals: int  # decimal places for DoubleSpinBox (0 for int)
    module_path: str  # dotted module path to patch


_V44_MODULE = "mt4_bridge.strategies.bollinger_range_v4_4"
_TREND_B_MODULE = "mt4_bridge.strategies.bollinger_trend_B"

_BOLLINGER_RANGE_V4_4_PARAMS: list[StrategyParamSpec] = [
    StrategyParamSpec(
        "BOLLINGER_PERIOD", "BB Period", "int", 20, 5, 200, 1, 0, _V44_MODULE
    ),
    StrategyParamSpec(
        "BOLLINGER_SIGMA", "BB Sigma", "float", 2.0, 0.5, 5.0, 0.1, 2, _V44_MODULE
    ),
    StrategyParamSpec(
        "BOLLINGER_EXTREME_SIGMA",
        "BB Extreme Sigma",
        "float",
        3.0,
        1.0,
        5.0,
        0.1,
        2,
        _V44_MODULE,
    ),
    StrategyParamSpec(
        "RANGE_SLOPE_THRESHOLD",
        "Range Slope Thr",
        "float",
        0.0005,
        0.0,
        0.01,
        0.0001,
        4,
        _V44_MODULE,
    ),
    StrategyParamSpec(
        "RANGE_BAND_WIDTH_THRESHOLD",
        "Range BW Thr",
        "float",
        0.003,
        0.0,
        0.05,
        0.0005,
        4,
        _V44_MODULE,
    ),
    StrategyParamSpec(
        "RANGE_MIDDLE_DISTANCE_THRESHOLD",
        "Range Mid Dist Thr",
        "float",
        0.002,
        0.0,
        0.05,
        0.0005,
        4,
        _V44_MODULE,
    ),
]

_BOLLINGER_TREND_B_PARAMS: list[StrategyParamSpec] = [
    StrategyParamSpec(
        "BOLLINGER_PERIOD", "Trend BB Period", "int", 20, 5, 200, 1, 0, _TREND_B_MODULE
    ),
    StrategyParamSpec(
        "BOLLINGER_SIGMA",
        "Trend BB Sigma",
        "float",
        2.0,
        0.5,
        5.0,
        0.1,
        2,
        _TREND_B_MODULE,
    ),
    StrategyParamSpec(
        "TREND_SLOPE_THRESHOLD",
        "Trend Slope Thr",
        "float",
        0.00002,
        0.0,
        0.01,
        0.00001,
        5,
        _TREND_B_MODULE,
    ),
    StrategyParamSpec(
        "STRONG_TREND_SLOPE_THRESHOLD",
        "Strong Trend Slope Thr",
        "float",
        0.0005,
        0.0,
        0.01,
        0.0001,
        4,
        _TREND_B_MODULE,
    ),
]

# Map strategy names to their parameter specs.
STRATEGY_PARAM_MAP: dict[str, list[StrategyParamSpec]] = {
    "bollinger_range_v4_4": _BOLLINGER_RANGE_V4_4_PARAMS,
    "bollinger_range_A": _BOLLINGER_RANGE_V4_4_PARAMS,
    "bollinger_trend_B": _BOLLINGER_TREND_B_PARAMS,
    "bollinger_combo_AB": _BOLLINGER_RANGE_V4_4_PARAMS + _BOLLINGER_TREND_B_PARAMS,
    "bollinger_combo_AB_v1": _BOLLINGER_RANGE_V4_4_PARAMS + _BOLLINGER_TREND_B_PARAMS,
}


def get_param_specs(strategy_name: str) -> list[StrategyParamSpec]:
    """Return parameter specs for a strategy, or empty list if unknown."""
    return STRATEGY_PARAM_MAP.get(strategy_name, [])


def read_current_defaults(specs: list[StrategyParamSpec]) -> dict[str, float]:
    """Read current module-level constant values for the given specs."""
    values: dict[str, float] = {}
    for spec in specs:
        try:
            mod = importlib.import_module(spec.module_path)
            val = getattr(mod, spec.name, spec.default)
            key = f"{spec.module_path}::{spec.name}"
            values[key] = val
        except ImportError:
            pass
    return values


@contextmanager
def apply_strategy_overrides(
    overrides: dict[str, float],
    specs: list[StrategyParamSpec],
):
    """Context manager that patches strategy module constants and restores them.

    ``overrides`` maps ``StrategyParamSpec.name`` → new value.
    For combo strategies where the same constant name appears in different
    modules, the key should be ``module_path::CONSTANT_NAME`` to disambiguate.
    Plain ``CONSTANT_NAME`` keys are also accepted and will be applied to all
    matching specs.
    """
    originals: list[tuple[object, str, object]] = []

    for spec in specs:
        qualified_key = f"{spec.module_path}::{spec.name}"
        new_value = overrides.get(qualified_key)
        if new_value is None:
            new_value = overrides.get(spec.name)
        if new_value is None:
            continue

        try:
            mod = importlib.import_module(spec.module_path)
        except ImportError:
            continue

        old_value = getattr(mod, spec.name, None)
        if old_value is None:
            continue

        originals.append((mod, spec.name, old_value))
        cast_value = int(new_value) if spec.param_type == "int" else float(new_value)
        setattr(mod, spec.name, cast_value)

    try:
        yield
    finally:
        for mod, attr_name, old_value in originals:
            setattr(mod, attr_name, old_value)
