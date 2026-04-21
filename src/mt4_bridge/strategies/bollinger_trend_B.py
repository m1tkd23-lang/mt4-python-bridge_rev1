# src/mt4_bridge/strategies/bollinger_trend_B.py
from __future__ import annotations

from dataclasses import dataclass

from mt4_bridge.models import (
    MarketSnapshot,
    OpenPosition,
    PositionSnapshot,
    SignalAction,
    SignalDecision,
)
from mt4_bridge.signal_exceptions import SignalEngineError

from mt4_bridge.strategies.bollinger_trend_B_params import (  # noqa: F401
    B_ENTRY_BANNED_HOURS,
    B_H1_LOOKBACK_BARS,
    B_H1_TREND_FILTER_ENABLED,
    B_H1_TREND_THRESHOLD_PIPS,
    B_PIP_MULTIPLIER,
    B_TIME_FILTER_ENABLED,
    BOLLINGER_PERIOD,
    BOLLINGER_SIGMA,
    CLOSE_ON_OPPOSITE_TREND_STATE,
    ENTRY_SIGMA_NORMAL,
    ENTRY_SIGMA_STRONG,
    EXIT_SIGMA,
    SL_PIPS,
    STRONG_TREND_SLOPE_THRESHOLD,
    TP_PIPS,
    TREND_MA_PERIOD,
    TREND_MAGIC_NUMBER,
    TREND_PRICE_POSITION_FILTER_ENABLED,
    TREND_SLOPE_LOOKBACK,
    TREND_SLOPE_THRESHOLD,
    required_bars,
)
from mt4_bridge.strategies.bollinger_trend_B_indicators import (
    _calculate_latest_bollinger_bands,
    _calculate_previous_bollinger_bands,
    _normalized_band_width,
    _normalized_slope,
)
from mt4_bridge.strategies.bollinger_trend_B_rules import (
    _determine_market_state,
    _get_trend_position,
    _trend_buy_take_profit_confirmed,
    _trend_buy_touch_confirmed,
    _trend_sell_take_profit_confirmed,
    _trend_sell_touch_confirmed,
)


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
    upper_entry_band: float
    lower_entry_band: float
    band_width: float
    normalized_width: float
    range_slope: float
    trend_slope: float
    trend_current_ma: float
    previous_upper_band: float
    previous_lower_band: float
    previous_upper_entry_band: float
    previous_lower_entry_band: float
    distance_from_middle: float
    market_state: str
    state_reason: str
    trend_up_slope_passed: bool
    trend_up_price_passed: bool
    trend_down_slope_passed: bool
    trend_down_price_passed: bool
    entry_mode: str | None


def _build_reason_suffix(
    context: _AnalysisContext,
) -> str:
    return (
        f" (bollinger_period={BOLLINGER_PERIOD},"
        f" bollinger_sigma={BOLLINGER_SIGMA},"
        f" entry_sigma_normal={ENTRY_SIGMA_NORMAL},"
        f" entry_sigma_strong={ENTRY_SIGMA_STRONG},"
        f" exit_sigma={EXIT_SIGMA},"
        f" trend_ma_period={TREND_MA_PERIOD},"
        f" trend_slope_lookback={TREND_SLOPE_LOOKBACK},"
        f" trend_slope_threshold={TREND_SLOPE_THRESHOLD},"
        f" strong_trend_slope_threshold={STRONG_TREND_SLOPE_THRESHOLD},"
        f" trend_price_position_filter_enabled={TREND_PRICE_POSITION_FILTER_ENABLED},"
        f" close_on_opposite_trend_state={CLOSE_ON_OPPOSITE_TREND_STATE},"
        f" state={context.market_state},"
        f" entry_mode={context.entry_mode},"
        f" middle={context.middle_band},"
        f" upper={context.upper_band},"
        f" lower={context.lower_band},"
        f" upper_entry_band={context.upper_entry_band},"
        f" lower_entry_band={context.lower_entry_band},"
        f" previous_upper={context.previous_upper_band},"
        f" previous_lower={context.previous_lower_band},"
        f" previous_upper_entry={context.previous_upper_entry_band},"
        f" previous_lower_entry={context.previous_lower_entry_band},"
        f" normalized_band_width={context.normalized_width:.6f},"
        f" latest_band_width={context.band_width:.6f},"
        f" distance_from_middle={context.distance_from_middle:.6f},"
        f" range_slope={context.range_slope:.6f},"
        f" trend_slope={context.trend_slope:.6f},"
        f" trend_current_ma={context.trend_current_ma},"
        f" trend_up_slope_passed={context.trend_up_slope_passed},"
        f" trend_up_price_passed={context.trend_up_price_passed},"
        f" trend_down_slope_passed={context.trend_down_slope_passed},"
        f" trend_down_price_passed={context.trend_down_price_passed},"
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
    exit_subtype: str | None = None,
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
        exit_subtype=exit_subtype,
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
            f"At least {required_bars()} bars are required to evaluate bollinger_trend_B"
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

    _, latest_upper_1sigma, latest_lower_1sigma, _ = _calculate_latest_bollinger_bands(
        closes,
        ENTRY_SIGMA_STRONG,
    )
    _, previous_upper_1sigma, previous_lower_1sigma, _ = (
        _calculate_previous_bollinger_bands(
            closes,
            ENTRY_SIGMA_STRONG,
        )
    )

    normalized_width = _normalized_band_width(latest_middle, latest_band_width)
    trend_slope, trend_current_ma, _ = _normalized_slope(
        closes=closes,
        period=TREND_MA_PERIOD,
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
        entry_mode,
    ) = _determine_market_state(
        latest_close=latest_close,
        middle_band=latest_middle,
        trend_current_ma=trend_current_ma,
        trend_slope=trend_slope,
        normalized_band_width=normalized_width,
    )

    if market_state == "strong_trend_up":
        upper_entry_band = latest_upper_1sigma
        lower_entry_band = latest_middle
        previous_upper_entry_band = previous_upper_1sigma
        previous_lower_entry_band = latest_middle
    elif market_state == "strong_trend_down":
        upper_entry_band = latest_middle
        lower_entry_band = latest_lower_1sigma
        previous_upper_entry_band = latest_middle
        previous_lower_entry_band = previous_lower_1sigma
    else:
        upper_entry_band = latest_middle
        lower_entry_band = latest_middle
        previous_upper_entry_band = latest_middle
        previous_lower_entry_band = latest_middle

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
        upper_entry_band=upper_entry_band,
        lower_entry_band=lower_entry_band,
        band_width=latest_band_width,
        normalized_width=normalized_width,
        range_slope=0.0,
        trend_slope=trend_slope,
        trend_current_ma=trend_current_ma,
        previous_upper_band=previous_upper,
        previous_lower_band=previous_lower,
        previous_upper_entry_band=previous_upper_entry_band,
        previous_lower_entry_band=previous_lower_entry_band,
        distance_from_middle=distance_from_middle,
        market_state=market_state,
        state_reason=state_reason,
        trend_up_slope_passed=trend_up_slope_passed,
        trend_up_price_passed=trend_up_price_passed,
        trend_down_slope_passed=trend_down_slope_passed,
        trend_down_price_passed=trend_down_price_passed,
        entry_mode=entry_mode,
    )


def _apply_b_filters(
    decision: SignalDecision,
    market_snapshot: MarketSnapshot,
) -> SignalDecision:
    """エントリー(BUY/SELL)に対して B戦術のゲーティングを適用する。

    逆張り禁止(H1 コンテキスト) と時刻フィルタ。
    existing positions のクローズ決定 (CLOSE/HOLD) は干渉しない。
    """
    from dataclasses import replace

    if decision.action not in (SignalAction.BUY, SignalAction.SELL):
        return decision

    new_action = decision.action
    new_reason = decision.reason

    # 修正2: H1 コンテキストフィルタ
    # 直近 60本 (=5時間) の close 変化で H1 トレンドを近似し、
    # 順張り(H1 と同方向)でない場合はエントリー見送り
    if B_H1_TREND_FILTER_ENABLED:
        bars = market_snapshot.bars
        if len(bars) >= B_H1_LOOKBACK_BARS + 1:
            h1_mom_pips = (
                bars[-1].close - bars[-(B_H1_LOOKBACK_BARS + 1)].close
            ) * B_PIP_MULTIPLIER
            if (
                new_action == SignalAction.BUY
                and h1_mom_pips < B_H1_TREND_THRESHOLD_PIPS
            ):
                new_action = SignalAction.HOLD
                new_reason = (
                    f"B strategy BUY suppressed because H1 is not uptrending:"
                    f" last-{B_H1_LOOKBACK_BARS}-bar mom={h1_mom_pips:.2f} pips"
                    f" (threshold=+{B_H1_TREND_THRESHOLD_PIPS});"
                    f" original decision: {decision.reason}"
                )
            elif (
                new_action == SignalAction.SELL
                and h1_mom_pips > -B_H1_TREND_THRESHOLD_PIPS
            ):
                new_action = SignalAction.HOLD
                new_reason = (
                    f"B strategy SELL suppressed because H1 is not downtrending:"
                    f" last-{B_H1_LOOKBACK_BARS}-bar mom={h1_mom_pips:.2f} pips"
                    f" (threshold=-{B_H1_TREND_THRESHOLD_PIPS});"
                    f" original decision: {decision.reason}"
                )

    # 修正3: 時刻フィルタ (A戦術と同一の banned hours)
    if (
        B_TIME_FILTER_ENABLED
        and new_action in (SignalAction.BUY, SignalAction.SELL)
    ):
        latest_bar_time = decision.latest_bar_time
        if latest_bar_time is not None and latest_bar_time.hour in B_ENTRY_BANNED_HOURS:
            new_action = SignalAction.HOLD
            new_reason = (
                f"B strategy entry suppressed by time filter: broker hour "
                f"{latest_bar_time.hour} is historically weak; "
                f"original decision: {decision.reason}"
            )

    if new_action == decision.action:
        return decision
    return replace(decision, action=new_action, reason=new_reason)


def evaluate_bollinger_trend_B(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_trend_B",
) -> SignalDecision:
    decision = _evaluate_bollinger_trend_B_core(
        market_snapshot, position_snapshot, strategy_name
    )
    return _apply_b_filters(decision, market_snapshot)


def _evaluate_bollinger_trend_B_core(
    market_snapshot: MarketSnapshot,
    position_snapshot: PositionSnapshot,
    strategy_name: str = "bollinger_trend_B",
) -> SignalDecision:
    context = _build_analysis_context(market_snapshot)
    trend_position = _get_trend_position(position_snapshot)
    reason_suffix = _build_reason_suffix(context)

    if trend_position is not None:
        current_type = trend_position.position_type.lower()

        if current_type == "buy":
            if _trend_buy_take_profit_confirmed(
                latest_high=context.latest_high,
                latest_upper_band=context.upper_band,
            ):
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "buy trend position closed because upper 2sigma was touched"
                        f" (latest_high={context.latest_high}, upper_band={context.upper_band})"
                        + reason_suffix
                    ),
                    entry_subtype="tp_upper_2sigma",
                    exit_subtype="tp_upper_2sigma",
                    current_position=trend_position,
                    context=context,
                )

            if CLOSE_ON_OPPOSITE_TREND_STATE and context.market_state in {
                "trend_down",
                "strong_trend_down",
            }:
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "buy trend position closed because state switched to down trend"
                        + reason_suffix
                    ),
                    entry_subtype="opposite_trend_exit",
                    exit_subtype="opposite_trend_exit",
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
            if _trend_sell_take_profit_confirmed(
                latest_low=context.latest_low,
                latest_lower_band=context.lower_band,
            ):
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "sell trend position closed because lower 2sigma was touched"
                        f" (latest_low={context.latest_low}, lower_band={context.lower_band})"
                        + reason_suffix
                    ),
                    entry_subtype="tp_lower_2sigma",
                    exit_subtype="tp_lower_2sigma",
                    current_position=trend_position,
                    context=context,
                )

            if CLOSE_ON_OPPOSITE_TREND_STATE and context.market_state in {
                "trend_up",
                "strong_trend_up",
            }:
                return _build_signal_decision(
                    strategy_name=strategy_name,
                    action=SignalAction.CLOSE,
                    reason=(
                        "sell trend position closed because state switched to up trend"
                        + reason_suffix
                    ),
                    entry_subtype="opposite_trend_exit",
                    exit_subtype="opposite_trend_exit",
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
        if _trend_buy_touch_confirmed(
            latest_low=context.latest_low,
            entry_band=context.middle_band,
        ):
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.BUY,
                reason=(
                    "trend-follow buy confirmed by middle-band touch in normal trend_up state;"
                    f" latest_low={context.latest_low}, middle={context.middle_band};"
                    f" {context.state_reason}"
                    + reason_suffix
                ),
                entry_subtype="middle_touch_entry",
                current_position=None,
                context=context,
            )

        return _build_signal_decision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=(
                "trend_up detected but middle-band touch entry was not confirmed"
                f" (latest_low={context.latest_low}, middle={context.middle_band})"
                + reason_suffix
            ),
            entry_subtype="debug_trend_up_middle_touch_miss",
            current_position=None,
            context=context,
        )

    if context.market_state == "strong_trend_up":
        if _trend_buy_touch_confirmed(
            latest_low=context.latest_low,
            entry_band=context.upper_entry_band,
        ):
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.BUY,
                reason=(
                    "trend-follow buy confirmed by upper 1sigma touch in strong_trend_up state;"
                    f" latest_low={context.latest_low}, upper_1sigma={context.upper_entry_band};"
                    f" {context.state_reason}"
                    + reason_suffix
                ),
                entry_subtype="upper_1sigma_touch_entry",
                current_position=None,
                context=context,
            )

        return _build_signal_decision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=(
                "strong_trend_up detected but upper 1sigma touch entry was not confirmed"
                f" (latest_low={context.latest_low}, upper_1sigma={context.upper_entry_band})"
                + reason_suffix
            ),
            entry_subtype="debug_strong_trend_up_1sigma_touch_miss",
            current_position=None,
            context=context,
        )

    if context.market_state == "trend_down":
        if _trend_sell_touch_confirmed(
            latest_high=context.latest_high,
            entry_band=context.middle_band,
        ):
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.SELL,
                reason=(
                    "trend-follow sell confirmed by middle-band touch in normal trend_down state;"
                    f" latest_high={context.latest_high}, middle={context.middle_band};"
                    f" {context.state_reason}"
                    + reason_suffix
                ),
                entry_subtype="middle_touch_entry",
                current_position=None,
                context=context,
            )

        return _build_signal_decision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=(
                "trend_down detected but middle-band touch entry was not confirmed"
                f" (latest_high={context.latest_high}, middle={context.middle_band})"
                + reason_suffix
            ),
            entry_subtype="debug_trend_down_middle_touch_miss",
            current_position=None,
            context=context,
        )

    if context.market_state == "strong_trend_down":
        if _trend_sell_touch_confirmed(
            latest_high=context.latest_high,
            entry_band=context.lower_entry_band,
        ):
            return _build_signal_decision(
                strategy_name=strategy_name,
                action=SignalAction.SELL,
                reason=(
                    "trend-follow sell confirmed by lower 1sigma touch in strong_trend_down state;"
                    f" latest_high={context.latest_high}, lower_1sigma={context.lower_entry_band};"
                    f" {context.state_reason}"
                    + reason_suffix
                ),
                entry_subtype="lower_1sigma_touch_entry",
                current_position=None,
                context=context,
            )

        return _build_signal_decision(
            strategy_name=strategy_name,
            action=SignalAction.HOLD,
            reason=(
                "strong_trend_down detected but lower 1sigma touch entry was not confirmed"
                f" (latest_high={context.latest_high}, lower_1sigma={context.lower_entry_band})"
                + reason_suffix
            ),
            entry_subtype="debug_strong_trend_down_1sigma_touch_miss",
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
