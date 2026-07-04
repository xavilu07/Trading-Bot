from __future__ import annotations

import hashlib
from typing import Any

from trading_signals.agents.qic_models import CIOProposal

CONFIDENCE_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


def build_cio_consensus(debate: dict[str, Any], *, min_confidence: str = "MEDIUM") -> dict[str, Any]:
    interventions = debate.get("interventions") if isinstance(debate.get("interventions"), list) else []
    simulation = _find_stage(interventions, "simulation")
    risk = _find_stage(interventions, "risk")
    research_response = _find_stage(interventions, "research_response")
    best = (simulation.get("data") or {}).get("best_simulation") if isinstance(simulation.get("data"), dict) else {}
    risks = (risk.get("data") or {}).get("risks") if isinstance(risk.get("data"), dict) else []
    confidence = str(simulation.get("confidence") or "LOW").upper()
    min_rank = CONFIDENCE_RANK.get(str(min_confidence).upper(), 2)
    risk_level = str(risk.get("risk_level") or "MEDIUM").upper()
    consensus_score = _consensus_score(simulation=simulation, risk=risk, research_response=research_response)
    discard_reasons = []
    if not best:
        discard_reasons.append("no_simulation_candidate")
    if CONFIDENCE_RANK.get(confidence, 1) < min_rank:
        discard_reasons.append("below_min_confidence")
    if risk_level == "HIGH":
        discard_reasons.append("high_risk_objection")
    if consensus_score <= 0:
        discard_reasons.append("weak_consensus")
    proposal = None
    if not discard_reasons:
        proposal = _proposal_from_simulation(best, confidence=confidence, risk_level=risk_level, interventions=interventions)
    return {
        "consensus_score": consensus_score,
        "confidence": confidence,
        "risk_level": risk_level,
        "discard_reasons": discard_reasons,
        "risk_objections": risks or [],
        "single_proposal": proposal.to_dict() if proposal else None,
    }


def _proposal_from_simulation(
    simulation: dict[str, Any],
    *,
    confidence: str,
    risk_level: str,
    interventions: list[dict[str, Any]],
) -> CIOProposal:
    conditions = simulation.get("conditions") or []
    title = f"CIO proposal: {', '.join(str(item) for item in conditions) or 'prioritize simulated context'}"
    hypothesis = "Strategy Simulator indicates this single candidate has the strongest current evidence."
    unique = f"{title}|{conditions}|{simulation.get('profit_factor')}|{simulation.get('total_r')}"
    proposal_id = "cio_" + hashlib.sha1(unique.encode("utf-8")).hexdigest()[:12]
    return CIOProposal(
        id=proposal_id,
        title=title,
        hypothesis=hypothesis,
        expected_pf=_float(simulation.get("profit_factor")),
        expected_total_r=_float(simulation.get("total_r")),
        trades_lost=_int(simulation.get("trades_eliminated")),
        confidence=confidence,
        risk_level=risk_level,
        evidence=_int(simulation.get("remaining_closed") or simulation.get("evidence")),
        agent_votes=[
            {
                "agent": item.get("agent"),
                "stage": item.get("stage"),
                "confidence": item.get("confidence"),
                "risk_level": item.get("risk_level"),
            }
            for item in interventions
        ],
        context={"conditions": conditions, "condition_details": simulation.get("condition_details") or []},
        rationale=f"Expected PF {simulation.get('profit_factor')} and TotalR {simulation.get('total_r')} after simulation.",
    )


def _find_stage(interventions: list[dict[str, Any]], stage: str) -> dict[str, Any]:
    for item in interventions:
        if item.get("stage") == stage:
            return item
    return {}


def _consensus_score(*, simulation: dict[str, Any], risk: dict[str, Any], research_response: dict[str, Any]) -> float:
    score = 0.0
    score += CONFIDENCE_RANK.get(str(simulation.get("confidence") or "LOW").upper(), 1)
    score += CONFIDENCE_RANK.get(str(research_response.get("confidence") or "LOW").upper(), 1) * 0.5
    if str(risk.get("risk_level") or "MEDIUM").upper() == "HIGH":
        score -= 3
    elif str(risk.get("risk_level") or "MEDIUM").upper() == "MEDIUM":
        score -= 1
    return round(score, 4)


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
