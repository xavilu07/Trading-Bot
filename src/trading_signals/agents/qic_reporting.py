from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_qic_reports(
    *,
    output_path: Path,
    debate: dict[str, Any],
    consensus: dict[str, Any],
    proposal: dict[str, Any] | None,
    agent_memory: dict[str, Any],
) -> dict[str, dict[str, Path]]:
    output_path.mkdir(parents=True, exist_ok=True)
    reports = {
        "debate": debate,
        "consensus": consensus,
        "proposal": proposal or {"single_proposal": None, "reason": "no_proposal_selected"},
        "agent_memory": agent_memory,
    }
    paths = {}
    for name, payload in reports.items():
        json_path = output_path / f"{name}.json"
        md_path = output_path / f"{name}.md"
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text(_markdown(name, payload), encoding="utf-8")
        paths[name] = {"json": json_path, "markdown": md_path}
    return paths


def _markdown(name: str, payload: Any) -> str:
    lines = [f"# QIC {name.replace('_', ' ').title()}", ""]
    if name == "debate":
        interventions = payload.get("interventions", []) if isinstance(payload, dict) else []
        lines.extend(_table(interventions, ["stage", "agent", "confidence", "risk_level", "evidence", "content"]))
    elif name == "consensus":
        lines.extend(_key_values(payload))
    elif name == "proposal":
        if isinstance(payload, dict) and payload.get("id"):
            lines.extend(_key_values(payload))
        else:
            lines.append("No CIO proposal selected.")
    elif name == "agent_memory":
        agents = payload.get("agents", {}) if isinstance(payload, dict) else {}
        rows = [{"agent": key, **value} for key, value in agents.items()]
        lines.extend(_table(rows, ["agent", "historical_precision", "proposals_accepted", "proposals_rejected", "proposals_pending", "total_interventions"]))
    return "\n".join(lines) + "\n"


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
