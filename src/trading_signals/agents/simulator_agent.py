from __future__ import annotations

from typing import Any


def generate_simulator_proposals(reports: dict[str, Any]) -> list[dict[str, Any]]:
    simulator = reports.get("strategy_simulator", {})
    recommendations = _list(simulator.get("recommendations", {}).get("recommendations", []))
    proposals = []
    for item in recommendations[:30]:
        if str(item.get("action")) == "Insufficient data":
            continue
        proposals.append(
            {
                "source_agent": "simulator_agent",
                "title": f"Simulator proposal: {item.get('action', 'Review simulated filter')}",
                "hypothesis": f"Simulated conditions: {', '.join(str(x) for x in _list(item.get('conditions')))}",
                "expected_pf": _float(item.get("expected_pf")),
                "expected_total_r": _float(item.get("expected_total_r")),
                "trades_lost": int(float(item.get("trades_lost") or 0)),
                "confidence": str(item.get("confidence") or "LOW").upper(),
                "risk_level": "LOW",
                "evidence": int(float(item.get("evidence") or 0)),
                "context": {"conditions": _list(item.get("conditions"))},
            }
        )
    return proposals


def vote_simulator_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    expected_pf = _float(proposal.get("expected_pf")) or 0.0
    expected_total_r = _float(proposal.get("expected_total_r")) or 0.0
    if expected_pf >= 1.1 and expected_total_r > 0:
        vote = "SUPPORT"
        reason = "Simulation improves PF and TotalR."
    elif expected_total_r > 0:
        vote = "CAUTION"
        reason = "Simulation improves TotalR but PF evidence is limited."
    else:
        vote = "REJECT"
        reason = "Simulation does not improve outcome."
    return {
        "agent": "simulator_agent",
        "vote": vote,
        "confidence": str(proposal.get("confidence") or "LOW").upper(),
        "reason": reason,
    }


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
