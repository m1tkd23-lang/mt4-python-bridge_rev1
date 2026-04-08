# src/app_cli.py
from __future__ import annotations

from collections.abc import Callable

from mt4_bridge.app_config import AppConfigError, load_app_config
from mt4_bridge.command_guard import should_emit_command
from mt4_bridge.command_writer import CommandWriteError, write_command
from mt4_bridge.json_loader import JsonLoadError
from mt4_bridge.logging_utils import setup_logging
from mt4_bridge.models import (
    ActiveCommandStatus,
    BridgeReadResult,
    CommandResult,
    ResultCommandMatch,
    ResultCommandMatchStatus,
    RuntimeState,
    SignalAction,
    SignalDecision,
)
from mt4_bridge.position_consistency import (
    PositionConsistencyWarning,
    evaluate_position_consistency,
)
from mt4_bridge.result_reader import (
    ResultReadError,
    find_unconsumed_results,
    match_result_to_runtime_state,
)
from mt4_bridge.risk_manager import calculate_sl_tp
from mt4_bridge.runtime_state import (
    RuntimeStateError,
    apply_result_to_active_command_status,
    build_updated_runtime_state,
    get_lane_active_command_status,
    get_lane_active_ticket,
    load_runtime_state,
    mark_command_pending,
    mark_result_consumed,
    mark_snapshot_observed,
    reconcile_active_tickets_with_position_snapshot,
    save_runtime_state,
)
from mt4_bridge.services.bridge_service import BridgeService
from mt4_bridge.signal_engine import (
    SignalEngineError,
    evaluate_signals,
)
from mt4_bridge.snapshot_reader import SnapshotValidationError
from mt4_bridge.stale_detector import (
    UpdateBasedStaleStatus,
    evaluate_update_based_staleness,
)

logger = setup_logging()

OutputFunc = Callable[[str], None]

RANGE_MAGIC_NUMBER = 44001
TREND_MAGIC_NUMBER = 44002


def _default_output(message: str) -> None:
    print(message)


def print_summary(
    result: BridgeReadResult,
    stale_status: UpdateBasedStaleStatus,
    output_func: OutputFunc,
) -> None:
    out = output_func
    market = result.market_snapshot
    runtime = result.runtime_status
    latest_bar = market.bars[-1] if market.bars else None

    out(f"Bridge root: {runtime.bridge_root}")
    out(f"Runtime mode: {runtime.mode}")
    out(f"Runtime detail: {runtime.detail}")
    out(f"Terminal connected: {runtime.terminal_connected}")
    out(f"Trade allowed: {runtime.trade_allowed}")
    out(f"Runtime updated at: {runtime.updated_at}")
    out(f"Market generated at: {market.generated_at}")
    out(f"Market update unchanged: {stale_status.market_unchanged}")
    out(f"Runtime update unchanged: {stale_status.runtime_unchanged}")
    out(f"Latest bar unchanged: {stale_status.latest_bar_unchanged}")
    out(f"Stale block: {stale_status.should_block}")
    out(f"Stale reason: {stale_status.reason}")
    out(f"Symbol: {market.symbol}")
    out(f"Timeframe: {market.timeframe}")
    out(f"Bid: {market.bid}")
    out(f"Ask: {market.ask}")
    out(f"Spread points: {market.spread_points}")
    out(f"Bars copied: {market.bars_copied}")

    if result.position_snapshot.positions:
        out("Current positions:")
        for pos in result.position_snapshot.positions:
            out(f"  Ticket: {pos.ticket}")
            out(f"  Type: {pos.position_type}")
            out(f"  Lots: {pos.lots}")
            out(f"  Open price: {pos.open_price}")
            out(f"  Open time: {pos.open_time}")
            out(f"  Magic number: {pos.magic_number}")
            out(f"  Comment: {pos.comment}")
    else:
        out("Current positions: none")

    if latest_bar is None:
        out("Latest bar: none")
        return

    out("Latest bar:")
    out(f"  Time: {latest_bar.time}")
    out(f"  Open: {latest_bar.open}")
    out(f"  High: {latest_bar.high}")
    out(f"  Low: {latest_bar.low}")
    out(f"  Close: {latest_bar.close}")
    out(f"  Tick volume: {latest_bar.tick_volume}")
    out(f"  Spread: {latest_bar.spread}")


def print_signal(
    decision: SignalDecision,
    output_func: OutputFunc,
    title: str = "Signal",
) -> None:
    out = output_func
    out(f"{title}:")
    out(f"  Strategy: {decision.strategy_name}")
    out(f"  Action: {decision.action.value}")
    out(f"  Reason: {decision.reason}")
    out(f"  Entry lane: {decision.entry_lane}")
    out(f"  Entry subtype: {decision.entry_subtype}")
    out(f"  Previous bar time: {decision.previous_bar_time}")
    out(f"  Latest bar time: {decision.latest_bar_time}")
    out(f"  Previous close: {decision.previous_close}")
    out(f"  Latest close: {decision.latest_close}")
    out(f"  Current position ticket: {decision.current_position_ticket}")
    out(f"  Current position type: {decision.current_position_type}")
    out(f"  SL price: {decision.sl_price}")
    out(f"  TP price: {decision.tp_price}")


def print_latest_result(
    title: str,
    result: CommandResult | None,
    output_func: OutputFunc,
) -> None:
    out = output_func

    if result is None:
        out(f"{title}: none")
        return

    out(f"{title}:")
    out(f"  Status: {result.status}")
    out(f"  Action: {result.action}")
    out(f"  Command id: {result.command_id}")
    out(f"  Ticket: {result.ticket}")
    out(f"  Error code: {result.error_code}")
    out(f"  Message: {result.message}")
    out(f"  Processed at: {result.processed_at}")


def print_result_match(
    match: ResultCommandMatch | None,
    output_func: OutputFunc,
) -> None:
    out = output_func

    if match is None:
        out("Result command match: none")
        return

    out("Result command match:")
    out(f"  Status: {match.status.value}")
    out(f"  Expected command id: {match.expected_command_id}")
    out(f"  Actual command id: {match.actual_command_id}")
    out(f"  Lane: {match.lane}")


def print_position_consistency_warnings(
    warnings: list[PositionConsistencyWarning],
    output_func: OutputFunc,
) -> None:
    out = output_func

    if not warnings:
        out("Position consistency warnings: none")
        return

    out("Position consistency warnings:")
    for item in warnings:
        out(f"  [{item.code}] {item.message}")


def _restore_runtime_state_from_open_positions(
    runtime_state: RuntimeState,
    result: BridgeReadResult,
) -> RuntimeState:
    range_positions = [
        item
        for item in result.position_snapshot.positions
        if item.magic_number == RANGE_MAGIC_NUMBER
    ]
    trend_positions = [
        item
        for item in result.position_snapshot.positions
        if item.magic_number == TREND_MAGIC_NUMBER
    ]

    restored_state = runtime_state

    if (
        len(range_positions) == 1
        and restored_state.range_active_ticket is None
        and restored_state.range_active_command_status is None
    ):
        restored_state = RuntimeState(
            range_last_command_bar_time=restored_state.range_last_command_bar_time,
            range_last_command_action=restored_state.range_last_command_action,
            range_last_command_id=restored_state.range_last_command_id,
            range_active_command_status=ActiveCommandStatus.FILLED.value,
            range_active_ticket=range_positions[0].ticket,
            trend_last_command_bar_time=restored_state.trend_last_command_bar_time,
            trend_last_command_action=restored_state.trend_last_command_action,
            trend_last_command_id=restored_state.trend_last_command_id,
            trend_active_command_status=restored_state.trend_active_command_status,
            trend_active_ticket=restored_state.trend_active_ticket,
            last_result_command_id=restored_state.last_result_command_id,
            last_result_status=restored_state.last_result_status,
            last_result_ticket=restored_state.last_result_ticket,
            last_result_processed_at=restored_state.last_result_processed_at,
            last_consumed_result_command_id=restored_state.last_consumed_result_command_id,
            last_consumed_result_processed_at=restored_state.last_consumed_result_processed_at,
            last_seen_market_generated_at=restored_state.last_seen_market_generated_at,
            last_seen_runtime_updated_at=restored_state.last_seen_runtime_updated_at,
            last_seen_latest_bar_time=restored_state.last_seen_latest_bar_time,
        )

    if (
        len(trend_positions) == 1
        and restored_state.trend_active_ticket is None
        and restored_state.trend_active_command_status is None
    ):
        restored_state = RuntimeState(
            range_last_command_bar_time=restored_state.range_last_command_bar_time,
            range_last_command_action=restored_state.range_last_command_action,
            range_last_command_id=restored_state.range_last_command_id,
            range_active_command_status=restored_state.range_active_command_status,
            range_active_ticket=restored_state.range_active_ticket,
            trend_last_command_bar_time=restored_state.trend_last_command_bar_time,
            trend_last_command_action=restored_state.trend_last_command_action,
            trend_last_command_id=restored_state.trend_last_command_id,
            trend_active_command_status=ActiveCommandStatus.FILLED.value,
            trend_active_ticket=trend_positions[0].ticket,
            last_result_command_id=restored_state.last_result_command_id,
            last_result_status=restored_state.last_result_status,
            last_result_ticket=restored_state.last_result_ticket,
            last_result_processed_at=restored_state.last_result_processed_at,
            last_consumed_result_command_id=restored_state.last_consumed_result_command_id,
            last_consumed_result_processed_at=restored_state.last_consumed_result_processed_at,
            last_seen_market_generated_at=restored_state.last_seen_market_generated_at,
            last_seen_runtime_updated_at=restored_state.last_seen_runtime_updated_at,
            last_seen_latest_bar_time=restored_state.last_seen_latest_bar_time,
        )

    if restored_state is not runtime_state:
        logger.info(
            "runtime state restored from open positions: range_status=%s range_ticket=%s trend_status=%s trend_ticket=%s",
            restored_state.range_active_command_status,
            restored_state.range_active_ticket,
            restored_state.trend_active_command_status,
            restored_state.trend_active_ticket,
        )

    return restored_state


def _apply_unconsumed_results_sequentially(
    runtime_state: RuntimeState,
    unconsumed_results: list[CommandResult],
) -> tuple[
    RuntimeState,
    CommandResult | None,
    ResultCommandMatch | None,
    CommandResult | None,
    ResultCommandMatch | None,
]:
    updated_state = runtime_state
    latest_processed_result: CommandResult | None = None
    latest_processed_match: ResultCommandMatch | None = None
    blocked_result: CommandResult | None = None
    blocked_match: ResultCommandMatch | None = None

    for item in unconsumed_results:
        item_match = match_result_to_runtime_state(
            result=item,
            runtime_state=updated_state,
        )

        logger.info(
            "result processing: command_id=%s status=%s ticket=%s match_status=%s expected=%s actual=%s lane=%s",
            item.command_id,
            item.status,
            item.ticket,
            item_match.status.value,
            item_match.expected_command_id,
            item_match.actual_command_id,
            item_match.lane,
        )

        if item_match.status != ResultCommandMatchStatus.MATCHED:
            logger.warning(
                "result left unconsumed because lane match failed: command_id=%s status=%s ticket=%s match_status=%s expected=%s actual=%s",
                item.command_id,
                item.status,
                item.ticket,
                item_match.status.value,
                item_match.expected_command_id,
                item_match.actual_command_id,
            )
            blocked_result = item
            blocked_match = item_match
            break

        updated_state = build_updated_runtime_state(
            current_state=updated_state,
            latest_result=item,
        )
        updated_state = apply_result_to_active_command_status(
            current_state=updated_state,
            result=item,
            result_match=item_match,
        )
        updated_state = mark_result_consumed(
            current_state=updated_state,
            result=item,
        )

        latest_processed_result = item
        latest_processed_match = item_match

    return (
        updated_state,
        latest_processed_result,
        latest_processed_match,
        blocked_result,
        blocked_match,
    )


def _build_decision_with_risk(
    raw_decision: SignalDecision,
    *,
    bid: float,
    ask: float,
    point: float,
    sl_pips: float,
    tp_pips: float,
) -> SignalDecision:
    sl_price = None
    tp_price = None

    if raw_decision.action in (SignalAction.BUY, SignalAction.SELL):
        sl_price, tp_price = calculate_sl_tp(
            action=raw_decision.action,
            bid=bid,
            ask=ask,
            point=point,
            sl_pips=sl_pips,
            tp_pips=tp_pips,
        )

    return SignalDecision(
        strategy_name=raw_decision.strategy_name,
        action=raw_decision.action,
        reason=raw_decision.reason,
        previous_bar_time=raw_decision.previous_bar_time,
        latest_bar_time=raw_decision.latest_bar_time,
        previous_close=raw_decision.previous_close,
        latest_close=raw_decision.latest_close,
        current_position_ticket=raw_decision.current_position_ticket,
        current_position_type=raw_decision.current_position_type,
        sl_price=sl_price,
        tp_price=tp_price,
        entry_lane=raw_decision.entry_lane,
        entry_subtype=raw_decision.entry_subtype,
        market_state=raw_decision.market_state,
        middle_band=raw_decision.middle_band,
        upper_band=raw_decision.upper_band,
        lower_band=raw_decision.lower_band,
        normalized_band_width=raw_decision.normalized_band_width,
        range_slope=raw_decision.range_slope,
        trend_slope=raw_decision.trend_slope,
        trend_current_ma=raw_decision.trend_current_ma,
        distance_from_middle=raw_decision.distance_from_middle,
        detected_market_state=raw_decision.detected_market_state,
        candidate_market_state=raw_decision.candidate_market_state,
        state_transition_event=raw_decision.state_transition_event,
        state_age=raw_decision.state_age,
        candidate_age=raw_decision.candidate_age,
        detector_reason=raw_decision.detector_reason,
        range_score=raw_decision.range_score,
        transition_up_score=raw_decision.transition_up_score,
        transition_down_score=raw_decision.transition_down_score,
        trend_up_score=raw_decision.trend_up_score,
        trend_down_score=raw_decision.trend_down_score,
    )


def main(output_func: OutputFunc | None = None) -> int:
    out = output_func or _default_output

    logger.info("app_cli start")

    try:
        app_config = load_app_config()
        service = BridgeService(app_config=app_config)
        result = service.read_current_state()
        runtime_state = load_runtime_state(app_config.runtime.state_file)
        runtime_state = _restore_runtime_state_from_open_positions(
            runtime_state=runtime_state,
            result=result,
        )
        logger.info(
            "state loaded: symbol=%s timeframe=%s positions=%s results=%s state_file=%s",
            result.market_snapshot.symbol,
            result.market_snapshot.timeframe,
            len(result.position_snapshot.positions),
            len(result.results),
            app_config.runtime.state_file,
        )
    except (
        AppConfigError,
        JsonLoadError,
        ResultReadError,
        SnapshotValidationError,
        RuntimeStateError,
        ValueError,
    ) as exc:
        logger.exception("startup failed")
        out(f"[ERROR] {exc}")
        return 1

    stale_status = evaluate_update_based_staleness(
        result=result,
        runtime_state=runtime_state,
    )
    logger.info(
        "update-based stale check: market_unchanged=%s runtime_unchanged=%s latest_bar_unchanged=%s should_block=%s reason=%s",
        stale_status.market_unchanged,
        stale_status.runtime_unchanged,
        stale_status.latest_bar_unchanged,
        stale_status.should_block,
        stale_status.reason,
    )

    observed_latest_result = result.results[-1] if result.results else None
    unconsumed_results = find_unconsumed_results(
        results=result.results,
        runtime_state=runtime_state,
    )

    logger.info(
        "result scan: observed_latest=%s unconsumed_count=%s latest_unconsumed=%s",
        observed_latest_result.command_id if observed_latest_result is not None else None,
        len(unconsumed_results),
        unconsumed_results[-1].command_id if unconsumed_results else None,
    )

    latest_processed_result: CommandResult | None = None
    latest_processed_match: ResultCommandMatch | None = None
    blocked_result: CommandResult | None = None
    blocked_match: ResultCommandMatch | None = None

    latest_bar_time = (
        result.market_snapshot.bars[-1].time.isoformat()
        if result.market_snapshot.bars
        else None
    )

    try:
        if unconsumed_results:
            (
                runtime_state,
                latest_processed_result,
                latest_processed_match,
                blocked_result,
                blocked_match,
            ) = _apply_unconsumed_results_sequentially(
                runtime_state=runtime_state,
                unconsumed_results=unconsumed_results,
            )
        elif observed_latest_result is not None:
            runtime_state = build_updated_runtime_state(
                current_state=runtime_state,
                latest_result=observed_latest_result,
            )

        reconciled_state = reconcile_active_tickets_with_position_snapshot(
            current_state=runtime_state,
            position_snapshot=result.position_snapshot,
        )
        if reconciled_state != runtime_state:
            logger.info(
                "runtime state reconciled from position snapshot: range_active_command_status=%s range_active_ticket=%s trend_active_command_status=%s trend_active_ticket=%s",
                reconciled_state.range_active_command_status,
                reconciled_state.range_active_ticket,
                reconciled_state.trend_active_command_status,
                reconciled_state.trend_active_ticket,
            )
        runtime_state = reconciled_state

        runtime_state = mark_snapshot_observed(
            current_state=runtime_state,
            market_generated_at=result.market_snapshot.generated_at.isoformat(),
            runtime_updated_at=result.runtime_status.updated_at.isoformat(),
            latest_bar_time=latest_bar_time,
        )
        save_runtime_state(app_config.runtime.state_file, runtime_state)
        logger.info(
            "runtime state saved after result handling: range_active_command_status=%s range_active_ticket=%s trend_active_command_status=%s trend_active_ticket=%s",
            runtime_state.range_active_command_status,
            runtime_state.range_active_ticket,
            runtime_state.trend_active_command_status,
            runtime_state.trend_active_ticket,
        )
    except RuntimeStateError as exc:
        logger.exception("runtime state save failed during result handling")
        out(f"[ERROR] Runtime state save failed: {exc}")
        return 1

    if latest_processed_match is not None:
        logger.info(
            "latest processed result match: status=%s expected=%s actual=%s lane=%s",
            latest_processed_match.status.value,
            latest_processed_match.expected_command_id,
            latest_processed_match.actual_command_id,
            latest_processed_match.lane,
        )

    if blocked_match is not None:
        logger.warning(
            "unmatched result remains pending: status=%s expected=%s actual=%s lane=%s",
            blocked_match.status.value,
            blocked_match.expected_command_id,
            blocked_match.actual_command_id,
            blocked_match.lane,
        )

    position_warnings = evaluate_position_consistency(
        position_snapshot=result.position_snapshot,
        runtime_state=runtime_state,
        latest_unconsumed_result=latest_processed_result,
        result_match=latest_processed_match,
    )

    if position_warnings:
        for item in position_warnings:
            logger.warning(
                "position consistency: code=%s message=%s",
                item.code,
                item.message,
            )
    else:
        logger.info("position consistency: no warnings")

    print_summary(result, stale_status, out)
    print_latest_result("Latest observed result", observed_latest_result, out)
    print_latest_result("Latest unconsumed result", latest_processed_result, out)
    print_result_match(latest_processed_match, out)
    out(f"Range active command status: {runtime_state.range_active_command_status}")
    out(f"Range active ticket: {get_lane_active_ticket(runtime_state, 'range')}")
    out(f"Trend active command status: {runtime_state.trend_active_command_status}")
    out(f"Trend active ticket: {get_lane_active_ticket(runtime_state, 'trend')}")
    print_position_consistency_warnings(position_warnings, out)

    if blocked_result is not None and blocked_match is not None:
        print_latest_result("Blocked unconsumed result", blocked_result, out)
        print_result_match(blocked_match, out)
        out("[WARNING] Unmatched result remains unconsumed. Command emission blocked.")
        logger.warning(
            "app_cli complete: unmatched result block command_id=%s status=%s ticket=%s match_status=%s",
            blocked_result.command_id,
            blocked_result.status,
            blocked_result.ticket,
            blocked_match.status.value,
        )
        return 0

    if not app_config.signal.enabled:
        logger.info("signal disabled")
        out("Signal: disabled")
        return 0

    try:
        raw_decisions = evaluate_signals(
            market_snapshot=result.market_snapshot,
            position_snapshot=result.position_snapshot,
            strategy_name=app_config.signal.strategy_name,
        )
        logger.info(
            "signals evaluated: strategy=%s count=%s",
            app_config.signal.strategy_name,
            len(raw_decisions),
        )
    except SignalEngineError as exc:
        logger.exception("signal evaluation failed")
        out(f"[ERROR] Signal evaluation failed: {exc}")
        return 1

    decisions: list[SignalDecision] = []
    for index, raw_decision in enumerate(raw_decisions, start=1):
        decision = _build_decision_with_risk(
            raw_decision,
            bid=result.market_snapshot.bid,
            ask=result.market_snapshot.ask,
            point=result.market_snapshot.point,
            sl_pips=app_config.risk.sl_pips,
            tp_pips=app_config.risk.tp_pips,
        )
        decisions.append(decision)

        logger.info(
            "signal evaluated: strategy=%s action=%s lane=%s subtype=%s reason=%s",
            decision.strategy_name,
            decision.action.value,
            decision.entry_lane,
            decision.entry_subtype,
            decision.reason,
        )
        if decision.action in (SignalAction.BUY, SignalAction.SELL):
            logger.info(
                "risk calculated: action=%s sl_price=%s tp_price=%s lane=%s subtype=%s",
                decision.action.value,
                decision.sl_price,
                decision.tp_price,
                decision.entry_lane,
                decision.entry_subtype,
            )

        print_signal(
            decision,
            out,
            title=f"Signal #{index}",
        )

    if stale_status.should_block:
        logger.warning(
            "stale detected by update markers -> command emission blocked: reason=%s",
            stale_status.reason,
        )
        out("[WARNING] Snapshot update markers did not advance. Command emission blocked.")
        for index, decision in enumerate(decisions, start=1):
            out(
                f"Command #{index}: skipped (stale snapshot, lane={decision.entry_lane}, action={decision.action.value})"
            )
        logger.info("app_cli complete: stale snapshot block")
        return 0

    emitted_count = 0

    for index, decision in enumerate(decisions, start=1):
        guard_result = should_emit_command(
            decision=decision,
            runtime_state=runtime_state,
            command_queue_path=app_config.bridge.command_queue_path,
            skip_if_pending_command=app_config.runtime.skip_if_pending_command,
        )

        logger.info(
            "command guard: allowed=%s reason=%s action=%s lane=%s latest_bar_time=%s",
            guard_result.allowed,
            guard_result.reason,
            decision.action.value,
            decision.entry_lane,
            decision.latest_bar_time.isoformat()
            if decision.latest_bar_time is not None
            else None,
        )

        if not guard_result.allowed:
            out(
                f"Command #{index}: skipped ({guard_result.reason}, lane={decision.entry_lane}, action={decision.action.value})"
            )
            continue

        if decision.action == SignalAction.HOLD:
            logger.info(
                "command skipped because action is HOLD: index=%s lane=%s",
                index,
                decision.entry_lane,
            )
            out(
                f"Command #{index}: skipped (signal is HOLD, lane={decision.entry_lane}, action={decision.action.value})"
            )
            continue

        try:
            command_result = write_command(
                decision=decision,
                bridge_root=app_config.bridge.root,
                symbol=result.market_snapshot.symbol,
            )
            logger.info(
                "command written: command_id=%s path=%s action=%s lane=%s subtype=%s",
                command_result.command_id if command_result is not None else None,
                command_result.command_path if command_result is not None else None,
                decision.action.value,
                decision.entry_lane,
                decision.entry_subtype,
            )
        except CommandWriteError as exc:
            logger.exception("command write failed")
            out(f"[ERROR] Command write failed for signal #{index}: {exc}")
            return 1

        if command_result is None:
            logger.info("command skipped because writer returned None")
            out(f"Command #{index}: skipped (writer returned None)")
            continue

        try:
            runtime_state = build_updated_runtime_state(
                current_state=runtime_state,
                lane=decision.entry_lane,
                latest_bar_time=(
                    decision.latest_bar_time.isoformat()
                    if decision.latest_bar_time is not None
                    else None
                ),
                action=decision.action.value,
                command_id=command_result.command_id,
            )
            runtime_state = mark_command_pending(
                current_state=runtime_state,
                lane=decision.entry_lane,
            )
            save_runtime_state(app_config.runtime.state_file, runtime_state)
            logger.info(
                "runtime state saved after command emit: range_active_command_status=%s range_active_ticket=%s trend_active_command_status=%s trend_active_ticket=%s",
                runtime_state.range_active_command_status,
                runtime_state.range_active_ticket,
                runtime_state.trend_active_command_status,
                runtime_state.trend_active_ticket,
            )
        except RuntimeStateError as exc:
            logger.exception("runtime state save failed after signal #%s", index)
            out(f"[ERROR] Runtime state save failed after signal #{index}: {exc}")
            return 1

        emitted_count += 1
        out(f"Command #{index} written: {command_result.command_path}")
        out(f"Command #{index} id: {command_result.command_id}")
        out(
            f"Range active command status: {get_lane_active_command_status(runtime_state, 'range')}"
        )
        out(
            f"Range active ticket: {get_lane_active_ticket(runtime_state, 'range')}"
        )
        out(
            f"Trend active command status: {get_lane_active_command_status(runtime_state, 'trend')}"
        )
        out(
            f"Trend active ticket: {get_lane_active_ticket(runtime_state, 'trend')}"
        )

    if emitted_count == 0:
        logger.info("app_cli complete: no commands emitted")
    else:
        logger.info("app_cli complete: emitted_count=%s", emitted_count)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())