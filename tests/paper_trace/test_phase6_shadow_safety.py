from __future__ import annotations

import logging
import threading
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from trading_signals.application.use_cases.run_market_scan import (
    _paper_trace_shadow_call,
)
from trading_signals.paper_trace.contracts import TraceContractError
from trading_signals.paper_trace.contracts import ReceiptEventType, TraceCandle
from trading_signals.paper_trace.engine import advance_trace, start_trace
from trading_signals.paper_trace.service import (
    ProspectivePaperTraceService,
    trace_candle_from_snapshot,
)
from trading_signals.paper_trace.store import JsonlTraceStore, TraceStoreError


def _snapshot(timestamp: str) -> SimpleNamespace:
    return SimpleNamespace(
        symbol="BTCUSDT",
        timeframe="1h",
        timestamp=timestamp,
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        source="binance",
    )


def test_binance_close_timestamp_normalizes_to_exact_boundaries() -> None:
    candle = trace_candle_from_snapshot(
        _snapshot("2026-01-01T10:59:59.999000+00:00"),
        observed_at=datetime(2026, 1, 1, 11, 0, 1, tzinfo=UTC),
    )
    assert candle.open_at == datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    assert candle.close_at == datetime(2026, 1, 1, 11, 0, tzinfo=UTC)
    assert candle.closed is True


def test_bybit_close_timestamp_preserves_exact_boundary() -> None:
    candle = trace_candle_from_snapshot(
        _snapshot("2026-01-01T11:00:00+00:00"),
        observed_at=datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
    )
    assert candle.open_at == datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    assert candle.close_at == datetime(2026, 1, 1, 11, 0, tzinfo=UTC)


def test_unverifiable_close_timestamp_fails_closed() -> None:
    with pytest.raises(TraceContractError, match="CANDLE_CLOSE_BOUNDARY_INVALID"):
        trace_candle_from_snapshot(
            _snapshot("2026-01-01T10:30:00+00:00"),
            observed_at=datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
        )


class _FailingStore:
    def __init__(self) -> None:
        self.calls = 0

    def read_all(self):
        self.calls += 1
        raise TraceStoreError("TRACE_STORE_READ_FAILED")


def test_runtime_trace_failure_is_isolated_and_circuit_breaks(caplog) -> None:
    store = _FailingStore()
    service = ProspectivePaperTraceService(store)  # type: ignore[arg-type]
    logger = logging.getLogger("paper-trace-phase6-test")
    with caplog.at_level(logging.INFO, logger=logger.name):
        first = _paper_trace_shadow_call(
            service,
            "advance_snapshot",
            logger,
            _snapshot("2026-01-01T11:00:00+00:00"),
        )
        second = _paper_trace_shadow_call(
            service,
            "advance_snapshot",
            logger,
            _snapshot("2026-01-01T12:00:00+00:00"),
        )
    assert first is None
    assert second == {
        "traces_advanced": 0,
        "traces_ignored": 0,
        "trace_isolated": 1,
    }
    assert service.isolated_error_code == "TRACE_STORE_READ_FAILED"
    assert store.calls == 1
    assert "paper_trace_shadow_isolated" in caplog.text


def _secure_runtime(tmp_path: Path) -> Path:
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    return runtime


def test_store_rejects_insecure_parent_and_existing_file(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o755)
    with pytest.raises(
        TraceStoreError,
        match="TRACE_STORE_PARENT_PERMISSIONS_UNSAFE",
    ):
        JsonlTraceStore(runtime / "trace.jsonl", data_root=tmp_path / "data")

    runtime.chmod(0o700)
    path = runtime / "trace.jsonl"
    path.touch(mode=0o644)
    store = JsonlTraceStore(path, data_root=tmp_path / "data")
    with pytest.raises(
        TraceStoreError,
        match="TRACE_STORE_FILE_PERMISSIONS_UNSAFE",
    ):
        store.read_all()


def test_store_rejects_symlink_and_outside_allowed_root(tmp_path: Path) -> None:
    allowed = _secure_runtime(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    with pytest.raises(TraceStoreError, match="TRACE_STORE_OUTSIDE_ALLOWED_ROOT"):
        JsonlTraceStore(
            outside / "trace.jsonl",
            data_root=tmp_path / "data",
            allowed_root=allowed,
        )
    target = allowed / "target.jsonl"
    target.touch(mode=0o600)
    link = allowed / "trace.jsonl"
    link.symlink_to(target)
    with pytest.raises(TraceStoreError, match="TRACE_STORE_SYMLINK_REJECTED"):
        JsonlTraceStore(
            link,
            data_root=tmp_path / "data",
            allowed_root=allowed,
        )


def test_store_enforces_configured_capacity(tmp_path: Path, identity_factory) -> None:
    runtime = _secure_runtime(tmp_path)
    store = JsonlTraceStore(
        runtime / "trace.jsonl",
        data_root=tmp_path / "data",
        allowed_root=runtime,
        max_bytes=64,
    )
    from trading_signals.paper_trace.engine import start_trace

    identity = identity_factory()
    result = start_trace(
        identity,
        accepted=True,
        observed_at=identity.decision_at,
    )
    with pytest.raises(TraceStoreError, match="TRACE_STORE_MAX_BYTES_EXCEEDED"):
        store.append(result.receipts)
    assert (runtime / "trace.jsonl").read_bytes() == b""


def test_ambiguous_entry_at_horizon_is_not_mislabeled_expired(
    identity_factory,
) -> None:
    identity = replace(identity_factory(), horizon_candles=1)
    started = start_trace(
        identity,
        accepted=True,
        observed_at=identity.decision_at,
    )
    candle = TraceCandle(
        symbol=identity.symbol,
        timeframe=identity.timeframe,
        open_at=identity.decision_at,
        close_at=datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
        open_price=99.0,
        high_price=111.0,
        low_price=94.0,
        close_price=101.0,
        market_source="synthetic",
    )
    result = advance_trace(
        identity,
        started.receipts,
        candle,
        observed_at=candle.close_at,
    )
    events = [receipt.event_type for receipt in result.receipts]
    assert ReceiptEventType.ENTRY_TOUCH_AMBIGUOUS in events
    assert ReceiptEventType.SIGNAL_EXPIRED_NOT_ACTIVATED not in events


def test_concurrent_writers_preserve_all_receipts_and_health(
    tmp_path: Path,
    identity_factory,
) -> None:
    runtime = _secure_runtime(tmp_path)
    path = runtime / "trace.jsonl"
    stores = [
        JsonlTraceStore(
            path,
            data_root=tmp_path / "data",
            allowed_root=runtime,
            max_bytes=1_048_576,
        )
        for _ in range(2)
    ]
    identities = [
        identity_factory(signal_id="concurrent-a"),
        identity_factory(signal_id="concurrent-b"),
    ]
    batches = [
        start_trace(
            identity,
            accepted=True,
            observed_at=identity.decision_at,
        ).receipts
        for identity in identities
    ]
    barrier = threading.Barrier(2)
    errors: list[Exception] = []

    def write(index: int) -> None:
        try:
            barrier.wait(timeout=2)
            stores[index].append(batches[index])
        except Exception as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    threads = [threading.Thread(target=write, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert not errors
    assert all(not thread.is_alive() for thread in threads)
    receipts = stores[0].read_all()
    assert len(receipts) == 6
    assert len({receipt.receipt_id for receipt in receipts}) == 6
    health = stores[0].health()
    assert health.status == "HEALTHY"
    assert health.trace_count == 2
    assert health.active_trace_count == 2
    assert health.size_bytes == path.stat().st_size
    assert health.max_bytes == 1_048_576
    assert health.last_receipt_id == receipts[-1].receipt_id
