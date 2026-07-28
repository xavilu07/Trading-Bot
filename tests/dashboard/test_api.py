from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from trading_signals.dashboard.ingestion.projector import (
    ProjectorConfig,
    migrate_read_model,
    project_once,
)
from trading_signals.interfaces.dashboard_api.main import create_app
from trading_signals.interfaces.dashboard_api.settings import DashboardSettings


def _manifest() -> Path:
    return Path("src/trading_signals/dashboard/ingestion/sources.v1.json").resolve()


def _settings(root: Path) -> DashboardSettings:
    return DashboardSettings(
        bot_root=root,
        data_root=root / "data",
        reports_root=root / "reports",
        runtime_root=root / "runtime",
        read_model_path=root / "runtime/read-model.sqlite",
    )


def _config(root: Path) -> ProjectorConfig:
    settings = _settings(root)
    return ProjectorConfig(
        data_root=settings.data_root,
        sqlite_path=settings.resolved_read_model_path(),
        manifest_path=_manifest(),
        variables=settings.source_variables(),
    )


def _heartbeat(path: Path, *, finished_at: datetime, overrides: dict[str, object] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "status": "ok",
        "cycle_number": 42,
        "last_cycle_started_at": (finished_at - timedelta(seconds=20)).isoformat(),
        "last_cycle_finished_at": finished_at.isoformat(),
        "last_cycle_duration_seconds": 20,
        "last_error": None,
        "git_commit_sha": "a" * 40,
        "deployment_id": "fixture-deployment",
        "config_hash": "b" * 64,
        "selected_engine": "legacy",
        "strategy_version": "v1",
        "policy_version": "v1",
        "experiment_id": "none",
    }
    payload.update(overrides or {})
    path.write_text(json.dumps(payload), encoding="utf-8")


def _cycle(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "id": "run_fixture",
                "started_at": "2026-07-28T11:00:00+00:00",
                "finished_at": "2026-07-28T11:00:20+00:00",
                "status": "completed",
                "symbols_total": 1,
                "symbols_processed": 1,
                "signals_emitted": 0,
                "signals_rejected": 1,
                "errors_count": 0,
                "config": {"strategy_id": "legacy", "strategy_version": "v1"},
            }
        ),
        encoding="utf-8",
    )


def _build_read_model(root: Path, *, heartbeat_overrides: dict[str, object] | None = None) -> Path:
    heartbeat = root / "data/runtime/scheduler_heartbeat.json"
    _heartbeat(heartbeat, finished_at=datetime.now(timezone.utc), overrides=heartbeat_overrides)
    _cycle(root / "data/scan_runs/2026-07-28/run_fixture.json")
    config = _config(root)
    assert migrate_read_model(config) == (1,)
    summary = project_once(config)
    assert summary.totals["records_skipped"] == 0
    return config.sqlite_path


def _tree_hashes(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def _get(app: object, path: str) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://dashboard.test") as client:
            return await client.get(path)

    return asyncio.run(request())


def test_api_exposes_only_foundation_get_routes(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    route_methods = {
        (route.path, method)
        for route in app.routes
        if route.path.startswith("/api/v1")
        for method in route.methods
    }
    assert route_methods == {
        ("/api/v1/health", "GET"),
        ("/api/v1/system", "GET"),
        ("/api/v1/metadata/freshness", "GET"),
    }


def test_missing_database_is_clear_and_request_does_not_create_it(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    target = settings.resolved_read_model_path()
    response = _get(create_app(settings), "/api/v1/health")
    assert response.status_code == 200
    assert response.json()["read_model"]["status"] == "NO_EVIDENCE"
    assert response.json()["read_model"]["classification"] == "UNAVAILABLE"
    assert not target.exists()
    assert not target.parent.exists()


def test_health_is_read_only_and_has_no_performance_metrics(tmp_path: Path) -> None:
    _build_read_model(tmp_path)
    response = _get(create_app(_settings(tmp_path)), "/api/v1/health")
    payload = response.json()
    assert response.status_code == 200
    assert payload["read_only"] is True
    assert payload["operational_controls_enabled"] is False
    assert payload["performance_metrics_enabled"] is False
    assert payload["read_model"]["status"] == "HEALTHY"
    serialized = json.dumps(payload).lower()
    for forbidden in ("win_rate", "profit_factor", "total_r", "drawdown", "equity_curve"):
        assert forbidden not in serialized


def test_system_reads_projected_fields_without_exposing_paths(tmp_path: Path) -> None:
    _build_read_model(tmp_path)
    response = _get(create_app(_settings(tmp_path)), "/api/v1/system")
    payload = response.json()
    assert response.status_code == 200
    assert payload["scheduler"]["status"] == "HEALTHY"
    assert payload["strategy"]["git_commit_sha"] == "a" * 40
    assert payload["last_cycle"]["cycle_number"] == 42
    assert payload["outcomes_canonical"] is False
    assert str(tmp_path) not in json.dumps(payload)


def test_system_redacts_sensitive_or_path_like_identity_values(tmp_path: Path) -> None:
    _build_read_model(
        tmp_path,
        heartbeat_overrides={
            "deployment_id": "/root/private/release",
            "experiment_id": "token=must-not-leak",
        },
    )
    response = _get(create_app(_settings(tmp_path)), "/api/v1/system")
    serialized = json.dumps(response.json())
    assert response.status_code == 200
    assert "/root/private/release" not in serialized
    assert "must-not-leak" not in serialized
    assert response.json()["strategy"]["deployment_id"] is None
    assert response.json()["strategy"]["experiment_id"] is None


def test_corrupt_and_unmigrated_databases_degrade_without_mutation(tmp_path: Path) -> None:
    corrupt = tmp_path / "runtime/read-model.sqlite"
    corrupt.parent.mkdir(parents=True)
    corrupt.write_bytes(b"not a sqlite database")
    before = corrupt.read_bytes()
    response = _get(create_app(_settings(tmp_path)), "/api/v1/health")
    assert response.json()["read_model"]["status"] == "DEGRADED"
    assert corrupt.read_bytes() == before

    corrupt.unlink()
    connection = sqlite3.connect(corrupt)
    connection.close()
    before = corrupt.read_bytes()
    response = _get(create_app(_settings(tmp_path)), "/api/v1/health")
    assert response.json()["read_model"]["status"] == "DEGRADED"
    assert corrupt.read_bytes() == before


def test_metadata_comes_from_read_model_and_is_redacted(tmp_path: Path) -> None:
    (tmp_path / "data/risk_plans").mkdir(parents=True)
    _build_read_model(tmp_path)
    response = _get(create_app(_settings(tmp_path)), "/api/v1/metadata/freshness")
    payload = response.json()
    assert response.status_code == 200
    assert len(payload["items"]) == 32
    by_name = {item["source_id"]: item for item in payload["items"]}
    assert by_name["signal_activity_active"]["availability"] == "NOT_CONFIGURED"
    assert by_name["paper_trades"]["canonicality"] == "MIXED"
    assert by_name["binance_market"]["availability"] == "DISABLED"
    assert by_name["scheduler_heartbeat"]["evidence"]["status"] == "HEALTHY"
    assert by_name["trade_signals"]["availability"] == "MISSING"
    assert by_name["risk_plans"]["availability"] == "AVAILABLE"
    assert by_name["risk_plans"]["evidence"]["status"] == "NO_EVIDENCE"
    serialized = json.dumps(payload)
    assert str(tmp_path) not in serialized
    assert "/root/" not in serialized


def test_stale_projected_heartbeat_remains_stale(tmp_path: Path) -> None:
    heartbeat = tmp_path / "data/runtime/scheduler_heartbeat.json"
    _heartbeat(heartbeat, finished_at=datetime.now(timezone.utc) - timedelta(hours=2))
    old = datetime.now(timezone.utc).timestamp() - 7200
    os.utime(heartbeat, (old, old))
    config = _config(tmp_path)
    migrate_read_model(config)
    project_once(config)
    payload = _get(create_app(_settings(tmp_path)), "/api/v1/system").json()
    assert payload["scheduler"]["status"] == "STALE_DATA"


def test_requests_write_neither_sources_nor_sqlite(tmp_path: Path) -> None:
    database = _build_read_model(tmp_path)
    source_before = _tree_hashes(tmp_path / "data")
    database_before = database.read_bytes()
    wal_before = Path(f"{database}-wal").exists()
    shm_before = Path(f"{database}-shm").exists()
    app = create_app(_settings(tmp_path))
    assert _get(app, "/api/v1/health").status_code == 200
    assert _get(app, "/api/v1/system").status_code == 200
    assert _get(app, "/api/v1/metadata/freshness").status_code == 200
    assert _tree_hashes(tmp_path / "data") == source_before
    assert database.read_bytes() == database_before
    assert Path(f"{database}-wal").exists() is wal_before
    assert Path(f"{database}-shm").exists() is shm_before
