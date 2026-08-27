from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from trading_signals.dashboard.ingestion.paper_trace import project_paper_trace
from trading_signals.dashboard.storage import apply_migrations, connect_writer, integrity_check
from trading_signals.paper_trace.cli import main
from trading_signals.paper_trace.engine import start_trace
from trading_signals.paper_trace.store import JsonlTraceStore


def _store_with_trace(tmp_path: Path, identity_factory) -> tuple[Path, object]:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    runtime.chmod(0o700)
    path = runtime / "trace.jsonl"
    result = start_trace(
        identity_factory(),
        accepted=True,
        observed_at=identity_factory().decision_at,
    )
    JsonlTraceStore(path, data_root=tmp_path / "data").append(result.receipts)
    return path, result


def test_migration_0004_and_projection_are_idempotent(tmp_path: Path, identity_factory) -> None:
    source, result = _store_with_trace(tmp_path, identity_factory)
    database = tmp_path / "read-model/model.sqlite"
    writer = connect_writer(database, data_root=tmp_path / "data")
    try:
        assert apply_migrations(writer) == (1, 2, 3, 4)
    finally:
        writer.close()
    first = project_paper_trace(
        source_path=source,
        sqlite_path=database,
        data_root=tmp_path / "data",
    )
    reader = sqlite3.connect(database)
    try:
        state_before = reader.execute(
            "SELECT * FROM paper_trace_states"
        ).fetchone()
    finally:
        reader.close()
    second = project_paper_trace(
        source_path=source,
        sqlite_path=database,
        data_root=tmp_path / "data",
    )
    assert first.receipts_inserted == len(result.receipts)
    assert second.receipts_inserted == 0
    reader = sqlite3.connect(database)
    try:
        assert reader.execute("SELECT * FROM paper_trace_states").fetchone() == state_before
        assert reader.execute("SELECT COUNT(*) FROM paper_trace_receipts").fetchone()[0] == 3
        assert reader.execute("SELECT COUNT(*) FROM paper_trace_states").fetchone()[0] == 1
        assert integrity_check(reader) == ("ok",)
    finally:
        reader.close()


def test_project_dry_run_does_not_create_database(tmp_path: Path, identity_factory) -> None:
    source, result = _store_with_trace(tmp_path, identity_factory)
    database = tmp_path / "read-model/missing.sqlite"
    summary = project_paper_trace(
        source_path=source,
        sqlite_path=database,
        data_root=tmp_path / "data",
        dry_run=True,
    )
    assert summary.receipts_seen == len(result.receipts)
    assert not database.exists()


def test_cli_validate_inspect_replay_and_policy_are_read_only(
    tmp_path: Path,
    identity_factory,
    capsys,
) -> None:
    source, result = _store_with_trace(tmp_path, identity_factory)
    original = source.read_bytes()
    common = ["--store-path", str(source), "--data-root", str(tmp_path / "data")]
    for operation in ("trace-validate", "trace-store-health"):
        assert main([operation, *common]) == 0
        assert json.loads(capsys.readouterr().out)["status"] == "ok"
    for operation in ("trace-inspect", "trace-replay"):
        assert main([operation, *common, "--trace-id", result.trace_id]) == 0
        assert json.loads(capsys.readouterr().out)["status"] == "ok"
    assert main(["trace-policy"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
    assert source.read_bytes() == original


def test_cli_synthetic_dry_run_creates_nothing(tmp_path: Path, capsys) -> None:
    store = tmp_path / "runtime/trace.jsonl"
    assert main(["trace-simulate", "--dry-run"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["result"]["state"]["position"] == "CLOSED_WIN"
    assert not store.exists()


def test_cli_errors_are_sanitized(tmp_path: Path, capsys) -> None:
    assert main(["trace-validate"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"status": "error", "code": "TRACE_COMMAND_FAILED"}
    assert "/root/" not in json.dumps(payload)
