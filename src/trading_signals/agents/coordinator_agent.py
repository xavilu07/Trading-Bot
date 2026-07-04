from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from trading_signals.agents.risk_agent import vote_committee_risk
from trading_signals.agents.simulator_agent import vote_simulator_proposal
from trading_signals.agents.strategy_agent import vote_strategy_proposal

CONFIDENCE_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


def coordinate_committee_proposals(
    proposals: list[dict[str, Any]],
    *,
    min_confidence: str = "MEDIUM",
) -> list[dict[str, Any]]:
    coordinated = []
    seen: set[str] = set()
    min_rank = CONFIDENCE_ORDER.get(str(min_confidence).upper(), 2)
    for draft in proposals:
        proposal = normalize_proposal(draft)
        if proposal["id"] in seen:
            continue
        seen.add(proposal["id"])
        votes = [
            {
                "agent": proposal.get("source_agent", "unknown_agent"),
                "vote": "SUPPORT",
                "confidence": proposal["confidence"],
                "reason": "Originating agent generated this proposal.",
            },
            vote_strategy_proposal(proposal),
            vote_simulator_proposal(proposal),
            vote_committee_risk(proposal),
        ]
        proposal["agent_votes"] = votes
        proposal["committee_score"] = committee_score(votes)
        proposal["status"] = proposal.get("status") or "pending"
        if CONFIDENCE_ORDER.get(proposal["confidence"], 1) >= min_rank:
            coordinated.append(proposal)
    return sorted(coordinated, key=lambda item: (item["committee_score"], item.get("expected_total_r") or 0), reverse=True)


def normalize_proposal(draft: dict[str, Any]) -> dict[str, Any]:
    context = draft.get("context") if isinstance(draft.get("context"), dict) else {}
    title = str(draft.get("title") or "Untitled proposal")
    hypothesis = str(draft.get("hypothesis") or "")
    unique = f"{title}|{hypothesis}|{context}"
    proposal_id = hashlib.sha1(unique.encode("utf-8")).hexdigest()[:12]
    return {
        "id": str(draft.get("id") or f"prop_{proposal_id}"),
        "title": title,
        "hypothesis": hypothesis,
        "expected_pf": _float(draft.get("expected_pf")),
        "expected_total_r": _float(draft.get("expected_total_r")),
        "trades_lost": _int(draft.get("trades_lost")),
        "confidence": _confidence(draft.get("confidence")),
        "risk_level": str(draft.get("risk_level") or "MEDIUM").upper(),
        "evidence": _int(draft.get("evidence")),
        "agent_votes": list(draft.get("agent_votes") or []),
        "status": str(draft.get("status") or "pending"),
        "context": context,
        "source_agent": str(draft.get("source_agent") or "unknown_agent"),
        "created_at": str(draft.get("created_at") or datetime.now(tz=UTC).isoformat()),
    }


def committee_score(votes: list[dict[str, Any]]) -> float:
    weights = {"SUPPORT": 1.0, "CAUTION": 0.25, "REJECT": -1.0}
    confidence = {"LOW": 0.5, "MEDIUM": 1.0, "HIGH": 1.5}
    if not votes:
        return 0.0
    total = 0.0
    for vote in votes:
        total += weights.get(str(vote.get("vote")).upper(), 0.0) * confidence.get(str(vote.get("confidence")).upper(), 1.0)
    return round(total / len(votes), 4)


def _confidence(value: Any) -> str:
    confidence = str(value or "LOW").upper()
    return confidence if confidence in CONFIDENCE_ORDER else "LOW"


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None
