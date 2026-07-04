from __future__ import annotations

from typing import Any

from trading_signals.research.statistics import compute_metrics, normalize_group_value


def auto_clusters(rows: list[dict[str, Any]], features: list[str], *, min_trades: int = 10) -> dict[str, Any]:
    signatures: dict[str, list[dict[str, Any]]] = {}
    usable = features[:8]
    for row in rows:
        values = [normalize_group_value(row.get(feature)) for feature in usable]
        known = [f"{feature}={value}" for feature, value in zip(usable, values, strict=True) if value != "UNKNOWN"]
        if len(known) < 3:
            continue
        signature = " | ".join(known[:5])
        signatures.setdefault(signature, []).append(row)
    clusters = []
    for signature, cluster_rows in signatures.items():
        metrics = compute_metrics(cluster_rows)
        if metrics["closed"] < min_trades:
            continue
        clusters.append({"cluster": signature, **metrics})
    ranked = sorted(clusters, key=lambda item: (item["profit_factor"], item["total_r"]), reverse=True)
    return {
        "clusters": ranked,
        "positive_clusters": [item for item in ranked if item["profit_factor"] > 1.2 and item["total_r"] > 0],
        "negative_clusters": [item for item in ranked if item["profit_factor"] < 0.85 and item["total_r"] < 0],
    }


def outliers(rows: list[dict[str, Any]], *, limit: int = 25) -> dict[str, Any]:
    closed = [row for row in rows if row.get("result_r") is not None]
    sorted_rows = sorted(closed, key=lambda row: row.get("result_r") or 0.0)
    return {
        "best_trades": [_outlier_row(row) for row in reversed(sorted_rows[-limit:])],
        "worst_trades": [_outlier_row(row) for row in sorted_rows[:limit]],
    }


def _outlier_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "trade_id": row.get("trade_id"),
        "symbol": row.get("symbol"),
        "direction": row.get("direction"),
        "setup": row.get("setup"),
        "session": row.get("session"),
        "market_regime": row.get("market_regime"),
        "location": row.get("location"),
        "score": row.get("score"),
        "result_r": row.get("result_r"),
        "status": row.get("status"),
    }
