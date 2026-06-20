from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any


CLOSED_STATUSES = {"expired", "sl_hit", "tp1_hit", "tp2_hit"}
GROUP_DEFINITIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("direction", ("direction",)),
    ("symbol", ("symbol",)),
    ("market_regime", ("market_regime",)),
    ("session", ("session",)),
    ("entry_context", ("entry_context",)),
    ("trade_location", ("trade_location",)),
    ("direction+session", ("direction", "session")),
    ("direction+entry_context", ("direction", "entry_context")),
    ("direction+market_regime", ("direction", "market_regime")),
    ("market_regime+entry_context", ("market_regime", "entry_context")),
    ("direction+market_regime+entry_context", ("direction", "market_regime", "entry_context")),
    ("symbol+direction", ("symbol", "direction")),
    ("symbol+direction+market_regime", ("symbol", "direction", "market_regime")),
    ("direction+session+entry_context", ("direction", "session", "entry_context")),
)


def build_edge_memory(data_path: Path, min_sample_size: int = 15) -> dict[str, Any]:
    rows = _read_closed_trades(data_path / "paper_trading" / "trades.csv")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for group_name, fields in GROUP_DEFINITIONS:
            values = tuple(_context_value(row, field) for field in fields)
            if any(value in {"", "unknown"} for value in values):
                continue
            groups[_edge_key(group_name, fields, values)].append(row)

    edges = []
    for key, items in groups.items():
        metrics = _metrics(items)
        group_name, values = _parse_edge_key(key)
        edge = {
            "key": key,
            "group": group_name,
            "values": values,
            **metrics,
            "edge_score": _edge_score(metrics),
            "edge_grade": _edge_grade(_edge_score(metrics)),
            "confidence": _confidence(metrics["sample_size"], min_sample_size=min_sample_size),
            "meets_min_sample": metrics["sample_size"] >= min_sample_size,
        }
        edges.append(edge)

    edges.sort(key=lambda item: (item["meets_min_sample"], item["edge_score"], item["sample_size"]), reverse=True)
    return {
        "version": "EDGE_MEMORY_V1",
        "data_file": str(data_path / "paper_trading" / "trades.csv"),
        "closed_trades": len(rows),
        "min_sample_size": min_sample_size,
        "groups": {edge["key"]: edge for edge in edges},
    }


def evaluate_edge_for_context(data_path: Path, context: dict[str, Any]) -> dict[str, Any]:
    memory = build_edge_memory(data_path)
    min_sample_size = int(memory.get("min_sample_size", 15) or 15)
    matched_edges = []
    for group_name, fields in GROUP_DEFINITIONS:
        values = tuple(_context_value(context, field) for field in fields)
        if any(value in {"", "unknown"} for value in values):
            continue
        edge = memory["groups"].get(_edge_key(group_name, fields, values))
        if isinstance(edge, dict) and int(edge.get("sample_size", 0) or 0) >= min_sample_size:
            matched_edges.append(edge)

    if not matched_edges:
        return {
            "available": bool(memory.get("closed_trades", 0)),
            "source": "EDGE_MEMORY_V1",
            "matched_patterns_count": 0,
            "historical_edge_score": 50,
            "historical_confidence": "LOW",
            "matched_edges": [],
            "best_edge": None,
            "worst_edge": None,
        }

    best = max(
        matched_edges,
        key=lambda item: (
            int(item.get("edge_score", 50)),
            len(item.get("values", {}) if isinstance(item.get("values"), dict) else {}),
            int(item.get("sample_size", 0)),
        ),
    )
    worst = min(
        matched_edges,
        key=lambda item: (
            int(item.get("edge_score", 50)),
            -len(item.get("values", {}) if isinstance(item.get("values"), dict) else {}),
            -int(item.get("sample_size", 0)),
        ),
    )
    matched_count = max(int(item.get("sample_size", 0) or 0) for item in matched_edges)
    return {
        "available": True,
        "source": "EDGE_MEMORY_V1",
        "matched_patterns_count": matched_count,
        "historical_edge_score": int(best.get("edge_score", 50)),
        "historical_confidence": _confidence(matched_count, min_sample_size=min_sample_size),
        "matched_edges": matched_edges,
        "best_edge": best,
        "worst_edge": worst,
    }


def _read_closed_trades(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = [dict(row) for row in csv.DictReader(handle)]
    except csv.Error:
        return []
    return [row for row in rows if str(row.get("status") or "").strip().lower() in CLOSED_STATUSES and _float(row.get("result_r")) is not None]


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [_float(row.get("result_r")) for row in rows]
    values = [value for value in values if value is not None]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    gross_profit = sum(max(0.0, value) for value in values)
    gross_loss = abs(sum(min(0.0, value) for value in values))
    return {
        "sample_size": len(values),
        "winrate": _round(len(wins) / len(values) * 100) if values else 0.0,
        "avg_r": _round(sum(values) / len(values)) if values else 0.0,
        "total_r": _round(sum(values)),
        "profit_factor": _profit_factor(gross_profit, gross_loss),
    }


def _edge_score(metrics: dict[str, Any]) -> int:
    score = 50
    profit_factor = _pf_float(metrics.get("profit_factor"))
    avg_r = float(metrics.get("avg_r", 0.0) or 0.0)
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    winrate = float(metrics.get("winrate", 0.0) or 0.0)

    if profit_factor >= 2:
        score += 18
    elif profit_factor >= 1.5:
        score += 10
    elif profit_factor < 0.75:
        score -= 18
    elif profit_factor < 0.95:
        score -= 10

    if avg_r > 0:
        score += 8
    elif avg_r < 0:
        score -= 8

    if total_r > 10:
        score += 8
    elif total_r < -10:
        score -= 8

    if winrate >= 52:
        score += 6
    elif winrate < 38:
        score -= 6

    return max(0, min(100, score))


def _edge_grade(score: int) -> str:
    if score >= 75:
        return "STRONG"
    if score >= 62:
        return "GOOD"
    if score >= 45:
        return "NEUTRAL"
    if score >= 32:
        return "WEAK"
    return "BAD"


def _confidence(sample_size: int, *, min_sample_size: int) -> str:
    if sample_size >= 80:
        return "HIGH"
    if sample_size >= min_sample_size:
        return "MEDIUM"
    return "LOW"


def _edge_key(group_name: str, fields: tuple[str, ...], values: tuple[str, ...]) -> str:
    return f"{group_name}|" + "|".join(f"{field}={value}" for field, value in zip(fields, values, strict=True))


def _parse_edge_key(key: str) -> tuple[str, dict[str, str]]:
    group_name, *parts = key.split("|")
    values = {}
    for part in parts:
        if "=" in part:
            field, value = part.split("=", 1)
            values[field] = value
    return group_name, values


def _context_value(row: dict[str, Any], field: str) -> str:
    aliases = {
        "direction": ("direction",),
        "symbol": ("symbol",),
        "market_regime": ("market_regime",),
        "session": ("session",),
        "entry_context": ("entry_context",),
        "trade_location": ("trade_location",),
    }
    for key in aliases.get(field, (field,)):
        value = str(row.get(key) or "").strip()
        if value:
            return value.lower()
    return "unknown"


def _profit_factor(gross_profit: float, gross_loss: float) -> float | str:
    if gross_loss > 0:
        return _round(gross_profit / gross_loss)
    if gross_profit > 0:
        return "inf"
    return 0.0


def _pf_float(value: object) -> float:
    if value == "inf":
        return 999.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float) -> float:
    rounded = round(value, 4)
    return 0.0 if rounded == 0 else rounded
