from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Mapping

from trading_signals.paper_trace.sanitize import (
    canonical_json,
    sanitized_payload,
    stable_hash,
)

TRACE_CONTRACT_VERSION = "paper.trace.v1"
RECEIPT_EVENT_VERSION = "paper.receipt.v1"


class TraceContractError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class TargetRole(str, Enum):
    SINGLE_TAKE_PROFIT = "SINGLE_TAKE_PROFIT"
    TP1 = "TP1"
    TP2 = "TP2"
    TP3 = "TP3"
    FINAL_TARGET = "FINAL_TARGET"
    UNKNOWN = "UNKNOWN"


class ReceiptEventType(str, Enum):
    SIGNAL_OBSERVED = "SIGNAL_OBSERVED"
    SIGNAL_ACCEPTED = "SIGNAL_ACCEPTED"
    SIGNAL_REJECTED = "SIGNAL_REJECTED"
    PAPER_ORDER_CREATED = "PAPER_ORDER_CREATED"
    PAPER_ORDER_CANCELLED = "PAPER_ORDER_CANCELLED"
    MARKET_CANDLE_OBSERVED = "MARKET_CANDLE_OBSERVED"
    ENTRY_TOUCHED = "ENTRY_TOUCHED"
    ENTRY_TOUCH_AMBIGUOUS = "ENTRY_TOUCH_AMBIGUOUS"
    SIMULATED_FILL_CREATED = "SIMULATED_FILL_CREATED"
    PAPER_POSITION_OPENED = "PAPER_POSITION_OPENED"
    STOP_TOUCHED = "STOP_TOUCHED"
    TARGET_TOUCHED = "TARGET_TOUCHED"
    EXIT_AMBIGUOUS = "EXIT_AMBIGUOUS"
    PAPER_POSITION_CLOSED = "PAPER_POSITION_CLOSED"
    SIGNAL_EXPIRED_NOT_ACTIVATED = "SIGNAL_EXPIRED_NOT_ACTIVATED"
    POSITION_HORIZON_REACHED = "POSITION_HORIZON_REACHED"
    POSITION_EXPIRED_CLOSED = "POSITION_EXPIRED_CLOSED"
    POSITION_EXPIRED_UNRESOLVED = "POSITION_EXPIRED_UNRESOLVED"
    MARKET_DATA_GAP = "MARKET_DATA_GAP"
    MARKET_DATA_CONFLICT = "MARKET_DATA_CONFLICT"
    TRACE_ERROR = "TRACE_ERROR"


class SignalTraceState(str, Enum):
    NONE = "NONE"
    OBSERVED = "OBSERVED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED_NOT_ACTIVATED = "EXPIRED_NOT_ACTIVATED"


class PaperOrderState(str, Enum):
    NONE = "NONE"
    PENDING = "PENDING"
    ACTIVATED = "ACTIVATED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class PaperPositionState(str, Enum):
    NONE = "NONE"
    OPEN = "OPEN"
    CLOSED_WIN = "CLOSED_WIN"
    CLOSED_LOSS = "CLOSED_LOSS"
    HORIZON_REACHED = "HORIZON_REACHED"
    CLOSED_TIME_EXIT = "CLOSED_TIME_EXIT"
    EXPIRED_UNRESOLVED = "EXPIRED_UNRESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    DATA_BLOCKED = "DATA_BLOCKED"


def utc_datetime(value: datetime | str, *, code: str) -> datetime:
    parsed = (
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, str)
        else value
    )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TraceContractError(code)
    return parsed.astimezone(UTC)


def timeframe_duration(timeframe: str) -> timedelta:
    values = {"1m": 60, "5m": 300, "15m": 900, "1h": 3_600, "4h": 14_400, "1d": 86_400}
    try:
        return timedelta(seconds=values[timeframe])
    except KeyError as exc:
        raise TraceContractError("UNSUPPORTED_TIMEFRAME") from exc


@dataclass(frozen=True, slots=True)
class ProspectiveSignalIdentity:
    signal_id: str
    signal_schema_version: str
    created_at: datetime
    decision_at: datetime
    symbol: str
    direction: str
    timeframe: str
    strategy_id: str
    strategy_version: str
    strategy_commit: str | None
    setup_id: str
    setup_version: str
    setup_parameters_hash: str
    policy_id: str
    policy_version: str
    fill_policy_id: str
    fill_policy_version: str
    expiry_policy_id: str
    engine_version: str
    config_hash: str
    market_context_fingerprint: str
    entry_price: float
    stop_price: float
    target_price: float
    target_role: TargetRole
    target_index: int | None
    horizon_candles: int
    source_cycle_id: str
    source_agent_decision_id: str | None
    correlation_group_id: str | None
    trace_version: str = TRACE_CONTRACT_VERSION
    fee_model_id: str = "NO_FEE_MODEL"
    fee_model_version: str = "none"
    slippage_model_id: str = "NO_SLIPPAGE_MODEL"
    slippage_model_version: str = "none"

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_at", utc_datetime(self.created_at, code="CREATED_AT_NOT_UTC"))
        object.__setattr__(self, "decision_at", utc_datetime(self.decision_at, code="DECISION_AT_NOT_UTC"))
        if not self.signal_id or not self.source_cycle_id:
            raise TraceContractError("SIGNAL_IDENTITY_MISSING")
        if self.direction not in {"long", "short"}:
            raise TraceContractError("SIGNAL_DIRECTION_INVALID")
        timeframe_duration(self.timeframe)
        required = (
            self.strategy_id,
            self.strategy_version,
            self.setup_id,
            self.setup_version,
            self.policy_id,
            self.policy_version,
            self.fill_policy_id,
            self.fill_policy_version,
            self.expiry_policy_id,
            self.engine_version,
        )
        if any(not value or value.lower() == "unknown" for value in required):
            raise TraceContractError("STRICT_IDENTITY_INCOMPLETE")
        if self.strategy_commit is not None and (
            len(self.strategy_commit) != 40
            or any(character not in "0123456789abcdef" for character in self.strategy_commit.lower())
        ):
            raise TraceContractError("STRATEGY_COMMIT_INVALID")
        for fingerprint in (
            self.setup_parameters_hash,
            self.config_hash,
            self.market_context_fingerprint,
        ):
            if len(fingerprint) != 64 or any(
                character not in "0123456789abcdef" for character in fingerprint.lower()
            ):
                raise TraceContractError("IDENTITY_FINGERPRINT_INVALID")
        prices = (self.entry_price, self.stop_price, self.target_price)
        if not all(math.isfinite(value) and value > 0 for value in prices):
            raise TraceContractError("SIGNAL_LEVELS_INVALID")
        if self.direction == "long" and not self.stop_price < self.entry_price < self.target_price:
            raise TraceContractError("SIGNAL_LEVELS_INVALID")
        if self.direction == "short" and not self.target_price < self.entry_price < self.stop_price:
            raise TraceContractError("SIGNAL_LEVELS_INVALID")
        if self.target_role is TargetRole.UNKNOWN:
            raise TraceContractError("TARGET_ROLE_UNKNOWN")
        if self.horizon_candles <= 0:
            raise TraceContractError("HORIZON_INVALID")

    def to_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload["created_at"] = self.created_at.isoformat()
        payload["decision_at"] = self.decision_at.isoformat()
        payload["target_role"] = self.target_role.value
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "ProspectiveSignalIdentity":
        values = dict(payload)
        values["target_role"] = TargetRole(str(values["target_role"]))
        return cls(**values)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class TraceCandle:
    symbol: str
    timeframe: str
    open_at: datetime
    close_at: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    closed: bool = True
    market_source: str = "UNSPECIFIED"

    def __post_init__(self) -> None:
        object.__setattr__(self, "open_at", utc_datetime(self.open_at, code="CANDLE_OPEN_NOT_UTC"))
        object.__setattr__(self, "close_at", utc_datetime(self.close_at, code="CANDLE_CLOSE_NOT_UTC"))
        if self.close_at - self.open_at != timeframe_duration(self.timeframe):
            raise TraceContractError("CANDLE_INTERVAL_INVALID")
        prices = (self.open_price, self.high_price, self.low_price, self.close_price)
        if (
            not all(math.isfinite(value) and value > 0 for value in prices)
            or self.low_price > min(self.open_price, self.close_price)
            or self.high_price < max(self.open_price, self.close_price)
            or self.low_price > self.high_price
        ):
            raise TraceContractError("CANDLE_OHLC_INVALID")

    def evidence_payload(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "open_at": self.open_at.isoformat(),
            "close_at": self.close_at.isoformat(),
            "open": self.open_price,
            "high": self.high_price,
            "low": self.low_price,
            "close": self.close_price,
            "closed": self.closed,
            "market_source": self.market_source,
        }

    @property
    def evidence_fingerprint(self) -> str:
        return stable_hash(self.evidence_payload(), namespace="paper_trace_candle.v1")

    @property
    def evidence_id(self) -> str:
        return hashlib.sha256(
            f"paper_trace_evidence:{self.symbol}|{self.timeframe}|{self.open_at.isoformat()}|{self.evidence_fingerprint}".encode(
                "utf-8"
            )
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class PaperTraceReceipt:
    receipt_id: str
    trace_id: str
    event_type: ReceiptEventType
    event_version: str
    occurred_at: datetime
    observed_at: datetime
    signal_id: str
    order_id: str | None
    fill_id: str | None
    position_id: str | None
    candle_open_time: datetime | None
    timeframe: str
    symbol: str
    direction: str
    price: float | None
    quantity: float | None
    evidence_id: str | None
    evidence_fingerprint: str
    previous_receipt_id: str | None
    event_sequence: int
    policy_id: str
    policy_version: str
    model_version: str
    source: str
    reason_code: str
    payload_json: str
    created_at: datetime
    receipt_hash: str

    def unsigned_payload(self) -> dict[str, object]:
        payload = self.to_dict()
        payload.pop("receipt_hash")
        return payload

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["event_type"] = self.event_type.value
        for field in ("occurred_at", "observed_at", "candle_open_time", "created_at"):
            value = payload[field]
            payload[field] = value.isoformat() if isinstance(value, datetime) else None
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "PaperTraceReceipt":
        values = dict(payload)
        values["event_type"] = ReceiptEventType(str(values["event_type"]))
        for field in ("occurred_at", "observed_at", "created_at"):
            values[field] = utc_datetime(values[field], code="RECEIPT_TIMESTAMP_NOT_UTC")  # type: ignore[arg-type]
        values["candle_open_time"] = (
            utc_datetime(values["candle_open_time"], code="CANDLE_OPEN_NOT_UTC")
            if values.get("candle_open_time")
            else None
        )
        receipt = cls(**values)  # type: ignore[arg-type]
        if receipt.receipt_hash != stable_hash(
            receipt.unsigned_payload(),
            namespace="paper_trace_receipt_hash.v1",
        ):
            raise TraceContractError("RECEIPT_HASH_MISMATCH")
        return receipt


def build_receipt(
    *,
    identity: ProspectiveSignalIdentity,
    trace_id: str,
    event_type: ReceiptEventType,
    occurred_at: datetime,
    observed_at: datetime,
    event_sequence: int,
    previous_receipt_id: str | None,
    policy_id: str,
    policy_version: str,
    model_version: str,
    reason_code: str,
    payload: Mapping[str, object] | None = None,
    order_id: str | None = None,
    fill_id: str | None = None,
    position_id: str | None = None,
    candle: TraceCandle | None = None,
    price: float | None = None,
    quantity: float | None = None,
) -> PaperTraceReceipt:
    occurred = utc_datetime(occurred_at, code="OCCURRED_AT_NOT_UTC")
    observed = utc_datetime(observed_at, code="OBSERVED_AT_NOT_UTC")
    safe_payload = sanitized_payload(dict(payload or {}))
    payload_json = canonical_json(safe_payload)
    evidence_fingerprint = candle.evidence_fingerprint if candle else stable_hash(
        {"event_type": event_type.value, "signal_id": identity.signal_id, "payload": safe_payload},
        namespace="paper_trace_non_market_evidence.v1",
    )
    evidence_id = candle.evidence_id if candle else None
    id_material = {
        "trace_id": trace_id,
        "event_type": event_type.value,
        "event_sequence": event_sequence,
        "evidence_fingerprint": evidence_fingerprint,
        "reason_code": reason_code,
        "order_id": order_id,
        "fill_id": fill_id,
        "position_id": position_id,
    }
    receipt_id = stable_hash(id_material, namespace="paper_trace_receipt_id.v1")
    draft = PaperTraceReceipt(
        receipt_id=receipt_id,
        trace_id=trace_id,
        event_type=event_type,
        event_version=RECEIPT_EVENT_VERSION,
        occurred_at=occurred,
        observed_at=observed,
        signal_id=identity.signal_id,
        order_id=order_id,
        fill_id=fill_id,
        position_id=position_id,
        candle_open_time=candle.open_at if candle else None,
        timeframe=identity.timeframe,
        symbol=identity.symbol,
        direction=identity.direction,
        price=price,
        quantity=quantity,
        evidence_id=evidence_id,
        evidence_fingerprint=evidence_fingerprint,
        previous_receipt_id=previous_receipt_id,
        event_sequence=event_sequence,
        policy_id=policy_id,
        policy_version=policy_version,
        model_version=model_version,
        source="PROSPECTIVE_PAPER_TRACE",
        reason_code=reason_code,
        payload_json=payload_json,
        created_at=observed,
        receipt_hash="",
    )
    receipt_hash = stable_hash(
        draft.unsigned_payload(),
        namespace="paper_trace_receipt_hash.v1",
    )
    return PaperTraceReceipt(**{**asdict(draft), "receipt_hash": receipt_hash})
