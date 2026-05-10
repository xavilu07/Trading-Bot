from fastapi.testclient import TestClient

from trading_signals.interfaces.api.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_frontend_index_served() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "Trading Signals Control Room" in response.text
