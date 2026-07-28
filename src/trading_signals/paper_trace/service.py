from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from trading_signals.paper_trace.contracts import TraceCandle
from trading_signals.paper_trace.engine import advance_trace, start_trace
from trading_signals.paper_trace.identity import build_prospective_identity
from trading_signals.paper_trace.policy import (
    DEFAULT_EXPIRY_POLICY_ID,
    DEFAULT_FILL_POLICY_ID,
)
from trading_signals.paper_trace.store import JsonlTraceStore, TraceStoreError


class PaperTraceConfigurationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ProspectivePaperTraceService:
    def __init__(self, store: JsonlTraceStore) -> None:
        self.store = store
        self._isolated_error_code: str | None = None

    @property
    def isolated_error_code(self) -> str | None:
        return self._isolated_error_code

    def isolate(self, error_code: str) -> None:
        if self._isolated_error_code is None:
            self._isolated_error_code = str(error_code)[:100]

    def observe_signal(
        self,
        *,
        signal: object,
        risk_plan: object,
        evaluation: object,
        entry_snapshot: object,
        higher_snapshot: object,
        setup_type: str,
        settings: object,
        runtime_identity: dict[str, object],
        accepted: bool,
        observed_at: datetime | None = None,
    ) -> str | None:
        if self._isolated_error_code is not None:
            return None
        identity = build_prospective_identity(
            signal=signal,
            risk_plan=risk_plan,
            evaluation=evaluation,
            entry_snapshot=entry_snapshot,
            higher_snapshot=higher_snapshot,
            setup_type=setup_type,
            settings=settings,
            runtime_identity=runtime_identity,
        )
        result = start_trace(
            identity,
            accepted=accepted,
            observed_at=observed_at or datetime.now(tz=UTC),
        )
        self.store.append(result.receipts)
        return result.trace_id

    def advance_snapshot(
        self,
        snapshot: object,
        *,
        observed_at: datetime | None = None,
    ) -> dict[str, int]:
        if self._isolated_error_code is not None:
            return {"traces_advanced": 0, "traces_ignored": 0, "trace_isolated": 1}
        now = observed_at or datetime.now(tz=UTC)
        candle = trace_candle_from_snapshot(snapshot, observed_at=now)
        advanced = ignored = 0
        receipts = self.store.read_all()
        trace_ids = sorted({item.trace_id for item in receipts if item.symbol == candle.symbol})
        for trace_id in trace_ids:
            trace_receipts = tuple(item for item in receipts if item.trace_id == trace_id)
            identity_payload = None
            if trace_receipts:
                import json

                first_payload = json.loads(trace_receipts[0].payload_json)
                identity_payload = first_payload.get("identity")
            if not isinstance(identity_payload, dict):
                continue
            from trading_signals.paper_trace.contracts import ProspectiveSignalIdentity

            identity = ProspectiveSignalIdentity.from_payload(identity_payload)
            result = advance_trace(identity, trace_receipts, candle, observed_at=now)
            if result.receipts:
                self.store.append(result.receipts)
                advanced += 1
            else:
                ignored += 1
        return {"traces_advanced": advanced, "traces_ignored": ignored}


def trace_candle_from_snapshot(
    snapshot: object,
    *,
    observed_at: datetime,
) -> TraceCandle:
    """Normalize provider close timestamps without inventing candle history.

    Binance reports a close timestamp one millisecond before the boundary,
    while Bybit reports the boundary itself. Only those two representations
    are accepted. The resulting evidence always uses exact UTC boundaries.
    """

    from trading_signals.paper_trace.contracts import (
        TraceContractError,
        timeframe_duration,
        utc_datetime,
    )

    now = utc_datetime(observed_at, code="OBSERVED_AT_NOT_UTC")
    raw_close = utc_datetime(
        str(getattr(snapshot, "timestamp")),
        code="CANDLE_CLOSE_NOT_UTC",
    )
    timeframe = str(getattr(snapshot, "timeframe"))
    duration = timeframe_duration(timeframe)
    interval_us = int(duration.total_seconds() * 1_000_000)
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    elapsed = raw_close - epoch
    elapsed_us = (
        elapsed.days * 86_400_000_000
        + elapsed.seconds * 1_000_000
        + elapsed.microseconds
    )
    remainder = elapsed_us % interval_us
    if remainder == 0:
        close_at = raw_close
    else:
        adjustment_us = interval_us - remainder
        if adjustment_us > 2_000_000:
            raise TraceContractError("CANDLE_CLOSE_BOUNDARY_INVALID")
        close_at = raw_close + timedelta(microseconds=adjustment_us)
    open_at = close_at - duration
    market_source = str(getattr(snapshot, "source", "")).strip().lower()
    if not market_source or market_source == "unknown":
        raise TraceContractError("MARKET_SOURCE_UNAVAILABLE")
    return TraceCandle(
        symbol=str(getattr(snapshot, "symbol")),
        timeframe=timeframe,
        open_at=open_at,
        close_at=close_at,
        open_price=float(getattr(snapshot, "open")),
        high_price=float(getattr(snapshot, "high")),
        low_price=float(getattr(snapshot, "low")),
        close_price=float(getattr(snapshot, "close")),
        closed=close_at <= now,
        market_source=market_source,
    )


def build_paper_trace_service(settings: object) -> ProspectivePaperTraceService | None:
    if not bool(getattr(settings, "paper_trace_enabled", False)):
        return None
    expected = {
        "paper_fill_policy_id": DEFAULT_FILL_POLICY_ID,
        "paper_expiry_policy_id": DEFAULT_EXPIRY_POLICY_ID,
        "paper_fee_model_id": "NO_FEE_MODEL",
        "paper_slippage_model_id": "NO_SLIPPAGE_MODEL",
    }
    if any(getattr(settings, key, None) != value for key, value in expected.items()):
        raise PaperTraceConfigurationError("PAPER_TRACE_POLICY_CONFIGURATION_UNSUPPORTED")
    if not bool(getattr(settings, "paper_trace_strict_identity", True)):
        raise PaperTraceConfigurationError("PAPER_TRACE_STRICT_IDENTITY_REQUIRED")
    raw_path = getattr(settings, "paper_trace_store_path", None)
    if raw_path in {None, ""}:
        raise PaperTraceConfigurationError("PAPER_TRACE_STORE_PATH_REQUIRED")
    allowed_root = getattr(settings, "paper_trace_allowed_root", None)
    if allowed_root in {None, ""}:
        raise PaperTraceConfigurationError("PAPER_TRACE_ALLOWED_ROOT_REQUIRED")
    raw_max_bytes = str(getattr(settings, "paper_trace_max_bytes", "")).strip()
    if not raw_max_bytes.isdigit() or int(raw_max_bytes) <= 0:
        raise PaperTraceConfigurationError("PAPER_TRACE_MAX_BYTES_INVALID")
    data_root = Path(getattr(settings, "data_storage_path"))
    try:
        store = JsonlTraceStore(
            Path(raw_path),
            data_root=data_root,
            allowed_root=Path(allowed_root),
            max_bytes=int(raw_max_bytes),
        )
    except (OSError, TraceStoreError) as exc:
        raise PaperTraceConfigurationError("PAPER_TRACE_STORE_PATH_UNSAFE") from exc
    return ProspectivePaperTraceService(store)
