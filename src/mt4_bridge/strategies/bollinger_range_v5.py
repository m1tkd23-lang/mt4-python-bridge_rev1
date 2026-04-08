# src\mt4_bridge\strategies\bollinger_range_v5.py
from __future__ import annotations

from math import sqrt

from mt4_bridge.models import (
    MarketSnapshot,
    PositionSnapshot,
    SignalAction,
    SignalDecision,
)
from mt4_bridge.signal_exceptions import SignalEngineError


# =========================
# 調整パラメータ
# =========================
# ボリンジャーバンド
BOLLINGER_PERIOD = 20
BOLLINGER_SIGMA = 2.0

# レンジ判定用 MA
RANGE_MA_PERIOD = 10
RANGE_SLOPE_LOOKBACK = 5
RANGE_SLOPE_THRESHOLD = 0.0002

# レンジ判定用のバンド幅しきい値
# normalized_band_width = (upper - lower) / middle
RANGE_BAND_WIDTH_THRESHOLD = 0.0025

# レンジ判定用のミドル距離しきい値
# distance_from_middle = abs(latest_close - middle_band) / middle_band
RANGE_MIDDLE_DISTANCE_THRESHOLD = 0.0016

# トレンド判定用 MA
TREND_MA_PERIOD = 30
TREND_SLOPE_LOOKBACK = 4
TREND_SLOPE_THRESHOLD = 0.0003

# トレンド判定時に価格位置も見る
TREND_PRICE_POSITION_FILTER_ENABLED = True

# 状態継続確認
STATE_CONFIRMATION_BARS = 3

# エントリー確認
# range:
#   previous_close がバンド外
#   latest_close がバンド内へ戻ったらエントリー
RANGE_REQUIRE_REENTRY_CONFIRMATION = True

# trend:
#   previous_close がまだブレイクしておらず
#   latest_close でブレイクしたらエントリー
TREND_REQUIRE_BREAK_CONFIRMATION = True

# エントリー最小余白
# range_reentry_margin:
#   バンド内に戻るだけでなく、少し中まで戻ったことを要求
# trend_break_margin:
#   バンドを抜けるだけでなく、少し抜け幅があることを要求
RANGE_REENTRY_MARGIN_RATIO = 0.00015
TREND_BREAK_MARGIN_RATIO = 0.00020

# 決済ルール
EXIT_ON_RANGE_MIDDLE_BAND = True
CLOSE_ON_OPPOSITE_TREND_STATE = True


def required_bars() -> int:
    state_window_requirement = (
        max(
            BOLLINGER_PERIOD,
            RANGE_MA_PERIOD + RANGE_SLOPE_LOOKBACK,
            TREND_MA_PERIOD + TREND_SLOPE_LOOKBACK,
        )
        + (STATE_CONFIRMATION_BARS - 1)
    )
    return state_window_requirement


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
) -> tuple[float, float, float, float]:
    if len(window) < BOLLINGER_PERIOD:
        raise SignalEngineError(
            f"At least {BOLLINGER_PERIOD} closes are required for Bollinger Bands"
        )

    middle = _simple_moving_average(window)
    stddev = _standard_deviation(window, middle)
    upper = middle + (BOLLINGER_SIGMA * stddev)
    lower = middle - (BOLLINGER_SIGMA * stddev)
    band_width = upper - lower
    return middle, upper, lower, band_width


def _calculate_latest_bollinger_bands(
    closes: list[float],
) -> tuple[float, float, float, float]:
    if len(closes) < BOLLINGER_PERIOD:
        raise SignalEngineError(
            f"At least {BOLLINGER_PERIOD} closes are required for Bollinger Bands"
        )
    return _calculate_bollinger_bands_from_window(closes[-BOLLINGER_PERIOD:])


def _calculate_previous_bollinger_bands(
    closes: list[float],
) -> tuple[float, float, float, float]:
    if len(closes) < BOLLINGER_PERIOD + 1:
        raise SignalEngineError(
            f"At least {BOLLINGER_PERIOD + 1} closes are required for previous Bollinger Bands"
        )
    return _calculate_bollinger_bands_from_window(closes[-(BOLLINGER_PERIOD + 1):-1])


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


def _determine_market_state_at_offset(
    closes: list[float],
    offset_from_latest: int,
) -> tuple[str, str, float, float, float, float, float]:
    if offset_from_latest < 0:
        raise SignalEngineError("offset_from_latest must be >= 0")

    end_index = len(closes) - offset_from_latest
    if end_index <= 0:
        raise SignalEngineError("Invalid offset for state determination")

    partial_closes = closes[:end_index]

    latest_middle, latest_upper, latest_lower, latest_band_width = _calculate_latest_bollinger_bands(partial_closes)
    normalized_width = _normalized_band_width(latest_middle, latest_band_width)

    range_slope, _, _ = _normalized_slope(
        closes=partial_closes,
        period=RANGE_MA_PERIOD,
        lookback=RANGE_SLOPE_LOOKBACK,
    )
    trend_slope, trend_current_ma, _ = _normalized_slope(
        closes=partial_closes,
        period=TREND_MA_PERIOD,
        lookback=TREND_SLOPE_LOOKBACK,
    )

    latest_close = partial_closes[-1]

    market_state, state_reason, distance_from_middle = _determine_market_state(
        latest_close=latest_close,
        middle_band=latest_middle,
        trend_current_ma=trend_current_ma,
        range_slope=range_slope,
        trend_slope=trend_slope,
        normalized_band_width=normalized_width,
    )

    return (
        market_state,
        state_reason,
        latest_middle,
        latest_upper,
        latest_lower,
        normalized_width,
        distance_from_middle,
    )


def _collect_recent_states(closes: list[float], bars_count: int) -> list[str]:
    if bars_count <= 0:
        raise SignalEngineError("bars_count must be >= 1")

    states: list[str] = []
    for offset in range(bars_count - 1, -1, -1):
        market_state, _, _, _, _, _, _ = _determine_market_state_at_offset(
            closes=closes,
            offset_from_latest=offset,
        )
        states.append(market_state)
    return states


def _is_state_confirmed(states: list[str], target_state: str) -> bool:
    if not states:
        return False
    return all(state == target_state for state in states)


def _range_buy_confirmed(
    previous_close: float,
    latest_close: float,
    previous_lower_band: float,
    latest_lower_band: float,
) -> bool:
    reentry_margin = abs(latest_lower_band) * RANGE_REENTRY_MARGIN_RATIO

    if not RANGE_REQUIRE_REENTRY_CONFIRMATION:
        return latest_close >= latest_lower_band + reentry_margin

    return (
        previous_close < previous_lower_band
        and latest_close >= latest_lower_band + reentry_margin
    )


def _range_sell_confirmed(
    previous_close: float,
    latest_close: float,
    previous_upper_band: float,
    latest_upper_band: float,
) -> bool:
    reentry_margin = abs(latest_upper_band) * RANGE_REENTRY_MARGIN_RATIO

    if not RANGE_REQUIRE_REENTRY_CONFIRMATION:
        return latest_close <= latest_upper_band - reentry_margin

    return (
        previous_close > previous_upper_band
        and latest_close <= latest_upper_band - reentry_margin
    )


def _trend_buy_confirmed(
    previous_close: float,
    latest_close: float,
    previous_upper_band: float,
    latest_upper_band: float,
) -> bool:
    break_margin = abs(latest_upper_band) * TREND_BREAK_MARGIN_RATIO

    if not TREND_REQUIRE_BREAK_CONFIRMATION:
        return latest_close >= latest_upper_band + break_margin

    return (
        previous_close <= previous_upper_band
        and latest_close > latest_upper_band + break_margin
    )


def _trend_sell_confirmed(
    previous_close: float,
    latest_close: float,
    previous_lower_band: float,
    latest_lower_band: float,
) -> bool:
    break_margin = abs(latest_lower_band) * TREND_BREAK_MARGIN_RATIO

    if not TREND_REQUIRE_BREAK_CONFIRMATION:
        return latest_close <= latest_lower_band - break_margin

    return (
        previous_close >= previous_lower_band
        and latest_close < latest_lower_band - break_margin
    )


def _base_signal(
    market_snapshot: MarketSnapshot,
) -> tuple[
    SignalAction,
    str,
    str,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    list[str],
]:
    bars = market_snapshot.bars

    if len(bars) < required_bars():
        raise SignalEngineError(
            f"At least {required_bars()} bars are required to evaluate bollinger_range_v5"
        )

    closes = [bar.close for bar in bars]
    previous_close = closes[-2]
    latest_close = closes[-1]

    latest_middle, latest_upper, latest_lower, latest_band_width = _calculate_latest_bollinger_bands(closes)
    _, previous_upper, previous_lower, _ = _calculate_previous_bollinger_bands(closes)

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

    recent_states = _collect_recent_states(
        closes=closes,
        bars_count=STATE_CONFIRMATION_BARS,
    )

    if not _is_state_confirmed(recent_states, market_state):
        return (
            SignalAction.HOLD,
            (
                f"state not confirmed for {STATE_CONFIRMATION_BARS} bars"
                f" (recent_states={recent_states}, latest_state={market_state});"
                f" {state_reason}"
            ),
            market_state,
            latest_middle,
            latest_upper,
            latest_lower,
            normalized_width,
            range_slope,
            trend_slope,
            trend_current_ma,
            previous_upper,
            previous_lower,
            distance_from_middle,
            recent_states,
        )

    if market_state == "range":
        if _range_sell_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            previous_upper_band=previous_upper,
            latest_upper_band=latest_upper,
        ):
            return (
                SignalAction.SELL,
                (
                    f"range mean-reversion sell confirmed by reentry from outside upper band"
                    f" with minimum margin;"
                    f" previous_close={previous_close}, latest_close={latest_close},"
                    f" previous_upper={previous_upper}, latest_upper={latest_upper};"
                    f" {state_reason}"
                ),
                market_state,
                latest_middle,
                latest_upper,
                latest_lower,
                normalized_width,
                range_slope,
                trend_slope,
                trend_current_ma,
                previous_upper,
                previous_lower,
                distance_from_middle,
                recent_states,
            )

        if _range_buy_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            previous_lower_band=previous_lower,
            latest_lower_band=latest_lower,
        ):
            return (
                SignalAction.BUY,
                (
                    f"range mean-reversion buy confirmed by reentry from outside lower band"
                    f" with minimum margin;"
                    f" previous_close={previous_close}, latest_close={latest_close},"
                    f" previous_lower={previous_lower}, latest_lower={latest_lower};"
                    f" {state_reason}"
                ),
                market_state,
                latest_middle,
                latest_upper,
                latest_lower,
                normalized_width,
                range_slope,
                trend_slope,
                trend_current_ma,
                previous_upper,
                previous_lower,
                distance_from_middle,
                recent_states,
            )

        return (
            SignalAction.HOLD,
            (
                f"range state confirmed but no qualified reentry signal"
                f" (previous_close={previous_close}, latest_close={latest_close},"
                f" previous_upper={previous_upper}, latest_upper={latest_upper},"
                f" previous_lower={previous_lower}, latest_lower={latest_lower});"
                f" {state_reason}"
            ),
            market_state,
            latest_middle,
            latest_upper,
            latest_lower,
            normalized_width,
            range_slope,
            trend_slope,
            trend_current_ma,
            previous_upper,
            previous_lower,
            distance_from_middle,
            recent_states,
        )

    if market_state == "trend_up":
        if _trend_buy_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            previous_upper_band=previous_upper,
            latest_upper_band=latest_upper,
        ):
            return (
                SignalAction.BUY,
                (
                    f"trend-follow buy confirmed by upper band breakout"
                    f" with minimum margin;"
                    f" previous_close={previous_close}, latest_close={latest_close},"
                    f" previous_upper={previous_upper}, latest_upper={latest_upper};"
                    f" {state_reason}"
                ),
                market_state,
                latest_middle,
                latest_upper,
                latest_lower,
                normalized_width,
                range_slope,
                trend_slope,
                trend_current_ma,
                previous_upper,
                previous_lower,
                distance_from_middle,
                recent_states,
            )

        return (
            SignalAction.HOLD,
            (
                f"trend_up state confirmed but no qualified upper band breakout"
                f" (previous_close={previous_close}, latest_close={latest_close},"
                f" previous_upper={previous_upper}, latest_upper={latest_upper});"
                f" {state_reason}"
            ),
            market_state,
            latest_middle,
            latest_upper,
            latest_lower,
            normalized_width,
            range_slope,
            trend_slope,
            trend_current_ma,
            previous_upper,
            previous_lower,
            distance_from_middle,
            recent_states,
        )

    if market_state == "trend_down":
        if _trend_sell_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            previous_lower_band=previous_lower,
            latest_lower_band=latest_lower,
        ):
            return (
                SignalAction.SELL,
                (
                    f"trend-follow sell confirmed by lower band breakout"
                    f" with minimum margin;"
                    f" previous_close={previous_close}, latest_close={latest_close},"
                    f" previous_lower={previous_lower}, latest_lower={latest_lower};"
                    f" {state_reason}"
                ),
                market_state,
                latest_middle,
                latest_upper,
                latest_lower,
                normalized_width,
                range_slope,
                trend_slope,
                trend_current_ma,
                previous_upper,
                previous_lower,
                distance_from_middle,
                recent_states,
            )

        return (
            SignalAction.HOLD,
            (
                f"trend_down state confirmed but no qualified lower band breakout"
                f" (previous_close={previous_close}, latest_close={latest_close},"
                f" previous_lower={previous_lower}, latest_lower={latest_lower});"
                f" {state_reason}"
            ),
            market_state,
            latest_middle,
            latest_upper,
            latest_lower,
            normalized_width,
            range_slope,
            trend_slope,
            trend_current_ma,
            previous_upper,
            previous_lower,
            distance_from_middle,
            recent_states,
        )

    return (
        SignalAction.HOLD,
        (
            f"neutral state so entry is skipped"
            f" (previous_close={previous_close}, latest_close={latest_close},"
            f" previous_upper={previous_upper}, latest_upper={latest_upper},"
            f" previous_lower={previous_lower}, latest_lower={latest_lower});"
            f" {state_reason}"
        ),
        market_state,
        latest_middle,
        latest_upper,
        latest_lower,
        normalized_width,
        range_slope,
        trend_slope,
        trend_current_ma,
        previous_upper,
        previous_lower,
        distance_from_middle,
        recent_states,
    )


def evaluate_bollinger_range_v5(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_range_v5",
) -> SignalDecision:
    bars = market_snapshot.bars
    if len(bars) < required_bars():
        raise SignalEngineError(
            f"At least {required_bars()} bars are required to evaluate bollinger_range_v5"
        )

    previous_bar = bars[-2]
    latest_bar = bars[-1]

    (
        base_action,
        base_reason,
        market_state,
        middle_band,
        upper_band,
        lower_band,
        normalized_width,
        range_slope,
        trend_slope,
        trend_current_ma,
        previous_upper_band,
        previous_lower_band,
        distance_from_middle,
        recent_states,
    ) = _base_signal(market_snapshot)

    current_position = position_snapshot.positions[0] if position_snapshot.positions else None

    reason_suffix = (
        f" (bollinger_period={BOLLINGER_PERIOD}, bollinger_sigma={BOLLINGER_SIGMA},"
        f" range_ma_period={RANGE_MA_PERIOD},"
        f" range_slope_lookback={RANGE_SLOPE_LOOKBACK},"
        f" range_slope_threshold={RANGE_SLOPE_THRESHOLD},"
        f" range_band_width_threshold={RANGE_BAND_WIDTH_THRESHOLD},"
        f" range_middle_distance_threshold={RANGE_MIDDLE_DISTANCE_THRESHOLD},"
        f" trend_ma_period={TREND_MA_PERIOD},"
        f" trend_slope_lookback={TREND_SLOPE_LOOKBACK},"
        f" trend_slope_threshold={TREND_SLOPE_THRESHOLD},"
        f" trend_price_position_filter_enabled={TREND_PRICE_POSITION_FILTER_ENABLED},"
        f" state_confirmation_bars={STATE_CONFIRMATION_BARS},"
        f" range_require_reentry_confirmation={RANGE_REQUIRE_REENTRY_CONFIRMATION},"
        f" trend_require_break_confirmation={TREND_REQUIRE_BREAK_CONFIRMATION},"
        f" range_reentry_margin_ratio={RANGE_REENTRY_MARGIN_RATIO},"
        f" trend_break_margin_ratio={TREND_BREAK_MARGIN_RATIO},"
        f" exit_on_range_middle_band={EXIT_ON_RANGE_MIDDLE_BAND},"
        f" close_on_opposite_trend_state={CLOSE_ON_OPPOSITE_TREND_STATE},"
        f" state={market_state}, recent_states={recent_states},"
        f" middle={middle_band}, upper={upper_band},"
        f" lower={lower_band}, previous_upper={previous_upper_band},"
        f" previous_lower={previous_lower_band},"
        f" normalized_band_width={normalized_width:.6f},"
        f" distance_from_middle={distance_from_middle:.6f},"
        f" range_slope={range_slope:.6f}, trend_slope={trend_slope:.6f},"
        f" trend_current_ma={trend_current_ma})"
    )

    if current_position is None:
        return SignalDecision(
            strategy_name=strategy_name,
            action=base_action,
            reason=base_reason + reason_suffix,
            previous_bar_time=previous_bar.time,
            latest_bar_time=latest_bar.time,
            previous_close=previous_bar.close,
            latest_close=latest_bar.close,
            current_position_ticket=None,
            current_position_type=None,
        )

    current_type = current_position.position_type.lower()

    if market_state == "range" and EXIT_ON_RANGE_MIDDLE_BAND:
        if current_type == "buy" and latest_bar.close >= middle_band:
            return SignalDecision(
                strategy_name=strategy_name,
                action=SignalAction.CLOSE,
                reason=(
                    f"buy position closed because range state returned to middle band:"
                    f" latest close {latest_bar.close} >= middle {middle_band}"
                    + reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_bar.close,
                latest_close=latest_bar.close,
                current_position_ticket=current_position.ticket,
                current_position_type=current_type,
            )

        if current_type == "sell" and latest_bar.close <= middle_band:
            return SignalDecision(
                strategy_name=strategy_name,
                action=SignalAction.CLOSE,
                reason=(
                    f"sell position closed because range state returned to middle band:"
                    f" latest close {latest_bar.close} <= middle {middle_band}"
                    + reason_suffix
                ),
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_bar.close,
                latest_close=latest_bar.close,
                current_position_ticket=current_position.ticket,
                current_position_type=current_type,
            )

    if CLOSE_ON_OPPOSITE_TREND_STATE:
        if current_type == "buy" and market_state == "trend_down":
            return SignalDecision(
                strategy_name=strategy_name,
                action=SignalAction.CLOSE,
                reason="buy position closed because state switched to trend_down" + reason_suffix,
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_bar.close,
                latest_close=latest_bar.close,
                current_position_ticket=current_position.ticket,
                current_position_type=current_type,
            )

        if current_type == "sell" and market_state == "trend_up":
            return SignalDecision(
                strategy_name=strategy_name,
                action=SignalAction.CLOSE,
                reason="sell position closed because state switched to trend_up" + reason_suffix,
                previous_bar_time=previous_bar.time,
                latest_bar_time=latest_bar.time,
                previous_close=previous_bar.close,
                latest_close=latest_bar.close,
                current_position_ticket=current_position.ticket,
                current_position_type=current_type,
            )

    if base_action == SignalAction.HOLD:
        return SignalDecision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=f"{base_reason}{reason_suffix}; existing {current_type} position kept",
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
                reason="buy signal but buy position already exists" + reason_suffix,
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
            reason="sell signal detected while buy position exists" + reason_suffix,
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
                reason="sell signal but sell position already exists" + reason_suffix,
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
            reason="buy signal detected while sell position exists" + reason_suffix,
            previous_bar_time=previous_bar.time,
            latest_bar_time=latest_bar.time,
            previous_close=previous_bar.close,
            latest_close=latest_bar.close,
            current_position_ticket=current_position.ticket,
            current_position_type=current_type,
        )

    raise SignalEngineError(f"Unsupported position type: {current_type}")