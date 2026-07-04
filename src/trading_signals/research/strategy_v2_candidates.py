from __future__ import annotations

from typing import Any


def generate_strategy_v2_candidates(
    feature_importance_rows: list[dict[str, Any]],
    edge_discovery: dict[str, Any],
) -> dict[str, Any]:
    candidates = []
    for item in feature_importance_rows:
        if item["worst_pf"] < 0.85 and item["worst_total_r"] < 0:
            candidates.append(
                _candidate(
                    action=_action_for_feature(item["feature"], negative=True),
                    context={item["feature"]: item["worst_value"]},
                    expected_improvement=abs(item["worst_total_r"]),
                    confidence=_confidence_from_group(item),
                    evidence=item["top_groups"][0]["closed"] if item.get("top_groups") else 0,
                    trades_affected=_find_group_closed(item, item["worst_value"]),
                    rationale=f"{item['feature']}={item['worst_value']} has PF {item['worst_pf']} and TotalR {item['worst_total_r']}",
                )
            )
        if item["best_pf"] > 1.3 and item["best_total_r"] > 0:
            candidates.append(
                _candidate(
                    action=_action_for_feature(item["feature"], negative=False),
                    context={item["feature"]: item["best_value"]},
                    expected_improvement=item["best_total_r"],
                    confidence=_confidence_from_group(item),
                    evidence=_find_group_closed(item, item["best_value"]),
                    trades_affected=_find_group_closed(item, item["best_value"]),
                    rationale=f"{item['feature']}={item['best_value']} has PF {item['best_pf']} and TotalR {item['best_total_r']}",
                )
            )
    for edge in edge_discovery.get("worst_by_total_r", [])[:10]:
        if edge["profit_factor"] < 0.85 and edge["total_r"] < 0:
            candidates.append(
                _candidate(
                    action="Eliminate context",
                    context=edge["context"],
                    expected_improvement=abs(edge["total_r"]),
                    confidence=edge["confidence"],
                    evidence=edge["closed"],
                    trades_affected=edge["closed"],
                    rationale=f"Multi-factor context loses {edge['total_r']}R with PF {edge['profit_factor']}",
                )
            )
    return {"candidates": sorted(candidates, key=lambda item: item["expected_improvement"], reverse=True)[:100]}


def _candidate(
    *,
    action: str,
    context: dict[str, Any],
    expected_improvement: float,
    confidence: str,
    evidence: int,
    trades_affected: int,
    rationale: str,
) -> dict[str, Any]:
    return {
        "action": action,
        "context": context,
        "expected_improvement": round(expected_improvement, 4),
        "confidence": confidence,
        "evidence": evidence,
        "trades_affected": trades_affected,
        "rationale": rationale,
    }


def _action_for_feature(feature: str, *, negative: bool) -> str:
    if feature == "symbol" and negative:
        return "Eliminar simbolo"
    if feature == "score_bucket":
        return "Cambiar score"
    if feature == "rr_bucket":
        return "Cambiar RR"
    if feature == "session":
        return "Cambiar sesion"
    if negative:
        return "Eliminar contexto"
    return "Priorizar contexto"


def _confidence_from_group(item: dict[str, Any]) -> str:
    evidence = max((group["closed"] for group in item.get("top_groups", [])), default=0)
    if evidence >= 80:
        return "HIGH"
    if evidence >= 30:
        return "MEDIUM"
    return "LOW"


def _find_group_closed(item: dict[str, Any], value: Any) -> int:
    for group in item.get("top_groups", []):
        if group["value"] == value:
            return group["closed"]
    return 0
