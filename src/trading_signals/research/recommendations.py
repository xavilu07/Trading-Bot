from __future__ import annotations

from typing import Any


def build_recommendations(strategy_candidates: dict[str, Any], clusters: dict[str, Any]) -> dict[str, Any]:
    candidates = strategy_candidates.get("candidates", [])
    recommendations = []
    for candidate in candidates[:30]:
        recommendations.append(
            {
                "recommendation": candidate["action"],
                "context": candidate["context"],
                "expected_impact": candidate["expected_improvement"],
                "confidence": candidate["confidence"],
                "evidence": candidate["evidence"],
                "trades_affected": candidate["trades_affected"],
                "rationale": candidate["rationale"],
            }
        )
    if not recommendations:
        recommendations.append(
            {
                "recommendation": "Insufficient data",
                "context": {},
                "expected_impact": 0.0,
                "confidence": "LOW",
                "evidence": 0,
                "trades_affected": 0,
                "rationale": "No statistically meaningful candidate was found.",
            }
        )
    return {
        "recommendations": recommendations,
        "positive_clusters_to_watch": clusters.get("positive_clusters", [])[:10],
        "negative_clusters_to_investigate": clusters.get("negative_clusters", [])[:10],
    }
