from __future__ import annotations

from typing import Any

from trading_signals.research.statistics import compute_metrics, group_metrics, pearson, rounded, to_float


def analyze_correlations(rows: list[dict[str, Any]], features: dict[str, list[str]]) -> dict[str, Any]:
    closed = [row for row in rows if to_float(row.get("result_r")) is not None]
    numeric = [_numeric_correlation(closed, feature) for feature in features["numeric"]]
    categorical = [_categorical_correlation(closed, feature) for feature in features["categorical"]]
    all_items = [item for item in [*numeric, *categorical] if item["evidence"] > 0]
    ranked = sorted(all_items, key=lambda item: abs(item["correlation_score"]), reverse=True)
    return {
        "ranked": ranked,
        "positive": [item for item in ranked if item["correlation_score"] > 0],
        "negative": [item for item in ranked if item["correlation_score"] < 0],
    }


def _numeric_correlation(rows: list[dict[str, Any]], feature: str) -> dict[str, Any]:
    pairs = [(to_float(row.get(feature)), to_float(row.get("result_r"))) for row in rows]
    valid = [(x, y) for x, y in pairs if x is not None and y is not None]
    score = pearson([x for x, _ in valid], [y for _, y in valid])
    return {
        "feature": feature,
        "type": "numeric",
        "correlation_score": rounded(score),
        "evidence": len(valid),
        "interpretation": "positive" if score > 0 else "negative" if score < 0 else "neutral",
    }


def _categorical_correlation(rows: list[dict[str, Any]], feature: str) -> dict[str, Any]:
    groups = group_metrics(rows, feature, min_trades=5)
    global_pf = compute_metrics(rows)["profit_factor"]
    if not groups:
        return {
            "feature": feature,
            "type": "categorical",
            "correlation_score": 0.0,
            "evidence": 0,
            "best_value": None,
            "worst_value": None,
        }
    best = max(groups, key=lambda item: (item["profit_factor"], item["total_r"]))
    worst = min(groups, key=lambda item: (item["profit_factor"], item["total_r"]))
    score = (best["profit_factor"] - worst["profit_factor"]) / max(abs(global_pf), 1.0)
    if abs(worst["profit_factor"] - global_pf) > abs(best["profit_factor"] - global_pf):
        score = -abs(score)
    return {
        "feature": feature,
        "type": "categorical",
        "correlation_score": rounded(score),
        "evidence": sum(item["closed"] for item in groups),
        "best_value": best["value"],
        "best_pf": best["profit_factor"],
        "worst_value": worst["value"],
        "worst_pf": worst["profit_factor"],
        "interpretation": "positive" if score > 0 else "negative" if score < 0 else "neutral",
    }
