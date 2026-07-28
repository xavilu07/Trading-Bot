from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from trading_signals.dashboard.ingestion.projector import (
    ProjectorConfig,
    inspect_read_model,
    migrate_read_model,
    project_once,
    rebuild_read_model,
)
from trading_signals.dashboard.storage import connect_read_only, integrity_check


def _manifest() -> Path:
    return Path("src/trading_signals/dashboard/ingestion/sources.v1.json").resolve()


def _config(root: Path, *, selected_sources=None) -> ProjectorConfig:
    data = root / "data"
    runtime = root / "runtime"
    return ProjectorConfig(
        data_root=data,
        sqlite_path=runtime / "read-model.sqlite",
        manifest_path=_manifest(),
        variables={
            "bot_root": root,
            "data_root": data,
            "reports_root": root / "reports",
            "runtime_root": runtime,
            "active_signal_log": None,
            "scheduler_lock": None,
        },
        selected_sources=selected_sources
        or ("scheduler_heartbeat", "scan_runs", "trade_signals"),
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _heartbeat(*, finished_at: datetime | None = None) -> dict[str, object]:
    finished = finished_at or datetime.now(timezone.utc)
    return {
        "status": "ok",
        "cycle_number": 7,
        "last_cycle_started_at": (finished - timedelta(seconds=25)).isoformat(),
        "last_cycle_finished_at": finished.isoformat(),
        "last_cycle_duration_seconds": 25,
        "last_error": None,
        "git_commit_sha": "a" * 40,
        "deployment_id": "fixture",
        "config_hash": "b" * 64,
        "selected_engine": "legacy",
        "strategy_version": "v1",
        "policy_version": "v1",
        "experiment_id": "none",
    }


def _cycle(identifier: str = "run_one") -> dict[str, object]:
    return {
        "id": identifier,
        "started_at": "2026-07-28T10:00:00+00:00",
        "finished_at": "2026-07-28T10:00:25+00:00",
        "status": "completed",
        "symbols_total": 1,
        "symbols_processed": 1,
        "signals_emitted": 0,
        "signals_rejected": 1,
        "errors_count": 0,
        "config": {"strategy_id": "legacy", "strategy_version": "v1"},
    }


def _signal(identifier: str | None = "sig_one") -> dict[str, object]:
    payload: dict[str, object] = {
        "scan_run_id": "run_one",
        "evaluation_id": "eval_one",
        "strategy_id": "legacy",
        "strategy_version": "v1",
        "symbol": "BTCUSDT",
        "decision": "no_trade",
        "status": "rejected",
        "entry_timeframe": "1h",
        "created_at": "2026-07-28T10:00:20+00:00",
        "accepted": False,
        "public_published": False,
        "universe": "rejected",
        "lifecycle_reason": "quality_gate",
        "git_commit_sha": "a" * 40,
        "config_hash": "b" * 64,
        "deployment_id": "fixture",
        "selected_engine": "legacy",
        "policy_version": "v1",
        "experiment_id": "none",
        "secret": "must-not-be-stored",
    }
    if identifier is not None:
        payload["id"] = identifier
    return payload


def _fixtures(root: Path) -> None:
    _write_json(root / "data/runtime/scheduler_heartbeat.json", _heartbeat())
    _write_json(root / "data/scan_runs/2026-07-28/run_one.json", _cycle())
    _write_json(root / "data/trade_signals/2026-07-28/sig_one.json", _signal())


def _source_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_projection_is_idempotent_and_uses_real_keys(tmp_path: Path) -> None:
    _fixtures(tmp_path)
    config = _config(tmp_path)
    migrate_read_model(config)
    first = project_once(config)
    second = project_once(config)
    assert first.totals == second.totals
    connection = connect_read_only(config.sqlite_path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM source_metadata").fetchone()[0] == 32
        assert connection.execute("SELECT COUNT(*) FROM system_snapshots").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM cycles").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 1
        cycle = connection.execute("SELECT cycle_id FROM cycles").fetchone()
        signal = connection.execute(
            "SELECT signal_id, observation_id, cycle_id, rejected, accepted FROM signals"
        ).fetchone()
        assert cycle["cycle_id"] == "run_one"
        assert tuple(signal) == ("sig_one", None, "run_one", 1, 0)
    finally:
        connection.close()


def test_duplicate_signal_id_and_source_duplicates_do_not_duplicate_rows(tmp_path: Path) -> None:
    _fixtures(tmp_path)
    _write_json(tmp_path / "data/trade_signals/2026-07-28/duplicate.json", _signal())
    config = _config(tmp_path)
    migrate_read_model(config)
    summary = project_once(config)
    connection = connect_read_only(config.sqlite_path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 1
    finally:
        connection.close()
    signal_result = next(item for item in summary.sources if item.source == "trade_signals")
    assert signal_result.records_seen == 2
    assert signal_result.records_written == 2


def test_missing_signal_id_uses_stable_namespaced_projection_key(tmp_path: Path) -> None:
    _write_json(tmp_path / "data/trade_signals/2026-07-28/no_id.json", _signal(None))
    config = _config(tmp_path, selected_sources=("trade_signals",))
    migrate_read_model(config)
    project_once(config)
    connection = connect_read_only(config.sqlite_path)
    try:
        first = connection.execute("SELECT projection_key, signal_id FROM signals").fetchone()
    finally:
        connection.close()
    project_once(config)
    connection = connect_read_only(config.sqlite_path)
    try:
        rows = tuple(connection.execute("SELECT projection_key, signal_id FROM signals"))
        assert len(rows) == 1
        assert rows[0]["projection_key"] == first["projection_key"]
        assert rows[0]["signal_id"] is None
    finally:
        connection.close()


def test_cycle_without_real_id_is_skipped_not_invented(tmp_path: Path) -> None:
    invalid = _cycle()
    invalid.pop("id")
    _write_json(tmp_path / "data/scan_runs/2026-07-28/invalid.json", invalid)
    config = _config(tmp_path, selected_sources=("scan_runs",))
    migrate_read_model(config)
    summary = project_once(config)
    result = summary.sources[0]
    assert result.status == "failed"
    assert result.records_skipped == 1
    connection = connect_read_only(config.sqlite_path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM cycles").fetchone()[0] == 0
        checkpoint = connection.execute(
            "SELECT completed FROM ingestion_checkpoints WHERE logical_source_name='scan_runs'"
        ).fetchone()
        assert checkpoint is None
    finally:
        connection.close()


def test_corrupt_heartbeat_preserves_previous_projection_and_success_timestamp(tmp_path: Path) -> None:
    heartbeat_path = tmp_path / "data/runtime/scheduler_heartbeat.json"
    _write_json(heartbeat_path, _heartbeat())
    config = _config(tmp_path, selected_sources=("scheduler_heartbeat",))
    migrate_read_model(config)
    project_once(config)
    connection = connect_read_only(config.sqlite_path)
    try:
        before = connection.execute(
            "SELECT last_success_at, source_fingerprint FROM source_metadata "
            "WHERE logical_source_name='scheduler_heartbeat'"
        ).fetchone()
    finally:
        connection.close()
    heartbeat_path.write_text('{"status":', encoding="utf-8")
    result = project_once(config).sources[0]
    assert result.status == "failed"
    assert result.error_code == "SOURCE_CORRUPT"
    connection = connect_read_only(config.sqlite_path)
    try:
        after = connection.execute(
            "SELECT last_success_at, source_fingerprint, last_error_code FROM source_metadata "
            "WHERE logical_source_name='scheduler_heartbeat'"
        ).fetchone()
        assert connection.execute("SELECT COUNT(*) FROM system_snapshots").fetchone()[0] == 1
        assert after["last_success_at"] == before["last_success_at"]
        assert after["source_fingerprint"] == before["source_fingerprint"]
        assert after["last_error_code"] == "SOURCE_CORRUPT"
    finally:
        connection.close()


def test_corrupt_file_in_set_preserves_last_success_and_other_sources_continue(tmp_path: Path) -> None:
    _write_json(tmp_path / "data/scan_runs/2026-07-28/valid.json", _cycle())
    _write_json(tmp_path / "data/trade_signals/2026-07-28/signal.json", _signal())
    config = _config(tmp_path, selected_sources=("scan_runs", "trade_signals"))
    migrate_read_model(config)
    project_once(config)
    connection = connect_read_only(config.sqlite_path)
    try:
        before = connection.execute(
            "SELECT last_success_at, source_fingerprint FROM source_metadata "
            "WHERE logical_source_name='scan_runs'"
        ).fetchone()
    finally:
        connection.close()
    corrupt = tmp_path / "data/scan_runs/2026-07-28/corrupt.json"
    corrupt.write_text('{"id":', encoding="utf-8")
    _write_json(tmp_path / "data/trade_signals/2026-07-28/second.json", _signal("sig_two"))
    results = project_once(config).sources
    scan_result = next(item for item in results if item.source == "scan_runs")
    signal_result = next(item for item in results if item.source == "trade_signals")
    assert scan_result.status == "failed"
    assert scan_result.records_written == 0
    assert scan_result.records_skipped == 1
    assert signal_result.status == "success"
    connection = connect_read_only(config.sqlite_path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM cycles").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 2
        metadata = connection.execute(
            "SELECT last_success_at, source_fingerprint, last_error_code, record_count "
            "FROM source_metadata "
            "WHERE logical_source_name='scan_runs'"
        ).fetchone()
        assert metadata["last_error_code"] == "SOURCE_CORRUPT"
        assert metadata["record_count"] == 1
        assert metadata["last_success_at"] == before["last_success_at"]
        assert metadata["source_fingerprint"] == before["source_fingerprint"]
    finally:
        connection.close()


def test_sanitized_raw_payload_drops_secrets_and_paths(tmp_path: Path) -> None:
    payload = _signal()
    payload["lifecycle_reason"] = "/root/private/reason"
    _write_json(tmp_path / "data/trade_signals/2026-07-28/signal.json", payload)
    config = _config(tmp_path, selected_sources=("trade_signals",))
    migrate_read_model(config)
    project_once(config)
    connection = connect_read_only(config.sqlite_path)
    try:
        row = connection.execute(
            "SELECT rejection_reason, raw_payload_json, source_record_identity FROM signals"
        ).fetchone()
        assert row["rejection_reason"] is None
        assert "must-not-be-stored" not in row["raw_payload_json"]
        assert "/root/" not in row["raw_payload_json"]
        assert len(row["source_record_identity"]) == 64
    finally:
        connection.close()


def test_rebuild_is_atomic_integral_and_does_not_modify_sources(tmp_path: Path) -> None:
    _fixtures(tmp_path)
    config = _config(tmp_path)
    sources_before = _source_hashes(tmp_path / "data")
    summary = rebuild_read_model(config)
    assert summary.totals["records_skipped"] == 0
    assert _source_hashes(tmp_path / "data") == sources_before
    assert inspect_read_model(config.sqlite_path)["status"] == "ready"
    connection = connect_read_only(config.sqlite_path)
    try:
        assert integrity_check(connection) == ("ok",)
    finally:
        connection.close()
    assert not Path(f"{config.sqlite_path}-wal").exists()
    assert not Path(f"{config.sqlite_path}-shm").exists()
    assert not tuple(config.sqlite_path.parent.glob(".*.rebuild-*.sqlite*"))


def test_rebuild_failure_before_replace_keeps_previous_database(tmp_path: Path) -> None:
    _fixtures(tmp_path)
    config = _config(tmp_path)
    rebuild_read_model(config)
    before = config.sqlite_path.read_bytes()

    def fail(_temporary: Path, _target: Path) -> None:
        raise RuntimeError("injected failure")

    with pytest.raises(RuntimeError, match="injected failure"):
        rebuild_read_model(config, before_replace=fail)
    assert config.sqlite_path.read_bytes() == before
    assert inspect_read_model(config.sqlite_path)["status"] == "ready"
    assert not tuple(config.sqlite_path.parent.glob(".*.rebuild-*.sqlite*"))


def test_project_once_requires_explicit_migration_and_does_not_create_database(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with pytest.raises(RuntimeError, match="does not exist"):
        project_once(config)
    assert not config.sqlite_path.exists()
