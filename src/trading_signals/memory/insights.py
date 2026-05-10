from __future__ import annotations

from collections import defaultdict


GROUP_FIELDS = (
    "direction",
    "setup_type",
    "market_regime",
    "session",
    "entry_context",
    "trade_location",
    "htf_trend",
    "ltf_trend",
    "warnings",
    "penalties",
    "blocking_reasons",
)


def build_pattern_memory_insights(records: list[dict[str, object]], *, min_cases: int = 5, limit: int = 3) -> dict[str, object]:
    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for record in records:
        if _to_float(record.get("r_result")) is None:
            continue
        for field in GROUP_FIELDS:
            for value in _group_values(record.get(field)):
                groups[(field, value)].append(record)

    positive = []
    negative = []
    for (field, value), items in groups.items():
        if len(items) < min_cases:
            continue
        stats = _stats(field, value, items)
        if stats["historical_winrate"] >= 60 and stats["historical_avg_r"] > 0:
            positive.append(stats)
        if stats["historical_winrate"] <= 40 and stats["historical_avg_r"] < 0:
            negative.append(stats)

    positive.sort(key=lambda item: (float(item["historical_avg_r"]), int(item["cases"])), reverse=True)
    negative.sort(key=lambda item: (float(item["historical_avg_r"]), -int(item["cases"])))
    return {
        "positive_patterns": positive[:limit],
        "negative_patterns": negative[:limit],
        "has_sufficient_data": bool(positive or negative),
    }


def _stats(field: str, value: str, items: list[dict[str, object]]) -> dict[str, object]:
    r_values = [float(item["r_result"]) for item in items if _to_float(item.get("r_result")) is not None]
    wins = [item for item in items if str(item.get("outcome", "")).lower() == "win"]
    return {
        "field": field,
        "value": value,
        "label": _label_for_group(items, field, value),
        "historical_winrate": round(len(wins) / len(items) * 100, 2),
        "historical_avg_r": round(sum(r_values) / len(r_values), 4) if r_values else 0.0,
        "cases": len(items),
    }


def _label_for_group(items: list[dict[str, object]], field: str, value: str) -> str:
    sample = items[0]
    direction = str(sample.get("direction", "")).upper()
    entry_context = str(sample.get("entry_context", "")).upper()
    market_regime = str(sample.get("market_regime", "")).upper()
    if field in {"warnings", "penalties", "blocking_reasons"}:
        return " | ".join(item for item in [direction, value, str(sample.get("trade_location", ""))] if item)
    return " | ".join(item for item in [direction, entry_context, market_regime] if item)


def _group_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _to_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
