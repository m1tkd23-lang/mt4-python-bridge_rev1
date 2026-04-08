# src/mt4_bridge/strategy_generator.py
"""Template-based strategy file generator.

Generates strategy files that conform to the existing pattern:
- required_bars() -> int
- evaluate_<name>(market_snapshot, position_snapshot, strategy_name) -> SignalDecision
"""
from __future__ import annotations

import logging
import random
import re
from pathlib import Path
from textwrap import dedent

logger = logging.getLogger(__name__)

STRATEGIES_DIR = Path(__file__).parent / "strategies"

SIGNAL_TEMPLATES: dict[str, dict[str, str]] = {
    "close_compare": {
        "required_bars": "2",
        "base_signal_body": dedent("""\
            previous_bar = bars[-2]
            latest_bar = bars[-1]

            if latest_bar.close > previous_bar.close:
                return SignalAction.BUY, f"latest close {{latest_bar.close}} > previous close {{previous_bar.close}}"

            if latest_bar.close < previous_bar.close:
                return SignalAction.SELL, f"latest close {{latest_bar.close}} < previous close {{previous_bar.close}}"

            return SignalAction.HOLD, f"latest close {{latest_bar.close}} == previous close {{previous_bar.close}}"
        """),
    },
    "ma_cross": {
        "required_bars": "{long_window}",
        "extra_constants": dedent("""\
            SHORT_WINDOW = {short_window}
            LONG_WINDOW = {long_window}
        """),
        "extra_helpers": dedent("""\

            def _simple_moving_average(values: list[float]) -> float:
                if not values:
                    raise SignalEngineError("Moving average requires at least 1 value")
                return sum(values) / len(values)
        """),
        "base_signal_body": dedent("""\
            closes = [bar.close for bar in bars]
            short_ma = _simple_moving_average(closes[-SHORT_WINDOW:])
            long_ma = _simple_moving_average(closes[-LONG_WINDOW:])

            if short_ma > long_ma:
                return SignalAction.BUY, f"short MA {{short_ma}} > long MA {{long_ma}}"

            if short_ma < long_ma:
                return SignalAction.SELL, f"short MA {{short_ma}} < long MA {{long_ma}}"

            return SignalAction.HOLD, f"short MA {{short_ma}} == long MA {{long_ma}}"
        """),
    },
}

_STRATEGY_TEMPLATE = dedent("""\
    # {file_path_comment}
    from __future__ import annotations

    from mt4_bridge.models import (
        MarketSnapshot,
        PositionSnapshot,
        SignalAction,
        SignalDecision,
    )
    from mt4_bridge.signal_exceptions import SignalEngineError

    {extra_constants}
    def required_bars() -> int:
        return {required_bars}

    {extra_helpers}
    def _base_signal(
        market_snapshot: MarketSnapshot,
    ) -> tuple[SignalAction, str]:
        bars = market_snapshot.bars

        if len(bars) < required_bars():
            raise SignalEngineError(
                f"At least {{required_bars()}} bars are required to evaluate {strategy_name}"
            )

        {base_signal_body}

    def evaluate_{strategy_name}(
        market_snapshot: MarketSnapshot,
        position_snapshot: PositionSnapshot,
        strategy_name: str = "{strategy_name}",
    ) -> SignalDecision:
        bars = market_snapshot.bars
        if len(bars) < required_bars():
            raise SignalEngineError(
                f"At least {{required_bars()}} bars are required to evaluate {strategy_name}"
            )

        previous_bar = bars[-2]
        latest_bar = bars[-1]
        base_action, base_reason = _base_signal(market_snapshot)

        current_position = (
            position_snapshot.positions[0] if position_snapshot.positions else None
        )

        if current_position is None:
            return SignalDecision(
                strategy_name=strategy_name,
                action=base_action,
                reason=base_reason,
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_bar.close,
                latest_close=latest_bar.close,
                current_position_ticket=None,
                current_position_type=None,
            )

        current_type = current_position.position_type.lower()

        if base_action == SignalAction.HOLD:
            return SignalDecision(
                strategy_name=strategy_name,
                action=SignalAction.HOLD,
                reason=f"{{base_reason}}; existing {{current_type}} position kept",
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_bar.close,
                latest_close=latest_bar.close,
                current_position_ticket=current_position.ticket,
                current_position_type=current_type,
            )

        if current_type == "buy":
            if base_action == SignalAction.BUY:
                return SignalDecision(
                    strategy_name=strategy_name,
                    action=SignalAction.HOLD,
                    reason="buy signal but buy position already exists",
                    previous_bar_time=previous_bar.time,
                    latest_bar_time=latest_bar.time,
                    previous_close=previous_bar.close,
                    latest_close=latest_bar.close,
                    current_position_ticket=current_position.ticket,
                    current_position_type=current_type,
                )
            return SignalDecision(
                strategy_name=strategy_name,
                action=SignalAction.CLOSE,
                reason="sell signal detected while buy position exists",
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_bar.close,
                latest_close=latest_bar.close,
                current_position_ticket=current_position.ticket,
                current_position_type=current_type,
            )

        if current_type == "sell":
            if base_action == SignalAction.SELL:
                return SignalDecision(
                    strategy_name=strategy_name,
                    action=SignalAction.HOLD,
                    reason="sell signal but sell position already exists",
                    previous_bar_time=previous_bar.time,
                    latest_bar_time=latest_bar.time,
                    previous_close=previous_bar.close,
                    latest_close=latest_bar.close,
                    current_position_ticket=current_position.ticket,
                    current_position_type=current_type,
                )
            return SignalDecision(
                strategy_name=strategy_name,
                action=SignalAction.CLOSE,
                reason="buy signal detected while sell position exists",
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_bar.close,
                latest_close=latest_bar.close,
                current_position_ticket=current_position.ticket,
                current_position_type=current_type,
            )

        raise SignalEngineError(f"Unsupported position type: {{current_type}}")
""")

_VALID_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*_v\d+$")


def validate_strategy_name(name: str) -> None:
    """Validate that a strategy name follows the naming convention."""
    if not _VALID_NAME_RE.match(name):
        raise ValueError(
            f"Invalid strategy name '{name}'. "
            "Must match pattern: <snake_case>_v<number> (e.g. my_strategy_v1)"
        )


def generate_strategy_file(
    strategy_name: str,
    signal_type: str,
    params: dict[str, object] | None = None,
    output_dir: Path | None = None,
) -> Path:
    """Generate a strategy file from a template.

    Args:
        strategy_name: Name of the strategy (e.g. "rsi_threshold_v1").
        signal_type: Type of signal logic to use. Must be a key in SIGNAL_TEMPLATES.
        params: Optional parameters for the signal template (e.g. short_window, long_window).
        output_dir: Directory to write the file to. Defaults to strategies/.

    Returns:
        Path to the generated file.
    """
    validate_strategy_name(strategy_name)

    if signal_type not in SIGNAL_TEMPLATES:
        raise ValueError(
            f"Unknown signal_type '{signal_type}'. "
            f"Available: {sorted(SIGNAL_TEMPLATES.keys())}"
        )

    template_data = SIGNAL_TEMPLATES[signal_type]
    params = params or {}

    required_bars_val = template_data["required_bars"].format(**params)
    base_signal_body = template_data["base_signal_body"].format(**params)
    extra_constants = template_data.get("extra_constants", "").format(**params)
    extra_helpers = template_data.get("extra_helpers", "").format(**params)

    dest_dir = output_dir or STRATEGIES_DIR
    file_path = dest_dir / f"{strategy_name}.py"
    file_path_comment = f"src/mt4_bridge/strategies/{strategy_name}.py"

    # Indent base_signal_body to match template indentation (8 spaces)
    indented_body = "\n    ".join(base_signal_body.strip().splitlines())

    content = _STRATEGY_TEMPLATE.format(
        file_path_comment=file_path_comment,
        strategy_name=strategy_name,
        required_bars=required_bars_val,
        base_signal_body=indented_body,
        extra_constants=extra_constants,
        extra_helpers=extra_helpers,
    )

    # Clean up excessive blank lines
    content = re.sub(r"\n{3,}", "\n\n\n", content)

    file_path.write_text(content, encoding="utf-8")
    return file_path


PARAM_VARIATION_RANGES: dict[str, dict[str, tuple[int, int, int]]] = {
    "ma_cross": {
        "short_window": (3, 20, 1),
        "long_window": (10, 50, 5),
    },
}

DEFAULT_PARAMS: dict[str, dict[str, int]] = {
    "close_compare": {},
    "ma_cross": {"short_window": 5, "long_window": 20},
}


def generate_param_variations(
    signal_type: str,
    base_params: dict[str, object] | None = None,
    count: int = 3,
) -> list[dict[str, object]]:
    """Generate parameter variations for a signal type.

    Produces up to *count* parameter sets that differ from *base_params*.
    Each variation adjusts values within the ranges defined in
    ``PARAM_VARIATION_RANGES``.  If the signal type has no tunable
    parameters, an empty list is returned (caller should fall back to
    generating a new strategy).

    Args:
        signal_type: Signal type key (must exist in ``SIGNAL_TEMPLATES``).
        base_params: Current parameter set.  Falls back to ``DEFAULT_PARAMS``.
        count: Maximum number of variations to generate.

    Returns:
        A list of parameter dicts, each different from *base_params*.
    """
    if signal_type not in SIGNAL_TEMPLATES:
        logger.warning("Unknown signal_type '%s' for param variation", signal_type)
        return []

    ranges = PARAM_VARIATION_RANGES.get(signal_type)
    if not ranges:
        return []

    effective_base = dict(DEFAULT_PARAMS.get(signal_type, {}))
    if base_params:
        effective_base.update(base_params)

    variations: list[dict[str, object]] = []
    seen: set[tuple[tuple[str, object], ...]] = set()
    base_key = tuple(sorted(effective_base.items()))
    seen.add(base_key)

    attempts = 0
    max_attempts = count * 10

    while len(variations) < count and attempts < max_attempts:
        attempts += 1
        candidate: dict[str, object] = {}
        for param_name, (lo, hi, step) in ranges.items():
            possible = list(range(lo, hi + 1, step))
            candidate[param_name] = random.choice(possible)

        # Enforce constraint: short_window < long_window for ma_cross
        if signal_type == "ma_cross":
            sw = int(candidate.get("short_window", 0))
            lw = int(candidate.get("long_window", 0))
            if sw >= lw:
                continue

        key = tuple(sorted(candidate.items()))
        if key in seen:
            continue
        seen.add(key)
        variations.append(candidate)

    return variations


def list_generated_strategies() -> list[str]:
    """List strategy names found in the strategies directory."""
    names = []
    for p in STRATEGIES_DIR.glob("*.py"):
        if p.name.startswith("_"):
            continue
        name = p.stem
        if _VALID_NAME_RE.match(name):
            names.append(name)
    return sorted(names)
