#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


DEFAULT_LOG_FILE = Path("logs") / "scheduler.log"
DEFAULT_REPORT_JSON = Path("reports") / "edge_optimizer_shadow_v1.json"
DEFAULT_REPORT_MD = Path("reports") / "edge_optimizer_shadow_v1.md"


def load_shadow_events(log_file: Path = DEFAULT_LOG_FILE) -> list[dict[str, Any]]:
    if not log_file.exists():
        return []
    events = []
    for line in log_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        payload = _parse_json_line(line)
        if payload and payload.get("event") == "edge_optimizer_shadow_decision":
            events.append(payload)
    return events


def analyze_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    adjustments = [_float(event.get("optimizer_adjustment")) or 0.0 for event in events]
    result = {
        "total_evaluations": len(events),
        "avg_adjustment": round(mean(adjustments), 4) if adjustments else 0.0,
        "bias_counts": dict(Counter(str(event.get("hypothetical_bias") or "UNKNOWN") for event in events)),
        "top_positive_edges": _matched_edge_summary(events, "matched_positive_edges"),
        "top_negative_edges": _matched_edge_summary(events, "matched_negative_edges"),
        "high_score_rejected_optimizer_positive": _high_score_rejected_optimizer_positive(events),
        "duplicate_signal_suppressed_optimizer_positive": _duplicate_signal_suppressed_optimizer_positive(events),
        "accepted_valid_optimizer_negative": _accepted_valid_optimizer_negative(events),
        "legacy_disagreements": _legacy_disagreements(events),
        "by_dimension": {
            "symbol": _group_events(events, "symbol"),
            "direction": _group_events(events, "direction"),
            "session": _group_context(events, "session"),
            "market_regime": _group_context(events, "market_regime"),
            "entry_context": _group_context(events, "entry_context"),
        },
        "best_hypothetical_boosts": _rank_events(events, reverse=True),
        "worst_hypothetical_penalties": _rank_events(events, reverse=False),
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
        "# Edge Optimizer Shadow V1",
        "",
        "## Executive Summary",
        "",
        f"- Total evaluations: {analysis.get('total_evaluations', 0)}",
        f"- Avg adjustment: {analysis.get('avg_adjustment', 0)}",
        f"- Legacy disagreements: {len(analysis.get('legacy_disagreements', []))}",
        "",
        "## Optimizer Distribution",
        "",
        _counter_table(analysis.get("bias_counts", {}), "Bias"),
        "",
        "## Best Hypothetical Boosts",
        "",
        _event_table(analysis.get("best_hypothetical_boosts", [])),
        "",
        "## Worst Hypothetical Penalties",
        "",
        _event_table(analysis.get("worst_hypothetical_penalties", [])),
        "",
        "## Top Positive Edges",
        "",
        _edge_table(analysis.get("top_positive_edges", [])),
        "",
        "## Top Negative Edges",
        "",
        _edge_table(analysis.get("top_negative_edges", [])),
        "",
        "## Disagreements With Legacy",
        "",
        f"- High score rejected + optimizer positive: {len(analysis.get('high_score_rejected_optimizer_positive', []))}",
        f"- duplicate_signal_suppressed + optimizer positive: {len(analysis.get('duplicate_signal_suppressed_optimizer_positive', []))}",
        f"- Accepted/valid + optimizer negative: {len(analysis.get('accepted_valid_optimizer_negative', []))}",
        "",
        "## By Dimension",
        "",
    ]
    by_dimension = analysis.get("by_dimension", {})
    if isinstance(by_dimension, dict):
        for dimension, rows in by_dimension.items():
            lines.extend([f"### {dimension}", "", _group_table(rows if isinstance(rows, list) else []), ""])
    lines.extend(
        [
            "## Recommended Next Action",
            "",
            "Keep this layer in shadow mode until enough runtime events are available to compare optimizer bias against closed outcomes.",
            "",
            "## What NOT To Activate Yet",
            "",
            "- Do not modify current_score from optimizer_adjustment.",
            "- Do not unblock rejected candidates from optimizer PRIORITIZE.",
            "- Do not block accepted signals from optimizer CAUTION/STRONG_AVOID.",
            "- Do not route public Telegram based on this layer.",
            "",
        ]
    )
    return "\n".join(lines)


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


def _matched_edge_summary(events: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for event in events:
        edges = event.get(key, [])
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
                    "evidence": [],
                },
            )
            row["count"] += 1
            row["weights"].append(_float(edge.get("statistical_weight")) or 0.0)
            row["evidence"].append(_float(edge.get("evidence_count")) or 0.0)
    rows = []
    for row in summary.values():
        weights = row.pop("weights")
        evidence = row.pop("evidence")
        row["avg_weight"] = round(mean(weights), 4) if weights else 0.0
        row["avg_evidence"] = round(mean(evidence), 2) if evidence else 0.0
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
        adjustments = [_float(event.get("optimizer_adjustment")) or 0.0 for event in group]
        rows.append(
            {
                "value": key,
                "count": len(group),
                "avg_adjustment": round(mean(adjustments), 4) if adjustments else 0.0,
                "strong_prioritize": sum(1 for event in group if event.get("hypothetical_bias") == "STRONG_PRIORITIZE"),
                "prioritize": sum(1 for event in group if event.get("hypothetical_bias") == "PRIORITIZE"),
                "neutral": sum(1 for event in group if event.get("hypothetical_bias") == "NEUTRAL"),
                "caution": sum(1 for event in group if event.get("hypothetical_bias") == "CAUTION"),
                "strong_avoid": sum(1 for event in group if event.get("hypothetical_bias") == "STRONG_AVOID"),
            }
        )
    return sorted(rows, key=lambda item: item["count"], reverse=True)


def _high_score_rejected_optimizer_positive(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _event_summary(event)
        for event in events
        if (_float(event.get("current_score")) or 0.0) >= 85 and _is_not_send(event) and _is_positive(event)
    ]


def _duplicate_signal_suppressed_optimizer_positive(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _event_summary(event)
        for event in events
        if _is_positive(event) and any("duplicate_signal_suppressed" in str(reason) for reason in _rejection_reasons(event))
    ]


def _accepted_valid_optimizer_negative(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_event_summary(event) for event in events if _is_send(event) and _is_negative(event)]


def _legacy_disagreements(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _event_summary(event)
        for event in events
        if (_is_not_send(event) and _is_positive(event)) or (_is_send(event) and _is_negative(event))
    ]


def _rank_events(events: list[dict[str, Any]], *, reverse: bool) -> list[dict[str, Any]]:
    ranked = sorted(events, key=lambda event: _float(event.get("optimizer_adjustment")) or 0.0, reverse=reverse)
    return [_event_summary(event) for event in ranked[:20]]


def _event_summary(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": event.get("symbol"),
        "direction": event.get("direction"),
        "setup_type": event.get("setup_type"),
        "current_decision": event.get("current_decision"),
        "current_score": event.get("current_score"),
        "optimizer_adjustment": event.get("optimizer_adjustment"),
        "hypothetical_bias": event.get("hypothetical_bias"),
        "hypothetical_score": event.get("hypothetical_score"),
        "optimizer_confidence": event.get("optimizer_confidence"),
        "rejection_reasons": _rejection_reasons(event),
    }


def _is_positive(event: dict[str, Any]) -> bool:
    return str(event.get("hypothetical_bias") or "") in {"PRIORITIZE", "STRONG_PRIORITIZE"}


def _is_negative(event: dict[str, Any]) -> bool:
    return str(event.get("hypothetical_bias") or "") in {"CAUTION", "STRONG_AVOID"}


def _is_send(event: dict[str, Any]) -> bool:
    return str(event.get("current_decision") or "").strip().upper() in {"SEND", "LONG", "SHORT"}


def _is_not_send(event: dict[str, Any]) -> bool:
    return not _is_send(event)


def _rejection_reasons(event: dict[str, Any]) -> list[Any]:
    reasons = event.get("rejection_reasons", [])
    return reasons if isinstance(reasons, list) else [reasons]


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
    lines = ["| Edge | Count | Avg weight | Avg evidence | Category | Context |", "|---|---:|---:|---:|---|---|"]
    for row in rows[:20]:
        lines.append(
            f"| `{row.get('edge')}` | {row.get('count', 0)} | {row.get('avg_weight', 0)} | "
            f"{row.get('avg_evidence', 0)} | {row.get('category') or ''} | {row.get('context', {})} |"
        )
    return "\n".join(lines)


def _event_table(rows: object) -> str:
    if not isinstance(rows, list) or not rows:
        return "_No data._"
    lines = ["| Symbol | Direction | Decision | Score | Adj | Hyp score | Bias | Reasons |", "|---|---|---|---:|---:|---:|---|---|"]
    for row in rows[:20]:
        lines.append(
            f"| {row.get('symbol')} | {row.get('direction')} | {row.get('current_decision')} | "
            f"{row.get('current_score')} | {row.get('optimizer_adjustment')} | {row.get('hypothetical_score')} | "
            f"{row.get('hypothetical_bias')} | {row.get('rejection_reasons', [])} |"
        )
    return "\n".join(lines)


def _group_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No data._"
    lines = [
        "| Value | Count | Avg adj | STRONG_PRIORITIZE | PRIORITIZE | NEUTRAL | CAUTION | STRONG_AVOID |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows[:20]:
        lines.append(
            f"| {row.get('value')} | {row.get('count', 0)} | {row.get('avg_adjustment', 0)} | "
            f"{row.get('strong_prioritize', 0)} | {row.get('prioritize', 0)} | {row.get('neutral', 0)} | "
            f"{row.get('caution', 0)} | {row.get('strong_avoid', 0)} |"
        )
    return "\n".join(lines)


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Edge Optimizer shadow runtime logs.")
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG_FILE)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    args = parser.parse_args()

    events = load_shadow_events(args.log_file)
    analysis = analyze_events(events)
    paths = write_reports(analysis, report_json=args.report_json, report_md=args.report_md)
    print("Edge Optimizer Shadow V1")
    print(f"Total evaluations: {analysis['total_evaluations']}")
    print(f"Avg adjustment: {analysis['avg_adjustment']}")
    print(f"Report JSON: {paths['json']}")
    print(f"Report MD: {paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
