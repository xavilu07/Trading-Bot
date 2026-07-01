#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


DEFAULT_LOG_FILE = Path("logs") / "scheduler.log"
DEFAULT_REPORT_JSON = Path("reports") / "edge_knowledge_shadow_v1.json"
DEFAULT_REPORT_MD = Path("reports") / "edge_knowledge_shadow_v1.md"


def load_shadow_events(log_file: Path = DEFAULT_LOG_FILE) -> list[dict[str, Any]]:
    if not log_file.exists():
        return []
    events = []
    for line in log_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        payload = _parse_json_line(line)
        if payload and payload.get("event") == "edge_knowledge_shadow_decision":
            events.append(payload)
    return events


def analyze_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    bonuses = [_float(event.get("ekb_bonus")) or 0.0 for event in events]
    bias_counts = Counter(str(event.get("hypothetical_bias") or "UNKNOWN") for event in events)
    matched_edges = _matched_edge_summary(events)
    by_dimension = {
        "symbol": _group_events(events, "symbol"),
        "direction": _group_events(events, "direction"),
        "session": _group_context(events, "session"),
        "market_regime": _group_context(events, "market_regime"),
    }
    disagreements = _disagreements(events)
    result = {
        "total_shadow_evaluations": len(events),
        "avg_ekb_bonus": round(mean(bonuses), 4) if bonuses else 0.0,
        "bias_counts": dict(bias_counts),
        "top_matched_edges": matched_edges,
        "candidates_where_ekb_disagrees_with_legacy": disagreements,
        "high_score_rejected_ekb_positive": _high_score_rejected_ekb_positive(events),
        "low_score_accepted_ekb_negative": _low_score_accepted_ekb_negative(events),
        "duplicate_signal_suppressed_ekb_positive": _duplicate_signal_suppressed_ekb_positive(events),
        "by_dimension": by_dimension,
    }
    return result


def write_reports(
    analysis: dict[str, Any],
    *,
    report_json: Path = DEFAULT_REPORT_JSON,
    report_md: Path = DEFAULT_REPORT_MD,
) -> dict[str, Path]:
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(analysis, indent=2, sort_keys=True), encoding="utf-8")
    report_md.write_text(format_markdown(analysis), encoding="utf-8")
    return {"json": report_json, "markdown": report_md}


def format_markdown(analysis: dict[str, Any]) -> str:
    lines = [
        "# Edge Knowledge Shadow V1",
        "",
        f"- Total shadow evaluations: {analysis.get('total_shadow_evaluations', 0)}",
        f"- Avg EKB bonus: {analysis.get('avg_ekb_bonus', 0)}",
        "",
        "## Bias Counts",
        "",
        _counter_table(analysis.get("bias_counts", {}), "Bias"),
        "",
        "## Top Matched Edges",
        "",
        _edge_table(analysis.get("top_matched_edges", [])),
        "",
        "## Disagreements",
        "",
        f"- Candidates where EKB disagrees with legacy: {len(analysis.get('candidates_where_ekb_disagrees_with_legacy', []))}",
        f"- High score rejected + EKB positive: {len(analysis.get('high_score_rejected_ekb_positive', []))}",
        f"- Low score accepted + EKB negative: {len(analysis.get('low_score_accepted_ekb_negative', []))}",
        f"- duplicate_signal_suppressed + EKB positive: {len(analysis.get('duplicate_signal_suppressed_ekb_positive', []))}",
        "",
        "## By Dimension",
        "",
    ]
    by_dimension = analysis.get("by_dimension", {})
    if isinstance(by_dimension, dict):
        for dimension, rows in by_dimension.items():
            lines.extend([f"### {dimension}", "", _group_table(rows if isinstance(rows, list) else []), ""])
    lines.append("Shadow-only analysis. It does not modify scores or decisions.")
    return "\n".join(lines) + "\n"


def _parse_json_line(line: str) -> dict[str, Any] | None:
    raw = line.strip()
    if not raw:
        return None
    candidates = [raw]
    brace = raw.find("{")
    if brace > 0:
        candidates.append(raw[brace:])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _matched_edge_summary(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for event in events:
        edges = event.get("top_matched_edges", [])
        if not isinstance(edges, list):
            continue
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            edge_id = str(edge.get("unique_id") or edge.get("context") or "unknown")
            row = summary.setdefault(
                edge_id,
                {
                    "edge": edge_id,
                    "count": 0,
                    "context": edge.get("context", {}),
                    "category": edge.get("category"),
                    "weights": [],
                },
            )
            row["count"] += 1
            row["weights"].append(_float(edge.get("statistical_weight")) or 0.0)
    rows = []
    for row in summary.values():
        weights = row.pop("weights")
        row["avg_weight"] = round(mean(weights), 4) if weights else 0.0
        rows.append(row)
    return sorted(rows, key=lambda item: item["count"], reverse=True)[:20]


def _group_events(events: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return _group_by(events, lambda event: str(event.get(key) or "UNKNOWN"))


def _group_context(events: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return _group_by(
        events,
        lambda event: str((event.get("context") if isinstance(event.get("context"), dict) else {}).get(key) or "UNKNOWN"),
    )


def _group_by(events: list[dict[str, Any]], key_fn) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[key_fn(event)].append(event)
    rows = []
    for key, group in grouped.items():
        bonuses = [_float(event.get("ekb_bonus")) or 0.0 for event in group]
        rows.append(
            {
                "value": key,
                "count": len(group),
                "avg_bonus": round(mean(bonuses), 4) if bonuses else 0.0,
                "prioritize": sum(1 for event in group if event.get("hypothetical_bias") == "PRIORITIZE"),
                "avoid": sum(1 for event in group if event.get("hypothetical_bias") == "AVOID"),
                "neutral": sum(1 for event in group if event.get("hypothetical_bias") == "NEUTRAL"),
            }
        )
    return sorted(rows, key=lambda item: item["count"], reverse=True)


def _disagreements(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _event_summary(event)
        for event in events
        if (_is_not_send(event) and event.get("hypothetical_bias") == "PRIORITIZE")
        or (_is_send(event) and event.get("hypothetical_bias") == "AVOID")
    ]


def _high_score_rejected_ekb_positive(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _event_summary(event)
        for event in events
        if (_float(event.get("current_score")) or 0.0) >= 85
        and _is_not_send(event)
        and event.get("hypothetical_bias") == "PRIORITIZE"
    ]


def _low_score_accepted_ekb_negative(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _event_summary(event)
        for event in events
        if (_float(event.get("current_score")) or 0.0) < 70
        and _is_send(event)
        and event.get("hypothetical_bias") == "AVOID"
    ]


def _duplicate_signal_suppressed_ekb_positive(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _event_summary(event)
        for event in events
        if event.get("hypothetical_bias") == "PRIORITIZE"
        and any("duplicate_signal_suppressed" in str(reason) for reason in _rejection_reasons(event))
    ]


def _event_summary(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": event.get("symbol"),
        "direction": event.get("direction"),
        "setup_type": event.get("setup_type"),
        "current_decision": event.get("current_decision"),
        "current_score": event.get("current_score"),
        "ekb_bonus": event.get("ekb_bonus"),
        "hypothetical_bias": event.get("hypothetical_bias"),
        "rejection_reasons": _rejection_reasons(event),
    }


def _rejection_reasons(event: dict[str, Any]) -> list[Any]:
    reasons = event.get("rejection_reasons", [])
    return reasons if isinstance(reasons, list) else [reasons]


def _is_send(event: dict[str, Any]) -> bool:
    return str(event.get("current_decision") or "").strip().upper() in {"SEND", "LONG", "SHORT"}


def _is_not_send(event: dict[str, Any]) -> bool:
    return not _is_send(event)


def _counter_table(counter: object, label: str) -> str:
    if not isinstance(counter, dict) or not counter:
        return "_No data._"
    lines = [f"| {label} | Count |", "|---|---:|"]
    for key, value in sorted(counter.items(), key=lambda item: str(item[0])):
        lines.append(f"| {key} | {value} |")
    return "\n".join(lines)


def _edge_table(rows: object) -> str:
    if not isinstance(rows, list) or not rows:
        return "_No matched edges._"
    lines = ["| Edge | Count | Avg weight | Category | Context |", "|---|---:|---:|---|---|"]
    for row in rows[:20]:
        lines.append(
            f"| `{row.get('edge')}` | {row.get('count', 0)} | {row.get('avg_weight', 0)} | "
            f"{row.get('category') or ''} | {row.get('context', {})} |"
        )
    return "\n".join(lines)


def _group_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No data._"
    lines = ["| Value | Count | Avg bonus | PRIORITIZE | AVOID | NEUTRAL |", "|---|---:|---:|---:|---:|---:|"]
    for row in rows[:20]:
        lines.append(
            f"| {row.get('value')} | {row.get('count', 0)} | {row.get('avg_bonus', 0)} | "
            f"{row.get('prioritize', 0)} | {row.get('avoid', 0)} | {row.get('neutral', 0)} |"
        )
    return "\n".join(lines)


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Edge Knowledge shadow runtime logs.")
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG_FILE)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    args = parser.parse_args()

    events = load_shadow_events(args.log_file)
    analysis = analyze_events(events)
    paths = write_reports(analysis, report_json=args.report_json, report_md=args.report_md)
    print("Edge Knowledge Shadow V1")
    print(f"Total shadow evaluations: {analysis['total_shadow_evaluations']}")
    print(f"Avg EKB bonus: {analysis['avg_ekb_bonus']}")
    print(f"Report JSON: {paths['json']}")
    print(f"Report MD: {paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
