# src\explore_gui_app\services\refinement.py
from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Iterable

from backtest.exploration_loop import BollingerExplorationResult
from backtest_gui_app.services.strategy_params import StrategyParamSpec


@dataclass(frozen=True)
class ScoredExplorationResult:
    result: BollingerExplorationResult
    score: float
    verdict_score: float
    cross_month_score: float
    pips_score: float
    pf_score: float
    win_rate_score: float


@dataclass(frozen=True)
class ParameterTrendSummary:
    param_key: str
    weighted_median: float | None
    weighted_min: float | None
    weighted_max: float | None
    normalized_span: float
    observation_count: int
    recommended_range: tuple[float, float, float]


@dataclass(frozen=True)
class RefinementPlan:
    scored_results: list[ScoredExplorationResult]
    top_results: list[ScoredExplorationResult]
    recommended_ranges: dict[str, tuple[float, float, float]]
    base_overrides: dict[str, float]
    seed_overrides_list: list[dict[str, float]]
    parameter_summaries: list[ParameterTrendSummary]
    summary_lines: list[str]


def build_refinement_plan(
    *,
    strategy_name: str,
    results: list[BollingerExplorationResult],
    current_ranges: dict[str, tuple[float, float, float]],
    specs: list[StrategyParamSpec],
    top_n: int = 5,
    max_seed_count: int = 3,
) -> RefinementPlan:
    if len(results) < 3:
        raise ValueError("At least 3 exploration results are required to refine trends.")

    if not current_ranges:
        raise ValueError("No exploration parameter ranges are enabled.")

    if not specs:
        raise ValueError(f"No parameter specs found for strategy '{strategy_name}'.")

    scored_results = score_exploration_results(results)
    scored_results = sorted(scored_results, key=lambda x: x.score, reverse=True)

    top_n = max(1, min(top_n, len(scored_results)))
    top_results = scored_results[:top_n]

    spec_index = _build_spec_index(specs)
    parameter_summaries: list[ParameterTrendSummary] = []
    recommended_ranges: dict[str, tuple[float, float, float]] = {}

    for param_key, current_range in current_ranges.items():
        spec = spec_index.get(param_key)
        if spec is None:
            recommended_ranges[param_key] = current_range
            parameter_summaries.append(
                ParameterTrendSummary(
                    param_key=param_key,
                    weighted_median=None,
                    weighted_min=None,
                    weighted_max=None,
                    normalized_span=1.0,
                    observation_count=0,
                    recommended_range=current_range,
                )
            )
            continue

        summary = summarize_parameter_trend(
            param_key=param_key,
            top_results=top_results,
            current_range=current_range,
            spec=spec,
        )
        parameter_summaries.append(summary)
        recommended_ranges[param_key] = summary.recommended_range

    recommended_ranges = apply_strategy_range_constraints(
        strategy_name=strategy_name,
        ranges=recommended_ranges,
        spec_index=spec_index,
    )

    base_overrides = dict(top_results[0].result.param_overrides or {})
    base_overrides = apply_strategy_override_constraints(
        strategy_name=strategy_name,
        overrides=base_overrides,
        spec_index=spec_index,
    )

    seed_overrides_list: list[dict[str, float]] = []
    seen: set[tuple[tuple[str, float], ...]] = set()

    for scored in top_results[:max_seed_count]:
        candidate = dict(scored.result.param_overrides or {})
        if not candidate:
            continue
        candidate = apply_strategy_override_constraints(
            strategy_name=strategy_name,
            overrides=candidate,
            spec_index=spec_index,
        )
        key = tuple(sorted((k, float(v)) for k, v in candidate.items()))
        if key in seen:
            continue
        seen.add(key)
        seed_overrides_list.append(candidate)

    summary_lines = build_summary_lines(
        strategy_name=strategy_name,
        top_results=top_results,
        parameter_summaries=parameter_summaries,
        original_ranges=current_ranges,
        refined_ranges=recommended_ranges,
    )

    return RefinementPlan(
        scored_results=scored_results,
        top_results=top_results,
        recommended_ranges=recommended_ranges,
        base_overrides=base_overrides,
        seed_overrides_list=seed_overrides_list,
        parameter_summaries=parameter_summaries,
        summary_lines=summary_lines,
    )


def score_exploration_results(
    results: list[BollingerExplorationResult],
) -> list[ScoredExplorationResult]:
    total_pips_values = [_get_total_pips(r) for r in results]
    min_pips = min(total_pips_values) if total_pips_values else 0.0
    max_pips = max(total_pips_values) if total_pips_values else 0.0

    scored: list[ScoredExplorationResult] = []
    for result in results:
        verdict_score = score_verdict(result.verdict)
        cross_month_score = score_cross_month(result)
        pips_score = score_total_pips(_get_total_pips(result), min_pips, max_pips)
        pf_score = score_profit_factor(_get_profit_factor(result))
        win_rate_score = score_win_rate(_get_win_rate(result))

        total_score = (
            0.40 * cross_month_score
            + 0.30 * pips_score
            + 0.20 * pf_score
            + 0.07 * verdict_score
            + 0.03 * win_rate_score
        )

        scored.append(
            ScoredExplorationResult(
                result=result,
                score=round(total_score, 6),
                verdict_score=verdict_score,
                cross_month_score=cross_month_score,
                pips_score=pips_score,
                pf_score=pf_score,
                win_rate_score=win_rate_score,
            )
        )
    return scored


def score_verdict(verdict: str | None) -> float:
    mapping = {
        "adopt": 1.00,
        "improve": 0.60,
        "discard": 0.20,
    }
    return mapping.get((verdict or "").lower(), 0.20)


def score_cross_month(result: BollingerExplorationResult) -> float:
    verdict: str | None = None

    if result.integrated_evaluation is not None:
        verdict = result.integrated_evaluation.verdict.value
    elif result.cross_month_evaluation is not None:
        verdict = result.cross_month_evaluation.verdict.value

    mapping = {
        "adopt": 1.00,
        "improve": 0.70,
        "discard": 0.10,
    }
    if verdict is None:
        return 0.35
    return mapping.get(verdict.lower(), 0.10)


def score_total_pips(value: float, min_value: float, max_value: float) -> float:
    if max_value <= min_value:
        return 0.5
    normalized = (value - min_value) / (max_value - min_value)
    return _clamp(normalized, 0.0, 1.0)


def score_profit_factor(value: float | None) -> float:
    if value is None:
        return 0.0
    if value <= 0.8:
        return 0.0
    if value < 1.0:
        return 0.2
    if value < 1.2:
        return 0.5
    if value < 1.5:
        return 0.8
    return 1.0


def score_win_rate(value: float | None) -> float:
    if value is None:
        return 0.0
    if value < 45.0:
        return 0.0
    if value < 50.0:
        return 0.3
    if value < 55.0:
        return 0.5
    if value < 60.0:
        return 0.7
    return 1.0


def summarize_parameter_trend(
    *,
    param_key: str,
    top_results: list[ScoredExplorationResult],
    current_range: tuple[float, float, float],
    spec: StrategyParamSpec,
) -> ParameterTrendSummary:
    observations: list[tuple[float, float]] = []
    for scored in top_results:
        value = scored.result.param_overrides.get(param_key)
        if value is None:
            continue
        observations.append((float(value), float(scored.score)))

    if len(observations) < 2:
        return ParameterTrendSummary(
            param_key=param_key,
            weighted_median=None,
            weighted_min=None,
            weighted_max=None,
            normalized_span=1.0,
            observation_count=len(observations),
            recommended_range=current_range,
        )

    values = [v for v, _ in observations]
    weights = [w for _, w in observations]

    weighted_med = weighted_median(values, weights)
    span_min = min(values)
    span_max = max(values)
    value_span = span_max - span_min

    current_lo, current_hi, step = current_range
    current_width = max(0.0, current_hi - current_lo)
    normalized_span = 1.0 if current_width <= 0 else _clamp(value_span / current_width, 0.0, 1.0)

    shrink_ratio = recommend_shrink_ratio(normalized_span)
    recommended_range = generate_refined_range(
        center=weighted_med,
        current_range=current_range,
        spec=spec,
        shrink_ratio=shrink_ratio,
    )

    return ParameterTrendSummary(
        param_key=param_key,
        weighted_median=weighted_med,
        weighted_min=span_min,
        weighted_max=span_max,
        normalized_span=normalized_span,
        observation_count=len(observations),
        recommended_range=recommended_range,
    )


def recommend_shrink_ratio(normalized_span: float) -> float:
    if normalized_span <= 0.20:
        return 0.35
    if normalized_span <= 0.40:
        return 0.50
    if normalized_span <= 0.70:
        return 0.70
    return 0.90


def generate_refined_range(
    *,
    center: float,
    current_range: tuple[float, float, float],
    spec: StrategyParamSpec,
    shrink_ratio: float,
) -> tuple[float, float, float]:
    current_lo, current_hi, step = current_range
    current_width = max(0.0, current_hi - current_lo)

    minimum_width = max(step * 2.0, current_width * 0.10)
    proposed_width = max(current_width * shrink_ratio, minimum_width)

    new_lo = center - proposed_width / 2.0
    new_hi = center + proposed_width / 2.0

    new_lo = max(spec.min_val, new_lo)
    new_hi = min(spec.max_val, new_hi)

    if new_hi <= new_lo:
        new_hi = min(spec.max_val, new_lo + minimum_width)
        new_lo = max(spec.min_val, new_hi - minimum_width)

    new_lo = normalize_to_step(new_lo, step, spec.min_val, mode="floor")
    new_hi = normalize_to_step(new_hi, step, spec.min_val, mode="ceil")

    if new_hi <= new_lo:
        new_hi = normalize_to_step(new_lo + max(step, minimum_width), step, spec.min_val, mode="ceil")
        new_hi = min(spec.max_val, new_hi)
        if new_hi <= new_lo:
            new_lo = max(spec.min_val, new_hi - step)

    if spec.param_type == "int":
        return (int(round(new_lo)), int(round(new_hi)), int(round(step)))

    decimals = spec.decimals
    return (
        round(float(new_lo), decimals),
        round(float(new_hi), decimals),
        round(float(step), decimals),
    )


def normalize_to_step(
    value: float,
    step: float,
    origin: float,
    *,
    mode: str,
) -> float:
    if step <= 0:
        return value

    relative = (value - origin) / step
    if mode == "floor":
        steps = int(relative // 1)
    elif mode == "ceil":
        steps = int(-(-relative // 1))
    else:
        steps = int(round(relative))

    return origin + steps * step


def weighted_median(values: Iterable[float], weights: Iterable[float]) -> float:
    pairs = sorted(zip(values, weights), key=lambda x: x[0])
    total_weight = sum(max(w, 0.0) for _, w in pairs)
    if total_weight <= 0:
        return float(median([v for v, _ in pairs]))

    cumulative = 0.0
    threshold = total_weight / 2.0
    for value, weight in pairs:
        cumulative += max(weight, 0.0)
        if cumulative >= threshold:
            return float(value)
    return float(pairs[-1][0])


def apply_strategy_override_constraints(
    *,
    strategy_name: str,
    overrides: dict[str, float],
    spec_index: dict[str, StrategyParamSpec],
) -> dict[str, float]:
    constrained = dict(overrides)

    trend_key = "mt4_bridge.strategies.bollinger_trend_B::TREND_SLOPE_THRESHOLD"
    strong_key = "mt4_bridge.strategies.bollinger_trend_B::STRONG_TREND_SLOPE_THRESHOLD"

    if strategy_name in {"bollinger_trend_B", "bollinger_combo_AB", "bollinger_combo_AB_v1"}:
        trend_val = constrained.get(trend_key)
        strong_val = constrained.get(strong_key)
        if trend_val is not None and strong_val is not None and strong_val < trend_val:
            constrained[strong_key] = trend_val

    for key, value in list(constrained.items()):
        spec = spec_index.get(key)
        if spec is None:
            continue
        bounded = min(max(float(value), spec.min_val), spec.max_val)
        if spec.param_type == "int":
            constrained[key] = int(round(bounded))
        else:
            constrained[key] = round(bounded, spec.decimals)

    return constrained


def apply_strategy_range_constraints(
    *,
    strategy_name: str,
    ranges: dict[str, tuple[float, float, float]],
    spec_index: dict[str, StrategyParamSpec],
) -> dict[str, tuple[float, float, float]]:
    constrained = dict(ranges)

    trend_key = "mt4_bridge.strategies.bollinger_trend_B::TREND_SLOPE_THRESHOLD"
    strong_key = "mt4_bridge.strategies.bollinger_trend_B::STRONG_TREND_SLOPE_THRESHOLD"

    if strategy_name in {"bollinger_trend_B", "bollinger_combo_AB", "bollinger_combo_AB_v1"}:
        trend_range = constrained.get(trend_key)
        strong_range = constrained.get(strong_key)

        if trend_range is not None and strong_range is not None:
            t_lo, t_hi, t_step = trend_range
            s_lo, s_hi, s_step = strong_range
            s_lo = max(s_lo, t_lo)
            s_hi = max(s_hi, t_hi)

            strong_spec = spec_index.get(strong_key)
            if strong_spec is not None:
                s_lo = min(max(s_lo, strong_spec.min_val), strong_spec.max_val)
                s_hi = min(max(s_hi, strong_spec.min_val), strong_spec.max_val)
                s_lo = normalize_to_step(s_lo, s_step, strong_spec.min_val, mode="floor")
                s_hi = normalize_to_step(s_hi, s_step, strong_spec.min_val, mode="ceil")

            if s_hi <= s_lo:
                s_hi = s_lo + max(s_step, 0.0)

            constrained[strong_key] = (s_lo, s_hi, s_step)

    return constrained


def build_summary_lines(
    *,
    strategy_name: str,
    top_results: list[ScoredExplorationResult],
    parameter_summaries: list[ParameterTrendSummary],
    original_ranges: dict[str, tuple[float, float, float]],
    refined_ranges: dict[str, tuple[float, float, float]],
) -> list[str]:
    lines: list[str] = []
    lines.append(f"Trend refinement prepared for strategy={strategy_name}")
    lines.append(f"Top results used: {len(top_results)}")

    for idx, scored in enumerate(top_results, start=1):
        total_pips = _get_total_pips(scored.result)
        pf = _get_profit_factor(scored.result)
        win_rate = _get_win_rate(scored.result)
        lines.append(
            "  "
            f"#{idx}: score={scored.score:.3f}, verdict={scored.result.verdict}, "
            f"pips={total_pips:.1f}, pf={pf if pf is not None else '-'}, "
            f"win_rate={f'{win_rate:.1f}%' if win_rate is not None else '-'}"
        )

    lines.append("Refined parameter ranges:")
    for summary in parameter_summaries:
        old_range = original_ranges.get(summary.param_key)
        new_range = refined_ranges.get(summary.param_key)
        param_name = summary.param_key.split("::", 1)[1]

        if old_range is None or new_range is None:
            lines.append(f"  {param_name}: unchanged (range unavailable)")
            continue

        if summary.observation_count < 2 or summary.weighted_median is None:
            lines.append(
                f"  {param_name}: kept {format_range(old_range)} "
                f"(insufficient observations: {summary.observation_count})"
            )
            continue

        lines.append(
            f"  {param_name}: {format_range(old_range)} -> {format_range(new_range)} "
            f"(center={summary.weighted_median}, span={summary.normalized_span:.2f}, "
            f"obs={summary.observation_count})"
        )
    return lines


def format_range(value: tuple[float, float, float]) -> str:
    lo, hi, step = value
    return f"{lo} .. {hi} (step {step})"


def _build_spec_index(
    specs: list[StrategyParamSpec],
) -> dict[str, StrategyParamSpec]:
    return {f"{spec.module_path}::{spec.name}": spec for spec in specs}


def _get_total_pips(result: BollingerExplorationResult) -> float:
    stats_summary = getattr(result.evaluation, "stats_summary", {}) or {}
    value = stats_summary.get("total_pips")
    return float(value) if value is not None else 0.0


def _get_profit_factor(result: BollingerExplorationResult) -> float | None:
    stats_summary = getattr(result.evaluation, "stats_summary", {}) or {}
    value = stats_summary.get("profit_factor")
    return float(value) if value is not None else None


def _get_win_rate(result: BollingerExplorationResult) -> float | None:
    stats_summary = getattr(result.evaluation, "stats_summary", {}) or {}
    value = stats_summary.get("win_rate")
    return float(value) if value is not None else None


def _clamp(value: float, lo: float, hi: float) -> float:
    return min(max(value, lo), hi)