from __future__ import annotations

import json
from pathlib import Path

from trading_signals.agents.proposal_store import save_proposals
from trading_signals.agents.telegram_approval import build_qic_command_response, process_telegram_update


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
