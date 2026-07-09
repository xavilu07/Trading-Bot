from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.agents.agent_memory import load_agent_memory


def evaluate_agents(
    *,
    agent_memory_path: Path = Path("data") / "qic" / "agent_memory.json",
    revalidation_report_path: Path = Path("reports") / "qic" / "revalidation.json",
    output_path: Path = Path("reports") / "qic",
) -> dict[str, Any]:
    memory = load_agent_memory(agent_memory_path)
    revalidation = _load_json(revalidation_report_path)
    improved = sum(1 for item in revalidation.get("results", []) if item.get("result") in {"edge_improved", "edge_still_valid"})
    degraded = sum(1 for item in revalidation.get("results", []) if item.get("result") in {"edge_degraded", "edge_invalidated"})
    agents = {}
    for name, item in (memory.get("agents") or {}).items():
        supported = int(item.get("hypotheses_supported", 0))
        opposed = int(item.get("hypotheses_opposed", 0))
        accepted = int(item.get("proposals_accepted", 0))
        rejected = int(item.get("proposals_rejected", 0))
        score = _accuracy_score(supported=supported, opposed=opposed, accepted=accepted, rejected=rejected, improved=improved, degraded=degraded)
        agents[name] = {
            **item,
            "proposals_supported": supported,
            "proposals_opposed": opposed,
            "supported_edges_that_improved": improved if supported else 0,
            "supported_edges_that_degraded": degraded if supported else 0,
            "rejected_edges_that_later_improved": improved if rejected else 0,
            "accuracy_score": score,
            "bias_notes": _bias_notes(score, supported, opposed),
            "last_self_review": datetime.now(tz=UTC).isoformat(),
        }
    report = {"agents": agents, "summary": {"improved_edges": improved, "degraded_edges": degraded}}
    write_agent_self_evaluation_reports(report, output_path=output_path)
    return report


def write_agent_self_evaluation_reports(report: dict[str, Any], *, output_path: Path = Path("reports") / "qic") -> dict[str, Path]:
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "agent_self_evaluation.json"
    md_path = output_path / "agent_self_evaluation.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def _accuracy_score(*, supported: int, opposed: int, accepted: int, rejected: int, improved: int, degraded: int) -> float:
    base = 50.0
    base += min(improved * 5, 25)
    base -= min(degraded * 7, 30)
    if accepted + rejected:
        base += (accepted / (accepted + rejected)) * 20 - 10
    if supported > opposed * 3 and degraded:
        base -= 10
    return round(max(0.0, min(100.0, base)), 4)


def _bias_notes(score: float, supported: int, opposed: int) -> list[str]:
    notes = []
    if supported > opposed * 3 and supported >= 3:
        notes.append("support_bias_possible")
    if opposed > supported * 3 and opposed >= 3:
        notes.append("risk_aversion_bias_possible")
    if score < 45:
        notes.append("needs_calibration")
    return notes


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _markdown(report: dict[str, Any]) -> str:
    lines = ["# QIC Agent Self Evaluation", ""]
    agents = report.get("agents") or {}
    lines.append(f"Agents: {len(agents)}")
    lines.append("")
    lines.append("| agent | accuracy_score | supported | opposed | bias_notes |")
    lines.append("| --- | --- | --- | --- | --- |")
    for name, item in agents.items():
        lines.append(
            f"| {name} | {item.get('accuracy_score')} | {item.get('proposals_supported')} | "
            f"{item.get('proposals_opposed')} | {', '.join(item.get('bias_notes') or [])} |"
        )
    return "\n".join(lines) + "\n"
