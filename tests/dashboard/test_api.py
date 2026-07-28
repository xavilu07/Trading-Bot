from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from trading_signals.interfaces.dashboard_api.main import create_app
from trading_signals.interfaces.dashboard_api.settings import DashboardSettings


def _settings(root: Path) -> DashboardSettings:
    return DashboardSettings(
        bot_root=root,
        data_root=root / "data",
        reports_root=root / "reports",
        runtime_root=root / "runtime",
    )


def _heartbeat(path: Path, *, finished_at: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
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
        ),
        encoding="utf-8",
    )


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


def test_health_is_read_only_and_has_no_performance_metrics(tmp_path: Path) -> None:
    response = _get(create_app(_settings(tmp_path)), "/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["read_only"] is True
    assert payload["operational_controls_enabled"] is False
    assert payload["performance_metrics_enabled"] is False
    assert payload["api"]["status"] == "HEALTHY"
    serialized = json.dumps(payload).lower()
    for forbidden in ("win_rate", "profit_factor", "total_r", "drawdown", "equity_curve"):
        assert forbidden not in serialized


def test_system_reads_allowlisted_heartbeat_fields_without_exposing_paths(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    _heartbeat(tmp_path / "data/runtime/scheduler_heartbeat.json", finished_at=now)
    response = _get(create_app(_settings(tmp_path)), "/api/v1/system")
    assert response.status_code == 200
    payload = response.json()
    assert payload["scheduler"]["status"] == "HEALTHY"
    assert payload["strategy"]["git_commit_sha"] == "a" * 40
    assert payload["last_cycle"]["cycle_number"] == 42
    assert payload["outcomes_canonical"] is False
    assert str(tmp_path) not in json.dumps(payload)


def test_system_redacts_sensitive_or_path_like_identity_values(tmp_path: Path) -> None:
    heartbeat = tmp_path / "data/runtime/scheduler_heartbeat.json"
    _heartbeat(heartbeat, finished_at=datetime.now(timezone.utc))
    payload = json.loads(heartbeat.read_text(encoding="utf-8"))
    payload["deployment_id"] = "/root/private/release"
    payload["experiment_id"] = "token=must-not-leak"
    heartbeat.write_text(json.dumps(payload), encoding="utf-8")
    response = _get(create_app(_settings(tmp_path)), "/api/v1/system")
    serialized = json.dumps(response.json())
    assert response.status_code == 200
    assert "/root/private/release" not in serialized
    assert "must-not-leak" not in serialized
    assert response.json()["strategy"]["deployment_id"] is None
    assert response.json()["strategy"]["experiment_id"] is None


def test_missing_and_stale_heartbeat_are_not_reported_healthy(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    missing = _get(app, "/api/v1/system").json()
    assert missing["scheduler"]["status"] == "NO_EVIDENCE"
    assert missing["scheduler"]["classification"] == "UNAVAILABLE"

    heartbeat = tmp_path / "data/runtime/scheduler_heartbeat.json"
    _heartbeat(heartbeat, finished_at=datetime.now(timezone.utc) - timedelta(hours=2))
    old = datetime.now(timezone.utc).timestamp() - 7200
    os.utime(heartbeat, (old, old))
    stale = _get(app, "/api/v1/system").json()
    assert stale["scheduler"]["status"] == "STALE_DATA"
    assert stale["scheduler"]["classification"] == "STALE"


def test_metadata_is_redacted_and_marks_noncanonical_sources(tmp_path: Path) -> None:
    (tmp_path / "data/risk_plans").mkdir(parents=True)
    response = _get(create_app(_settings(tmp_path)), "/api/v1/metadata/freshness")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 32
    by_name = {item["source_id"]: item for item in payload["items"]}
    assert by_name["signal_activity_active"]["availability"] == "NOT_CONFIGURED"
    assert by_name["paper_trades"]["canonicality"] == "MIXED"
    assert by_name["paper_trades"]["classification"] == "UNAVAILABLE"
    assert by_name["binance_market"]["availability"] == "DISABLED"
    assert by_name["risk_plans"]["availability"] == "AVAILABLE"
    assert by_name["risk_plans"]["evidence"]["status"] == "NO_EVIDENCE"
    assert by_name["risk_plans"]["classification"] == "NO_EVIDENCE"
    serialized = json.dumps(payload)
    assert str(tmp_path) not in serialized
    assert "/root/" not in serialized


def test_requests_do_not_write_inside_data_root(tmp_path: Path) -> None:
    heartbeat = tmp_path / "data/runtime/scheduler_heartbeat.json"
    _heartbeat(heartbeat, finished_at=datetime.now(timezone.utc))
    before = _tree_hashes(tmp_path / "data")
    app = create_app(_settings(tmp_path))
    assert _get(app, "/api/v1/health").status_code == 200
    assert _get(app, "/api/v1/system").status_code == 200
    assert _get(app, "/api/v1/metadata/freshness").status_code == 200
    assert _tree_hashes(tmp_path / "data") == before
