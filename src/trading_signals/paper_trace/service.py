from __future__ import annotations

from datetime import UTC, datetime
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
    ) -> str:
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
        now = observed_at or datetime.now(tz=UTC)
        close_at = datetime.fromisoformat(
            str(getattr(snapshot, "timestamp")).replace("Z", "+00:00")
        ).astimezone(UTC)
        timeframe = str(getattr(snapshot, "timeframe"))
        from trading_signals.paper_trace.contracts import timeframe_duration

        candle = TraceCandle(
            symbol=str(getattr(snapshot, "symbol")),
            timeframe=timeframe,
            open_at=close_at - timeframe_duration(timeframe),
            close_at=close_at,
            open_price=float(getattr(snapshot, "open")),
            high_price=float(getattr(snapshot, "high")),
            low_price=float(getattr(snapshot, "low")),
            close_price=float(getattr(snapshot, "close")),
            closed=close_at <= now,
        )
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
    data_root = Path(getattr(settings, "data_storage_path"))
    try:
        store = JsonlTraceStore(Path(raw_path), data_root=data_root)
    except (OSError, TraceStoreError) as exc:
        raise PaperTraceConfigurationError("PAPER_TRACE_STORE_PATH_UNSAFE") from exc
    return ProspectivePaperTraceService(store)
