from __future__ import annotations

from typing import Any


def generate_strategy_proposals(reports: dict[str, Any]) -> list[dict[str, Any]]:
    historical = reports.get("historical_intelligence", {})
    proposals: list[dict[str, Any]] = []
    for edge in _list(historical.get("negative_edges", {}).get("edges", []))[:15]:
        proposals.append(
            {
                "source_agent": "strategy_agent",
                "title": f"Avoid negative edge: {edge.get('label') or edge.get('context')}",
                "hypothesis": f"Blocking or shadow-testing this context may reduce losses. PF={edge.get('profit_factor')} TotalR={edge.get('total_r')}",
                "expected_pf": edge.get("profit_factor"),
                "expected_total_r": abs(_float(edge.get("total_r")) or 0.0),
                "trades_lost": int(edge.get("closed") or edge.get("trades") or 0),
                "confidence": str(edge.get("confidence") or "LOW").upper(),
                "risk_level": "MEDIUM",
                "evidence": int(edge.get("evidence_count") or edge.get("closed") or 0),
                "context": edge.get("context") or {},
            }
        )
    for edge in _list(historical.get("positive_edges", {}).get("edges", []))[:15]:
        proposals.append(
            {
                "source_agent": "strategy_agent",
                "title": f"Prioritize positive edge: {edge.get('label') or edge.get('context')}",
                "hypothesis": f"Prioritizing this context may improve selectivity. PF={edge.get('profit_factor')} TotalR={edge.get('total_r')}",
                "expected_pf": edge.get("profit_factor"),
                "expected_total_r": edge.get("total_r"),
                "trades_lost": 0,
                "confidence": str(edge.get("confidence") or "LOW").upper(),
                "risk_level": "LOW",
                "evidence": int(edge.get("evidence_count") or edge.get("closed") or 0),
                "context": edge.get("context") or {},
            }
        )
    return proposals


def vote_strategy_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    confidence = str(proposal.get("confidence") or "LOW").upper()
    vote = "SUPPORT" if confidence in {"MEDIUM", "HIGH"} else "CAUTION"
    return {
        "agent": "strategy_agent",
        "vote": vote,
        "confidence": confidence,
        "reason": "Strategy evidence reviewed from offline reports.",
    }


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
