from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import compute_trade_metrics, load_canonical_closed_trades


EDGE_CLASSES = {"CONFIRMED_EDGE", "POSSIBLE_EDGE", "NO_EDGE", "TOXIC_CONTEXT"}
ACTION_LEVELS = {"HIGH IMPACT", "MEDIUM IMPACT", "LOW IMPACT"}


def generate_bot_audit_ai(
    *,
    data_path: Path = Path("data"),
    reports_path: Path = Path("reports"),
) -> dict[str, Any]:
    trades = load_canonical_closed_trades(data_path)
    canonical_metrics = compute_trade_metrics(trades)
    inputs = _load_inputs(reports_path)
    edge_detection = _edge_detection(inputs)
    experiments = _experiment_tracking(inputs)
    rejection_analysis = _rejection_analysis(inputs)
    improved = _what_improved(inputs, edge_detection, experiments)
    worsened = _what_worsened(inputs, edge_detection, experiments)
    actions = _recommended_actions(
        canonical_metrics=canonical_metrics,
        edge_detection=edge_detection,
        experiments=experiments,
        rejection_analysis=rejection_analysis,
        worsened=worsened,
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset": "data/paper_trading/trades.csv",
        "inputs": inputs["manifest"],
        "executive_summary": _executive_summary(canonical_metrics, edge_detection, experiments),
        "what_improved": improved,
        "what_worsened": worsened,
        "edge_detection": edge_detection,
        "experiment_tracking": experiments,
        "rejection_analysis": rejection_analysis,
        "recommended_actions": actions,
        "tomorrow_priorities": actions["tomorrow_priorities"],
    }


def write_bot_audit_ai(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "bot_audit_ai.json"
    md_path = reports_path / "bot_audit_ai.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    md_path.write_text(format_bot_audit_ai_markdown(result), encoding="utf-8")
    return {"json_path": json_path, "markdown_path": md_path}


def format_bot_audit_ai_markdown(result: dict[str, Any]) -> str:
    summary = _dict(result.get("executive_summary"))
    lines = [
        "# BOT_AUDIT_AI",
        "",
        f"- Generated at: {result.get('generated_at')}",
        f"- Dataset: `{result.get('dataset')}`",
        "",
        "## 1. Executive Summary",
        "",
        f"- Current state: {summary.get('current_state', 'UNKNOWN')}",
        f"- Risk level: {summary.get('risk_level', 'UNKNOWN')}",
        f"- Confidence level: {summary.get('confidence_level', 'UNKNOWN')}",
        f"- Diagnosis: {summary.get('diagnosis', 'Datos insuficientes.')}",
        "",
        "## 2. What Improved",
        "",
        *_bullet_lines(result.get("what_improved")),
        "",
        "## 3. What Worsened",
        "",
        *_bullet_lines(result.get("what_worsened")),
        "",
        "## 4. Edge Detection",
        "",
    ]
    edge = _dict(result.get("edge_detection"))
    for classification in ("CONFIRMED_EDGE", "POSSIBLE_EDGE", "NO_EDGE", "TOXIC_CONTEXT"):
        lines.append(f"### {classification}")
        items = edge.get(classification.lower(), [])
        lines.extend(_edge_lines(items))
        lines.append("")

    experiments = _dict(result.get("experiment_tracking"))
    lines.extend(["## 5. Experiment Tracking", "", "### Winning experiments"])
    lines.extend(_experiment_lines(experiments.get("winning_experiments")))
    lines.extend(["", "### Losing experiments"])
    lines.extend(_experiment_lines(experiments.get("losing_experiments")))
    lines.extend(["", "## 6. Rejection Analysis", ""])
    lines.extend(_rejection_lines(_dict(result.get("rejection_analysis")).get("most_expensive_rejection_reasons")))
    lines.extend(["", "## 7. Recommended Actions", ""])
    actions = _dict(result.get("recommended_actions"))
    for level in ("HIGH IMPACT", "MEDIUM IMPACT", "LOW IMPACT"):
        lines.append(f"### {level}")
        lines.extend(_action_lines(actions.get(level.lower().replace(" ", "_"))))
        lines.append("")
    lines.extend(["## 8. Tomorrow Priorities", ""])
    priorities = result.get("tomorrow_priorities", [])
    if isinstance(priorities, list) and priorities:
        for idx, item in enumerate(priorities[:3], start=1):
            lines.append(f"{idx}. {item}")
    else:
        lines.append("1. Mantener observación hasta tener más datos.")
    return "\n".join(lines).rstrip() + "\n"


def _load_inputs(reports_path: Path) -> dict[str, Any]:
    files = {
        "intelligence_manifest": reports_path / "intelligence_layer_manifest.json",
        "outcome_intelligence": reports_path / "outcome_intelligence.csv",
        "edge_breakdown": reports_path / "edge_breakdown.csv",
        "setup_rankings": reports_path / "setup_rankings.csv",
        "relaxation_shadow_v1_summary": reports_path / "relaxation_shadow_v1_summary.csv",
        "relaxation_shadow_v1_trades": reports_path / "relaxation_shadow_v1_trades.csv",
        "relaxation_shadow_v2": reports_path / "relaxation_shadow_v2_intelligence.json",
        "context_toxicity": reports_path / "context_toxicity_deep_dive.json",
        "post_consistency_edge": reports_path / "post_consistency_edge_recalc.json",
        "shadow_current_reject": reports_path / "shadow_send_current_reject_deep_dive.json",
        "shadow_rejection_reasons": reports_path / "shadow_send_current_reject_rejection_reasons.csv",
        "london_short_attribution": reports_path / "london_short_edge_attribution.json",
        "range_penalty_shadow": reports_path / "range_penalty_shadow.json",
    }
    payload = {
        "manifest": {
            name: {
                "path": str(path),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else 0,
            }
            for name, path in files.items()
        }
    }
    for name, path in files.items():
        payload[name] = _read_csv(path) if path.suffix == ".csv" else _read_json(path)
    return payload


def _executive_summary(metrics: dict[str, Any], edge_detection: dict[str, Any], experiments: dict[str, Any]) -> dict[str, Any]:
    closed = int(metrics.get("closed_trades") or 0)
    total_r = float(metrics.get("total_r") or 0.0)
    pf = float(metrics.get("profit_factor") or 0.0)
    winrate = float(metrics.get("winrate") or 0.0)
    if closed == 0:
        state = "NO_DATA"
    elif total_r > 0 and pf >= 1.2:
        state = "IMPROVING"
    elif total_r < 0 or pf < 1.0:
        state = "DEFENSIVE"
    else:
        state = "MIXED"
    toxic_count = len(edge_detection.get("toxic_context", []))
    if pf < 0.9 or total_r < 0 or toxic_count >= 2:
        risk = "HIGH"
    elif pf < 1.2 or winrate < 45:
        risk = "MEDIUM"
    else:
        risk = "LOW"
    confidence = "HIGH" if closed >= 100 else "MEDIUM" if closed >= 30 else "LOW"
    winning = len(experiments.get("winning_experiments", []))
    diagnosis = (
        f"{closed} closed trades, totalR={metrics.get('total_r')}, PF={metrics.get('profit_factor')}. "
        f"Winning experiments detected: {winning}."
    )
    return {
        "current_state": state,
        "risk_level": risk,
        "confidence_level": confidence,
        "closed_trades": closed,
        "total_r": metrics.get("total_r"),
        "winrate": metrics.get("winrate"),
        "profit_factor": metrics.get("profit_factor"),
        "diagnosis": diagnosis,
    }


def _what_improved(inputs: dict[str, Any], edge_detection: dict[str, Any], experiments: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for edge in edge_detection.get("confirmed_edge", [])[:5]:
        items.append(_item("confirmed_edge", edge.get("name"), edge.get("summary"), edge.get("total_r"), "Validated positive edge."))
    for edge in edge_detection.get("possible_edge", [])[:5]:
        items.append(_item("possible_edge", edge.get("name"), edge.get("summary"), edge.get("total_r"), "Promising but needs more sample."))
    for experiment in experiments.get("winning_experiments", [])[:5]:
        items.append(_item("winning_experiment", experiment.get("name"), experiment.get("summary"), experiment.get("total_r"), "Experiment improved historical R."))
    return _sorted_items(items, reverse=True) or [_item("no_improvement", "none", "No measurable improvement detected yet.", 0, "Collect more data.")]


def _what_worsened(inputs: dict[str, Any], edge_detection: dict[str, Any], experiments: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for edge in edge_detection.get("toxic_context", [])[:8]:
        items.append(_item("toxic_context", edge.get("name"), edge.get("summary"), edge.get("total_r"), "Keep blocked or isolate in shadow."))
    for experiment in experiments.get("losing_experiments", [])[:5]:
        items.append(_item("losing_experiment", experiment.get("name"), experiment.get("summary"), experiment.get("total_r"), "Do not promote."))
    return _sorted_items(items, reverse=False) or [_item("no_worsening", "none", "No measurable worsening detected from available reports.", 0, "Continue monitoring.")]


def _edge_detection(inputs: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    buckets = {key.lower(): [] for key in EDGE_CLASSES}
    post = _dict(inputs.get("post_consistency_edge"))
    for row in _list(post.get("hypotheses")):
        classification = str(row.get("classification") or "NO_EDGE").upper()
        if classification not in EDGE_CLASSES:
            classification = "NO_EDGE"
        buckets[classification.lower()].append(
            {
                "name": row.get("hypothesis"),
                "source": "post_consistency_edge",
                "sample_size": row.get("sample_size"),
                "total_r": row.get("total_r"),
                "winrate": row.get("winrate"),
                "profit_factor": row.get("profit_factor"),
                "summary": f"n={row.get('sample_size')} totalR={row.get('total_r')} PF={row.get('profit_factor')}",
            }
        )
    toxicity = _dict(inputs.get("context_toxicity"))
    for key in ("confirmed_toxic_contexts", "hidden_edge_contexts", "unstable_contexts"):
        for row in _list(toxicity.get(key)):
            classification = "TOXIC_CONTEXT" if key == "confirmed_toxic_contexts" else "POSSIBLE_EDGE" if key == "hidden_edge_contexts" else "NO_EDGE"
            buckets[classification.lower()].append(_context_item(row, source=f"context_toxicity.{key}"))
    return {key: _sorted_items(value, reverse=(key != "toxic_context")) for key, value in buckets.items()}


def _experiment_tracking(inputs: dict[str, Any]) -> dict[str, Any]:
    experiments: list[dict[str, Any]] = []
    shadow = _dict(inputs.get("shadow_current_reject"))
    metrics = _dict(shadow.get("metrics"))
    if metrics:
        experiments.append(
            _experiment(
                name="SHADOW_SEND_CURRENT_REJECT",
                source="shadow_current_reject",
                metrics=metrics,
                summary=f"Current rejects that relaxed shadow would send: totalR={metrics.get('total_r')} PF={metrics.get('profit_factor')}",
            )
        )
    relaxation_v2 = _dict(inputs.get("relaxation_shadow_v2"))
    recommendations = _dict(relaxation_v2.get("recommendations"))
    for row in _list(recommendations.get("safe_to_relax")):
        experiments.append(_experiment_from_group(row, "RELAXATION_SHADOW_V2_SAFE", "relaxation_shadow_v2"))
    for row in _list(recommendations.get("toxic_to_relax")):
        experiments.append(_experiment_from_group(row, "RELAXATION_SHADOW_V2_TOXIC", "relaxation_shadow_v2"))
    london = _dict(inputs.get("london_short_attribution"))
    for row in _list(london.get("recommended_rules")):
        if isinstance(row, dict):
            experiments.append(_context_item(row, source="london_short_attribution"))
        else:
            experiments.append(
                {
                    "name": str(row),
                    "source": "london_short_attribution",
                    "sample_size": None,
                    "total_r": 0.0,
                    "winrate": None,
                    "profit_factor": 0.0,
                    "summary": str(row),
                }
            )
    winners = [item for item in experiments if float(item.get("total_r") or 0.0) > 0 and float(item.get("profit_factor") or 0.0) >= 1.1]
    losers = [item for item in experiments if float(item.get("total_r") or 0.0) < 0 or str(item.get("classification", "")).upper() in {"TOXIC_TO_RELAX", "TOXIC_CONTEXT"}]
    return {
        "winning_experiments": _sorted_items(winners, reverse=True),
        "losing_experiments": _sorted_items(losers, reverse=False),
        "all_experiments": experiments,
    }


def _rejection_analysis(inputs: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for row in _list(inputs.get("shadow_rejection_reasons")):
        total_r = _float(row.get("total_r")) or 0.0
        rows.append(
            {
                "reason": row.get("reason"),
                "classification": row.get("classification"),
                "sample_size": _int(row.get("sample_size")),
                "total_r": total_r,
                "winrate": _float(row.get("winrate")) or 0.0,
                "profit_factor": _float(row.get("profit_factor")) or 0.0,
                "expense_type": "edge_destroyed" if total_r > 0 else "protective_or_unproven",
                "recommendation": row.get("recommendation") or "",
            }
        )
    expensive = sorted(rows, key=lambda item: float(item.get("total_r") or 0.0), reverse=True)
    return {
        "most_expensive_rejection_reasons": expensive[:10],
        "protective_rejection_reasons": sorted(rows, key=lambda item: float(item.get("total_r") or 0.0))[:10],
    }


def _recommended_actions(
    *,
    canonical_metrics: dict[str, Any],
    edge_detection: dict[str, Any],
    experiments: dict[str, Any],
    rejection_analysis: dict[str, Any],
    worsened: list[dict[str, Any]],
) -> dict[str, Any]:
    high: list[dict[str, Any]] = []
    medium: list[dict[str, Any]] = []
    low: list[dict[str, Any]] = []
    if float(canonical_metrics.get("profit_factor") or 0.0) < 1.0:
        high.append(_action("Keep production defensive", "PF is below 1.0 on canonical trades.", "Do not relax public policy globally."))
    for item in edge_detection.get("toxic_context", [])[:3]:
        high.append(_action(f"Keep blocked: {item.get('name')}", item.get("summary"), "Do not promote this context."))
    for item in experiments.get("winning_experiments", [])[:3]:
        medium.append(_action(f"Forward-test: {item.get('name')}", item.get("summary"), "Track in shadow before promotion."))
    for item in _list(rejection_analysis.get("most_expensive_rejection_reasons"))[:3]:
        if float(item.get("total_r") or 0.0) > 0:
            medium.append(_action(f"Review rejection: {item.get('reason')}", f"Destroyed {item.get('total_r')}R in shadow analysis.", "Keep DEV-only until sample increases."))
    low.append(_action("Regenerate intelligence reports daily", "Audit depends on fresh reports.", "Run report generation before the audit."))
    priorities = [item["action"] for item in (high + medium + low)[:3]]
    return {
        "high_impact": high,
        "medium_impact": medium,
        "low_impact": low,
        "tomorrow_priorities": priorities,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _item(kind: str, name: object, summary: object, total_r: object, recommendation: object) -> dict[str, Any]:
    return {
        "kind": kind,
        "name": str(name or "unknown"),
        "summary": str(summary or ""),
        "total_r": _float(total_r) or 0.0,
        "recommendation": str(recommendation or ""),
    }


def _experiment(name: str, source: str, metrics: dict[str, Any], summary: str) -> dict[str, Any]:
    return {
        "name": name,
        "source": source,
        "sample_size": metrics.get("closed_trades"),
        "total_r": metrics.get("total_r"),
        "winrate": metrics.get("winrate"),
        "profit_factor": metrics.get("profit_factor"),
        "summary": summary,
    }


def _experiment_from_group(row: dict[str, Any], name: str, source: str) -> dict[str, Any]:
    return {
        "name": f"{name}:{row.get('dimension')}={row.get('value')}",
        "source": source,
        "classification": row.get("classification"),
        "sample_size": row.get("closed_trades"),
        "total_r": row.get("total_r"),
        "winrate": row.get("winrate"),
        "profit_factor": row.get("profit_factor"),
        "summary": f"{row.get('dimension')}={row.get('value')} n={row.get('closed_trades')} totalR={row.get('total_r')}",
    }


def _context_item(row: dict[str, Any], *, source: str) -> dict[str, Any]:
    name = row.get("name") or row.get("context") or row.get("value") or row.get("rule") or row.get("hypothesis") or "unknown"
    return {
        "name": name,
        "source": source,
        "sample_size": row.get("sample_size") or row.get("trades") or row.get("closed_trades"),
        "total_r": row.get("total_r") or row.get("total_result_r") or row.get("avg_r"),
        "winrate": row.get("winrate"),
        "profit_factor": row.get("profit_factor") or row.get("pf"),
        "summary": row.get("summary") or f"{name}: totalR={row.get('total_r')} PF={row.get('profit_factor')}",
    }


def _action(action: object, rationale: object, next_step: object) -> dict[str, str]:
    return {
        "action": str(action or ""),
        "rationale": str(rationale or ""),
        "next_step": str(next_step or ""),
    }


def _sorted_items(items: list[dict[str, Any]], *, reverse: bool) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: float(item.get("total_r") or 0.0), reverse=reverse)


def _bullet_lines(items: object) -> list[str]:
    if not isinstance(items, list) or not items:
        return ["- none"]
    return [f"- {item.get('name')}: {item.get('summary')} | Recommendation: {item.get('recommendation', '')}" for item in items[:10] if isinstance(item, dict)]


def _edge_lines(items: object) -> list[str]:
    if not isinstance(items, list) or not items:
        return ["- none"]
    return [f"- {item.get('name')} | {item.get('summary')} | source={item.get('source')}" for item in items[:10] if isinstance(item, dict)]


def _experiment_lines(items: object) -> list[str]:
    if not isinstance(items, list) or not items:
        return ["- none"]
    return [f"- {item.get('name')} | {item.get('summary')} | PF={item.get('profit_factor')}" for item in items[:10] if isinstance(item, dict)]


def _rejection_lines(items: object) -> list[str]:
    if not isinstance(items, list) or not items:
        return ["- none"]
    return [f"- {item.get('reason')}: totalR={item.get('total_r')} | class={item.get('classification')} | n={item.get('sample_size')}" for item in items[:10] if isinstance(item, dict)]


def _action_lines(items: object) -> list[str]:
    if not isinstance(items, list) or not items:
        return ["- none"]
    return [f"- {item.get('action')}: {item.get('rationale')} Next: {item.get('next_step')}" for item in items[:10] if isinstance(item, dict)]


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: object) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0
