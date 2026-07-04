from __future__ import annotations

from typing import Any


def discover_positive_edges(groups: list[dict[str, Any]], *, min_trades: int = 20, limit: int = 50) -> list[dict[str, Any]]:
    candidates = [
        _edge(item, "POSITIVE_EDGE")
        for item in groups
        if int(item.get("closed", 0)) >= min_trades
        and float(item.get("profit_factor", 0.0)) > 1.2
        and float(item.get("total_r", 0.0)) > 0
    ]
    return sorted(candidates, key=lambda item: (float(item["profit_factor"]), float(item["total_r"])), reverse=True)[:limit]


def discover_negative_edges(groups: list[dict[str, Any]], *, min_trades: int = 20, limit: int = 50) -> list[dict[str, Any]]:
    candidates = [
        _edge(item, "NEGATIVE_EDGE")
        for item in groups
        if int(item.get("closed", 0)) >= min_trades
        and float(item.get("profit_factor", 0.0)) < 0.85
        and float(item.get("total_r", 0.0)) < 0
    ]
    return sorted(candidates, key=lambda item: (float(item["total_r"]), float(item["profit_factor"])))[:limit]


def _edge(item: dict[str, Any], edge_type: str) -> dict[str, Any]:
    return {
        "edge_type": edge_type,
        "dimension": item.get("dimension"),
        "dimensions": item.get("dimensions"),
        "value": item.get("value"),
        "context": item.get("context", {}),
        "label": item.get("label") or f"{item.get('dimension')}={item.get('value')}",
        "trades": item.get("trades", 0),
        "closed": item.get("closed", 0),
        "winrate": item.get("winrate", 0.0),
        "profit_factor": item.get("profit_factor", 0.0),
        "total_r": item.get("total_r", 0.0),
        "avg_r": item.get("avg_r", 0.0),
        "expectancy": item.get("expectancy", 0.0),
        "confidence": item.get("confidence", "LOW"),
        "evidence_count": item.get("evidence_count", 0),
    }
