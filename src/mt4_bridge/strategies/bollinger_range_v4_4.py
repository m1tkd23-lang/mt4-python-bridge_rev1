# src\mt4_bridge\strategies\bollinger_range_v4_4.py

# src/mt4_bridge/strategies/bollinger_range_v4_4.py

from __future__ import annotations

import logging

from mt4_bridge.models import (
    MarketSnapshot,
    PositionSnapshot,
    SignalAction,
    SignalDecision,
)
from mt4_bridge.signal_exceptions import SignalEngineError

from mt4_bridge.strategies.bollinger_range_v4_4_params import (  # noqa: F401
    BAND_WALK_LOOKBACK_BARS,
    BAND_WIDTH_EXPANSION_LOOKBACK_BARS,
    BOLLINGER_EXTREME_SIGMA,
    BOLLINGER_PERIOD,
    BOLLINGER_SIGMA,
    CLOSE_ON_OPPOSITE_TREND_STATE,
    ENABLE_RANGE_EXTREME_TOUCH_ENTRY,
    ENABLE_RANGE_FAILURE_EXIT,
    EXIT_ON_RANGE_MIDDLE_BAND,
    MIDDLE_CROSS_LOOKBACK_BARS,
    ONE_SIDE_STAY_LOOKBACK_BARS,
    RANGE_BAND_WIDTH_THRESHOLD,
    RANGE_FAILURE_ADVERSE_MOVE_RATIO,
    RANGE_MA_PERIOD,
    RANGE_MIDDLE_DISTANCE_THRESHOLD,
    RANGE_REQUIRE_REENTRY_CONFIRMATION,
    RANGE_SLOPE_LOOKBACK,
    RANGE_SLOPE_THRESHOLD,
    TREND_MA_PERIOD,
    TREND_PRICE_POSITION_FILTER_ENABLED,
    TREND_REQUIRE_BREAK_CONFIRMATION,
    TREND_SLOPE_LOOKBACK,
    TREND_SLOPE_THRESHOLD,
    required_bars,
)
from mt4_bridge.strategies.bollinger_range_v4_4_indicators import (
    _calculate_band_walk_stats,
    _calculate_band_width_expansion_ratio,
    _calculate_bollinger_bands_from_window,
    _calculate_latest_bollinger_bands,
    _calculate_middle_cross_stats,
    _calculate_one_side_stay_stats,
    _calculate_previous_bollinger_bands,
    _calculate_trend_slope_acceleration_ratio,
    _normalized_band_width,
    _normalized_slope,
)
from mt4_bridge.strategies.bollinger_range_v4_4_rules import (
    _determine_market_state,
    _range_buy_confirmed,
    _range_buy_failure_exit,
    _range_extreme_buy_touch_confirmed,
    _range_extreme_sell_touch_confirmed,
    _range_sell_confirmed,
    _range_sell_failure_exit,
    _trend_buy_confirmed,
    _trend_sell_confirmed,
    build_range_observation,
    range_observation_to_dict,
)

logger = logging.getLogger(__name__)


def _build_signal_decision(
    *,
    strategy_name: str,
    action: SignalAction,
    reason: str,
    previous_bar_time,
    latest_bar_time,
    previous_close: float,
    latest_close: float,
    current_position_ticket: int | None,
    current_position_type: str | None,
    market_state: str,
    middle_band: float,
    upper_band: float,
    lower_band: float,
    normalized_width: float,
    range_slope: float,
    trend_slope: float,
    trend_current_ma: float,
    distance_from_middle: float,
    debug_metrics: dict[str, object] | None = None,
) -> SignalDecision:
    return SignalDecision(
        strategy_name=strategy_name,
        action=action,
        reason=reason,
        previous_bar_time=previous_bar_time,
        latest_bar_time=latest_bar_time,
        previous_close=previous_close,
        latest_close=latest_close,
        current_position_ticket=current_position_ticket,
        current_position_type=current_position_type,
        market_state=market_state,
        middle_band=middle_band,
        upper_band=upper_band,
        lower_band=lower_band,
        normalized_band_width=normalized_width,
        range_slope=range_slope,
        trend_slope=trend_slope,
        trend_current_ma=trend_current_ma,
        distance_from_middle=distance_from_middle,
        debug_metrics=debug_metrics,
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
    float,
    float,
]:
    bars = market_snapshot.bars

    if len(bars) < required_bars():
        raise SignalEngineError(
            f"At least {required_bars()} bars are required to evaluate bollinger_range_v4_4"
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

    (
        _,
        latest_upper_extreme,
        latest_lower_extreme,
        _,
    ) = _calculate_latest_bollinger_bands(closes, BOLLINGER_EXTREME_SIGMA)

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

    if market_state == "range":
        if ENABLE_RANGE_EXTREME_TOUCH_ENTRY:
            if _range_extreme_sell_touch_confirmed(
                latest_high=latest_bar.high,
                latest_upper_extreme_band=latest_upper_extreme,
            ):
                return (
                    SignalAction.SELL,
                    (
                        f"range extreme-touch sell confirmed by 3sigma upper band touch;"
                        f" latest_high={latest_bar.high}, latest_upper_3sigma={latest_upper_extreme};"
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
                    latest_upper_extreme,
                    latest_lower_extreme,
                )

            if _range_extreme_buy_touch_confirmed(
                latest_low=latest_bar.low,
                latest_lower_extreme_band=latest_lower_extreme,
            ):
                return (
                    SignalAction.BUY,
                    (
                        f"range extreme-touch buy confirmed by 3sigma lower band touch;"
                        f" latest_low={latest_bar.low}, latest_lower_3sigma={latest_lower_extreme};"
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
                    latest_upper_extreme,
                    latest_lower_extreme,
                )

        if _range_sell_confirmed(
            previous_close=previous_close,
            latest_close=latest_close,
            previous_upper_band=previous_upper,
            latest_upper_band=latest_upper,
        ):
            return (
                SignalAction.SELL,
                (
                    f"range mean-reversion sell confirmed by reentry from outside upper band;"
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
                latest_upper_extreme,
                latest_lower_extreme,
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
                    f"range mean-reversion buy confirmed by reentry from outside lower band;"
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
                latest_upper_extreme,
                latest_lower_extreme,
            )

        return (
            SignalAction.HOLD,
            (
                f"range state but no confirmed signal"
                f" (previous_close={previous_close}, latest_close={latest_close},"
                f" previous_upper={previous_upper}, latest_upper={latest_upper},"
                f" previous_lower={previous_lower}, latest_lower={latest_lower},"
                f" latest_upper_3sigma={latest_upper_extreme},"
                f" latest_lower_3sigma={latest_lower_extreme},"
                f" latest_high={latest_bar.high}, latest_low={latest_bar.low});"
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
            latest_upper_extreme,
            latest_lower_extreme,
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
                    f"trend-follow buy confirmed by upper band breakout;"
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
                latest_upper_extreme,
                latest_lower_extreme,
            )

        return (
            SignalAction.HOLD,
            (
                f"trend_up state but no confirmed upper band breakout"
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
            latest_upper_extreme,
            latest_lower_extreme,
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
                    f"trend-follow sell confirmed by lower band breakout;"
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
                latest_upper_extreme,
                latest_lower_extreme,
            )

        return (
            SignalAction.HOLD,
            (
                f"trend_down state but no confirmed lower band breakout"
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
            latest_upper_extreme,
            latest_lower_extreme,
        )

    return (
        SignalAction.HOLD,
        (
            f"neutral state so entry is skipped"
            f" (previous_close={previous_close}, latest_close={latest_close},"
            f" previous_upper={previous_upper}, latest_upper={latest_upper},"
            f" previous_lower={previous_lower}, latest_lower={latest_lower},"
            f" latest_upper_3sigma={latest_upper_extreme},"
            f" latest_lower_3sigma={latest_lower_extreme},"
            f" latest_high={latest_bar.high}, latest_low={latest_bar.low});"
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
        latest_upper_extreme,
        latest_lower_extreme,
    )


def evaluate_bollinger_range_v4_4(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_range_v4_4",
) -> SignalDecision:
    bars = market_snapshot.bars
    if len(bars) < required_bars():
        raise SignalEngineError(
            f"At least {required_bars()} bars are required to evaluate bollinger_range_v4_4"
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
        latest_upper_extreme_band,
        latest_lower_extreme_band,
    ) = _base_signal(market_snapshot)

    current_position = (
        position_snapshot.positions[0] if position_snapshot.positions else None
    )
    latest_band_width = upper_band - lower_band

    # --- RangeObservation 生成 (TASK-0110) ---
    range_observation_dict: dict[str, object] | None = None
    try:
        closes = [bar.close for bar in bars]
        obs_lookback = max(
            BAND_WALK_LOOKBACK_BARS,
            MIDDLE_CROSS_LOOKBACK_BARS,
            ONE_SIDE_STAY_LOOKBACK_BARS,
            BAND_WIDTH_EXPANSION_LOOKBACK_BARS,
        )
        n_bars = len(closes)
        n_series = obs_lookback + 1

        middle_series: list[float] = []
        upper_series: list[float] = []
        lower_series: list[float] = []
        closes_for_obs: list[float] = []

        for offset in range(n_series - 1, -1, -1):
            idx = n_bars - 1 - offset
            start = idx - BOLLINGER_PERIOD + 1
            if start < 0:
                continue
            window = closes[start : idx + 1]
            m, u, lo, _ = _calculate_bollinger_bands_from_window(
                window, BOLLINGER_SIGMA
            )
            middle_series.append(m)
            upper_series.append(u)
            lower_series.append(lo)
            closes_for_obs.append(closes[idx])

        band_walk_stats = _calculate_band_walk_stats(
            closes_for_obs, upper_series, lower_series
        )
        middle_cross_stats = _calculate_middle_cross_stats(
            closes_for_obs, middle_series
        )
        one_side_stay_stats = _calculate_one_side_stay_stats(
            closes_for_obs, middle_series
        )
        band_width_expansion_stats = _calculate_band_width_expansion_ratio(
            upper_series, lower_series
        )
        trend_slope_accel_stats = _calculate_trend_slope_acceleration_ratio(
            closes, TREND_MA_PERIOD
        )

        obs = build_range_observation(
            market_state=market_state,
            entry_setup_type=None,
            middle_band=middle_band,
            upper_band=upper_band,
            lower_band=lower_band,
            upper_extreme_band_3sigma=latest_upper_extreme_band,
            lower_extreme_band_3sigma=latest_lower_extreme_band,
            band_width=latest_band_width,
            normalized_band_width=normalized_width,
            distance_from_middle=distance_from_middle,
            range_slope=range_slope,
            trend_slope=trend_slope,
            trend_current_ma=trend_current_ma,
            band_walk_stats=band_walk_stats,
            middle_cross_stats=middle_cross_stats,
            one_side_stay_stats=one_side_stay_stats,
            band_width_expansion_stats=band_width_expansion_stats,
            trend_slope_accel_stats=trend_slope_accel_stats,
        )
        range_observation_dict = range_observation_to_dict(obs)
    except Exception as e:
        logger.debug(
            "RangeObservation build failed for %s at bar_time=%s: %s: %s",
            strategy_name,
            latest_bar.time,
            type(e).__name__,
            str(e),
        )
        range_observation_dict = None

    reason_suffix = (
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
        f" range_require_reentry_confirmation={RANGE_REQUIRE_REENTRY_CONFIRMATION},"
        f" trend_require_break_confirmation={TREND_REQUIRE_BREAK_CONFIRMATION},"
        f" exit_on_range_middle_band={EXIT_ON_RANGE_MIDDLE_BAND},"
        f" close_on_opposite_trend_state={CLOSE_ON_OPPOSITE_TREND_STATE},"
        f" enable_range_failure_exit={ENABLE_RANGE_FAILURE_EXIT},"
        f" range_failure_adverse_move_ratio={RANGE_FAILURE_ADVERSE_MOVE_RATIO},"
        f" enable_range_extreme_touch_entry={ENABLE_RANGE_EXTREME_TOUCH_ENTRY},"
        f" state={market_state}, middle={middle_band}, upper={upper_band},"
        f" lower={lower_band}, upper_3sigma={latest_upper_extreme_band},"
        f" lower_3sigma={latest_lower_extreme_band},"
        f" previous_upper={previous_upper_band}, previous_lower={previous_lower_band},"
        f" normalized_band_width={normalized_width:.6f},"
        f" latest_band_width={latest_band_width:.6f},"
        f" distance_from_middle={distance_from_middle:.6f},"
        f" range_slope={range_slope:.6f}, trend_slope={trend_slope:.6f},"
        f" trend_current_ma={trend_current_ma},"
        f" latest_high={latest_bar.high}, latest_low={latest_bar.low})"
    )

    common_kwargs = {
        "strategy_name": strategy_name,
        "previous_bar_time": previous_bar.time,
        "latest_bar_time": latest_bar.time,
        "previous_close": previous_bar.close,
        "latest_close": latest_bar.close,
        "current_position_ticket": current_position.ticket if current_position else None,
        "current_position_type": current_position.position_type.lower()
        if current_position
        else None,
        "market_state": market_state,
        "middle_band": middle_band,
        "upper_band": upper_band,
        "lower_band": lower_band,
        "normalized_width": normalized_width,
        "range_slope": range_slope,
        "trend_slope": trend_slope,
        "trend_current_ma": trend_current_ma,
        "distance_from_middle": distance_from_middle,
        "debug_metrics": range_observation_dict,
    }

    if current_position is None:
        return _build_signal_decision(
            action=base_action,
            reason=base_reason + reason_suffix,
            **common_kwargs,
        )

    current_type = current_position.position_type.lower()
    entry_price = current_position.open_price

    if ENABLE_RANGE_FAILURE_EXIT and market_state == "range":
        if current_type == "buy" and _range_buy_failure_exit(
            latest_close=latest_bar.close,
            previous_close=previous_bar.close,
            entry_price=entry_price,
            middle_band=middle_band,
            band_width=latest_band_width,
        ):
            return _build_signal_decision(
                action=SignalAction.CLOSE,
                reason=(
                    "buy position closed because range recovery failed and adverse move resumed"
                    f" (entry_price={entry_price}, previous_close={previous_bar.close},"
                    f" latest_close={latest_bar.close}, middle={middle_band},"
                    f" band_width={latest_band_width})"
                    + reason_suffix
                ),
                **common_kwargs,
            )

        if current_type == "sell" and _range_sell_failure_exit(
            latest_close=latest_bar.close,
            previous_close=previous_bar.close,
            entry_price=entry_price,
            middle_band=middle_band,
            band_width=latest_band_width,
        ):
            return _build_signal_decision(
                action=SignalAction.CLOSE,
                reason=(
                    "sell position closed because range recovery failed and adverse move resumed"
                    f" (entry_price={entry_price}, previous_close={previous_bar.close},"
                    f" latest_close={latest_bar.close}, middle={middle_band},"
                    f" band_width={latest_band_width})"
                    + reason_suffix
                ),
                **common_kwargs,
            )

    if market_state == "range" and EXIT_ON_RANGE_MIDDLE_BAND:
        if current_type == "buy" and latest_bar.close >= middle_band:
            return _build_signal_decision(
                action=SignalAction.CLOSE,
                reason=(
                    f"buy position closed because range state returned to middle band:"
                    f" latest close {latest_bar.close} >= middle {middle_band}"
                    + reason_suffix
                ),
                **common_kwargs,
            )

        if current_type == "sell" and latest_bar.close <= middle_band:
            return _build_signal_decision(
                action=SignalAction.CLOSE,
                reason=(
                    f"sell position closed because range state returned to middle band:"
                    f" latest close {latest_bar.close} <= middle {middle_band}"
                    + reason_suffix
                ),
                **common_kwargs,
            )

    if CLOSE_ON_OPPOSITE_TREND_STATE:
        if current_type == "buy" and market_state == "trend_down":
            return _build_signal_decision(
                action=SignalAction.CLOSE,
                reason="buy position closed because state switched to trend_down"
                + reason_suffix,
                **common_kwargs,
            )

        if current_type == "sell" and market_state == "trend_up":
            return _build_signal_decision(
                action=SignalAction.CLOSE,
                reason="sell position closed because state switched to trend_up"
                + reason_suffix,
                **common_kwargs,
            )

    if base_action == SignalAction.HOLD:
        return _build_signal_decision(
            action=SignalAction.HOLD,
            reason=f"{base_reason}{reason_suffix}; existing {current_type} position kept",
            **common_kwargs,
        )

    if current_type == "buy":
        if base_action == SignalAction.BUY:
            return _build_signal_decision(
                action=SignalAction.HOLD,
                reason="buy signal but buy position already exists" + reason_suffix,
                **common_kwargs,
            )
        return _build_signal_decision(
            action=SignalAction.CLOSE,
            reason="sell signal detected while buy position exists" + reason_suffix,
            **common_kwargs,
        )

    if current_type == "sell":
        if base_action == SignalAction.SELL:
            return _build_signal_decision(
                action=SignalAction.HOLD,
                reason="sell signal but sell position already exists" + reason_suffix,
                **common_kwargs,
            )
        return _build_signal_decision(
            action=SignalAction.CLOSE,
            reason="buy signal detected while sell position exists" + reason_suffix,
            **common_kwargs,
        )

    raise SignalEngineError(f"Unsupported position type: {current_type}")