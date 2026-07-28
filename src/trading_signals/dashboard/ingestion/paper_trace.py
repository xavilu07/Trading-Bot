from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from trading_signals.dashboard.storage import (
    connect_read_only,
    connect_writer,
    finalize_writer,
    schema_is_current,
)
from trading_signals.paper_trace.state_machine import replay_receipts
from trading_signals.paper_trace.store import JsonlTraceStore


class PaperTraceProjectionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PaperTraceProjectionSummary:
    receipts_seen: int
    receipts_inserted: int
    traces_projected: int
    dry_run: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "receipts_seen": self.receipts_seen,
            "receipts_inserted": self.receipts_inserted,
            "traces_projected": self.traces_projected,
            "dry_run": self.dry_run,
        }


def project_paper_trace(
    *,
    source_path: Path,
    sqlite_path: Path,
    data_root: Path,
    dry_run: bool = False,
    projected_at: datetime | None = None,
) -> PaperTraceProjectionSummary:
    receipts = JsonlTraceStore(source_path, data_root=data_root).read_all()
    traces: dict[str, list[object]] = {}
    for receipt in receipts:
        traces.setdefault(receipt.trace_id, []).append(receipt)
    for trace_receipts in traces.values():
        replay_receipts(trace_receipts)  # validates chain and transitions before writes
    if dry_run:
        return PaperTraceProjectionSummary(len(receipts), 0, len(traces), True)

    now = (projected_at or datetime.now(tz=UTC)).astimezone(UTC).isoformat()
    connection = connect_writer(sqlite_path, data_root=data_root)
    committed = False
    try:
        if not schema_is_current(connection):
            raise PaperTraceProjectionError("READ_MODEL_SCHEMA_NOT_CURRENT")
        connection.execute("BEGIN IMMEDIATE")
        before = connection.total_changes
        for receipt in receipts:
            values = receipt.to_dict()
            connection.execute(
                """
                INSERT OR IGNORE INTO paper_trace_receipts(
                    receipt_id,receipt_hash,trace_id,event_type,event_version,
                    event_sequence,previous_receipt_id,occurred_at,observed_at,
                    signal_id,order_id,fill_id,position_id,candle_open_time,
                    timeframe,symbol,direction,price,quantity,evidence_id,
                    evidence_fingerprint,policy_id,policy_version,model_version,
                    source,reason_code,payload_json,created_at,projected_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    values["receipt_id"], values["receipt_hash"], values["trace_id"],
                    values["event_type"], values["event_version"], values["event_sequence"],
                    values["previous_receipt_id"], values["occurred_at"], values["observed_at"],
                    values["signal_id"], values["order_id"], values["fill_id"],
                    values["position_id"], values["candle_open_time"], values["timeframe"],
                    values["symbol"], values["direction"], values["price"], values["quantity"],
                    values["evidence_id"], values["evidence_fingerprint"], values["policy_id"],
                    values["policy_version"], values["model_version"], values["source"],
                    values["reason_code"], values["payload_json"], values["created_at"], now,
                ),
            )
            stored = connection.execute(
                "SELECT receipt_hash FROM paper_trace_receipts WHERE receipt_id=?",
                (receipt.receipt_id,),
            ).fetchone()
            if stored is None or str(stored[0]) != receipt.receipt_hash:
                raise PaperTraceProjectionError("READ_MODEL_RECEIPT_COLLISION")
        inserted = connection.total_changes - before
        for trace_id, trace_receipts in traces.items():
            state = replay_receipts(trace_receipts)
            last = trace_receipts[-1]
            connection.execute(
                """
                INSERT INTO paper_trace_states(
                    trace_id,signal_id,signal_state,order_state,position_state,
                    last_receipt_id,last_sequence,candles_before_entry,candles_after_entry,
                    last_candle_open_time,trace_blocked_reason,
                    policy_id,policy_version,model_version,
                    source,projected_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(trace_id) DO UPDATE SET
                    signal_state=excluded.signal_state,
                    order_state=excluded.order_state,
                    position_state=excluded.position_state,
                    last_receipt_id=excluded.last_receipt_id,
                    last_sequence=excluded.last_sequence,
                    candles_before_entry=excluded.candles_before_entry,
                    candles_after_entry=excluded.candles_after_entry,
                    last_candle_open_time=excluded.last_candle_open_time,
                    trace_blocked_reason=excluded.trace_blocked_reason,
                    projected_at=excluded.projected_at
                WHERE excluded.last_sequence > paper_trace_states.last_sequence
                """,
                (
                    trace_id, last.signal_id, state.signal.value, state.order.value,
                    state.position.value, state.last_receipt_id, state.last_sequence,
                    state.candles_before_entry, state.candles_after_entry,
                    state.last_candle_open_time, state.trace_blocked_reason,
                    last.policy_id, last.policy_version,
                    last.model_version, "PROSPECTIVE_PAPER_TRACE", now,
                ),
            )
        connection.execute("COMMIT")
        committed = True
        return PaperTraceProjectionSummary(len(receipts), inserted, len(traces), False)
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    finally:
        if committed:
            finalize_writer(connection)
        connection.close()


def inspect_projected_trace(sqlite_path: Path, trace_id: str) -> dict[str, object]:
    connection = connect_read_only(sqlite_path)
    try:
        state = connection.execute(
            "SELECT * FROM paper_trace_states WHERE trace_id=?",
            (trace_id,),
        ).fetchone()
        if state is None:
            raise PaperTraceProjectionError("TRACE_NOT_FOUND")
        receipts = connection.execute(
            "SELECT event_sequence,event_type,occurred_at,reason_code "
            "FROM paper_trace_receipts WHERE trace_id=? ORDER BY event_sequence",
            (trace_id,),
        ).fetchall()
        return {
            "trace": dict(state),
            "receipts": [dict(row) for row in receipts],
        }
    finally:
        connection.close()
