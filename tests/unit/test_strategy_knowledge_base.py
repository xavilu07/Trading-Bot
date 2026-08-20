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


def _revalidated(kb: dict, item_id: str, result: str, **extra: object) -> None:
    kb["items"][item_id]["last_revalidation_result"] = {"result": result, **extra}


def test_enrich_repeated_in_sample_edge_is_not_promoted(tmp_path: Path) -> None:
    """Being ranked highly twice by the simulator is not evidence.

    The simulator refreshes daily against a dataset it has already been fitted
    to, so `times_seen >= 2` is satisfied roughly 48 hours after discovery. That
    alone used to be enough to call an edge confirmed.
    """
    path = tmp_path / "strategy_knowledge_base.json"
    proposal = _proposal()
    upsert_knowledge_from_proposal(proposal, path=path)
    upsert_knowledge_from_proposal(proposal, path=path)
    kb = load_strategy_knowledge_base(path)

    enriched = enrich_proposal_with_knowledge(proposal, kb)

    assert enriched["action"] != "PROMOTE_TO_CONFIRMED_EDGE"
    assert "never_revalidated" in enriched["context"]["promotion_withheld"]


def test_enrich_promotes_edge_backed_by_positive_revalidation(tmp_path: Path) -> None:
    path = tmp_path / "strategy_knowledge_base.json"
    proposal = _proposal()
    item = upsert_knowledge_from_proposal(proposal, path=path)
    upsert_knowledge_from_proposal(proposal, path=path)
    kb = load_strategy_knowledge_base(path)
    _revalidated(kb, item["id"], "edge_still_valid", new_trades=203.0)

    enriched = enrich_proposal_with_knowledge(proposal, kb)

    assert enriched["action"] == "PROMOTE_TO_CONFIRMED_EDGE"
    assert enriched["known_edge_status"] == "candidate"
    assert enriched["context"]["promotion_withheld"] == []


def test_enrich_withholds_promotion_when_revalidation_invalidated(tmp_path: Path) -> None:
    path = tmp_path / "strategy_knowledge_base.json"
    proposal = _proposal()
    item = upsert_knowledge_from_proposal(proposal, path=path)
    upsert_knowledge_from_proposal(proposal, path=path)
    kb = load_strategy_knowledge_base(path)
    _revalidated(kb, item["id"], "edge_invalidated", current_pf=0.919)

    enriched = enrich_proposal_with_knowledge(proposal, kb)

    assert enriched["action"] != "PROMOTE_TO_CONFIRMED_EDGE"
    assert "revalidation_edge_invalidated" in enriched["context"]["promotion_withheld"]


def test_enrich_withholds_promotion_for_an_edge_classified_overfit(tmp_path: Path) -> None:
    path = tmp_path / "strategy_knowledge_base.json"
    proposal = _proposal(trade_reduction_pct=75, complexity=2, evidence=90, expected_pf=2.0, expected_total_r=20)
    item = upsert_knowledge_from_proposal(proposal, path=path)
    upsert_knowledge_from_proposal(proposal, path=path)
    kb = load_strategy_knowledge_base(path)
    _revalidated(kb, item["id"], "edge_still_valid", new_trades=203.0)

    enriched = enrich_proposal_with_knowledge(proposal, kb)

    assert enriched["action"] != "PROMOTE_TO_CONFIRMED_EDGE"
    assert "classified_overfit_risk" in enriched["context"]["promotion_withheld"]


def test_retired_edge_is_not_resurrected_by_a_fresh_in_sample_proposal(tmp_path: Path) -> None:
    path = tmp_path / "strategy_knowledge_base.json"
    proposal = _proposal()
    item = upsert_knowledge_from_proposal(proposal, path=path)
    kb = load_strategy_knowledge_base(path)
    kb["items"][item["id"]]["status"] = "retired"
    (path).write_text(__import__("json").dumps(kb), encoding="utf-8")

    refreshed = upsert_knowledge_from_proposal(proposal, path=path)

    assert refreshed["status"] == "retired"


def test_upsert_preserves_revalidation_evidence(tmp_path: Path) -> None:
    """The item dict is rebuilt per proposal; measured evidence must survive."""
    path = tmp_path / "strategy_knowledge_base.json"
    proposal = _proposal()
    item = upsert_knowledge_from_proposal(proposal, path=path)
    kb = load_strategy_knowledge_base(path)
    kb["items"][item["id"]]["last_revalidation_result"] = {"result": "edge_invalidated"}
    kb["items"][item["id"]]["last_revalidated_pf"] = 0.919
    (path).write_text(__import__("json").dumps(kb), encoding="utf-8")

    refreshed = upsert_knowledge_from_proposal(proposal, path=path)

    assert refreshed["last_revalidation_result"] == {"result": "edge_invalidated"}
    assert refreshed["last_revalidated_pf"] == 0.919


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
