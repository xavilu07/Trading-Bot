from __future__ import annotations

from itertools import combinations
from typing import Any

from trading_signals.research.statistics import combination_metrics, group_metrics


def feature_importance(rows: list[dict[str, Any]], features: list[str], *, min_trades: int = 10) -> list[dict[str, Any]]:
    output = []
    for feature in features:
        groups = group_metrics(rows, feature, min_trades=min_trades)
        if not groups:
            continue
        best = max(groups, key=lambda item: (item["profit_factor"], item["total_r"]))
        worst = min(groups, key=lambda item: (item["profit_factor"], item["total_r"]))
        output.append(
            {
                "feature": feature,
                "groups": len(groups),
                "best_value": best["value"],
                "best_pf": best["profit_factor"],
                "best_total_r": best["total_r"],
                "worst_value": worst["value"],
                "worst_pf": worst["profit_factor"],
                "worst_total_r": worst["total_r"],
                "importance_score": round((best["profit_factor"] - worst["profit_factor"]) + abs(best["total_r"] - worst["total_r"]) / 10, 4),
                "top_groups": groups[:10],
            }
        )
    return sorted(output, key=lambda item: item["importance_score"], reverse=True)


def discover_edges(
    rows: list[dict[str, Any]],
    features: list[str],
    *,
    min_trades: int = 20,
    max_features: int = 4,
) -> dict[str, Any]:
    combinations_out: dict[str, list[dict[str, Any]]] = {}
    for size in range(2, max_features + 1):
        discovered = []
        for combo in combinations(features, size):
            discovered.extend(combination_metrics(rows, combo, min_trades=min_trades))
        combinations_out[f"{size}_feature_edges"] = sorted(
            discovered,
            key=lambda item: (item["profit_factor"], item["expectancy"], item["total_r"]),
            reverse=True,
        )[:100]
    all_edges = [edge for edges in combinations_out.values() for edge in edges]
    return {
        **combinations_out,
        "top_by_pf": sorted(all_edges, key=lambda item: item["profit_factor"], reverse=True)[:50],
        "top_by_expectancy": sorted(all_edges, key=lambda item: item["expectancy"], reverse=True)[:50],
        "top_by_total_r": sorted(all_edges, key=lambda item: item["total_r"], reverse=True)[:50],
        "worst_by_total_r": sorted(all_edges, key=lambda item: item["total_r"])[:50],
    }
