from __future__ import annotations

from typing import Any

from trading_signals.intelligence.edge_knowledge import evaluate_context, load_edge_knowledge


MAX_ADJUSTMENT = 15.0
LOW_CONFIDENCE_CAP = 3.0
LOW_SAMPLE_CAP = 5.0
LOW_SAMPLE_THRESHOLD = 30
CONFLICT_THRESHOLD = 8.0


def optimize_edge_context(
    context: dict[str, Any],
    *,
    current_score: float,
    knowledge: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = knowledge if knowledge is not None else load_edge_knowledge()
    edge_result = evaluate_context(context, data)
    matched_edges = edge_result.get("matched_edges", [])
    if not isinstance(matched_edges, list):
        matched_edges = []

    positive_edges = [_edge_summary(edge) for edge in matched_edges if _weight(edge) > 0]
    negative_edges = [_edge_summary(edge) for edge in matched_edges if _weight(edge) < 0]
    positive_total = sum(_adjusted_weight(edge) for edge in matched_edges if _weight(edge) > 0)
    negative_total = sum(_adjusted_weight(edge) for edge in matched_edges if _weight(edge) < 0)
    adjustment = positive_total + negative_total

    conflict_reduced = False
    if positive_total >= CONFLICT_THRESHOLD and abs(negative_total) >= CONFLICT_THRESHOLD:
        adjustment *= 0.5
        conflict_reduced = True

    confidence = _combined_confidence(matched_edges)
    min_evidence = _min_evidence(matched_edges)
    caps_applied: list[str] = []
    adjustment = _cap(adjustment, MAX_ADJUSTMENT)
    if confidence == "LOW":
        adjustment = _cap(adjustment, LOW_CONFIDENCE_CAP)
        caps_applied.append("low_confidence_cap")
    if matched_edges and min_evidence < LOW_SAMPLE_THRESHOLD:
        adjustment = _cap(adjustment, LOW_SAMPLE_CAP)
        caps_applied.append("low_sample_cap")

    adjustment = round(adjustment, 4)
    top_edges = sorted((_edge_summary(edge) for edge in matched_edges), key=lambda edge: abs(edge["statistical_weight"]), reverse=True)[:5]
    return {
        "optimizer_adjustment": adjustment,
        "matched_positive_edges": positive_edges,
        "matched_negative_edges": negative_edges,
        "top_edges": top_edges,
        "confidence": confidence,
        "matched_edges_count": len(matched_edges),
        "min_evidence_count": min_evidence if matched_edges else 0,
        "conflict_reduced": conflict_reduced,
        "caps_applied": caps_applied,
        "hypothetical_score": round(float(current_score) + adjustment, 4),
        "hypothetical_bias": optimizer_bias(adjustment),
    }


def optimizer_bias(adjustment: float | int) -> str:
    value = float(adjustment)
    if value >= 10:
        return "STRONG_PRIORITIZE"
    if value >= 5:
        return "PRIORITIZE"
    if value <= -10:
        return "STRONG_AVOID"
    if value <= -5:
        return "CAUTION"
    return "NEUTRAL"


def _adjusted_weight(edge: dict[str, Any]) -> float:
    weight = _weight(edge)
    context = edge.get("context", {})
    specificity = len(context) if isinstance(context, dict) else 1
    evidence = _evidence(edge)
    return weight * min(1.25, 0.85 + specificity * 0.1) * min(1.15, 0.75 + evidence / 120.0)


def _edge_summary(edge: dict[str, Any]) -> dict[str, Any]:
    return {
        "unique_id": edge.get("unique_id"),
        "category": edge.get("category"),
        "context": edge.get("context", {}),
        "statistical_weight": _weight(edge),
        "confidence": str(edge.get("confidence") or "LOW").upper(),
        "evidence_count": _evidence(edge),
        "metrics": edge.get("metrics", {}),
    }


def _combined_confidence(edges: list[dict[str, Any]]) -> str:
    if not edges:
        return "LOW"
    confidence_values = {str(edge.get("confidence") or "LOW").upper() for edge in edges}
    if "HIGH" in confidence_values:
        return "HIGH"
    if "MEDIUM" in confidence_values:
        return "MEDIUM"
    return "LOW"


def _min_evidence(edges: list[dict[str, Any]]) -> int:
    if not edges:
        return 0
    return min(_evidence(edge) for edge in edges)


def _weight(edge: dict[str, Any]) -> float:
    return _float(edge.get("statistical_weight")) or 0.0


def _evidence(edge: dict[str, Any]) -> int:
    return int(_float(edge.get("evidence_count")) or 0)


def _cap(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
