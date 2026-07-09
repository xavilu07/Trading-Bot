from __future__ import annotations

import json
from pathlib import Path

from trading_signals.agents.decision_ledger import append_decision_ledger_entry, load_decision_ledger
from trading_signals.agents.implementation.code_engineer import run_code_engineer
from trading_signals.agents.implementation.implementation_review_council import run_implementation_review
from trading_signals.agents.implementation.patch_generator import generate_patch_report
from trading_signals.agents.learning_loop import run_qic_learning_loop, should_discard_repeated_rejected_proposal
from trading_signals.agents.qic_autonomous_reports import write_autonomous_qic_reports
from trading_signals.agents.proposal_store import save_proposals
from trading_signals.agents.research_memory import (
    load_research_memory,
    record_research_memory_decision,
    update_research_memory_from_proposal,
)
from trading_signals.agents.revalidation_engine import revalidate_edge, run_revalidation_engine
from trading_signals.agents.state_of_council import build_state_of_council
from trading_signals.agents.strategy_knowledge_base import upsert_knowledge_from_proposal
from trading_signals.agents.telegram_approval import handle_approval_callback


def test_research_memory_create_update_and_normalized_dedup(tmp_path: Path) -> None:
    path = tmp_path / "data" / "qic" / "research_memory.json"
    first = update_research_memory_from_proposal(_proposal(), path=path)
    proposal = _proposal()
    proposal["conditions"] = [" exclude  htf_alignment = against "]
    second = update_research_memory_from_proposal(proposal, path=path)

    memory = load_research_memory(path)

    assert first["id"] == second["id"]
    assert len(memory["experiments"]) == 1
    assert next(iter(memory["experiments"].values()))["times_seen"] == 2


def test_rejected_cooldown_prevents_repeat_without_new_evidence(tmp_path: Path) -> None:
    path = tmp_path / "data" / "qic" / "research_memory.json"
    proposal = _proposal(evidence=100)
    record_research_memory_decision(proposal, "rejected", path=path, reason="manual_reject")
    memory = load_research_memory(path)

    result = should_discard_repeated_rejected_proposal(_proposal(evidence=110), research_memory=memory, cooldown_days=14)

    assert result["skip"] is True
    assert result["reason"] == "rejected_cooldown_active"


def test_revalidation_classifies_improved_degraded_invalidated() -> None:
    item = {"id": "edge_1", "rule_conditions": ["exclude htf_alignment=against"], "last_expected_pf": 1.2, "last_expected_total_r": 10, "last_evidence": 100}

    improved = revalidate_edge(item, simulator_rows=[_sim_row(pf=1.3, total_r=12, evidence=170)], min_new_trades=50)
    degraded = revalidate_edge(item, simulator_rows=[_sim_row(pf=1.0, total_r=8, evidence=170)], min_new_trades=50)
    invalidated = revalidate_edge(item, simulator_rows=[_sim_row(pf=0.9, total_r=-1, evidence=170)], min_new_trades=50)

    assert improved["result"] == "edge_improved"
    assert degraded["result"] == "edge_degraded"
    assert invalidated["result"] == "edge_invalidated"


def test_run_revalidation_engine_writes_reports(tmp_path: Path) -> None:
    kb_path = tmp_path / "data" / "qic" / "strategy_knowledge_base.json"
    memory_path = tmp_path / "data" / "qic" / "research_memory.json"
    reports_root = tmp_path / "reports"
    upsert_knowledge_from_proposal(_proposal(evidence=100), path=kb_path)
    update_research_memory_from_proposal(_proposal(evidence=100), path=memory_path)
    simulator_path = reports_root / "strategy_simulator"
    simulator_path.mkdir(parents=True)
    (simulator_path / "single_filters.json").write_text(json.dumps({"results": [_sim_row(pf=1.3, total_r=30, evidence=170)]}), encoding="utf-8")

    report = run_revalidation_engine(
        knowledge_base_path=kb_path,
        research_memory_path=memory_path,
        reports_root=reports_root,
        output_path=reports_root / "qic",
        min_new_trades=50,
    )

    assert report["results"][0]["result"] == "edge_improved"
    assert (reports_root / "qic" / "revalidation.json").exists()
    assert (reports_root / "qic" / "revalidation.md").exists()


def test_decision_ledger_append_and_read(tmp_path: Path) -> None:
    path = tmp_path / "data" / "qic" / "decision_ledger.jsonl"

    entry = append_decision_ledger_entry(_proposal(), path=path, final_decision="PROPOSE_IMPLEMENTATION")

    assert entry["final_decision"] == "PROPOSE_IMPLEMENTATION"
    assert load_decision_ledger(path)[0]["proposal_id"] == "cio_htf_against"


def test_learning_loop_generates_state_reports(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_root = tmp_path / "reports"
    upsert_knowledge_from_proposal(_proposal(evidence=100), path=data_path / "qic" / "strategy_knowledge_base.json")
    simulator_path = reports_root / "strategy_simulator"
    simulator_path.mkdir(parents=True)
    (simulator_path / "single_filters.json").write_text(json.dumps({"results": [_sim_row(pf=1.3, total_r=12, evidence=170)]}), encoding="utf-8")

    result = run_qic_learning_loop(
        proposal=_proposal(evidence=100),
        final_action="PROPOSE_IMPLEMENTATION",
        data_path=data_path,
        reports_root=reports_root,
        output_path=reports_root / "qic",
        min_new_trades=50,
    )

    assert result["state_of_council"]["total_known_edges"] == 1
    assert (reports_root / "qic" / "research_memory.json").exists()
    assert (reports_root / "qic" / "state_of_council.json").exists()


def test_telegram_history_edge_memory_agent_review_and_revalidate_callbacks(tmp_path: Path) -> None:
    proposal_store = tmp_path / "data" / "agent_proposals" / "proposals.jsonl"
    qic_output = tmp_path / "reports" / "qic"
    kb_path = tmp_path / "data" / "qic" / "strategy_knowledge_base.json"
    proposal = _proposal()
    save_proposals([proposal], proposal_store)
    upsert_knowledge_from_proposal(proposal, path=kb_path)
    update_research_memory_from_proposal(proposal, path=tmp_path / "data" / "qic" / "research_memory.json")
    append_decision_ledger_entry(proposal, path=tmp_path / "data" / "qic" / "decision_ledger.jsonl")

    history = handle_approval_callback("agent:history:cio_htf_against", proposal_store_path=proposal_store, knowledge_base_path=kb_path, qic_output_path=qic_output)
    edge_memory = handle_approval_callback("agent:edge_memory:cio_htf_against", proposal_store_path=proposal_store, knowledge_base_path=kb_path, qic_output_path=qic_output)
    agent_review = handle_approval_callback("agent:agent_review:cio_htf_against", proposal_store_path=proposal_store, knowledge_base_path=kb_path, qic_output_path=qic_output)

    assert history["status"] == "history_loaded"
    assert edge_memory["status"] == "edge_memory_loaded"
    assert agent_review["status"] == "agent_review_loaded"


def test_code_engineer_blocked_preconditions_updates_research_memory(tmp_path: Path) -> None:
    proposal_store = tmp_path / "data" / "agent_proposals" / "proposals.jsonl"
    proposal = _proposal()
    proposal["status"] = "pending"
    save_proposals([proposal], proposal_store)

    report = run_code_engineer(
        proposal_id="cio_htf_against",
        project_root=tmp_path / "project",
        proposal_store_path=proposal_store,
        reports_path=tmp_path / "reports" / "qic",
        dry_run=True,
    )
    memory = load_research_memory(tmp_path / "data" / "qic" / "research_memory.json")

    assert report["status"] == "failed_preconditions"
    assert next(iter(memory["experiments"].values()))["current_status"] == "blocked_preconditions"


def test_code_engineer_dry_run_updates_code_generated_status(tmp_path: Path) -> None:
    proposal_store, reports_path, project_root = _prepare_code_engineer_fixture(tmp_path)

    report = run_code_engineer(
        proposal_id="cio_htf_against",
        project_root=project_root,
        proposal_store_path=proposal_store,
        reports_path=reports_path,
        dry_run=True,
    )
    memory = load_research_memory(tmp_path / "data" / "qic" / "research_memory.json")

    assert report["status"] == "dry_run_generated"
    assert next(iter(memory["experiments"].values()))["current_status"] == "code_generated"


def test_state_of_council_report_generation(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports" / "qic"
    proposal = _proposal()
    save_proposals([proposal], data_path / "agent_proposals" / "proposals.jsonl")
    upsert_knowledge_from_proposal(proposal, path=data_path / "qic" / "strategy_knowledge_base.json")
    update_research_memory_from_proposal(proposal, path=data_path / "qic" / "research_memory.json")

    report = build_state_of_council(
        knowledge_base_path=data_path / "qic" / "strategy_knowledge_base.json",
        research_memory_path=data_path / "qic" / "research_memory.json",
        proposal_store_path=data_path / "agent_proposals" / "proposals.jsonl",
        output_path=reports_path,
    )

    assert report["total_known_edges"] == 1
    assert (reports_path / "state_of_council.md").exists()


def test_autonomous_qic_daily_and_weekly_reports(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports" / "qic"
    proposal = _proposal()
    upsert_knowledge_from_proposal(proposal, path=data_path / "qic" / "strategy_knowledge_base.json")
    update_research_memory_from_proposal(proposal, path=data_path / "qic" / "research_memory.json")
    append_decision_ledger_entry(proposal, path=data_path / "qic" / "decision_ledger.jsonl")

    result = write_autonomous_qic_reports(
        output_path=reports_path,
        knowledge_base_path=data_path / "qic" / "strategy_knowledge_base.json",
        research_memory_path=data_path / "qic" / "research_memory.json",
        decision_ledger_path=data_path / "qic" / "decision_ledger.jsonl",
        events=[{"type": "known_edge_degraded"}],
    )

    assert result["daily_brief"]["action_required"] is True
    assert (reports_path / "daily_brief.json").exists()
    assert (reports_path / "weekly_research_review.md").exists()


def _proposal(*, evidence: int = 586) -> dict[str, object]:
    return {
        "id": "cio_htf_against",
        "title": "CIO proposal: exclude htf_alignment=against",
        "action": "PROPOSE_IMPLEMENTATION",
        "conditions": ["exclude htf_alignment=against"],
        "expected_pf": 1.113,
        "expected_total_r": 21.1506,
        "baseline_pf": 0.8743,
        "baseline_total_r": -54.1711,
        "trades_lost": 562,
        "baseline_trades": 1148,
        "trade_reduction_pct": 48.9547,
        "confidence": "HIGH",
        "risk_level": "HIGH",
        "risk_objections": ["high_trade_reduction"],
        "evidence": evidence,
        "knowledge_item_id": "edge_htf_against",
        "edge_type": "STRUCTURAL_EDGE",
        "implementation_priority": "HIGH",
        "status": "pending",
        "context": {
            "conditions": ["exclude htf_alignment=against"],
            "normalized_conditions": ["exclude:htf_alignment=against"],
            "source": "single_filter",
            "complexity": 1,
            "baseline_pf": 0.8743,
            "baseline_total_r": -54.1711,
        },
    }


def _sim_row(*, pf: float, total_r: float, evidence: int) -> dict[str, object]:
    return {
        "conditions": ["exclude htf_alignment=against"],
        "profit_factor": pf,
        "total_r": total_r,
        "evidence": evidence,
    }


def _prepare_code_engineer_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    proposal_store = tmp_path / "data" / "agent_proposals" / "proposals.jsonl"
    reports_path = tmp_path / "reports" / "qic"
    project_root = tmp_path / "project"
    proposal = _proposal()
    proposal["status"] = "approved_for_implementation_review"
    save_proposals([proposal], proposal_store)
    review = run_implementation_review(proposal, output_path=reports_path, knowledge_base_path=tmp_path / "data" / "qic" / "strategy_knowledge_base.json")
    generate_patch_report(review, output_path=reports_path)
    return proposal_store, reports_path, project_root
