from __future__ import annotations

import json
from pathlib import Path

from trading_signals.agents.committee import run_agent_committee
from trading_signals.agents.proposal_store import load_proposals, save_proposals, update_proposal_status
from trading_signals.agents.risk_agent import vote_committee_risk
from trading_signals.agents.telegram_approval import (
    build_approval_payload,
    handle_approval_callback,
    process_approval_update,
    resolve_qic_telegram_config,
    send_proposals_for_approval,
)


def test_committee_generates_single_cio_proposal_from_strategy_simulator(tmp_path: Path) -> None:
    _write_reports(tmp_path)

    result = run_agent_committee(
        reports_root=tmp_path / "reports",
        data_path=tmp_path / "data",
        output_path=tmp_path / "reports" / "agent_committee",
        enabled=True,
        min_confidence="MEDIUM",
        telegram_enabled=False,
    )

    assert result["proposal_count"] <= 1
    assert result["proposal_count"] == 1
    assert result["single_proposal"]["title"].startswith("CIO proposal")
    assert "exclude htf_alignment=against" in result["single_proposal"]["title"]
    assert (tmp_path / "data" / "agent_proposals" / "proposals.jsonl").exists()
    assert (tmp_path / "reports" / "agent_committee" / "debate.json").exists()
    json.loads((tmp_path / "reports" / "agent_committee" / "debate.json").read_text())


def test_risk_agent_penalizes_extreme_trade_reduction() -> None:
    proposal = {"trades_lost": 750, "baseline_trades": 1000, "evidence": 20, "expected_total_r": 10}

    vote = vote_committee_risk(proposal)

    assert vote["vote"] == "REJECT"
    assert proposal["risk_level"] == "EXTREME"
    assert proposal["trade_reduction_pct"] == 75.0
    assert "extreme_trade_reduction" in vote["risks"]


def test_proposal_store_saves_and_updates_status(tmp_path: Path) -> None:
    path = tmp_path / "data" / "agent_proposals" / "proposals.jsonl"
    proposal = {
        "id": "prop_1",
        "title": "Test",
        "status": "pending",
        "created_at": "2026-01-01T00:00:00+00:00",
    }

    save_proposals([proposal], path)
    updated = update_proposal_status("prop_1", "approved", path=path, actor="test")

    assert updated is not None
    assert updated["status"] == "approved"
    assert load_proposals(path)[0]["reviewed_by"] == "test"


def test_telegram_payload_includes_buttons() -> None:
    proposal = _proposal("prop_1")

    payload = build_approval_payload(proposal, chat_id="123")

    assert payload["chat_id"] == "123"
    buttons = [button for row in payload["reply_markup"]["inline_keyboard"] for button in row]
    assert [button["text"] for button in buttons] == [
        "✅ Approve",
        "❌ Reject",
        "📊 Details",
        "🧠 Debate",
        "🔁 Revalidate",
        "🧪 Find Alternative",
        "🛠 Implementation Review",
        "📦 Generate Patch",
        "🧪 Start Shadow",
    ]
    assert buttons[0]["callback_data"] == "agent:approve:prop_1"


def test_approval_callback_updates_status(tmp_path: Path) -> None:
    path = tmp_path / "proposals.jsonl"
    save_proposals([_proposal("prop_1")], path)

    kb_path = tmp_path / "strategy_knowledge_base.json"
    result = handle_approval_callback("agent:reject:prop_1", proposal_store_path=path, knowledge_base_path=kb_path, actor="tester")

    assert result["handled"] is True
    assert result["status"] == "rejected"
    assert load_proposals(path)[0]["status"] == "rejected"
    assert result["knowledge_item"] is not None


def test_approval_callback_approve_updates_store_and_knowledge_base(tmp_path: Path) -> None:
    path = tmp_path / "proposals.jsonl"
    kb_path = tmp_path / "strategy_knowledge_base.json"
    save_proposals([_proposal("prop_1")], path)

    result = handle_approval_callback("agent:approve:prop_1", proposal_store_path=path, knowledge_base_path=kb_path, actor="tester")

    assert result["handled"] is True
    assert result["status"] == "approved_for_implementation_review"
    assert load_proposals(path)[0]["status"] == "approved_for_implementation_review"
    assert result["knowledge_item"]["times_approved"] == 1


def test_process_approval_update_handles_telegram_callback(tmp_path: Path) -> None:
    path = tmp_path / "proposals.jsonl"
    kb_path = tmp_path / "strategy_knowledge_base.json"
    save_proposals([_proposal("prop_1")], path)
    update = {
        "update_id": 100,
        "callback_query": {
            "id": "cb_1",
            "from": {"id": 123},
            "data": "agent:approve:prop_1",
        },
    }

    result = process_approval_update(update, proposal_store_path=path, knowledge_base_path=kb_path)

    assert result["handled"] is True
    assert result["callback_query_id"] == "cb_1"
    assert load_proposals(path)[0]["reviewed_by"] == "123"


def test_resolve_qic_telegram_config_prefers_qic_and_falls_back_to_dev() -> None:
    class Settings:
        qic_telegram_enabled = "true"
        qic_telegram_bot_token = ""
        qic_telegram_chat_id = ""
        qic_telegram_send_no_actionable = "true"
        qic_telegram_min_priority = "HIGH"
        agent_telegram_bot_token = ""
        agent_telegram_chat_id = ""
        telegram_bot_token = "bot-token"
        telegram_dev_chat_id = "dev-chat"

    config = resolve_qic_telegram_config(Settings())

    assert config["enabled"] is True
    assert config["bot_token"] == "bot-token"
    assert config["chat_id"] == "dev-chat"
    assert config["configured"] is True
    assert config["min_priority"] == "HIGH"


def test_qic_proposal_send_supports_multiple_dev_chat_ids() -> None:
    results = send_proposals_for_approval([_proposal("prop_1")], bot_token="token", chat_id="111,222", dry_run=True)

    assert len(results) == 2
    assert [item["payload"]["chat_id"] for item in results] == ["111", "222"]


def test_disabled_flags_do_not_send_telegram(tmp_path: Path) -> None:
    _write_reports(tmp_path)

    result = run_agent_committee(
        reports_root=tmp_path / "reports",
        data_path=tmp_path / "data",
        output_path=tmp_path / "reports" / "agent_committee",
        enabled=False,
        telegram_enabled=True,
        telegram_bot_token="token",
        telegram_chat_id="chat",
    )

    assert result["enabled"] is False
    assert result["telegram_results"] == []
    assert result["proposals"] == []


def _write_reports(tmp_path: Path) -> None:
    simulator_path = tmp_path / "reports" / "strategy_simulator"
    simulator_path.mkdir(parents=True)
    (simulator_path / "recommendations.json").write_text(
        json.dumps(
            {
                "recommendations": [
                    {
                        "action": "Simulate filter before production",
                        "conditions": ["exclude htf_alignment=against"],
                        "expected_pf": 1.2,
                        "expected_total_r": 21.1,
                        "trades_lost": 100,
                        "confidence": "MEDIUM",
                        "evidence": 586,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    historical_path = tmp_path / "reports" / "historical_intelligence"
    historical_path.mkdir(parents=True)
    (historical_path / "positive_edges.json").write_text(json.dumps({"edges": []}), encoding="utf-8")
    (historical_path / "negative_edges.json").write_text(json.dumps({"edges": []}), encoding="utf-8")
    (historical_path / "recommendations.json").write_text(json.dumps({"recommendations": []}), encoding="utf-8")
    quant_path = tmp_path / "reports" / "quant_research"
    quant_path.mkdir(parents=True)
    (quant_path / "strategy_v2_candidates.json").write_text(json.dumps({"candidates": []}), encoding="utf-8")


def _proposal(proposal_id: str) -> dict[str, object]:
    return {
        "id": proposal_id,
        "title": "Proposal",
        "hypothesis": "Test hypothesis",
        "expected_pf": 1.2,
        "expected_total_r": 5,
        "trades_lost": 10,
        "confidence": "MEDIUM",
        "risk_level": "LOW",
        "evidence": 30,
        "agent_votes": [],
        "status": "pending",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
