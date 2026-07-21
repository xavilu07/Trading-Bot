from __future__ import annotations

from fastapi.testclient import TestClient

from trading_signals.interfaces.api.main import app


def test_qic_read_endpoints_handle_missing_runtime(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    response = client.get("/api/qic/control-center")

    assert response.status_code == 200
    assert response.json()["status"]["health"] == "UNKNOWN"
    assert response.json()["actions_enabled"] is False


def test_qic_mutation_endpoint_is_disabled_without_admin_auth() -> None:
    client = TestClient(app)

    response = client.post("/api/qic/proposals/p1/approve")

    assert response.status_code == 503
    assert "authentication" in response.json()["detail"]
