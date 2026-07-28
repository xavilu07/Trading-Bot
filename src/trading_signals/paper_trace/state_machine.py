from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from trading_signals.paper_trace.contracts import (
    PaperOrderState,
    PaperPositionState,
    PaperTraceReceipt,
    ReceiptEventType,
    SignalTraceState,
)


class TraceTransitionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class TraceState:
    trace_id: str | None = None
    signal: SignalTraceState = SignalTraceState.NONE
    order: PaperOrderState = PaperOrderState.NONE
    position: PaperPositionState = PaperPositionState.NONE
    last_receipt_id: str | None = None
    last_sequence: int = 0
    candles_before_entry: int = 0
    candles_after_entry: int = 0
    last_candle_open_time: str | None = None
    last_candle_fingerprint: str | None = None
    trace_blocked_reason: str | None = None


def apply_receipt(state: TraceState, receipt: PaperTraceReceipt) -> TraceState:
    if state.trace_id not in {None, receipt.trace_id}:
        raise TraceTransitionError("TRACE_ID_MISMATCH")
    if (
        receipt.event_sequence != state.last_sequence + 1
        or receipt.previous_receipt_id != state.last_receipt_id
    ):
        raise TraceTransitionError("EVENT_OUT_OF_ORDER")

    event = receipt.event_type
    updated = state
    if event is ReceiptEventType.SIGNAL_OBSERVED:
        if state.signal is not SignalTraceState.NONE:
            raise TraceTransitionError("SIGNAL_ALREADY_OBSERVED")
        updated = replace(state, signal=SignalTraceState.OBSERVED)
    elif event is ReceiptEventType.SIGNAL_ACCEPTED:
        if state.signal is not SignalTraceState.OBSERVED:
            raise TraceTransitionError("SIGNAL_ACCEPT_INVALID")
        updated = replace(state, signal=SignalTraceState.ACCEPTED)
    elif event is ReceiptEventType.SIGNAL_REJECTED:
        if state.signal is not SignalTraceState.OBSERVED:
            raise TraceTransitionError("SIGNAL_REJECT_INVALID")
        updated = replace(state, signal=SignalTraceState.REJECTED)
    elif event is ReceiptEventType.PAPER_ORDER_CREATED:
        if state.signal is not SignalTraceState.ACCEPTED or state.order is not PaperOrderState.NONE:
            raise TraceTransitionError("ORDER_CREATE_INVALID")
        updated = replace(state, order=PaperOrderState.PENDING)
    elif event is ReceiptEventType.PAPER_ORDER_CANCELLED:
        if state.order not in {PaperOrderState.PENDING, PaperOrderState.ACTIVATED}:
            raise TraceTransitionError("ORDER_CANCEL_INVALID")
        updated = replace(state, order=PaperOrderState.CANCELLED)
    elif event is ReceiptEventType.MARKET_CANDLE_OBSERVED:
        if receipt.candle_open_time is None:
            raise TraceTransitionError("CANDLE_IDENTITY_MISSING")
        candle_open = receipt.candle_open_time.isoformat()
        if state.last_candle_open_time == candle_open:
            raise TraceTransitionError("CANDLE_ALREADY_OBSERVED")
        if state.position is PaperPositionState.OPEN:
            updated = replace(
                state,
                candles_after_entry=state.candles_after_entry + 1,
                last_candle_open_time=candle_open,
                last_candle_fingerprint=receipt.evidence_fingerprint,
            )
        elif state.order is PaperOrderState.PENDING:
            updated = replace(
                state,
                candles_before_entry=state.candles_before_entry + 1,
                last_candle_open_time=candle_open,
                last_candle_fingerprint=receipt.evidence_fingerprint,
            )
        else:
            updated = replace(
                state,
                last_candle_open_time=candle_open,
                last_candle_fingerprint=receipt.evidence_fingerprint,
            )
    elif event is ReceiptEventType.ENTRY_TOUCHED:
        if state.order is not PaperOrderState.PENDING:
            raise TraceTransitionError("ENTRY_TOUCH_INVALID")
        updated = replace(state, order=PaperOrderState.ACTIVATED)
    elif event is ReceiptEventType.ENTRY_TOUCH_AMBIGUOUS:
        if state.order is not PaperOrderState.PENDING:
            raise TraceTransitionError("ENTRY_AMBIGUITY_INVALID")
        updated = replace(state, trace_blocked_reason=receipt.reason_code)
    elif event is ReceiptEventType.SIMULATED_FILL_CREATED:
        if state.order is not PaperOrderState.ACTIVATED:
            raise TraceTransitionError("FILL_WITHOUT_ACTIVATION")
        updated = replace(state, order=PaperOrderState.FILLED)
    elif event is ReceiptEventType.PAPER_POSITION_OPENED:
        if state.order is not PaperOrderState.FILLED or state.position is not PaperPositionState.NONE:
            raise TraceTransitionError("POSITION_OPEN_INVALID")
        updated = replace(state, position=PaperPositionState.OPEN)
    elif event in {ReceiptEventType.STOP_TOUCHED, ReceiptEventType.TARGET_TOUCHED}:
        if state.position is not PaperPositionState.OPEN:
            raise TraceTransitionError("BARRIER_TOUCH_WITHOUT_POSITION")
    elif event is ReceiptEventType.EXIT_AMBIGUOUS:
        if state.position is not PaperPositionState.OPEN:
            raise TraceTransitionError("EXIT_AMBIGUITY_INVALID")
        updated = replace(state, position=PaperPositionState.AMBIGUOUS)
    elif event is ReceiptEventType.PAPER_POSITION_CLOSED:
        if state.position is not PaperPositionState.OPEN:
            raise TraceTransitionError("POSITION_CLOSE_INVALID")
        if receipt.reason_code == "TARGET_FIRST":
            position = PaperPositionState.CLOSED_WIN
        elif receipt.reason_code == "STOP_FIRST":
            position = PaperPositionState.CLOSED_LOSS
        elif receipt.reason_code == "TIME_EXIT":
            position = PaperPositionState.CLOSED_TIME_EXIT
        else:
            raise TraceTransitionError("POSITION_CLOSE_REASON_INVALID")
        updated = replace(state, position=position)
    elif event is ReceiptEventType.SIGNAL_EXPIRED_NOT_ACTIVATED:
        if state.order is not PaperOrderState.PENDING:
            raise TraceTransitionError("SIGNAL_EXPIRY_INVALID")
        updated = replace(
            state,
            signal=SignalTraceState.EXPIRED_NOT_ACTIVATED,
            order=PaperOrderState.EXPIRED,
        )
    elif event is ReceiptEventType.POSITION_HORIZON_REACHED:
        if state.position is not PaperPositionState.OPEN:
            raise TraceTransitionError("POSITION_HORIZON_INVALID")
        updated = replace(state, position=PaperPositionState.HORIZON_REACHED)
    elif event is ReceiptEventType.POSITION_EXPIRED_UNRESOLVED:
        if state.position is not PaperPositionState.HORIZON_REACHED:
            raise TraceTransitionError("POSITION_UNRESOLVED_INVALID")
        updated = replace(state, position=PaperPositionState.EXPIRED_UNRESOLVED)
    elif event is ReceiptEventType.POSITION_EXPIRED_CLOSED:
        if state.position is not PaperPositionState.HORIZON_REACHED:
            raise TraceTransitionError("POSITION_TIME_EXIT_INVALID")
        updated = replace(state, position=PaperPositionState.CLOSED_TIME_EXIT)
    elif event in {ReceiptEventType.MARKET_DATA_GAP, ReceiptEventType.MARKET_DATA_CONFLICT}:
        updated = (
            replace(state, position=PaperPositionState.DATA_BLOCKED)
            if state.position is PaperPositionState.OPEN
            else replace(state, trace_blocked_reason=receipt.reason_code)
        )
    elif event is ReceiptEventType.TRACE_ERROR:
        updated = (
            replace(state, position=PaperPositionState.DATA_BLOCKED)
            if state.position is PaperPositionState.OPEN
            else replace(state, trace_blocked_reason=receipt.reason_code)
        )
    else:
        raise TraceTransitionError("EVENT_TYPE_UNSUPPORTED")

    return replace(
        updated,
        trace_id=receipt.trace_id,
        last_receipt_id=receipt.receipt_id,
        last_sequence=receipt.event_sequence,
    )


def replay_receipts(receipts: Iterable[PaperTraceReceipt]) -> TraceState:
    state = TraceState()
    seen: dict[str, str] = {}
    for receipt in receipts:
        prior_hash = seen.get(receipt.receipt_id)
        if prior_hash is not None:
            if prior_hash != receipt.receipt_hash:
                raise TraceTransitionError("RECEIPT_ID_COLLISION")
            continue
        seen[receipt.receipt_id] = receipt.receipt_hash
        state = apply_receipt(state, receipt)
    return state
