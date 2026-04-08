# src/mt4_bridge/strategies/bollinger_range_v4_6_1.py
from __future__ import annotations

from dataclasses import dataclass, replace
from math import sqrt

from mt4_bridge.models import (
    MarketSnapshot,
    OpenPosition,
    PositionSnapshot,
    SignalAction,
    SignalDecision,
)
from mt4_bridge.signal_exceptions import SignalEngineError
from mt4_bridge.strategies.bollinger_range_v4_4 import (
    evaluate_bollinger_range_v4_4,
)


# =========================
# 調整パラメータ
# =========================
# ボリンジャーバンド
BOLLINGER_PERIOD = 20
BOLLINGER_SIGMA = 2.0
BOLLINGER_EXTREME_SIGMA = 3.0  # v4.4 追加: 3σ即時タッチ用

# レンジ判定用 MA
RANGE_MA_PERIOD = 10
RANGE_SLOPE_LOOKBACK = 5
RANGE_SLOPE_THRESHOLD = 0.0002

# レンジ判定用のバンド幅しきい値
# normalized_band_width = (upper - lower) / middle
RANGE_BAND_WIDTH_THRESHOLD = 0.0025

# レンジ判定用のミドル距離しきい値
# distance_from_middle = abs(latest_close - middle_band) / middle_band
RANGE_MIDDLE_DISTANCE_THRESHOLD = 0.0012

# トレンド判定用 MA
TREND_MA_PERIOD = 30
TREND_SLOPE_LOOKBACK = 2
TREND_SLOPE_THRESHOLD = 0.0003

# トレンド判定時に価格位置も見る
TREND_PRICE_POSITION_FILTER_ENABLED = True

# エントリー確認
# trend:
#   previous_close がまだブレイクしておらず
#   latest_close でブレイクしたらエントリー
TREND_REQUIRE_BREAK_CONFIRMATION = True

# 決済ルール
CLOSE_ON_OPPOSITE_TREND_STATE = True

RANGE_MAGIC_NUMBER = 44001
TREND_MAGIC_NUMBER = 44002


@dataclass(frozen=True)
class _AnalysisContext:
    previous_bar_time: object
    latest_bar_time: object
    previous_close: float
    latest_close: float
    latest_high: float
    latest_low: float
    middle_band: float
    upper_band: float
    lower_band: float
    band_width: float
    normalized_width: float
    range_slope: float
    trend_slope: float
    trend_current_ma: float
    previous_upper_band: float
    previous_lower_band: float
    distance_from_middle: float
    latest_upper_extreme_band: float
    latest_lower_extreme_band: float
    market_state: str
    state_reason: str


def required_bars() -> int:
    return max(
        BOLLINGER_PERIOD,
        RANGE_MA_PERIOD + RANGE_SLOPE_LOOKBACK,
        TREND_MA_PERIOD + TREND_SLOPE_LOOKBACK,
    )


def _simple_moving_average(values: list[float]) -> float:
    if not values:
        raise SignalEngineError("Moving average requires at least 1 value")
    return sum(values) / len(values)


def _standard_deviation(values: list[float], mean: float) -> float:
    if not values:
        raise SignalEngineError("Standard deviation requires at least 1 value")
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return sqrt(variance)


def _calculate_bollinger_bands_from_window(
    window: list[float],
    sigma: float,
) -> tuple[float, float, float, float]:
    if len(window) < BOLLINGER_PERIOD:
        raise SignalEngineError(
            f"At least {BOLLINGER_PERIOD} closes are required for Bollinger Bands"
        )

    middle = _simple_moving_average(window)
    stddev = _standard_deviation(window, middle)
    upper = middle + (sigma * stddev)
    lower = middle - (sigma * stddev)
    band_width = upper - lower
    return middle, upper, lower, band_width


def _calculate_latest_bollinger_bands(
    closes: list[float],
    sigma: float,
) -> tuple[float, float, float, float]:
    if len(closes) < BOLLINGER_PERIOD:
        raise SignalEngineError(
            f"At least {BOLLINGER_PERIOD} closes are required to calculate Bollinger Bands"
        )
    return _calculate_bollinger_bands_from_window(closes[-BOLLINGER_PERIOD:], sigma)


def _calculate_previous_bollinger_bands(
    closes: list[float],
    sigma: float,
) -> tuple[float, float, float, float]:
    if len(closes) < BOLLINGER_PERIOD + 1:
        raise SignalEngineError(
            f"At least {BOLLINGER_PERIOD + 1} closes are required for previous Bollinger Bands"
        )
    return _calculate_bollinger_bands_from_window(
        closes[-(BOLLINGER_PERIOD + 1) : -1],
        sigma,
    )


def _normalized_band_width(middle: float, band_width: float) -> float:
    if middle == 0:
        raise SignalEngineError("Middle band is zero; normalized band width undefined")
    return band_width / middle


def _distance_from_middle(latest_close: float, middle: float) -> float:
    if middle == 0:
        raise SignalEngineError("Middle band is zero; distance from middle undefined")
    return abs(latest_close - middle) / middle


def _calculate_recent_ma(
    closes: list[float],
    period: int,
) -> float:
    if len(closes) < period:
        raise SignalEngineError(
            f"At least {period} closes are required to calculate MA"
        )
    return _simple_moving_average(closes[-period:])


def _calculate_past_ma(
    closes: list[float],
    period: int,
    lookback: int,
) -> float:
    if len(closes) < period + lookback:
        raise SignalEngineError(
            f"At least {period + lookback} closes are required to calculate past MA"
        )
    end_index = len(closes) - lookback
    start_index = end_index - period
    window = closes[start_index:end_index]
    return _simple_moving_average(window)


def _normalized_slope(
    closes: list[float],
    period: int,
    lookback: int,
) -> tuple[float, float, float]:
    current_ma = _calculate_recent_ma(closes, period)
    past_ma = _calculate_past_ma(closes, period, lookback)

    if current_ma == 0:
        raise SignalEngineError("Current MA is zero; normalized slope undefined")

    slope = current_ma - past_ma
    normalized = slope / current_ma
    return normalized, current_ma, past_ma


def _is_trend_up(
    latest_close: float,
    trend_current_ma: float,
    trend_slope: float,
) -> bool:
    if trend_slope <= TREND_SLOPE_THRESHOLD:
        return False
    if TREND_PRICE_POSITION_FILTER_ENABLED and latest_close < trend_current_ma:
        return False
    return True


def _is_trend_down(
    latest_close: float,
    trend_current_ma: float,
    trend_slope: float,
) -> bool:
    if trend_slope >= -TREND_SLOPE_THRESHOLD:
        return False
    if TREND_PRICE_POSITION_FILTER_ENABLED and latest_close > trend_current_ma:
        return False
    return True


def _is_range(
    latest_close: float,
    middle_band: float,
    range_slope: float,
    normalized_band_width: float,
) -> bool:
    distance_from_middle = _distance_from_middle(latest_close, middle_band)
    return (
        abs(range_slope) <= RANGE_SLOPE_THRESHOLD
        and normalized_band_width <= RANGE_BAND_WIDTH_THRESHOLD
        and distance_from_middle <= RANGE_MIDDLE_DISTANCE_THRESHOLD
    )


def _determine_market_state(
    latest_close: float,
    middle_band: float,
    trend_current_ma: float,
    range_slope: float,
    trend_slope: float,
    normalized_band_width: float,
) -> tuple[str, str, float]:
    distance_from_middle = _distance_from_middle(latest_close, middle_band)

    if _is_trend_up(latest_close, trend_current_ma, trend_slope):
        return (
            "trend_up",
            (
                f"trend_up because trend_slope={trend_slope:.6f}"
                f" > threshold={TREND_SLOPE_THRESHOLD:.6f}"
                f" and latest_close={latest_close} >= trend_ma={trend_current_ma}"
            ),
            distance_from_middle,
        )

    if _is_trend_down(latest_close, trend_current_ma, trend_slope):
        return (
            "trend_down",
            (
                f"trend_down because trend_slope={trend_slope:.6f}"
                f" < -threshold={TREND_SLOPE_THRESHOLD:.6f}"
                f" and latest_close={latest_close} <= trend_ma={trend_current_ma}"
            ),
            distance_from_middle,
        )

    if _is_range(
        latest_close=latest_close,
        middle_band=middle_band,
        range_slope=range_slope,
        normalized_band_width=normalized_band_width,
    ):
        return (
            "range",
            (
                f"range because abs(range_slope)={abs(range_slope):.6f}"
                f" <= threshold={RANGE_SLOPE_THRESHOLD:.6f}"
                f" and normalized_band_width={normalized_band_width:.6f}"
                f" <= threshold={RANGE_BAND_WIDTH_THRESHOLD:.6f}"
                f" and distance_from_middle={distance_from_middle:.6f}"
                f" <= threshold={RANGE_MIDDLE_DISTANCE_THRESHOLD:.6f}"
            ),
            distance_from_middle,
        )

    return (
        "neutral",
        (
            f"neutral because no strong trend or range was confirmed"
            f" (range_slope={range_slope:.6f}, trend_slope={trend_slope:.6f},"
            f" normalized_band_width={normalized_band_width:.6f},"
            f" distance_from_middle={distance_from_middle:.6f})"
        ),
        distance_from_middle,
    )


def _trend_buy_confirmed(
    previous_close: float,
    latest_close: float,
    previous_upper_band: float,
    latest_upper_band: float,
) -> bool:
    if not TREND_REQUIRE_BREAK_CONFIRMATION:
        return latest_close >= latest_upper_band
    return previous_close <= previous_upper_band and latest_close > latest_upper_band


def _trend_sell_confirmed(
    previous_close: float,
    latest_close: float,
    previous_lower_band: float,
    latest_lower_band: float,
) -> bool:
    if not TREND_REQUIRE_BREAK_CONFIRMATION:
        return latest_close <= latest_lower_band
    return previous_close >= previous_lower_band and latest_close < latest_lower_band


def _is_range_lane_position(position: OpenPosition) -> bool:
    comment = (position.comment or "").lower()
    return (
        position.magic_number == RANGE_MAGIC_NUMBER
        or "lane:range" in comment
        or "entry_lane=range" in comment
    )


def _is_trend_lane_position(position: OpenPosition) -> bool:
    comment = (position.comment or "").lower()
    return (
        position.magic_number == TREND_MAGIC_NUMBER
        or "lane:trend" in comment
        or "entry_lane=trend" in comment
    )


def _get_range_position(position_snapshot: PositionSnapshot) -> OpenPosition | None:
    for position in position_snapshot.positions:
        if _is_range_lane_position(position):
            return position
    return None


def _get_trend_position(position_snapshot: PositionSnapshot) -> OpenPosition | None:
    for position in position_snapshot.positions:
        if _is_trend_lane_position(position):
            return position
    return None


def _build_reason_suffix(
    context: _AnalysisContext,
) -> str:
    return (
        f" (bollinger_period={BOLLINGER_PERIOD}, bollinger_sigma={BOLLINGER_SIGMA},"
        f" bollinger_extreme_sigma={BOLLINGER_EXTREME_SIGMA},"
        f" range_ma_period={RANGE_MA_PERIOD},"
        f" range_slope_lookback={RANGE_SLOPE_LOOKBACK},"
        f" range_slope_threshold={RANGE_SLOPE_THRESHOLD},"
        f" range_band_width_threshold={RANGE_BAND_WIDTH_THRESHOLD},"
        f" range_middle_distance_threshold={RANGE_MIDDLE_DISTANCE_THRESHOLD},"
        f" trend_ma_period={TREND_MA_PERIOD},"
        f" trend_slope_lookback={TREND_SLOPE_LOOKBACK},"
        f" trend_slope_threshold={TREND_SLOPE_THRESHOLD},"
        f" trend_price_position_filter_enabled={TREND_PRICE_POSITION_FILTER_ENABLED},"
        f" trend_require_break_confirmation={TREND_REQUIRE_BREAK_CONFIRMATION},"
        f" close_on_opposite_trend_state={CLOSE_ON_OPPOSITE_TREND_STATE},"
        f" state={context.market_state}, middle={context.middle_band},"
        f" upper={context.upper_band}, lower={context.lower_band},"
        f" upper_3sigma={context.latest_upper_extreme_band},"
        f" lower_3sigma={context.latest_lower_extreme_band},"
        f" previous_upper={context.previous_upper_band},"
        f" previous_lower={context.previous_lower_band},"
        f" normalized_band_width={context.normalized_width:.6f},"
        f" latest_band_width={context.band_width:.6f},"
        f" distance_from_middle={context.distance_from_middle:.6f},"
        f" range_slope={context.range_slope:.6f},"
        f" trend_slope={context.trend_slope:.6f},"
        f" trend_current_ma={context.trend_current_ma},"
        f" latest_high={context.latest_high}, latest_low={context.latest_low})"
    )


def _build_signal_decision(
    *,
    strategy_name: str,
    action: SignalAction,
    reason: str,
    entry_lane: str | None,
    entry_subtype: str | None,
    current_position: OpenPosition | None,
    context: _AnalysisContext,
) -> SignalDecision:
    return SignalDecision(
        strategy_name=strategy_name,
        action=action,
        reason=reason,
        previous_bar_time=context.previous_bar_time,
        latest_bar_time=context.latest_bar_time,
        previous_close=context.previous_close,
        latest_close=context.latest_close,
        current_position_ticket=current_position.ticket if current_position else None,
        current_position_type=(
            current_position.position_type.lower() if current_position else None
        ),
        entry_lane=entry_lane,
        entry_subtype=entry_subtype,
        market_state=context.market_state,
        middle_band=context.middle_band,
        upper_band=context.upper_band,
        lower_band=context.lower_band,
        normalized_band_width=context.normalized_width,
        range_slope=context.range_slope,
        trend_slope=context.trend_slope,
        trend_current_ma=context.trend_current_ma,
        distance_from_middle=context.distance_from_middle,
    )


def _build_analysis_context(
    market_snapshot: MarketSnapshot,
) -> _AnalysisContext:
    bars = market_snapshot.bars
    if len(bars) < required_bars():
        raise SignalEngineError(
            f"At least {required_bars()} bars are required to evaluate bollinger_range_v4_6_1"
        )

    closes = [bar.close for bar in bars]
    previous_bar = bars[-2]
    latest_bar = bars[-1]
    previous_close = previous_bar.close
    latest_close = latest_bar.close

    latest_middle, latest_upper, latest_lower, latest_band_width = (
        _calculate_latest_bollinger_bands(closes, BOLLINGER_SIGMA)
    )
    _, previous_upper, previous_lower, _ = _calculate_previous_bollinger_bands(
        closes,
        BOLLINGER_SIGMA,
    )
    _, latest_upper_extreme, latest_lower_extreme, _ = _calculate_latest_bollinger_bands(
        closes,
        BOLLINGER_EXTREME_SIGMA,
    )

    normalized_width = _normalized_band_width(latest_middle, latest_band_width)
    range_slope, _, _ = _normalized_slope(
        closes=closes,
        period=RANGE_MA_PERIOD,
        lookback=RANGE_SLOPE_LOOKBACK,
    )
    trend_slope, trend_current_ma, _ = _normalized_slope(
        closes=closes,
        period=TREND_MA_PERIOD,
        lookback=TREND_SLOPE_LOOKBACK,
    )

    market_state, state_reason, distance_from_middle = _determine_market_state(
        latest_close=latest_close,
        middle_band=latest_middle,
        trend_current_ma=trend_current_ma,
        range_slope=range_slope,
        trend_slope=trend_slope,
        normalized_band_width=normalized_width,
    )

    return _AnalysisContext(
        previous_bar_time=previous_bar.time,
        latest_bar_time=latest_bar.time,
        previous_close=previous_close,
        latest_close=latest_close,
        latest_high=latest_bar.high,
        latest_low=latest_bar.low,
        middle_band=latest_middle,
        upper_band=latest_upper,
        lower_band=latest_lower,
        band_width=latest_band_width,
        normalized_width=normalized_width,
        range_slope=range_slope,
        trend_slope=trend_slope,
        trend_current_ma=trend_current_ma,
        previous_upper_band=previous_upper,
        previous_lower_band=previous_lower,
        distance_from_middle=distance_from_middle,
        latest_upper_extreme_band=latest_upper_extreme,
        latest_lower_extreme_band=latest_lower_extreme,
        market_state=market_state,
        state_reason=state_reason,
    )


def _build_range_filtered_position_snapshot(
    market_snapshot: MarketSnapshot,
    range_position: OpenPosition | None,
) -> PositionSnapshot:
    positions: list[OpenPosition] = []
    if range_position is not None:
        positions.append(range_position)

    return PositionSnapshot(
        schema_version=position_snapshot_schema_version(range_position),
        generated_at=market_snapshot.generated_at,
        positions=positions,
    )


def position_snapshot_schema_version(range_position: OpenPosition | None) -> str:
    del range_position
    return "lane-filtered-1.0"


def _clone_range_decision_from_v4_4(
    decision: SignalDecision,
) -> SignalDecision:
    return replace(
        decision,
        entry_lane="range",
        entry_subtype="v4_4",
    )


def _evaluate_range_lane_v4_4(
    market_snapshot: MarketSnapshot,
    range_position: OpenPosition | None,
    strategy_name: str,
) -> SignalDecision:
    filtered_snapshot = _build_range_filtered_position_snapshot(
        market_snapshot=market_snapshot,
        range_position=range_position,
    )
    range_decision = evaluate_bollinger_range_v4_4(
        market_snapshot=market_snapshot,
        position_snapshot=filtered_snapshot,
        strategy_name=strategy_name,
    )
    return _clone_range_decision_from_v4_4(range_decision)


def _evaluate_trend_lane(
    strategy_name: str,
    context: _AnalysisContext,
    trend_position: OpenPosition | None,
) -> SignalDecision | None:
    reason_suffix = _build_reason_suffix(context)

    if trend_position is not None:
        current_type = trend_position.position_type.lower()

        if CLOSE_ON_OPPOSITE_TREND_STATE:
            if current_type == "buy" and context.market_state == "trend_down":
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "buy trend position closed because state switched to trend_down"
                        + reason_suffix
                    ),
                    entry_lane="trend",
                    entry_subtype="opposite_trend_exit",
                    current_position=trend_position,
                    context=context,
                )

            if current_type == "sell" and context.market_state == "trend_up":
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "sell trend position closed because state switched to trend_up"
                        + reason_suffix
                    ),
                    entry_lane="trend",
                    entry_subtype="opposite_trend_exit",
                    current_position=trend_position,
                    context=context,
                )

        return None

    if context.market_state == "trend_up" and _trend_buy_confirmed(
        previous_close=context.previous_close,
        latest_close=context.latest_close,
        previous_upper_band=context.previous_upper_band,
        latest_upper_band=context.upper_band,
    ):
        return _build_signal_decision(
            strategy_name=strategy_name,
            action=SignalAction.BUY,
            reason=(
                "trend-follow buy confirmed by upper band breakout;"
                f" previous_close={context.previous_close}, latest_close={context.latest_close},"
                f" previous_upper={context.previous_upper_band}, latest_upper={context.upper_band};"
                f" {context.state_reason}"
                + reason_suffix
            ),
            entry_lane="trend",
            entry_subtype="breakout",
            current_position=None,
            context=context,
        )

    if context.market_state == "trend_down" and _trend_sell_confirmed(
        previous_close=context.previous_close,
        latest_close=context.latest_close,
        previous_lower_band=context.previous_lower_band,
        latest_lower_band=context.lower_band,
    ):
        return _build_signal_decision(
            strategy_name=strategy_name,
            action=SignalAction.SELL,
            reason=(
                "trend-follow sell confirmed by lower band breakout;"
                f" previous_close={context.previous_close}, latest_close={context.latest_close},"
                f" previous_lower={context.previous_lower_band}, latest_lower={context.lower_band};"
                f" {context.state_reason}"
                + reason_suffix
            ),
            entry_lane="trend",
            entry_subtype="breakout",
            current_position=None,
            context=context,
        )

    return None


def evaluate_bollinger_range_v4_6_1_signals(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_range_v4_6_1",
) -> list[SignalDecision]:
    context = _build_analysis_context(market_snapshot)
    range_position = _get_range_position(position_snapshot)
    trend_position = _get_trend_position(position_snapshot)

    decisions: list[SignalDecision] = []

    range_decision = _evaluate_range_lane_v4_4(
        market_snapshot=market_snapshot,
        range_position=range_position,
        strategy_name=strategy_name,
    )
    if range_decision.action != SignalAction.HOLD:
        decisions.append(range_decision)

    trend_decision = _evaluate_trend_lane(
        strategy_name=strategy_name,
        context=context,
        trend_position=trend_position,
    )
    if trend_decision is not None:
        decisions.append(trend_decision)

    if decisions:
        return decisions

    return [
        _build_signal_decision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=(
                "no actionable lane decision"
                f" (market_state={context.market_state},"
                f" has_range_position={range_position is not None},"
                f" has_trend_position={trend_position is not None};"
                f" {context.state_reason})"
                + _build_reason_suffix(context)
            ),
            entry_lane=None,
            entry_subtype=None,
            current_position=None,
            context=context,
        )
    ]


def evaluate_bollinger_range_v4_6_1(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_range_v4_6_1",
) -> SignalDecision:
    decisions = evaluate_bollinger_range_v4_6_1_signals(
        market_snapshot=market_snapshot,
        position_snapshot=position_snapshot,
        strategy_name=strategy_name,
    )
    return decisions[0]