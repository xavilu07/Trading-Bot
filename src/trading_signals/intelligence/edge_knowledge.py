from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_REPORT_PATH = Path("reports") / "performance_intelligence_report_v2.json"
DEFAULT_KNOWLEDGE_PATH = Path("data") / "edge_knowledge" / "knowledge_v1.json"
DEFAULT_SOURCE_REPORT = "reports/performance_intelligence_report_v2.json"

CONFIDENCE_MULTIPLIERS = {
    "HIGH": 1.0,
    "MEDIUM": 0.75,
    "LOW": 0.45,
}


def build_edge_knowledge_from_report(
    report_path: Path = DEFAULT_REPORT_PATH,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    report = _read_json(report_path)
    generated = generated_at or datetime.now(UTC).isoformat(timespec="seconds")
    priority_edges = _extract_priority_edges(report)
    avoid_edges = _extract_avoid_edges(report)
    watch_edges = _extract_watch_edges(report)
    all_edges = [
        *_build_edges(priority_edges, category="priority_edges", source_report=str(report_path), generated_at=generated),
        *_build_edges(avoid_edges, category="avoid_edges", source_report=str(report_path), generated_at=generated),
        *_build_edges(watch_edges, category="watch_edges", source_report=str(report_path), generated_at=generated),
    ]
    return {
        "schema_version": "1.0",
        "generated_at": generated,
        "source_report": str(report_path),
        "priority_edges": [edge for edge in all_edges if edge["category"] == "priority_edges"],
        "avoid_edges": [edge for edge in all_edges if edge["category"] == "avoid_edges"],
        "watch_edges": [edge for edge in all_edges if edge["category"] == "watch_edges"],
        "edges": all_edges,
        "summary": {
            "priority_edges": len(priority_edges),
            "avoid_edges": len(avoid_edges),
            "watch_edges": len(watch_edges),
            "total_edges": len(all_edges),
        },
    }


def write_edge_knowledge(
    *,
    report_path: Path = DEFAULT_REPORT_PATH,
    output_path: Path = DEFAULT_KNOWLEDGE_PATH,
    reports_path: Path = Path("reports"),
) -> dict[str, Path]:
    knowledge = build_edge_knowledge_from_report(report_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(knowledge, indent=2, sort_keys=True), encoding="utf-8")

    reports_path.mkdir(parents=True, exist_ok=True)
    report_json = reports_path / "edge_knowledge_v1.json"
    report_md = reports_path / "edge_knowledge_v1.md"
    report_json.write_text(json.dumps(knowledge, indent=2, sort_keys=True), encoding="utf-8")
    report_md.write_text(format_edge_knowledge_markdown(knowledge), encoding="utf-8")
    return {"knowledge": output_path, "json": report_json, "markdown": report_md}


def load_edge_knowledge(path: Path = DEFAULT_KNOWLEDGE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": "1.0",
            "generated_at": None,
            "source_report": str(DEFAULT_SOURCE_REPORT),
            "priority_edges": [],
            "avoid_edges": [],
            "watch_edges": [],
            "edges": [],
            "summary": {"priority_edges": 0, "avoid_edges": 0, "watch_edges": 0, "total_edges": 0},
        }
    return _read_json(path)


def evaluate_context(context: dict[str, Any], knowledge: dict[str, Any] | None = None) -> dict[str, Any]:
    data = knowledge if knowledge is not None else load_edge_knowledge()
    edges = data.get("edges", [])
    if not isinstance(edges, list):
        edges = []
    matched = [edge for edge in edges if _edge_matches_context(edge, context)]
    bonus = _combined_bonus(matched)
    return {
        "bonus": bonus,
        "matched_edges": matched,
        "confidence": _combined_confidence(matched),
    }


def format_edge_knowledge_markdown(knowledge: dict[str, Any]) -> str:
    summary = knowledge.get("summary", {})
    lines = [
        "# Edge Knowledge Base V1",
        "",
        f"Generated at: {knowledge.get('generated_at')}",
        f"Source report: `{knowledge.get('source_report')}`",
        "",
        "## Summary",
        "",
        f"- Priority edges: {summary.get('priority_edges', 0)}",
        f"- Avoid edges: {summary.get('avoid_edges', 0)}",
        f"- Watch edges: {summary.get('watch_edges', 0)}",
        f"- Total edges: {summary.get('total_edges', 0)}",
        "",
        "## Priority Edges",
        "",
        _edge_table(knowledge.get("priority_edges", [])),
        "",
        "## Avoid Edges",
        "",
        _edge_table(knowledge.get("avoid_edges", [])),
        "",
        "## Watch Edges",
        "",
        _edge_table(knowledge.get("watch_edges", [])[:30]),
        "",
        "## API Contract",
        "",
        "`load_edge_knowledge()` loads `data/edge_knowledge/knowledge_v1.json`.",
        "`evaluate_context(context)` returns `{bonus, matched_edges, confidence}`.",
        "",
        "This layer is offline/shadow only and does not change production decisions.",
    ]
    return "\n".join(lines) + "\n"


def _extract_priority_edges(report: dict[str, Any]) -> list[dict[str, Any]]:
    rankings = report.get("rankings", {}) if isinstance(report.get("rankings"), dict) else {}
    actions = report.get("actionable_decisions", {}) if isinstance(report.get("actionable_decisions"), dict) else {}
    return _dedupe_rows(
        [
            *_rows(rankings.get("prioritize")),
            *_rows(actions.get("prioritize")),
            *_rows_by_hint(report, "PRIORITIZE"),
        ]
    )


def _extract_avoid_edges(report: dict[str, Any]) -> list[dict[str, Any]]:
    rankings = report.get("rankings", {}) if isinstance(report.get("rankings"), dict) else {}
    actions = report.get("actionable_decisions", {}) if isinstance(report.get("actionable_decisions"), dict) else {}
    return _dedupe_rows(
        [
            *_rows(rankings.get("avoid")),
            *_rows(actions.get("avoid")),
            *_rows_by_hint(report, "AVOID"),
        ]
    )


def _extract_watch_edges(report: dict[str, Any]) -> list[dict[str, Any]]:
    actions = report.get("actionable_decisions", {}) if isinstance(report.get("actionable_decisions"), dict) else {}
    rankings = report.get("rankings", {}) if isinstance(report.get("rankings"), dict) else {}
    return _dedupe_rows(
        [
            *_rows(actions.get("watch")),
            *_rows_by_hint(report, "WATCH"),
            *_rows(rankings.get("best_edges"))[:15],
            *_rows(rankings.get("worst_edges"))[:15],
        ]
    )


def _build_edges(
    rows: list[dict[str, Any]],
    *,
    category: str,
    source_report: str,
    generated_at: str,
) -> list[dict[str, Any]]:
    edges = []
    for row in rows:
        context = _context_from_row(row)
        statistical_weight = calculate_statistical_weight(row)
        edge = {
            "unique_id": _edge_id(category=category, context=context),
            "category": category,
            "context": context,
            "dimension": row.get("dimension", ""),
            "value": row.get("value", ""),
            "statistical_weight": statistical_weight,
            "confidence": str(row.get("confidence") or "LOW").upper(),
            "evidence_count": _evidence_count(row),
            "last_generated": generated_at,
            "source_report": source_report,
            "metrics": {
                "n": _evidence_count(row),
                "profit_factor": _metric_value(row, "profit_factor", "PF", "pf"),
                "totalR": _round(_float(_metric_value(row, "totalR", "total_r", "TotalR")) or 0.0),
                "avgR": _round(_float(_metric_value(row, "avgR", "avg_r", "AvgR")) or 0.0),
                "winrate": _round(_float(_metric_value(row, "winrate", "WR", "wr")) or 0.0),
                "decision_hint": _decision_hint(row),
            },
        }
        edges.append(edge)
    return edges


def calculate_statistical_weight(row: dict[str, Any]) -> float:
    pf = _pf_float(_metric_value(row, "profit_factor", "PF", "pf"))
    total_r = _float(_metric_value(row, "totalR", "total_r", "TotalR")) or 0.0
    avg_r = _float(_metric_value(row, "avgR", "avg_r", "AvgR")) or 0.0
    n = _evidence_count(row)
    confidence = str(row.get("confidence") or "LOW").upper()
    sample_factor = min(1.0, max(0.15, n / 60.0))
    confidence_factor = CONFIDENCE_MULTIPLIERS.get(confidence, 0.45)

    pf_component = max(-10.0, min(10.0, (pf - 1.0) * 8.0))
    total_component = max(-7.5, min(7.5, total_r / 2.0))
    avg_component = max(-5.0, min(5.0, avg_r * 12.0))
    sample_component = max(-2.5, min(2.5, (n - 15) / 18.0))
    raw = pf_component + total_component + avg_component + sample_component
    return _round(max(-25.0, min(25.0, raw * sample_factor * confidence_factor)))


def _context_from_row(row: dict[str, Any]) -> dict[str, str]:
    dimension = str(row.get("dimension") or "").strip()
    value = str(row.get("value") or "").strip()
    fields = [part.strip() for part in dimension.split("+") if part.strip()]
    values = [part.strip() for part in value.split("+") if part.strip()]
    if not fields:
        return {}
    if len(fields) != len(values):
        return {dimension: value}
    return {field: values[index] for index, field in enumerate(fields)}


def _edge_matches_context(edge: dict[str, Any], context: dict[str, Any]) -> bool:
    edge_context = edge.get("context", {})
    if not isinstance(edge_context, dict) or not edge_context:
        return False
    normalized = {_normalize_key(key): _normalize_value(value) for key, value in context.items()}
    for key, value in edge_context.items():
        normalized_key = _normalize_key(key)
        if normalized.get(normalized_key) != _normalize_value(value):
            return False
    return True


def _combined_bonus(matched: list[dict[str, Any]]) -> int:
    if not matched:
        return 0
    total = 0.0
    for edge in matched:
        weight = _float(edge.get("statistical_weight")) or 0.0
        evidence = int(_float(edge.get("evidence_count")) or 0)
        specificity = len(edge.get("context", {})) if isinstance(edge.get("context"), dict) else 1
        total += weight * min(1.5, 0.8 + specificity * 0.15) * min(1.2, 0.7 + evidence / 100.0)
    return int(round(max(-25.0, min(25.0, total))))


def _combined_confidence(matched: list[dict[str, Any]]) -> str:
    if not matched:
        return "LOW"
    if any(str(edge.get("confidence")) == "HIGH" for edge in matched):
        return "HIGH"
    if any(str(edge.get("confidence")) == "MEDIUM" for edge in matched):
        return "MEDIUM"
    return "LOW"


def _edge_table(edges: object) -> str:
    rows = _rows(edges)
    if not rows:
        return "_No edges._"
    lines = [
        "| ID | Context | Weight | Confidence | Evidence | PF | TotalR | AvgR | Hint |",
        "|---|---|---:|---|---:|---:|---:|---:|---|",
    ]
    for edge in rows:
        metrics = edge.get("metrics", {}) if isinstance(edge.get("metrics"), dict) else {}
        lines.append(
            f"| `{edge.get('unique_id', '')}` | {edge.get('context', {})} | {edge.get('statistical_weight', 0)} | "
            f"{edge.get('confidence', '')} | {edge.get('evidence_count', 0)} | {metrics.get('profit_factor', 0)} | "
            f"{metrics.get('totalR', 0)} | {metrics.get('avgR', 0)} | {metrics.get('decision_hint', '')} |"
        )
    return "\n".join(lines)


def _edge_id(*, category: str, context: dict[str, str]) -> str:
    raw = json.dumps({"category": category, "context": context}, sort_keys=True)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"edge_v1_{digest}"


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped = []
    for row in rows:
        key = (str(row.get("dimension")), str(row.get("value")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _rows_by_hint(report: dict[str, Any], hint: str) -> list[dict[str, Any]]:
    target = hint.strip().upper()
    return [
        row
        for row in _collect_metric_rows(report)
        if _decision_hint(row) == target
    ]


def _collect_metric_rows(value: object) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if _is_metric_row(value):
            rows.append(value)
        for child in value.values():
            rows.extend(_collect_metric_rows(child))
    elif isinstance(value, list):
        for child in value:
            rows.extend(_collect_metric_rows(child))
    return rows


def _is_metric_row(row: dict[str, Any]) -> bool:
    return bool(row.get("dimension")) and bool(row.get("value")) and bool(_decision_hint(row))


def _decision_hint(row: dict[str, Any]) -> str:
    return str(row.get("decision_hint") or row.get("hint") or row.get("action") or "").strip().upper()


def _evidence_count(row: dict[str, Any]) -> int:
    return int(_float(_metric_value(row, "n", "trades", "closed_trades", "sample_size", "evidence_count")) or 0)


def _metric_value(row: dict[str, Any], *keys: str) -> object:
    for key in keys:
        if key in row and _has_value(row.get(key)):
            return row.get(key)
    metrics = row.get("metrics")
    if isinstance(metrics, dict):
        for key in keys:
            if key in metrics and _has_value(metrics.get(key)):
                return metrics.get(key)
    return None


def _has_value(value: object) -> bool:
    return value is not None and str(value) != ""


def _rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _normalize_key(value: object) -> str:
    return str(value or "").strip().lower()


def _normalize_value(value: object) -> str:
    return str(value or "").strip().lower()


def _pf_float(value: object) -> float:
    if value == "inf":
        return 4.0
    parsed = _float(value)
    return 0.0 if parsed is None else parsed


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float) -> float:
    return round(value, 4)
