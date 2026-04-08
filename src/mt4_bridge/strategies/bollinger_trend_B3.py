# src/mt4_bridge/strategies/bollinger_trend_B3.py
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from mt4_bridge.models import (
    MarketSnapshot,
    OpenPosition,
    PositionSnapshot,
    SignalAction,
    SignalDecision,
)
from mt4_bridge.signal_exceptions import SignalEngineError


# =========================
# M5向け trend-follow 戦略
# =========================
# 目的:
# - bollinger_range_v4_4 が苦手な「片方向に伸び続ける相場」を補う
# - ミドルバンド傾きで trend 判定
# - 押し目買い / 戻り売りの再開を狙う
#
# 基本思想:
# - trend_up では BUY のみ
# - trend_down では SELL のみ
# - エントリーは「いったんミドル近辺へ戻した後の再開確認」
# - 利確は 2σ 到達
# - 撤退は ミドル逆抜け or trend 崩れ
#
# M5前提のため、ノイズ対策として
# - slope lookback を短すぎず
# - 押し目 / 戻り目確認を 2本構造にしている


# =========================
# 調整パラメータ
# =========================
BOLLINGER_PERIOD = 20
BOLLINGER_SIGMA = 2.0

# trend 判定はボリンジャーミドルの傾きを使う
TREND_SLOPE_LOOKBACK = 2
TREND_SLOPE_THRESHOLD = 0.0004

# 価格位置フィルタ
TREND_PRICE_POSITION_FILTER_ENABLED = True

# 押し目 / 戻り目の「ミドル近辺」判定
# abs(close - middle) / middle <= threshold
PULLBACK_NEAR_MIDDLE_THRESHOLD = 0.00045

# エントリー確認
# trend_up:
#   previous_close が middle 近辺まで戻し
#   latest_close が previous_close を上抜き
#   latest_close が middle より上
#
# trend_down:
#   previous_close が middle 近辺まで戻し
#   latest_close が previous_close を下抜き
#   latest_close が middle より下
REQUIRE_PULLBACK_RESUME_CONFIRMATION = True

# 利確
EXIT_ON_OUTER_BAND_TOUCH = True

# 撤退
EXIT_ON_MIDDLE_CROSS = True
EXIT_ON_TREND_STATE_LOSS = True

# 早期撤退（押し戻し失敗）
ENABLE_FAILED_RESUME_EXIT = True
FAILED_RESUME_ADVERSE_MOVE_RATIO = 0.22

# 識別用
TREND_MAGIC_NUMBER = 44003


@dataclass(frozen=True)
class _AnalysisContext:
    previous_bar_time: object
    latest_bar_time: object
    previous_close: float
    latest_close: float
    previous_high: float
    previous_low: float
    latest_high: float
    latest_low: float
    previous_middle_band: float
    previous_upper_band: float
    previous_lower_band: float
    middle_band: float
    upper_band: float
    lower_band: float
    band_width: float
    normalized_width: float
    trend_slope: float
    trend_current_ma: float
    distance_from_middle: float
    previous_distance_from_middle: float
    previous_is_near_middle: bool
    latest_is_near_middle: bool
    market_state: str
    state_reason: str
    trend_up_slope_passed: bool
    trend_up_price_passed: bool
    trend_down_slope_passed: bool
    trend_down_price_passed: bool


def required_bars() -> int:
    return max(
        BOLLINGER_PERIOD + 1,
        BOLLINGER_PERIOD + TREND_SLOPE_LOOKBACK,
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


def _distance_from_middle(close: float, middle: float) -> float:
    if middle == 0:
        raise SignalEngineError("Middle band is zero; distance from middle undefined")
    return abs(close - middle) / middle


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


def _analyze_trend_up(
    latest_close: float,
    trend_current_ma: float,
    trend_slope: float,
) -> tuple[bool, bool, bool]:
    slope_passed = trend_slope > TREND_SLOPE_THRESHOLD
    price_passed = (
        latest_close >= trend_current_ma
        if TREND_PRICE_POSITION_FILTER_ENABLED
        else True
    )
    return slope_passed and price_passed, slope_passed, price_passed


def _analyze_trend_down(
    latest_close: float,
    trend_current_ma: float,
    trend_slope: float,
) -> tuple[bool, bool, bool]:
    slope_passed = trend_slope < -TREND_SLOPE_THRESHOLD
    price_passed = (
        latest_close <= trend_current_ma
        if TREND_PRICE_POSITION_FILTER_ENABLED
        else True
    )
    return slope_passed and price_passed, slope_passed, price_passed


def _determine_market_state(
    latest_close: float,
    middle_band: float,
    trend_current_ma: float,
    trend_slope: float,
    normalized_band_width: float,
) -> tuple[str, str, float, bool, bool, bool, bool]:
    distance_from_middle = _distance_from_middle(latest_close, middle_band)

    is_trend_up, trend_up_slope_passed, trend_up_price_passed = _analyze_trend_up(
        latest_close=latest_close,
        trend_current_ma=trend_current_ma,
        trend_slope=trend_slope,
    )
    if is_trend_up:
        return (
            "trend_up",
            (
                f"trend_up because trend_slope={trend_slope:.6f}"
                f" > threshold={TREND_SLOPE_THRESHOLD:.6f}"
                f" and latest_close={latest_close} >= trend_ma={trend_current_ma}"
            ),
            distance_from_middle,
            trend_up_slope_passed,
            trend_up_price_passed,
            False,
            False,
        )

    is_trend_down, trend_down_slope_passed, trend_down_price_passed = (
        _analyze_trend_down(
            latest_close=latest_close,
            trend_current_ma=trend_current_ma,
            trend_slope=trend_slope,
        )
    )
    if is_trend_down:
        return (
            "trend_down",
            (
                f"trend_down because trend_slope={trend_slope:.6f}"
                f" < -threshold={TREND_SLOPE_THRESHOLD:.6f}"
                f" and latest_close={latest_close} <= trend_ma={trend_current_ma}"
            ),
            distance_from_middle,
            trend_up_slope_passed,
            trend_up_price_passed,
            trend_down_slope_passed,
            trend_down_price_passed,
        )

    if trend_up_slope_passed and not trend_up_price_passed:
        state_reason = (
            "neutral because up-slope passed but up price-position filter failed"
            f" (latest_close={latest_close}, trend_ma={trend_current_ma},"
            f" trend_slope={trend_slope:.6f}, threshold={TREND_SLOPE_THRESHOLD:.6f})"
        )
    elif trend_down_slope_passed and not trend_down_price_passed:
        state_reason = (
            "neutral because down-slope passed but down price-position filter failed"
            f" (latest_close={latest_close}, trend_ma={trend_current_ma},"
            f" trend_slope={trend_slope:.6f}, threshold={TREND_SLOPE_THRESHOLD:.6f})"
        )
    else:
        state_reason = (
            "neutral because no strong trend was confirmed"
            f" (trend_slope={trend_slope:.6f},"
            f" normalized_band_width={normalized_band_width:.6f},"
            f" distance_from_middle={distance_from_middle:.6f})"
        )

    return (
        "neutral",
        state_reason,
        distance_from_middle,
        trend_up_slope_passed,
        trend_up_price_passed,
        trend_down_slope_passed,
        trend_down_price_passed,
    )


def _is_near_middle(close: float, middle: float) -> bool:
    return _distance_from_middle(close, middle) <= PULLBACK_NEAR_MIDDLE_THRESHOLD


def _trend_buy_entry_confirmed(
    previous_close: float,
    latest_close: float,
    previous_middle_band: float,
    latest_middle_band: float,
) -> bool:
    previous_near_middle = _is_near_middle(previous_close, previous_middle_band)

    if not REQUIRE_PULLBACK_RESUME_CONFIRMATION:
        return latest_close > latest_middle_band

    return (
        previous_near_middle
        and latest_close > latest_middle_band
        and latest_close > previous_close
    )


def _trend_sell_entry_confirmed(
    previous_close: float,
    latest_close: float,
    previous_middle_band: float,
    latest_middle_band: float,
) -> bool:
    previous_near_middle = _is_near_middle(previous_close, previous_middle_band)

    if not REQUIRE_PULLBACK_RESUME_CONFIRMATION:
        return latest_close < latest_middle_band

    return (
        previous_near_middle
        and latest_close < latest_middle_band
        and latest_close < previous_close
    )


def _trend_buy_take_profit_confirmed(
    latest_high: float,
    latest_upper_band: float,
) -> bool:
    return latest_high >= latest_upper_band


def _trend_sell_take_profit_confirmed(
    latest_low: float,
    latest_lower_band: float,
) -> bool:
    return latest_low <= latest_lower_band


def _trend_buy_middle_cross_exit_confirmed(
    previous_close: float,
    latest_close: float,
    previous_middle_band: float,
    latest_middle_band: float,
) -> bool:
    return previous_close >= previous_middle_band and latest_close < latest_middle_band


def _trend_sell_middle_cross_exit_confirmed(
    previous_close: float,
    latest_close: float,
    previous_middle_band: float,
    latest_middle_band: float,
) -> bool:
    return previous_close <= previous_middle_band and latest_close > latest_middle_band


def _trend_buy_failed_resume_exit(
    latest_close: float,
    previous_close: float,
    entry_price: float,
    middle_band: float,
    band_width: float,
) -> bool:
    adverse_threshold = band_width * FAILED_RESUME_ADVERSE_MOVE_RATIO
    adverse_move = max(0.0, entry_price - latest_close)
    return (
        latest_close < entry_price
        and latest_close <= previous_close
        and latest_close < middle_band
        and adverse_move >= adverse_threshold
    )


def _trend_sell_failed_resume_exit(
    latest_close: float,
    previous_close: float,
    entry_price: float,
    middle_band: float,
    band_width: float,
) -> bool:
    adverse_threshold = band_width * FAILED_RESUME_ADVERSE_MOVE_RATIO
    adverse_move = max(0.0, latest_close - entry_price)
    return (
        latest_close > entry_price
        and latest_close >= previous_close
        and latest_close > middle_band
        and adverse_move >= adverse_threshold
    )


def _is_trend_lane_position(position: OpenPosition) -> bool:
    comment = (position.comment or "").lower()
    return (
        position.magic_number == TREND_MAGIC_NUMBER
        or "lane:trend" in comment
        or "entry_lane=trend" in comment
        or "strategy=bollinger_trend_b3" in comment
    )


def _get_trend_position(position_snapshot: PositionSnapshot) -> OpenPosition | None:
    for position in position_snapshot.positions:
        if _is_trend_lane_position(position):
            return position
    return None


def _build_reason_suffix(context: _AnalysisContext) -> str:
    return (
        f" (bollinger_period={BOLLINGER_PERIOD},"
        f" bollinger_sigma={BOLLINGER_SIGMA},"
        f" trend_slope_lookback={TREND_SLOPE_LOOKBACK},"
        f" trend_slope_threshold={TREND_SLOPE_THRESHOLD},"
        f" trend_price_position_filter_enabled={TREND_PRICE_POSITION_FILTER_ENABLED},"
        f" pullback_near_middle_threshold={PULLBACK_NEAR_MIDDLE_THRESHOLD},"
        f" require_pullback_resume_confirmation={REQUIRE_PULLBACK_RESUME_CONFIRMATION},"
        f" exit_on_outer_band_touch={EXIT_ON_OUTER_BAND_TOUCH},"
        f" exit_on_middle_cross={EXIT_ON_MIDDLE_CROSS},"
        f" exit_on_trend_state_loss={EXIT_ON_TREND_STATE_LOSS},"
        f" enable_failed_resume_exit={ENABLE_FAILED_RESUME_EXIT},"
        f" failed_resume_adverse_move_ratio={FAILED_RESUME_ADVERSE_MOVE_RATIO},"
        f" state={context.market_state},"
        f" previous_middle={context.previous_middle_band},"
        f" middle={context.middle_band},"
        f" upper={context.upper_band},"
        f" lower={context.lower_band},"
        f" previous_upper={context.previous_upper_band},"
        f" previous_lower={context.previous_lower_band},"
        f" normalized_band_width={context.normalized_width:.6f},"
        f" latest_band_width={context.band_width:.6f},"
        f" previous_distance_from_middle={context.previous_distance_from_middle:.6f},"
        f" distance_from_middle={context.distance_from_middle:.6f},"
        f" previous_is_near_middle={context.previous_is_near_middle},"
        f" latest_is_near_middle={context.latest_is_near_middle},"
        f" trend_slope={context.trend_slope:.6f},"
        f" trend_current_ma={context.trend_current_ma},"
        f" trend_up_slope_passed={context.trend_up_slope_passed},"
        f" trend_up_price_passed={context.trend_up_price_passed},"
        f" trend_down_slope_passed={context.trend_down_slope_passed},"
        f" trend_down_price_passed={context.trend_down_price_passed},"
        f" previous_high={context.previous_high},"
        f" previous_low={context.previous_low},"
        f" latest_high={context.latest_high},"
        f" latest_low={context.latest_low})"
    )


def _build_signal_decision(
    *,
    strategy_name: str,
    action: SignalAction,
    reason: str,
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
        entry_lane="trend",
        entry_subtype=entry_subtype,
        market_state=context.market_state,
        middle_band=context.middle_band,
        upper_band=context.upper_band,
        lower_band=context.lower_band,
        normalized_band_width=context.normalized_width,
        range_slope=0.0,
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
            f"At least {required_bars()} bars are required to evaluate bollinger_trend_B3"
        )

    closes = [bar.close for bar in bars]
    previous_bar = bars[-2]
    latest_bar = bars[-1]

    previous_close = previous_bar.close
    latest_close = latest_bar.close

    latest_middle, latest_upper, latest_lower, latest_band_width = (
        _calculate_latest_bollinger_bands(closes, BOLLINGER_SIGMA)
    )
    previous_middle, previous_upper, previous_lower, _ = (
        _calculate_previous_bollinger_bands(closes, BOLLINGER_SIGMA)
    )

    normalized_width = _normalized_band_width(latest_middle, latest_band_width)
    trend_slope, trend_current_ma, _ = _normalized_slope(
        closes=closes,
        period=BOLLINGER_PERIOD,
        lookback=TREND_SLOPE_LOOKBACK,
    )

    (
        market_state,
        state_reason,
        distance_from_middle,
        trend_up_slope_passed,
        trend_up_price_passed,
        trend_down_slope_passed,
        trend_down_price_passed,
    ) = _determine_market_state(
        latest_close=latest_close,
        middle_band=latest_middle,
        trend_current_ma=trend_current_ma,
        trend_slope=trend_slope,
        normalized_band_width=normalized_width,
    )

    previous_distance_from_middle = _distance_from_middle(
        previous_close,
        previous_middle,
    )

    return _AnalysisContext(
        previous_bar_time=previous_bar.time,
        latest_bar_time=latest_bar.time,
        previous_close=previous_close,
        latest_close=latest_close,
        previous_high=previous_bar.high,
        previous_low=previous_bar.low,
        latest_high=latest_bar.high,
        latest_low=latest_bar.low,
        previous_middle_band=previous_middle,
        previous_upper_band=previous_upper,
        previous_lower_band=previous_lower,
        middle_band=latest_middle,
        upper_band=latest_upper,
        lower_band=latest_lower,
        band_width=latest_band_width,
        normalized_width=normalized_width,
        trend_slope=trend_slope,
        trend_current_ma=trend_current_ma,
        distance_from_middle=distance_from_middle,
        previous_distance_from_middle=previous_distance_from_middle,
        previous_is_near_middle=_is_near_middle(previous_close, previous_middle),
        latest_is_near_middle=_is_near_middle(latest_close, latest_middle),
        market_state=market_state,
        state_reason=state_reason,
        trend_up_slope_passed=trend_up_slope_passed,
        trend_up_price_passed=trend_up_price_passed,
        trend_down_slope_passed=trend_down_slope_passed,
        trend_down_price_passed=trend_down_price_passed,
    )


def evaluate_bollinger_trend_B3(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_trend_B3",
) -> SignalDecision:
    context = _build_analysis_context(market_snapshot)
    trend_position = _get_trend_position(position_snapshot)
    reason_suffix = _build_reason_suffix(context)

    if trend_position is not None:
        current_type = trend_position.position_type.lower()
        entry_price = trend_position.open_price

        if current_type == "buy":
            if ENABLE_FAILED_RESUME_EXIT and _trend_buy_failed_resume_exit(
                latest_close=context.latest_close,
                previous_close=context.previous_close,
                entry_price=entry_price,
                middle_band=context.middle_band,
                band_width=context.band_width,
            ):
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "buy trend position closed because pullback-resume failed and"
                        f" adverse move resumed (entry_price={entry_price},"
                        f" previous_close={context.previous_close},"
                        f" latest_close={context.latest_close},"
                        f" middle={context.middle_band},"
                        f" band_width={context.band_width})"
                        + reason_suffix
                    ),
                    entry_subtype="failed_resume_exit",
                    current_position=trend_position,
                    context=context,
                )

            if EXIT_ON_OUTER_BAND_TOUCH and _trend_buy_take_profit_confirmed(
                latest_high=context.latest_high,
                latest_upper_band=context.upper_band,
            ):
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "buy trend position closed because upper 2sigma was touched"
                        f" (latest_high={context.latest_high},"
                        f" upper_band={context.upper_band})"
                        + reason_suffix
                    ),
                    entry_subtype="tp_upper_2sigma",
                    current_position=trend_position,
                    context=context,
                )

            if EXIT_ON_MIDDLE_CROSS and _trend_buy_middle_cross_exit_confirmed(
                previous_close=context.previous_close,
                latest_close=context.latest_close,
                previous_middle_band=context.previous_middle_band,
                latest_middle_band=context.middle_band,
            ):
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "buy trend position closed because middle band downward cross"
                        " was confirmed"
                        f" (previous_close={context.previous_close},"
                        f" latest_close={context.latest_close},"
                        f" previous_middle={context.previous_middle_band},"
                        f" middle={context.middle_band})"
                        + reason_suffix
                    ),
                    entry_subtype="middle_cross_exit",
                    current_position=trend_position,
                    context=context,
                )

            if EXIT_ON_TREND_STATE_LOSS and context.market_state != "trend_up":
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "buy trend position closed because trend_up state was lost"
                        f" (state={context.market_state}; {context.state_reason})"
                        + reason_suffix
                    ),
                    entry_subtype="trend_state_loss_exit",
                    current_position=trend_position,
                    context=context,
                )

            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.HOLD,
                reason="buy trend position kept" + reason_suffix,
                entry_subtype="hold_existing",
                current_position=trend_position,
                context=context,
            )

        if current_type == "sell":
            if ENABLE_FAILED_RESUME_EXIT and _trend_sell_failed_resume_exit(
                latest_close=context.latest_close,
                previous_close=context.previous_close,
                entry_price=entry_price,
                middle_band=context.middle_band,
                band_width=context.band_width,
            ):
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "sell trend position closed because pullback-resume failed and"
                        f" adverse move resumed (entry_price={entry_price},"
                        f" previous_close={context.previous_close},"
                        f" latest_close={context.latest_close},"
                        f" middle={context.middle_band},"
                        f" band_width={context.band_width})"
                        + reason_suffix
                    ),
                    entry_subtype="failed_resume_exit",
                    current_position=trend_position,
                    context=context,
                )

            if EXIT_ON_OUTER_BAND_TOUCH and _trend_sell_take_profit_confirmed(
                latest_low=context.latest_low,
                latest_lower_band=context.lower_band,
            ):
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "sell trend position closed because lower 2sigma was touched"
                        f" (latest_low={context.latest_low},"
                        f" lower_band={context.lower_band})"
                        + reason_suffix
                    ),
                    entry_subtype="tp_lower_2sigma",
                    current_position=trend_position,
                    context=context,
                )

            if EXIT_ON_MIDDLE_CROSS and _trend_sell_middle_cross_exit_confirmed(
                previous_close=context.previous_close,
                latest_close=context.latest_close,
                previous_middle_band=context.previous_middle_band,
                latest_middle_band=context.middle_band,
            ):
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "sell trend position closed because middle band upward cross"
                        " was confirmed"
                        f" (previous_close={context.previous_close},"
                        f" latest_close={context.latest_close},"
                        f" previous_middle={context.previous_middle_band},"
                        f" middle={context.middle_band})"
                        + reason_suffix
                    ),
                    entry_subtype="middle_cross_exit",
                    current_position=trend_position,
                    context=context,
                )

            if EXIT_ON_TREND_STATE_LOSS and context.market_state != "trend_down":
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "sell trend position closed because trend_down state was lost"
                        f" (state={context.market_state}; {context.state_reason})"
                        + reason_suffix
                    ),
                    entry_subtype="trend_state_loss_exit",
                    current_position=trend_position,
                    context=context,
                )

            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.HOLD,
                reason="sell trend position kept" + reason_suffix,
                entry_subtype="hold_existing",
                current_position=trend_position,
                context=context,
            )

        raise SignalEngineError(f"Unsupported trend position type: {current_type}")

    if context.market_state == "trend_up":
        if _trend_buy_entry_confirmed(
            previous_close=context.previous_close,
            latest_close=context.latest_close,
            previous_middle_band=context.previous_middle_band,
            latest_middle_band=context.middle_band,
        ):
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.BUY,
                reason=(
                    "trend-follow buy confirmed by pullback-and-resume in trend_up state;"
                    f" previous_close={context.previous_close},"
                    f" latest_close={context.latest_close},"
                    f" previous_middle={context.previous_middle_band},"
                    f" middle={context.middle_band}; {context.state_reason}"
                    + reason_suffix
                ),
                entry_subtype="pullback_resume_entry",
                current_position=None,
                context=context,
            )

        return _build_signal_decision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=(
                "trend_up detected but buy pullback-resume entry was not confirmed"
                f" (previous_close={context.previous_close},"
                f" latest_close={context.latest_close},"
                f" previous_middle={context.previous_middle_band},"
                f" middle={context.middle_band},"
                f" previous_is_near_middle={context.previous_is_near_middle})"
                + reason_suffix
            ),
            entry_subtype="debug_trend_up_entry_miss",
            current_position=None,
            context=context,
        )

    if context.market_state == "trend_down":
        if _trend_sell_entry_confirmed(
            previous_close=context.previous_close,
            latest_close=context.latest_close,
            previous_middle_band=context.previous_middle_band,
            latest_middle_band=context.middle_band,
        ):
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.SELL,
                reason=(
                    "trend-follow sell confirmed by pullback-and-resume in trend_down state;"
                    f" previous_close={context.previous_close},"
                    f" latest_close={context.latest_close},"
                    f" previous_middle={context.previous_middle_band},"
                    f" middle={context.middle_band}; {context.state_reason}"
                    + reason_suffix
                ),
                entry_subtype="pullback_resume_entry",
                current_position=None,
                context=context,
            )

        return _build_signal_decision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=(
                "trend_down detected but sell pullback-resume entry was not confirmed"
                f" (previous_close={context.previous_close},"
                f" latest_close={context.latest_close},"
                f" previous_middle={context.previous_middle_band},"
                f" middle={context.middle_band},"
                f" previous_is_near_middle={context.previous_is_near_middle})"
                + reason_suffix
            ),
            entry_subtype="debug_trend_down_entry_miss",
            current_position=None,
            context=context,
        )

    if context.trend_up_slope_passed and not context.trend_up_price_passed:
        return _build_signal_decision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=(
                "trend_up slope passed but price-position filter blocked entry"
                + reason_suffix
            ),
            entry_subtype="debug_trend_up_price_filter_blocked",
            current_position=None,
            context=context,
        )

    if context.trend_down_slope_passed and not context.trend_down_price_passed:
        return _build_signal_decision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=(
                "trend_down slope passed but price-position filter blocked entry"
                + reason_suffix
            ),
            entry_subtype="debug_trend_down_price_filter_blocked",
            current_position=None,
            context=context,
        )

    if context.trend_slope > 0:
        return _build_signal_decision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=(
                "positive slope observed but trend_up threshold not reached"
                + reason_suffix
            ),
            entry_subtype="debug_trend_up_slope_blocked",
            current_position=None,
            context=context,
        )

    if context.trend_slope < 0:
        return _build_signal_decision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=(
                "negative slope observed but trend_down threshold not reached"
                + reason_suffix
            ),
            entry_subtype="debug_trend_down_slope_blocked",
            current_position=None,
            context=context,
        )

    return _build_signal_decision(
        strategy_name=strategy_name,
        action=SignalAction.HOLD,
        reason=(
            "flat slope so no actionable trend decision"
            f" (market_state={context.market_state}; {context.state_reason})"
            + reason_suffix
        ),
        entry_subtype="debug_flat_slope",
        current_position=None,
        context=context,
    )