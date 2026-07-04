from __future__ import annotations

from typing import Any


def build_recommendations(
    *,
    positive_edges: list[dict[str, Any]],
    negative_edges: list[dict[str, Any]],
    overview: dict[str, Any],
) -> dict[str, Any]:
    recommendations: list[dict[str, Any]] = []
    for edge in positive_edges[:20]:
        recommendations.append(
            {
                "action": "Prioritize context",
                "context": edge.get("context") or {edge.get("dimension"): edge.get("value")},
                "label": edge.get("label"),
                "expected_impact": round(float(edge.get("total_r", 0.0)), 4),
                "confidence": edge.get("confidence", "LOW"),
                "evidence": edge.get("evidence_count", 0),
                "reason": f"PF {edge.get('profit_factor')} with TotalR {edge.get('total_r')}",
            }
        )
    for edge in negative_edges[:20]:
        action = "Avoid context"
        if edge.get("dimension") == "score_bucket":
            action = "Raise minimum score"
        elif edge.get("dimension") == "symbol":
            action = "Avoid symbol"
        recommendations.append(
            {
                "action": action,
                "context": edge.get("context") or {edge.get("dimension"): edge.get("value")},
                "label": edge.get("label"),
                "expected_impact": round(abs(float(edge.get("total_r", 0.0))), 4),
                "confidence": edge.get("confidence", "LOW"),
                "evidence": edge.get("evidence_count", 0),
                "reason": f"PF {edge.get('profit_factor')} with TotalR {edge.get('total_r')}",
            }
        )
    if not recommendations:
        recommendations.append(
            {
                "action": "Insufficient data",
                "context": {},
                "expected_impact": 0.0,
                "confidence": "LOW",
                "evidence": overview.get("closed", 0),
                "reason": "No statistically meaningful positive or negative edges found.",
            }
        )
    watchlist = [
        item
        for item in recommendations
        if item.get("confidence") == "LOW" and int(item.get("evidence", 0) or 0) < 30
    ][:20]
    return {
        "recommendations": recommendations,
        "watchlist": watchlist,
        "summary": {
            "total_recommendations": len(recommendations),
            "positive_actions": len(positive_edges),
            "negative_actions": len(negative_edges),
            "global_profit_factor": overview.get("profit_factor", 0.0),
            "global_total_r": overview.get("total_r", 0.0),
        },
    }
