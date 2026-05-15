from fastapi.testclient import TestClient

from trading_signals.interfaces.api.routes import ai
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


def test_dashboard_summary_endpoint_handles_missing_files(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    response = client.get("/dashboard/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["files"]["paper_trades"]["state"] == "missing"
    assert data["files"]["experimental_signals"]["state"] == "missing"
    assert data["last_cycle"]["status"] == "missing"
    assert data["paper_stats"]["trades_total"] == 0


def test_ai_chat_general_question_does_not_use_bot_context(monkeypatch) -> None:
    prompts = []

    def fake_generate(prompt: str) -> str:
        prompts.append(prompt)
        return "Hola, ¿en qué puedo ayudarte?"

    monkeypatch.setattr(ai, "_generate_gemini_response", fake_generate)
    client = TestClient(app)

    response = client.post("/ai/chat", json={"message": "hola"})

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Hola, ¿en qué puedo ayudarte?"
    assert data["used_context"] is False
    assert "Contexto real del bot" not in prompts[0]


def test_ai_chat_trading_question_uses_real_bot_context(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    paper_dir = data_dir / "paper_trading"
    paper_dir.mkdir(parents=True)
    (paper_dir / "trades.csv").write_text(
        "\n".join(
            [
                "symbol,direction,status,result_r,opened_at,updated_at,entry_or_rejection_reason",
                "BTCUSDT,long,tp_hit,1.0,2026-05-01T00:00:00+00:00,2026-05-01T01:00:00+00:00,paper_tradeable",
                "ETHUSDT,short,sl_hit,-1.0,2026-05-02T00:00:00+00:00,2026-05-02T01:00:00+00:00,directional_confluence_failed",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    prompts = []

    def fake_generate(prompt: str) -> str:
        prompts.append(prompt)
        return "Con estos datos, los shorts van peor que los longs."

    monkeypatch.setattr(ai, "_generate_gemini_response", fake_generate)
    client = TestClient(app)

    response = client.post("/ai/chat", json={"message": "¿los shorts están funcionando peor?"})

    assert response.status_code == 200
    data = response.json()
    assert data["used_context"] is True
    assert "Contexto real del bot" in prompts[0]
    assert '"direction_performance"' in prompts[0]
    assert '"short"' in prompts[0]
    assert '"total_r": -1.0' in prompts[0]
