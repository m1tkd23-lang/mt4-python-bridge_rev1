# src/mt4_bridge/strategies/bollinger_range_v4_4_guarded.py
from __future__ import annotations

from dataclasses import replace

from mt4_bridge.models import MarketSnapshot, PositionSnapshot, SignalAction, SignalDecision
from mt4_bridge.signal_exceptions import SignalEngineError
from mt4_bridge.strategies import bollinger_range_v4_4 as base_strategy


# =========================
# 危険検知パラメータ
# =========================
# 「range前提が壊れ始めた」だけでなく、
# 「すでにトレンド継続中で逆張りが危険」な状態も止める。
BANDWIDTH_EXPANSION_THRESHOLD = 1.15
DISTANCE_EXPANSION_THRESHOLD = 1.30
TREND_SLOPE_ACCEL_THRESHOLD = 1.50

# 絶対傾き。
# まずは guarded_bac と同じ控えめ設定を採用する。
ABSOLUTE_SLOPE_THRESHOLD = 0.030

# バンドウォーク検知
BAND_WALK_LOOKBACK_BARS = 4
BAND_WALK_MIN_HITS = 3

# バンド端にどれだけ近いか。
# 0.20 なら「下位20%以内 / 上位20%以内」を意味する。
BAND_EDGE_ZONE_RATIO = 0.20

# =========================
# エントリーブロック条件
# =========================
# スコア条件に加えて、方向別の明確な危険条件でもブロックする。
BLOCK_NEW_ENTRY_ON_RISK_SCORE = 3


def required_bars() -> int:
    period = base_strategy.BOLLINGER_PERIOD
    return max(
        base_strategy.required_bars(),
        period + BAND_WALK_LOOKBACK_BARS + 2,
    )


def _simple_moving_average(values: list[float]) -> float:
    if not values:
        raise SignalEngineError("Moving average requires at least 1 value")
    return sum(values) / len(values)


def _estimate_upper_lower(
    window: list[float],
    middle: float,
) -> tuple[float, float]:
    variance = sum((value - middle) ** 2 for value in window) / len(window)
    stddev = variance**0.5
    upper = middle + (base_strategy.BOLLINGER_SIGMA * stddev)
    lower = middle - (base_strategy.BOLLINGER_SIGMA * stddev)
    return upper, lower


def _compute_band_snapshot(closes: list[float]) -> dict[str, float]:
    period = base_strategy.BOLLINGER_PERIOD
    if len(closes) != period:
        raise SignalEngineError(f"Band snapshot requires exactly {period} closes")

    middle = _simple_moving_average(closes)
    upper, lower = _estimate_upper_lower(closes, middle)
    width = upper - lower

    return {
        "middle": middle,
        "upper": upper,
        "lower": lower,
        "width": width,
    }


def _is_close_near_lower_band(
    *,
    close: float,
    lower: float,
    upper: float,
) -> bool:
    width = upper - lower
    if width <= 0.0:
        return False
    edge_limit = lower + (width * BAND_EDGE_ZONE_RATIO)
    return close <= edge_limit


def _is_close_near_upper_band(
    *,
    close: float,
    lower: float,
    upper: float,
) -> bool:
    width = upper - lower
    if width <= 0.0:
        return False
    edge_limit = upper - (width * BAND_EDGE_ZONE_RATIO)
    return close >= edge_limit


def _detect_band_walk_flags(
    closes: list[float],
) -> dict[str, bool | int]:
    period = base_strategy.BOLLINGER_PERIOD
    lower_hits = 0
    upper_hits = 0

    for offset in range(BAND_WALK_LOOKBACK_BARS):
        end_index = len(closes) - offset
        start_index = end_index - period
        window = closes[start_index:end_index]
        if len(window) != period:
            continue

        snapshot = _compute_band_snapshot(window)
        close = window[-1]

        if _is_close_near_lower_band(
            close=close,
            lower=snapshot["lower"],
            upper=snapshot["upper"],
        ):
            lower_hits += 1

        if _is_close_near_upper_band(
            close=close,
            lower=snapshot["lower"],
            upper=snapshot["upper"],
        ):
            upper_hits += 1

    lower_band_walk = lower_hits >= BAND_WALK_MIN_HITS
    upper_band_walk = upper_hits >= BAND_WALK_MIN_HITS

    return {
        "lower_band_walk": lower_band_walk,
        "upper_band_walk": upper_band_walk,
        "lower_band_walk_hits": lower_hits,
        "upper_band_walk_hits": upper_hits,
    }


def _build_debug_metrics(
    risk_flags: dict[str, bool | float | int],
) -> dict[str, object]:
    return {
        "bandwidth_expanding": bool(risk_flags["bandwidth_expanding"]),
        "distance_expanding": bool(risk_flags["distance_expanding"]),
        "trend_slope_accelerating": bool(risk_flags["trend_slope_accelerating"]),
        "risk_score": int(risk_flags["risk_score"]),
        "latest_band_width": float(risk_flags["latest_band_width"]),
        "prev_band_width": float(risk_flags["prev_band_width"]),
        "latest_distance": float(risk_flags["latest_distance"]),
        "prev_distance": float(risk_flags["prev_distance"]),
        "latest_slope": float(risk_flags["latest_slope"]),
        "prev_slope": float(risk_flags["prev_slope"]),
        "strong_down_slope": bool(risk_flags["strong_down_slope"]),
        "strong_up_slope": bool(risk_flags["strong_up_slope"]),
        "lower_band_walk": bool(risk_flags["lower_band_walk"]),
        "upper_band_walk": bool(risk_flags["upper_band_walk"]),
        "lower_band_walk_hits": int(risk_flags["lower_band_walk_hits"]),
        "upper_band_walk_hits": int(risk_flags["upper_band_walk_hits"]),
        "dangerous_for_buy": bool(risk_flags["dangerous_for_buy"]),
        "dangerous_for_sell": bool(risk_flags["dangerous_for_sell"]),
    }


def _detect_risk_flags(market_snapshot: MarketSnapshot) -> dict[str, bool | float | int]:
    bars = market_snapshot.bars
    if len(bars) < required_bars():
        return {}

    closes = [bar.close for bar in bars]
    period = base_strategy.BOLLINGER_PERIOD

    latest_window = closes[-period:]
    prev_window = closes[-(period + 1) : -1]
    prev2_window = closes[-(period + 2) : -2]

    latest_snapshot = _compute_band_snapshot(latest_window)
    prev_snapshot = _compute_band_snapshot(prev_window)
    prev2_snapshot = _compute_band_snapshot(prev2_window)

    latest_middle = latest_snapshot["middle"]
    prev_middle = prev_snapshot["middle"]
    prev2_middle = prev2_snapshot["middle"]

    latest_band_width = latest_snapshot["width"]
    prev_band_width = prev_snapshot["width"]

    latest_close = closes[-1]
    prev_close = closes[-2]

    latest_distance = abs(latest_close - latest_middle)
    prev_distance = abs(prev_close - prev_middle)

    latest_slope = latest_middle - prev_middle
    prev_slope = prev_middle - prev2_middle

    bandwidth_expanding = (
        prev_band_width > 0.0
        and (latest_band_width / prev_band_width) >= BANDWIDTH_EXPANSION_THRESHOLD
    )

    distance_expanding = (
        prev_distance > 0.0
        and (latest_distance / prev_distance) >= DISTANCE_EXPANSION_THRESHOLD
    )

    trend_slope_accelerating = (
        abs(prev_slope) > 0.0
        and (abs(latest_slope) / abs(prev_slope)) >= TREND_SLOPE_ACCEL_THRESHOLD
    )

    strong_down_slope = latest_slope <= -ABSOLUTE_SLOPE_THRESHOLD
    strong_up_slope = latest_slope >= ABSOLUTE_SLOPE_THRESHOLD

    band_walk_flags = _detect_band_walk_flags(closes)

    lower_band_walk = bool(band_walk_flags["lower_band_walk"])
    upper_band_walk = bool(band_walk_flags["upper_band_walk"])

    dangerous_for_buy = strong_down_slope and lower_band_walk
    dangerous_for_sell = strong_up_slope and upper_band_walk

    risk_score = int(bandwidth_expanding) + int(distance_expanding) + int(
        trend_slope_accelerating
    )

    return {
        "bandwidth_expanding": bandwidth_expanding,
        "distance_expanding": distance_expanding,
        "trend_slope_accelerating": trend_slope_accelerating,
        "risk_score": risk_score,
        "latest_band_width": latest_band_width,
        "prev_band_width": prev_band_width,
        "latest_distance": latest_distance,
        "prev_distance": prev_distance,
        "latest_slope": latest_slope,
        "prev_slope": prev_slope,
        "strong_down_slope": strong_down_slope,
        "strong_up_slope": strong_up_slope,
        "lower_band_walk": lower_band_walk,
        "upper_band_walk": upper_band_walk,
        "lower_band_walk_hits": int(band_walk_flags["lower_band_walk_hits"]),
        "upper_band_walk_hits": int(band_walk_flags["upper_band_walk_hits"]),
        "dangerous_for_buy": dangerous_for_buy,
        "dangerous_for_sell": dangerous_for_sell,
    }


def _append_risk_flags_to_reason(
    reason: str,
    risk_flags: dict[str, bool | float | int],
) -> str:
    if not risk_flags:
        return reason

    risk_text = (
        "risk_flags=("
        f"bandwidth_expanding={risk_flags['bandwidth_expanding']}, "
        f"distance_expanding={risk_flags['distance_expanding']}, "
        f"trend_slope_accelerating={risk_flags['trend_slope_accelerating']}, "
        f"risk_score={risk_flags['risk_score']}, "
        f"latest_band_width={float(risk_flags['latest_band_width']):.6f}, "
        f"prev_band_width={float(risk_flags['prev_band_width']):.6f}, "
        f"latest_distance={float(risk_flags['latest_distance']):.6f}, "
        f"prev_distance={float(risk_flags['prev_distance']):.6f}, "
        f"latest_slope={float(risk_flags['latest_slope']):.6f}, "
        f"prev_slope={float(risk_flags['prev_slope']):.6f}, "
        f"strong_down_slope={risk_flags['strong_down_slope']}, "
        f"strong_up_slope={risk_flags['strong_up_slope']}, "
        f"lower_band_walk={risk_flags['lower_band_walk']}, "
        f"upper_band_walk={risk_flags['upper_band_walk']}, "
        f"lower_band_walk_hits={risk_flags['lower_band_walk_hits']}, "
        f"upper_band_walk_hits={risk_flags['upper_band_walk_hits']}, "
        f"dangerous_for_buy={risk_flags['dangerous_for_buy']}, "
        f"dangerous_for_sell={risk_flags['dangerous_for_sell']})"
    )
    return f"{reason} | {risk_text}"


def _should_block_new_entry(
    *,
    decision: SignalDecision,
    position_snapshot: PositionSnapshot,
    risk_flags: dict[str, bool | float | int],
) -> bool:
    if not risk_flags:
        return False

    if position_snapshot.positions:
        return False

    if decision.action not in {SignalAction.BUY, SignalAction.SELL}:
        return False

    if decision.action == SignalAction.BUY and bool(risk_flags["dangerous_for_buy"]):
        return True

    if decision.action == SignalAction.SELL and bool(risk_flags["dangerous_for_sell"]):
        return True

    risk_score = int(risk_flags["risk_score"])
    return risk_score >= BLOCK_NEW_ENTRY_ON_RISK_SCORE


def evaluate_bollinger_range_v4_4_guarded(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_range_v4_4_guarded",
) -> SignalDecision:
    decision = base_strategy.evaluate_bollinger_range_v4_4(
        market_snapshot=market_snapshot,
        position_snapshot=position_snapshot,
        strategy_name=strategy_name,
    )

    risk_flags = _detect_risk_flags(market_snapshot)
    reason_with_flags = _append_risk_flags_to_reason(decision.reason, risk_flags)
    debug_metrics = _build_debug_metrics(risk_flags) if risk_flags else None

    if _should_block_new_entry(
        decision=decision,
        position_snapshot=position_snapshot,
        risk_flags=risk_flags,
    ):
        blocked_reason = (
            "new entry blocked by guarded filter"
            f" | original_action={decision.action.value}"
            f" | {reason_with_flags}"
        )
        return replace(
            decision,
            action=SignalAction.HOLD,
            reason=blocked_reason,
            debug_metrics=debug_metrics,
        )

    return replace(
        decision,
        reason=reason_with_flags,
        debug_metrics=debug_metrics,
    )