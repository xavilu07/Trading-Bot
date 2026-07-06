from __future__ import annotations

import hashlib
from typing import Any

from trading_signals.agents.qic_models import CIOProposal
from trading_signals.agents.risk_agent import classify_trade_reduction_risk

CONFIDENCE_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


def build_cio_consensus(debate: dict[str, Any], *, min_confidence: str = "MEDIUM") -> dict[str, Any]:
    interventions = debate.get("interventions") if isinstance(debate.get("interventions"), list) else []
    simulation = _find_stage(interventions, "simulation")
    risk = _find_stage(interventions, "risk")
    research_response = _find_stage(interventions, "research_response")
    best = (simulation.get("data") or {}).get("best_simulation") if isinstance(simulation.get("data"), dict) else {}
    baseline_trades = _baseline_trades(best, risk)
    selected_reduction = classify_trade_reduction_risk(_int(best.get("trades_eliminated")) if isinstance(best, dict) else 0, baseline_trades)
    risks = _selected_risk_objections(best, risk, selected_reduction)
    confidence = str(simulation.get("confidence") or "LOW").upper()
    min_rank = CONFIDENCE_RANK.get(str(min_confidence).upper(), 2)
    risk_level = str(selected_reduction.get("risk_level") or "MEDIUM").upper()
    consensus_score = _consensus_score(simulation=simulation, risk_level=risk_level, research_response=research_response)
    discard_reasons = []
    if not best:
        discard_reasons.append("no_simulation_candidate")
    if CONFIDENCE_RANK.get(confidence, 1) < min_rank:
        discard_reasons.append("below_min_confidence")
    if consensus_score <= 0:
        discard_reasons.append("weak_consensus")
    proposal = None
    if not discard_reasons:
        proposal = _proposal_from_simulation(
            best,
            confidence=confidence,
            risk_level=risk_level,
            interventions=interventions,
            baseline_trades=baseline_trades,
            trade_reduction_pct=float(selected_reduction.get("trade_reduction_pct") or 0),
            risk_objections=risks,
        )
    return {
        "consensus_score": consensus_score,
        "confidence": confidence,
        "risk_level": risk_level,
        "discard_reasons": discard_reasons,
        "risk_objections": risks or [],
        "single_proposal": proposal.to_dict() if proposal else None,
    }


def build_cio_hypothesis_candidates(debate: dict[str, Any], *, min_confidence: str = "MEDIUM") -> list[dict[str, Any]]:
    interventions = debate.get("interventions") if isinstance(debate.get("interventions"), list) else []
    simulation = _find_stage(interventions, "simulation")
    risk = _find_stage(interventions, "risk")
    research_response = _find_stage(interventions, "research_response")
    simulation_data = simulation.get("data") if isinstance(simulation.get("data"), dict) else {}
    simulations = simulation_data.get("top_simulations") if isinstance(simulation_data.get("top_simulations"), list) else []
    min_rank = CONFIDENCE_RANK.get(str(min_confidence).upper(), 2)
    candidates = []
    for rank, item in enumerate(simulations, start=1):
        if not isinstance(item, dict):
            continue
        confidence = str(item.get("confidence") or "LOW").upper()
        baseline_trades = _baseline_trades(item, risk)
        selected_reduction = classify_trade_reduction_risk(_int(item.get("trades_eliminated")), baseline_trades)
        risk_level = str(selected_reduction.get("risk_level") or "MEDIUM").upper()
        consensus_score = _consensus_score(simulation={"confidence": confidence}, risk_level=risk_level, research_response=research_response)
        discard_reasons = []
        if CONFIDENCE_RANK.get(confidence, 1) < min_rank:
            discard_reasons.append("below_min_confidence")
        if consensus_score <= 0:
            discard_reasons.append("weak_consensus")
        proposal = None
        if not discard_reasons:
            proposal = _proposal_from_simulation(
                item,
                confidence=confidence,
                risk_level=risk_level,
                interventions=interventions,
                baseline_trades=baseline_trades,
                trade_reduction_pct=float(selected_reduction.get("trade_reduction_pct") or 0),
                risk_objections=_selected_risk_objections(item, risk, selected_reduction),
            ).to_dict()
        candidates.append(
            {
                "rank": rank,
                "status": "candidate" if proposal else "discarded",
                "discard_reason": ", ".join(discard_reasons),
                "proposal": proposal,
                "simulation": item,
                "consensus_score": consensus_score,
                "risk_level": risk_level,
                "trade_reduction_pct": selected_reduction.get("trade_reduction_pct"),
            }
        )
    return candidates


def _proposal_from_simulation(
    simulation: dict[str, Any],
    *,
    confidence: str,
    risk_level: str,
    interventions: list[dict[str, Any]],
    baseline_trades: int,
    trade_reduction_pct: float,
    risk_objections: list[str],
) -> CIOProposal:
    conditions = simulation.get("conditions") or []
    action = "IMPLEMENTATION_CANDIDATE"
    if risk_level == "EXTREME":
        action = "REQUIRES_VARIANT_SEARCH"
    title_prefix = "CIO variant search required" if action == "REQUIRES_VARIANT_SEARCH" else "CIO proposal"
    title = f"{title_prefix}: {', '.join(str(item) for item in conditions) or 'prioritize simulated context'}"
    hypothesis = "Strategy Simulator indicates this single candidate has the strongest current evidence."
    if action == "REQUIRES_VARIANT_SEARCH":
        hypothesis = "Simulation result is promising but removes too much of the operating universe; find a less aggressive variant."
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
        action=action,
        baseline_trades=baseline_trades,
        trade_reduction_pct=round(trade_reduction_pct, 4),
        risk_objections=risk_objections,
        agent_votes=[
            {
                "agent": item.get("agent"),
                "stage": item.get("stage"),
                "confidence": item.get("confidence"),
                "risk_level": item.get("risk_level"),
            }
            for item in interventions
        ],
        context={
            "conditions": conditions,
            "condition_details": simulation.get("condition_details") or [],
            "baseline_trades": baseline_trades,
            "trade_reduction_pct": round(trade_reduction_pct, 4),
            "source": simulation.get("source"),
            "composite_score": simulation.get("composite_score"),
            "complexity": simulation.get("complexity"),
        },
        rationale=_rationale(simulation, action, trade_reduction_pct),
    )


def _find_stage(interventions: list[dict[str, Any]], stage: str) -> dict[str, Any]:
    for item in interventions:
        if item.get("stage") == stage:
            return item
    return {}


def _consensus_score(*, simulation: dict[str, Any], risk_level: str, research_response: dict[str, Any]) -> float:
    score = 0.0
    score += CONFIDENCE_RANK.get(str(simulation.get("confidence") or "LOW").upper(), 1)
    score += CONFIDENCE_RANK.get(str(research_response.get("confidence") or "LOW").upper(), 1) * 0.5
    normalized_risk = str(risk_level or "MEDIUM").upper()
    if normalized_risk == "EXTREME":
        score -= 0.5
    elif normalized_risk == "HIGH":
        score -= 0.5
    elif normalized_risk == "MEDIUM":
        score -= 1
    return round(score, 4)


def _baseline_trades(best: dict[str, Any], risk: dict[str, Any]) -> int:
    risk_data = risk.get("data") if isinstance(risk.get("data"), dict) else {}
    baseline = _int((risk_data or {}).get("baseline_closed"))
    if baseline:
        return baseline
    return _int(best.get("trades_eliminated")) + _int(best.get("remaining_closed") or best.get("evidence"))


def _selected_risk_objections(
    best: dict[str, Any],
    risk: dict[str, Any],
    selected_reduction: dict[str, object],
) -> list[str]:
    objections = []
    risk_name = str(selected_reduction.get("risk") or "")
    if risk_name:
        objections.append(risk_name)
    conditions = [str(item) for item in best.get("conditions") or []]
    all_risks = (risk.get("data") or {}).get("risks") if isinstance(risk.get("data"), dict) else []
    for item in all_risks or []:
        candidate = str(item.get("candidate") or "")
        if conditions and not all(condition in candidate for condition in conditions):
            continue
        item_risk = str(item.get("risk") or "")
        if item_risk and item_risk not in objections:
            objections.append(item_risk)
    return objections


def _rationale(simulation: dict[str, Any], action: str, trade_reduction_pct: float) -> str:
    base = f"Expected PF {simulation.get('profit_factor')} and TotalR {simulation.get('total_r')} after simulation."
    if action == "REQUIRES_VARIANT_SEARCH":
        return f"{base} Trade reduction is {trade_reduction_pct:.2f}%, so this is not a direct implementation candidate."
    if action == "SHADOW_VALIDATION_REQUIRED":
        return f"{base} Trade reduction is {trade_reduction_pct:.2f}%, so shadow validation is required before implementation."
    return base


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
