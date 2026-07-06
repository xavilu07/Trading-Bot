from __future__ import annotations

from pathlib import Path

from trading_signals.agents.proposal_store import load_proposals, save_proposals
from trading_signals.agents.strategy_knowledge_base import (
    classify_edge,
    enrich_proposal_with_knowledge,
    load_strategy_knowledge_base,
    normalize_conditions,
    record_proposal_review,
    upsert_knowledge_from_proposal,
)


def test_strategy_knowledge_base_creates_and_updates_existing_item(tmp_path: Path) -> None:
    path = tmp_path / "strategy_knowledge_base.json"
    proposal = _proposal()

    first = upsert_knowledge_from_proposal(proposal, path=path)
    second = upsert_knowledge_from_proposal(proposal, path=path)

    assert first["id"] == second["id"]
    assert second["times_seen"] == 2
    assert second["times_proposed"] == 2
    assert load_strategy_knowledge_base(path)["items"][first["id"]]["status"] == "candidate"


def test_strategy_knowledge_base_normalizes_conditions() -> None:
    assert normalize_conditions([" exclude  htf_alignment == against ", "EXCLUDE htf_alignment=against"]) == [
        "exclude:htf_alignment=against"
    ]


def test_strategy_knowledge_base_approve_and_reject_changes_status(tmp_path: Path) -> None:
    path = tmp_path / "strategy_knowledge_base.json"
    proposal = _proposal()
    item = upsert_knowledge_from_proposal(proposal, path=path)

    approved = record_proposal_review({**proposal, "knowledge_item_id": item["id"]}, "approved", path=path)
    rejected = record_proposal_review({**proposal, "knowledge_item_id": item["id"]}, "rejected", path=path, rejection_reason="too aggressive")

    assert approved is not None
    assert approved["times_approved"] == 1
    assert rejected is not None
    assert rejected["status"] == "rejected"
    assert rejected["times_rejected"] == 1


def test_edge_classification_marks_htf_against_as_structural_high_priority() -> None:
    proposal = _proposal()

    classification = classify_edge(proposal)

    assert classification["edge_type"] == "STRUCTURAL_EDGE"
    assert classification["implementation_priority"] == "HIGH"


def test_edge_classification_marks_extreme_reduction_as_overfit() -> None:
    proposal = _proposal(trade_reduction_pct=75, complexity=2, evidence=90, expected_pf=2.0, expected_total_r=20)

    classification = classify_edge(proposal)

    assert classification["edge_type"] == "OVERFIT_RISK"


def test_edge_classification_rejects_negative_total_r() -> None:
    proposal = _proposal(expected_pf=1.2, expected_total_r=-1)

    classification = classify_edge(proposal)

    assert classification["edge_type"] == "REJECTED_EDGE"
    assert classification["implementation_priority"] == "REJECT"


def test_enrich_repeated_consistent_edge_promotes_to_confirmed(tmp_path: Path) -> None:
    path = tmp_path / "strategy_knowledge_base.json"
    proposal = _proposal()
    upsert_knowledge_from_proposal(proposal, path=path)
    upsert_knowledge_from_proposal(proposal, path=path)
    kb = load_strategy_knowledge_base(path)

    enriched = enrich_proposal_with_knowledge(proposal, kb)

    assert enriched["action"] == "PROMOTE_TO_CONFIRMED_EDGE"
    assert enriched["known_edge_status"] == "candidate"


def test_proposal_store_deduplicates_pending_same_day_by_conditions(tmp_path: Path) -> None:
    path = tmp_path / "proposals.jsonl"
    proposal = _proposal()
    proposal["created_at"] = "2026-07-06T10:00:00+00:00"
    duplicate = {**proposal, "id": "different_id", "expected_pf": 1.2, "created_at": "2026-07-06T11:00:00+00:00"}

    save_proposals([proposal], path)
    save_proposals([duplicate], path)

    rows = load_proposals(path)
    assert len(rows) == 1
    assert rows[0]["id"] == proposal["id"]
    assert rows[0]["expected_pf"] == 1.2


def _proposal(
    *,
    trade_reduction_pct: float = 48.9547,
    complexity: int = 1,
    evidence: int = 586,
    expected_pf: float = 1.113,
    expected_total_r: float = 21.1506,
) -> dict[str, object]:
    return {
        "id": "cio_test",
        "title": "CIO proposal: exclude htf_alignment=against",
        "action": "PROPOSE_IMPLEMENTATION",
        "conditions": ["exclude htf_alignment=against"],
        "expected_pf": expected_pf,
        "expected_total_r": expected_total_r,
        "baseline_pf": 0.8743,
        "baseline_total_r": -54.1711,
        "trades_lost": 562,
        "baseline_trades": 1148,
        "trade_reduction_pct": trade_reduction_pct,
        "confidence": "HIGH",
        "risk_level": "HIGH",
        "risk_objections": ["high_trade_reduction"],
        "evidence": evidence,
        "context": {
            "conditions": ["exclude htf_alignment=against"],
            "source": "single_filter",
            "complexity": complexity,
            "composite_score": 39.4,
        },
    }
