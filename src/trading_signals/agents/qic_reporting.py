from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from trading_signals.agents.qic_runtime import atomic_write_json, atomic_write_text


def write_qic_reports(
    *,
    output_path: Path,
    debate: dict[str, Any],
    consensus: dict[str, Any],
    proposal: dict[str, Any] | None,
    agent_memory: dict[str, Any],
    strategy_knowledge_base: dict[str, Any] | None = None,
) -> dict[str, dict[str, Path]]:
    output_path.mkdir(parents=True, exist_ok=True)
    reports = {
        "debate": debate,
        "consensus": consensus,
        "proposal": proposal or {"single_proposal": None, "reason": "no_proposal_selected"},
        "agent_memory": agent_memory,
        "strategy_knowledge_base": strategy_knowledge_base or {"items": {}},
    }
    paths = {}
    for name, payload in reports.items():
        json_path = output_path / f"{name}.json"
        md_path = output_path / f"{name}.md"
        atomic_write_json(json_path, payload)
        atomic_write_text(md_path, _markdown(name, payload))
        paths[name] = {"json": json_path, "markdown": md_path}
    return paths


def write_hypothesis_ranking_report(output_path: Path, ranking: dict[str, Any]) -> dict[str, Path]:
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "hypothesis_ranking.json"
    md_path = output_path / "hypothesis_ranking.md"
    atomic_write_json(json_path, ranking)
    atomic_write_text(md_path, _hypothesis_ranking_markdown(ranking))
    return {"json": json_path, "markdown": md_path}


def _markdown(name: str, payload: Any) -> str:
    lines = [f"# QIC {name.replace('_', ' ').title()}", ""]
    if name == "debate":
        interventions = payload.get("interventions", []) if isinstance(payload, dict) else []
        lines.extend(_table(interventions, ["stage", "agent", "confidence", "risk_level", "evidence", "content"]))
    elif name == "consensus":
        lines.extend(_key_values(payload))
    elif name == "proposal":
        if isinstance(payload, dict) and payload.get("id"):
            lines.extend(_proposal_markdown(payload))
        else:
            lines.append("No CIO proposal selected.")
    elif name == "agent_memory":
        agents = payload.get("agents", {}) if isinstance(payload, dict) else {}
        rows = [{"agent": key, **value} for key, value in agents.items()]
        lines.extend(_table(rows, ["agent", "historical_precision", "proposals_accepted", "proposals_rejected", "proposals_pending", "total_interventions"]))
    elif name == "strategy_knowledge_base":
        items = list((payload.get("items") or {}).values()) if isinstance(payload, dict) else []
        lines.extend(
            _table(
                items,
                ["id", "status", "edge_type", "implementation_priority", "times_seen", "times_approved", "times_rejected", "last_expected_pf", "last_expected_total_r"],
            )
        )
    return "\n".join(lines) + "\n"


def _proposal_markdown(payload: dict[str, Any]) -> list[str]:
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    fields = [
        "id",
        "action",
        "edge_type",
        "implementation_priority",
        "known_edge_status",
        "title",
        "expected_pf",
        "expected_total_r",
        "baseline_trades",
        "trades_lost",
        "trade_reduction_pct",
        "risk_level",
        "risk_objections",
        "confidence",
        "evidence",
        "knowledge_item_id",
        "rationale",
    ]
    output = []
    for key in fields:
        value = payload.get(key, context.get(key))
        if isinstance(value, (dict, list)):
            value = json.dumps(value, sort_keys=True)
        output.append(f"- {key}: {value}")
    output.append("")
    output.append("## Recommended Next Step")
    if payload.get("edge_type") == "STRUCTURAL_EDGE":
        output.append("Implementar con feature flag reversible y seguimiento DEV antes de activación permanente.")
    elif payload.get("action") == "REVALIDATE_KNOWN_EDGE":
        output.append("Revalidar edge conocido con muestra nueva antes de implementar.")
    elif payload.get("action") == "PROMOTE_TO_CONFIRMED_EDGE":
        output.append("Promover a edge confirmado; cualquier implementación sigue requiriendo aprobación manual.")
    else:
        output.append("Mantener como hipótesis QIC hasta tener evidencia suficiente.")
    return output


def _key_values(payload: dict[str, Any]) -> list[str]:
    output = []
    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, sort_keys=True)
        output.append(f"- {key}: {value}")
    return output


def _table(rows: list[dict[str, Any]], columns: list[str]) -> list[str]:
    if not rows:
        return ["No data."]
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(_md(row.get(column, "")) for column in columns) + " |")
    return lines


def _md(value: Any) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, sort_keys=True)
    return str(value).replace("|", "\\|")


def _hypothesis_ranking_markdown(ranking: dict[str, Any]) -> str:
    lines = ["# QIC Hypothesis Ranking", ""]
    lines.append(f"- final_action: {ranking.get('final_action')}")
    lines.append(f"- selected_rank: {ranking.get('selected_rank')}")
    lines.append("")
    rows = ranking.get("candidates") if isinstance(ranking.get("candidates"), list) else []
    lines.extend(
        _table(
            rows,
            [
                "rank",
                "status",
                "source",
                "edge_type",
                "known_edge_status",
                "composite_score",
                "action",
                "risk_level",
                "trade_reduction_pct",
                "expected_pf",
                "expected_total_r",
                "reason",
                "discard_reason",
            ],
        )
    )
    return "\n".join(lines) + "\n"
