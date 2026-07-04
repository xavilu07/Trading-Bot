from __future__ import annotations

from itertools import combinations
from typing import Any

from trading_signals.intelligence.historical_intelligence.metrics import compute_metrics, group_by_dimensions


DNA_DIMENSIONS = (
    "symbol",
    "direction",
    "setup_type",
    "session",
    "market_regime",
    "entry_context",
    "trade_location",
    "score_bucket",
)


def build_dna_profiles(rows: list[dict[str, Any]], *, min_trades: int = 10, limit: int = 100) -> dict[str, Any]:
    profiles: list[dict[str, Any]] = []
    for size in (3, 4):
        for dims in combinations(DNA_DIMENSIONS, size):
            for item in group_by_dimensions(rows, dims, min_trades=min_trades):
                profile = {
                    "profile": item["context"],
                    "label": item["label"],
                    "historical_confidence": item["confidence"],
                    "profit_factor": item["profit_factor"],
                    "winrate": item["winrate"],
                    "holding": _holding_summary(rows, item["context"]),
                    "drawdown": item["max_drawdown"],
                    "expected_r": item["expectancy"],
                    "total_r": item["total_r"],
                    "evidence": item["evidence_count"],
                    "classification": _classification(item),
                }
                profiles.append(profile)
    profiles = sorted(
        profiles,
        key=lambda item: (float(item["profit_factor"]), float(item["total_r"]), int(item["evidence"])),
        reverse=True,
    )[:limit]
    return {
        "profiles": profiles,
        "top_elite": [item for item in profiles if item["classification"] == "ELITE"][:20],
        "top_negative": sorted(
            [item for item in profiles if float(item["total_r"]) < 0],
            key=lambda item: (float(item["total_r"]), float(item["profit_factor"])),
        )[:20],
    }


def _classification(item: dict[str, Any]) -> str:
    pf = float(item.get("profit_factor", 0.0))
    total_r = float(item.get("total_r", 0.0))
    if pf >= 1.8 and total_r > 0:
        return "ELITE"
    if pf >= 1.4 and total_r > 0:
        return "STRONG"
    if pf >= 1.2 and total_r > 0:
        return "PROMISING"
    if pf < 0.85 and total_r < 0:
        return "NEGATIVE"
    return "NEUTRAL"


def _holding_summary(rows: list[dict[str, Any]], context: dict[str, str]) -> dict[str, Any]:
    matching = [
        row
        for row in rows
        if all(str(row.get(key) or "UNKNOWN") == str(value) for key, value in context.items())
    ]
    values = []
    for row in matching:
        try:
            values.append(float(row.get("candles_held") or row.get("bars_held") or 0))
        except (TypeError, ValueError):
            continue
    return compute_metrics(matching) | {
        "avg_candles_held": round(sum(values) / len(values), 4) if values else 0.0,
    }
