from __future__ import annotations

import json
from pathlib import Path

from trading_signals.agents.proposal_store import save_proposals
from trading_signals.agents.telegram_approval import build_qic_command_response, process_telegram_update
from trading_signals.risk.trading_pause import is_trading_paused, pause_trading


def test_unauthorized_chat_is_rejected(tmp_path: Path) -> None:
    update = {"update_id": 1, "message": {"chat": {"id": 999}, "text": "/status"}}

    result = process_telegram_update(update, authorized_chat_ids=["123"], qic_output_path=tmp_path / "reports")

    assert result["handled"] is False
    assert result["reason"] == "unauthorized_chat"


def test_command_status_uses_reports(tmp_path: Path) -> None:
    reports = tmp_path / "reports" / "qic"
    reports.mkdir(parents=True)
    (reports / "autonomous_run.json").write_text(json.dumps({"status": "completed", "run_id": "run_1"}), encoding="utf-8")
    (reports / "system_health.json").write_text(json.dumps({"autonomous_score": 82}), encoding="utf-8")

    text = build_qic_command_response("/status", proposal_store_path=tmp_path / "proposals.jsonl", qic_output_path=reports)

    assert "completed" in text
    assert "82" in text


def test_callback_is_idempotent_and_records_actor(tmp_path: Path) -> None:
    proposal_store = tmp_path / "data" / "agent_proposals" / "proposals.jsonl"
    save_proposals([{"id": "p1", "status": "pending", "action": "PROPOSE_IMPLEMENTATION"}], proposal_store)
    update = {
        "update_id": 4,
        "callback_query": {
            "id": "callback-1",
            "data": "agent:approve:p1",
            "from": {"id": 123},
            "message": {"chat": {"id": 123}},
        },
    }
    callback_history = tmp_path / "data" / "qic" / "callbacks.jsonl"

    first = process_telegram_update(update, proposal_store_path=proposal_store, knowledge_base_path=tmp_path / "kb.json", qic_output_path=tmp_path / "reports", authorized_chat_ids=["123"], callback_history_path=callback_history)
    second = process_telegram_update(update, proposal_store_path=proposal_store, knowledge_base_path=tmp_path / "kb.json", qic_output_path=tmp_path / "reports", authorized_chat_ids=["123"], callback_history_path=callback_history)

    assert first["status"] == "approved_for_implementation_review"
    assert first["actor"] == "123"
    assert second["idempotent"] is True
    assert second["reason"] == "duplicate_callback_ignored"


def test_trading_status_reports_not_paused_by_default(tmp_path: Path) -> None:
    pause_path = tmp_path / "trading_paused.json"

    text = build_qic_command_response("/trading_status", qic_output_path=tmp_path / "reports", pause_path=pause_path)

    assert "no pausado" in text.lower() or "activo" in text.lower()


def test_pause_trading_command_pauses_and_records_actor(tmp_path: Path) -> None:
    pause_path = tmp_path / "trading_paused.json"

    text = build_qic_command_response("/pause_trading", qic_output_path=tmp_path / "reports", actor="42", pause_path=pause_path)

    assert "pausado" in text.lower()
    state = is_trading_paused(pause_path)
    assert state["paused"] is True
    assert state["details"]["actor"] == "42"
    assert state["resume_requires"] == "manual"


def test_pause_trading_command_is_idempotent(tmp_path: Path) -> None:
    pause_path = tmp_path / "trading_paused.json"
    pause_trading(reason="kill_switch", details={}, path=pause_path)

    text = build_qic_command_response("/pause_trading", qic_output_path=tmp_path / "reports", actor="42", pause_path=pause_path)

    assert "ya estaba pausado" in text.lower()
    state = is_trading_paused(pause_path)
    assert state["reason"] == "kill_switch"


def test_resume_trading_command_clears_pause_and_records_actor(tmp_path: Path) -> None:
    pause_path = tmp_path / "trading_paused.json"
    pause_trading(reason="kill_switch", details={}, path=pause_path)

    text = build_qic_command_response("/resume_trading", qic_output_path=tmp_path / "reports", actor="42", pause_path=pause_path)

    assert "reanudado" in text.lower()
    state = is_trading_paused(pause_path)
    assert state["paused"] is False


def test_resume_trading_command_when_not_paused_is_a_noop(tmp_path: Path) -> None:
    pause_path = tmp_path / "trading_paused.json"

    text = build_qic_command_response("/resume_trading", qic_output_path=tmp_path / "reports", actor="42", pause_path=pause_path)

    assert "ya estaba activo" in text.lower()
    assert not pause_path.exists()


def test_resume_trading_via_process_telegram_update_uses_chat_id_as_actor(tmp_path: Path) -> None:
    pause_path = tmp_path / "trading_paused.json"
    pause_trading(reason="kill_switch", details={}, path=pause_path)
    update = {"update_id": 5, "message": {"chat": {"id": 123}, "text": "/resume_trading"}}

    result = process_telegram_update(
        update,
        authorized_chat_ids=["123"],
        qic_output_path=tmp_path / "reports",
        pause_path=pause_path,
    )

    assert result["handled"] is True
    assert "123" in result["response_text"]
    assert is_trading_paused(pause_path)["paused"] is False
