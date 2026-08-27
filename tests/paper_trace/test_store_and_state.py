from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from trading_signals.paper_trace.contracts import ReceiptEventType
from trading_signals.paper_trace.engine import start_trace
from trading_signals.paper_trace.state_machine import (
    TraceState,
    TraceTransitionError,
    apply_receipt,
    replay_receipts,
)
from trading_signals.paper_trace.store import JsonlTraceStore, TraceStoreError


def test_jsonl_store_is_append_only_durable_and_idempotent(tmp_path, identity_factory) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    runtime.chmod(0o700)
    store = JsonlTraceStore(runtime / "trace.jsonl", data_root=tmp_path / "data")
    result = start_trace(
        identity_factory(),
        accepted=True,
        observed_at=identity_factory().decision_at,
    )
    assert store.append(result.receipts) == 3
    before = (runtime / "trace.jsonl").read_bytes()
    assert store.append(result.receipts) == 0
    assert (runtime / "trace.jsonl").read_bytes() == before
    assert store.health().status == "HEALTHY"
    assert (runtime / "trace.jsonl").stat().st_mode & 0o777 == 0o600


def test_store_detects_truncation_and_tampering(tmp_path, identity_factory) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    runtime.chmod(0o700)
    path = runtime / "trace.jsonl"
    store = JsonlTraceStore(path, data_root=tmp_path / "data")
    result = start_trace(
        identity_factory(),
        accepted=True,
        observed_at=identity_factory().decision_at,
    )
    store.append(result.receipts)
    path.write_bytes(path.read_bytes()[:-1])
    with pytest.raises(TraceStoreError, match="TRACE_STORE_TRUNCATED_LINE"):
        store.read_all()

    path.write_text(
        json.dumps({**result.receipts[0].to_dict(), "reason_code": "tampered"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(TraceStoreError, match="TRACE_STORE_INVALID_RECEIPT_LINE"):
        store.read_all()


def test_store_rejects_data_root_relative_and_dangerous_paths(tmp_path) -> None:
    (tmp_path / "data").mkdir()
    with pytest.raises(TraceStoreError, match="TRACE_STORE_DATA_ROOT_REJECTED"):
        JsonlTraceStore(tmp_path / "data/trace.jsonl", data_root=tmp_path / "data")
    with pytest.raises(TraceStoreError, match="TRACE_STORE_PATH_UNSAFE"):
        JsonlTraceStore(Path("trace.jsonl"), data_root=tmp_path / "data")


def test_store_detects_broken_chain(tmp_path, identity_factory) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    runtime.chmod(0o700)
    store = JsonlTraceStore(runtime / "trace.jsonl", data_root=tmp_path / "data")
    result = start_trace(
        identity_factory(),
        accepted=True,
        observed_at=identity_factory().decision_at,
    )
    with pytest.raises(TraceStoreError, match="TRACE_STORE_CHAIN_BROKEN"):
        store.append((result.receipts[1],))


def test_state_machine_rejects_fill_without_activation(identity_factory) -> None:
    receipts = start_trace(
        identity_factory(),
        accepted=True,
        observed_at=identity_factory().decision_at,
    ).receipts
    invalid = replace(
        receipts[-1],
        event_type=ReceiptEventType.SIMULATED_FILL_CREATED,
        event_sequence=1,
        previous_receipt_id=None,
    )
    with pytest.raises(TraceTransitionError):
        apply_receipt(TraceState(), invalid)


def test_state_machine_rejects_close_before_position_open(identity_factory) -> None:
    receipts = start_trace(
        identity_factory(),
        accepted=True,
        observed_at=identity_factory().decision_at,
    ).receipts
    invalid = replace(
        receipts[-1],
        event_type=ReceiptEventType.PAPER_POSITION_CLOSED,
        reason_code="STOP_FIRST",
    )
    state = replay_receipts(receipts[:-1])
    with pytest.raises(TraceTransitionError, match="POSITION_CLOSE_INVALID"):
        apply_receipt(state, invalid)


def test_replay_is_deterministic_and_exact_duplicate_is_idempotent(identity_factory) -> None:
    receipts = start_trace(
        identity_factory(),
        accepted=True,
        observed_at=identity_factory().decision_at,
    ).receipts
    assert replay_receipts(receipts) == replay_receipts((*receipts, receipts[-1]))
