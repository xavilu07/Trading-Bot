from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable, Mapping

from trading_signals.paper_trace.contracts import (
    PaperOrderState,
    PaperPositionState,
    PaperTraceReceipt,
    ProspectiveSignalIdentity,
    ReceiptEventType,
    SignalTraceState,
    TraceCandle,
    build_receipt,
    timeframe_duration,
    utc_datetime,
)
from trading_signals.paper_trace.policy import (
    DEFAULT_EXPIRY_POLICY_ID,
    DEFAULT_FILL_POLICY_ID,
    TRACE_MODEL_VERSION,
    trace_policy_checksum,
)
from trading_signals.paper_trace.sanitize import stable_hash
from trading_signals.paper_trace.state_machine import TraceState, replay_receipts


class TraceEngineError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class TraceAdvanceResult:
    trace_id: str
    receipts: tuple[PaperTraceReceipt, ...]
    state: TraceState
    ignored_reason: str | None = None


def deterministic_trace_id(identity: ProspectiveSignalIdentity) -> str:
    return stable_hash(
        {
            "signal_id": identity.signal_id,
            "fill_policy_id": identity.fill_policy_id,
            "fill_policy_version": identity.fill_policy_version,
            "model_version": identity.engine_version,
        },
        namespace="paper_trace_id.v1",
    )


def deterministic_entity_id(trace_id: str, entity: str) -> str:
    return stable_hash(
        {"trace_id": trace_id, "entity": entity},
        namespace="paper_trace_entity_id.v1",
    )


def _evaluation_start(identity: ProspectiveSignalIdentity) -> datetime:
    duration = timeframe_duration(identity.timeframe)
    seconds = int(duration.total_seconds())
    decision = identity.decision_at.astimezone(UTC)
    epoch = int(decision.timestamp())
    boundary = ((epoch + seconds - 1) // seconds) * seconds
    return datetime.fromtimestamp(boundary, tz=UTC)


class _ReceiptBuilder:
    def __init__(
        self,
        identity: ProspectiveSignalIdentity,
        existing: Iterable[PaperTraceReceipt],
        *,
        observed_at: datetime,
    ) -> None:
        self.identity = identity
        self.trace_id = deterministic_trace_id(identity)
        self.receipts = list(existing)
        self.observed_at = utc_datetime(observed_at, code="OBSERVED_AT_NOT_UTC")
        if any(receipt.trace_id != self.trace_id for receipt in self.receipts):
            raise TraceEngineError("TRACE_IDENTITY_MISMATCH")
        replay_receipts(self.receipts)

    def emit(
        self,
        event_type: ReceiptEventType,
        *,
        occurred_at: datetime,
        reason_code: str,
        payload: Mapping[str, object] | None = None,
        candle: TraceCandle | None = None,
        price: float | None = None,
        order_id: str | None = None,
        fill_id: str | None = None,
        position_id: str | None = None,
    ) -> PaperTraceReceipt:
        previous = self.receipts[-1] if self.receipts else None
        receipt = build_receipt(
            identity=self.identity,
            trace_id=self.trace_id,
            event_type=event_type,
            occurred_at=occurred_at,
            observed_at=self.observed_at,
            event_sequence=1 if previous is None else previous.event_sequence + 1,
            previous_receipt_id=None if previous is None else previous.receipt_id,
            policy_id=self.identity.fill_policy_id,
            policy_version=self.identity.fill_policy_version,
            model_version=self.identity.engine_version,
            reason_code=reason_code,
            payload=payload,
            order_id=order_id,
            fill_id=fill_id,
            position_id=position_id,
            candle=candle,
            price=price,
        )
        self.receipts.append(receipt)
        replay_receipts(self.receipts)
        return receipt


def start_trace(
    identity: ProspectiveSignalIdentity,
    *,
    accepted: bool,
    observed_at: datetime,
) -> TraceAdvanceResult:
    if identity.fill_policy_id != DEFAULT_FILL_POLICY_ID:
        raise TraceEngineError("FILL_POLICY_UNSUPPORTED")
    if identity.fill_policy_version != trace_policy_checksum():
        raise TraceEngineError("FILL_POLICY_CHECKSUM_MISMATCH")
    if identity.engine_version != TRACE_MODEL_VERSION:
        raise TraceEngineError("TRACE_ENGINE_VERSION_MISMATCH")
    builder = _ReceiptBuilder(identity, (), observed_at=observed_at)
    builder.emit(
        ReceiptEventType.SIGNAL_OBSERVED,
        occurred_at=identity.decision_at,
        reason_code="SIGNAL_IDENTITY_CAPTURED",
        payload={"identity": identity.to_payload()},
    )
    builder.emit(
        ReceiptEventType.SIGNAL_ACCEPTED if accepted else ReceiptEventType.SIGNAL_REJECTED,
        occurred_at=identity.decision_at,
        reason_code="PAPER_TRACE_ACCEPTED" if accepted else "PAPER_TRACE_REJECTED",
    )
    if accepted:
        builder.emit(
            ReceiptEventType.PAPER_ORDER_CREATED,
            occurred_at=identity.decision_at,
            reason_code="SIMULATED_LIMIT_ORDER_CREATED",
            order_id=deterministic_entity_id(builder.trace_id, "order"),
            payload={
                "entry_price": identity.entry_price,
                "target_role": identity.target_role.value,
                "target_index": identity.target_index,
                "fee_model_id": identity.fee_model_id,
                "slippage_model_id": identity.slippage_model_id,
            },
        )
    return TraceAdvanceResult(
        trace_id=builder.trace_id,
        receipts=tuple(builder.receipts),
        state=replay_receipts(builder.receipts),
    )


def _last_market_receipt(
    receipts: Iterable[PaperTraceReceipt],
) -> PaperTraceReceipt | None:
    market = [
        receipt
        for receipt in receipts
        if receipt.event_type is ReceiptEventType.MARKET_CANDLE_OBSERVED
    ]
    return market[-1] if market else None


def _payload(receipt: PaperTraceReceipt) -> Mapping[str, object]:
    value = json.loads(receipt.payload_json)
    return value if isinstance(value, dict) else {}


def _contains(candle: TraceCandle, price: float) -> bool:
    return candle.low_price <= price <= candle.high_price


def _entry_gap_crossed(
    identity: ProspectiveSignalIdentity,
    candle: TraceCandle,
    last_market: PaperTraceReceipt | None,
) -> bool:
    if last_market is None:
        return False
    prior_close = _payload(last_market).get("close")
    if not isinstance(prior_close, (int, float)):
        return False
    entry = identity.entry_price
    return (
        (prior_close < entry < candle.open_price)
        or (prior_close > entry > candle.open_price)
    ) and not _contains(candle, entry)


def _terminal_position(state: TraceState) -> bool:
    return state.trace_blocked_reason is not None or state.position in {
        PaperPositionState.CLOSED_WIN,
        PaperPositionState.CLOSED_LOSS,
        PaperPositionState.CLOSED_TIME_EXIT,
        PaperPositionState.EXPIRED_UNRESOLVED,
        PaperPositionState.AMBIGUOUS,
        PaperPositionState.DATA_BLOCKED,
    }


def advance_trace(
    identity: ProspectiveSignalIdentity,
    existing: Iterable[PaperTraceReceipt],
    candle: TraceCandle,
    *,
    observed_at: datetime,
) -> TraceAdvanceResult:
    prior = tuple(existing)
    state = replay_receipts(prior)
    trace_id = deterministic_trace_id(identity)
    observed = utc_datetime(observed_at, code="OBSERVED_AT_NOT_UTC")
    if not prior:
        raise TraceEngineError("TRACE_NOT_STARTED")
    if state.trace_id != trace_id:
        raise TraceEngineError("TRACE_IDENTITY_MISMATCH")
    if candle.symbol != identity.symbol:
        raise TraceEngineError("CANDLE_SYMBOL_MISMATCH")
    if candle.timeframe != identity.timeframe:
        raise TraceEngineError("CANDLE_TIMEFRAME_MISMATCH")
    if not candle.closed or candle.close_at > observed:
        return TraceAdvanceResult(trace_id, (), state, "CANDLE_NOT_CLOSED")
    if candle.open_at < _evaluation_start(identity):
        return TraceAdvanceResult(trace_id, (), state, "CANDLE_BEFORE_EVALUATION_START")
    if _terminal_position(state) or state.order in {
        PaperOrderState.CANCELLED,
        PaperOrderState.EXPIRED,
    } or state.signal in {
        SignalTraceState.REJECTED,
        SignalTraceState.EXPIRED_NOT_ACTIVATED,
    }:
        return TraceAdvanceResult(trace_id, (), state, "TRACE_TERMINAL")

    same_open = [
        receipt
        for receipt in prior
        if receipt.event_type is ReceiptEventType.MARKET_CANDLE_OBSERVED
        and receipt.candle_open_time == candle.open_at
    ]
    if same_open:
        if same_open[-1].evidence_fingerprint == candle.evidence_fingerprint:
            return TraceAdvanceResult(trace_id, (), state, "CANDLE_ALREADY_PROCESSED")
        builder = _ReceiptBuilder(identity, prior, observed_at=observed)
        new = builder.emit(
            ReceiptEventType.MARKET_DATA_CONFLICT,
            occurred_at=candle.close_at,
            reason_code="SAME_CANDLE_DIFFERENT_OHLC",
            candle=candle,
        )
        return TraceAdvanceResult(
            trace_id,
            (new,),
            replay_receipts(builder.receipts),
        )

    last_market = _last_market_receipt(prior)
    if last_market is not None and last_market.candle_open_time is not None:
        expected = last_market.candle_open_time + timeframe_duration(identity.timeframe)
        if candle.open_at < expected:
            raise TraceEngineError("CANDLE_OUT_OF_ORDER")
        if candle.open_at > expected:
            builder = _ReceiptBuilder(identity, prior, observed_at=observed)
            gap = builder.emit(
                ReceiptEventType.MARKET_DATA_GAP,
                occurred_at=candle.open_at,
                reason_code="NON_CONTIGUOUS_CLOSED_CANDLES",
                candle=candle,
                payload={"expected_open_at": expected.isoformat()},
            )
            return TraceAdvanceResult(trace_id, (gap,), replay_receipts(builder.receipts))

    builder = _ReceiptBuilder(identity, prior, observed_at=observed)
    emitted: list[PaperTraceReceipt] = []
    emitted.append(
        builder.emit(
            ReceiptEventType.MARKET_CANDLE_OBSERVED,
            occurred_at=candle.close_at,
            reason_code="UNIQUE_CLOSED_CANDLE",
            candle=candle,
            payload=candle.evidence_payload(),
        )
    )
    state = replay_receipts(builder.receipts)
    order_id = deterministic_entity_id(trace_id, "order")
    fill_id = deterministic_entity_id(trace_id, "fill")
    position_id = deterministic_entity_id(trace_id, "position")

    if state.order is PaperOrderState.PENDING:
        if _entry_gap_crossed(identity, candle, last_market):
            emitted.append(
                builder.emit(
                    ReceiptEventType.ENTRY_TOUCH_AMBIGUOUS,
                    occurred_at=candle.open_at,
                    reason_code="ENTRY_GAP_CROSS_WITHOUT_EXECUTABLE_PRICE",
                    candle=candle,
                    order_id=order_id,
                )
            )
        elif _contains(candle, identity.entry_price):
            stop_hit = _contains(candle, identity.stop_price)
            target_hit = _contains(candle, identity.target_price)
            entry_at_open = candle.open_price == identity.entry_price
            if (stop_hit or target_hit) and not entry_at_open:
                emitted.append(
                    builder.emit(
                        ReceiptEventType.ENTRY_TOUCH_AMBIGUOUS,
                        occurred_at=candle.close_at,
                        reason_code="ENTRY_AND_BARRIER_ORDER_UNKNOWN",
                        candle=candle,
                        order_id=order_id,
                    )
                )
            else:
                emitted.append(
                    builder.emit(
                        ReceiptEventType.ENTRY_TOUCHED,
                        occurred_at=candle.open_at if entry_at_open else candle.close_at,
                        reason_code="FIXED_ENTRY_IN_CLOSED_CANDLE_RANGE",
                        candle=candle,
                        order_id=order_id,
                        price=identity.entry_price,
                    )
                )
                emitted.append(
                    builder.emit(
                        ReceiptEventType.SIMULATED_FILL_CREATED,
                        occurred_at=candle.open_at if entry_at_open else candle.close_at,
                        reason_code="MODELED_FILL_AT_FIXED_ENTRY",
                        candle=candle,
                        order_id=order_id,
                        fill_id=fill_id,
                        price=identity.entry_price,
                        payload={
                            "fill_is_simulated": True,
                            "observed_touch_price": None,
                            "fee_model_id": identity.fee_model_id,
                            "slippage_model_id": identity.slippage_model_id,
                        },
                    )
                )
                emitted.append(
                    builder.emit(
                        ReceiptEventType.PAPER_POSITION_OPENED,
                        occurred_at=candle.open_at if entry_at_open else candle.close_at,
                        reason_code="SIMULATED_FILL_ACCEPTED",
                        candle=candle,
                        order_id=order_id,
                        fill_id=fill_id,
                        position_id=position_id,
                        price=identity.entry_price,
                    )
                )
                if entry_at_open and stop_hit and target_hit:
                    emitted.append(
                        builder.emit(
                            ReceiptEventType.EXIT_AMBIGUOUS,
                            occurred_at=candle.close_at,
                            reason_code="STOP_AND_TARGET_SAME_CANDLE",
                            candle=candle,
                            order_id=order_id,
                            fill_id=fill_id,
                            position_id=position_id,
                        )
                    )
                elif entry_at_open and (stop_hit or target_hit):
                    barrier_event = (
                        ReceiptEventType.STOP_TOUCHED
                        if stop_hit
                        else ReceiptEventType.TARGET_TOUCHED
                    )
                    reason = "STOP_FIRST" if stop_hit else "TARGET_FIRST"
                    level = identity.stop_price if stop_hit else identity.target_price
                    emitted.append(
                        builder.emit(
                            barrier_event,
                            occurred_at=candle.close_at,
                            reason_code=reason,
                            candle=candle,
                            position_id=position_id,
                            price=level,
                        )
                    )
                    emitted.append(
                        builder.emit(
                            ReceiptEventType.PAPER_POSITION_CLOSED,
                            occurred_at=candle.close_at,
                            reason_code=reason,
                            candle=candle,
                            position_id=position_id,
                            price=level,
                        )
                    )
        if (
            replay_receipts(builder.receipts).order is PaperOrderState.PENDING
            and replay_receipts(builder.receipts).trace_blocked_reason is None
            and replay_receipts(builder.receipts).candles_before_entry >= identity.horizon_candles
        ):
            emitted.append(
                builder.emit(
                    ReceiptEventType.SIGNAL_EXPIRED_NOT_ACTIVATED,
                    occurred_at=candle.close_at,
                    reason_code="ENTRY_HORIZON_COMPLETE",
                    candle=candle,
                    order_id=order_id,
                )
            )
    elif state.position is PaperPositionState.OPEN:
        stop_gap = (
            candle.open_price <= identity.stop_price
            if identity.direction == "long"
            else candle.open_price >= identity.stop_price
        )
        target_gap = (
            candle.open_price >= identity.target_price
            if identity.direction == "long"
            else candle.open_price <= identity.target_price
        )
        stop_hit = _contains(candle, identity.stop_price)
        target_hit = _contains(candle, identity.target_price)
        if stop_gap or target_gap:
            reason = "STOP_FIRST" if stop_gap else "TARGET_FIRST"
            barrier_event = (
                ReceiptEventType.STOP_TOUCHED if stop_gap else ReceiptEventType.TARGET_TOUCHED
            )
            emitted.append(
                builder.emit(
                    barrier_event,
                    occurred_at=candle.open_at,
                    reason_code=f"{reason}_GAP_AT_OPEN",
                    candle=candle,
                    position_id=position_id,
                    price=candle.open_price,
                )
            )
            emitted.append(
                builder.emit(
                    ReceiptEventType.PAPER_POSITION_CLOSED,
                    occurred_at=candle.open_at,
                    reason_code=reason,
                    candle=candle,
                    position_id=position_id,
                    price=candle.open_price,
                    payload={"exit_price_rule": "OBSERVED_CANDLE_OPEN_GAP"},
                )
            )
        elif stop_hit and target_hit:
            emitted.append(
                builder.emit(
                    ReceiptEventType.EXIT_AMBIGUOUS,
                    occurred_at=candle.close_at,
                    reason_code="STOP_AND_TARGET_SAME_CANDLE",
                    candle=candle,
                    position_id=position_id,
                )
            )
        elif stop_hit or target_hit:
            reason = "STOP_FIRST" if stop_hit else "TARGET_FIRST"
            level = identity.stop_price if stop_hit else identity.target_price
            emitted.append(
                builder.emit(
                    ReceiptEventType.STOP_TOUCHED
                    if stop_hit
                    else ReceiptEventType.TARGET_TOUCHED,
                    occurred_at=candle.close_at,
                    reason_code=reason,
                    candle=candle,
                    position_id=position_id,
                    price=level,
                )
            )
            emitted.append(
                builder.emit(
                    ReceiptEventType.PAPER_POSITION_CLOSED,
                    occurred_at=candle.close_at,
                    reason_code=reason,
                    candle=candle,
                    position_id=position_id,
                    price=level,
                )
            )
        elif state.candles_after_entry >= identity.horizon_candles:
            emitted.append(
                builder.emit(
                    ReceiptEventType.POSITION_HORIZON_REACHED,
                    occurred_at=candle.close_at,
                    reason_code="POSITION_HORIZON_COMPLETE",
                    candle=candle,
                    position_id=position_id,
                )
            )
            emitted.append(
                builder.emit(
                    ReceiptEventType.POSITION_EXPIRED_UNRESOLVED,
                    occurred_at=candle.close_at,
                    reason_code="NO_CANONICAL_TERMINAL_PRICE_POLICY",
                    candle=candle,
                    position_id=position_id,
                    payload={
                        "expiry_policy_id": DEFAULT_EXPIRY_POLICY_ID,
                        "gross_r": None,
                        "modeled_net_r": None,
                    },
                )
            )

    return TraceAdvanceResult(
        trace_id=trace_id,
        receipts=tuple(emitted),
        state=replay_receipts(builder.receipts),
    )
