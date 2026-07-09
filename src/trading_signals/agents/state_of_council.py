from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trading_signals.agents.decision_ledger import load_decision_ledger
from trading_signals.agents.proposal_store import load_proposals
from trading_signals.agents.research_memory import load_research_memory
from trading_signals.agents.strategy_knowledge_base import load_strategy_knowledge_base


def build_state_of_council(
    *,
    knowledge_base_path: Path = Path("data") / "qic" / "strategy_knowledge_base.json",
    research_memory_path: Path = Path("data") / "qic" / "research_memory.json",
    proposal_store_path: Path = Path("data") / "agent_proposals" / "proposals.jsonl",
    agent_self_evaluation_path: Path = Path("reports") / "qic" / "agent_self_evaluation.json",
    decision_ledger_path: Path = Path("data") / "qic" / "decision_ledger.jsonl",
    output_path: Path = Path("reports") / "qic",
) -> dict[str, Any]:
    kb = load_strategy_knowledge_base(knowledge_base_path)
    memory = load_research_memory(research_memory_path)
    proposals = load_proposals(proposal_store_path)
    agent_eval = _load_json(agent_self_evaluation_path)
    ledger = load_decision_ledger(decision_ledger_path)
    items = list((kb.get("items") or {}).values())
    experiments = list((memory.get("experiments") or {}).values())
    report = {
        "total_known_edges": len(items),
        "confirmed_edges": _count(items, "status", "confirmed"),
        "candidates": _count(items, "status", "candidate"),
        "rejected": _count(items, "status", "rejected"),
        "degraded": sum(1 for item in experiments if item.get("current_status") == "degraded"),
        "pending_implementation": sum(1 for item in items if item.get("implementation_status") in {"approved_for_review", "implementation_allowed", "patch_generated"}),
        "pending_approval": sum(1 for item in proposals if str(item.get("status") or "pending") == "pending"),
        "agent_accuracy": {
            name: item.get("accuracy_score")
            for name, item in (agent_eval.get("agents") or {}).items()
        },
        "last_cio_decision": ledger[-1] if ledger else None,
        "last_telegram_action": _last_reviewed(proposals),
        "open_blockers": _open_blockers(items, experiments, proposals),
    }
    write_state_of_council_reports(report, output_path=output_path)
    return report


def write_state_of_council_reports(report: dict[str, Any], *, output_path: Path = Path("reports") / "qic") -> dict[str, Path]:
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "state_of_council.json"
    md_path = output_path / "state_of_council.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def _count(items: list[dict[str, Any]], key: str, value: str) -> int:
    return sum(1 for item in items if item.get(key) == value)


def _last_reviewed(proposals: list[dict[str, Any]]) -> dict[str, Any] | None:
    reviewed = [item for item in proposals if item.get("reviewed_at")]
    if not reviewed:
        return None
    latest = sorted(reviewed, key=lambda item: str(item.get("reviewed_at")))[-1]
    return {"proposal_id": latest.get("id"), "status": latest.get("status"), "reviewed_at": latest.get("reviewed_at")}


def _open_blockers(items: list[dict[str, Any]], experiments: list[dict[str, Any]], proposals: list[dict[str, Any]]) -> list[str]:
    blockers = []
    if any(item.get("current_status") == "degraded" for item in experiments):
        blockers.append("degraded_edge_requires_review")
    if any(str(item.get("status") or "pending") == "approved_for_implementation_review" for item in proposals):
        blockers.append("approved_proposal_waiting_implementation")
    if any(item.get("implementation_status") == "blocked_preconditions" for item in items):
        blockers.append("code_engineer_blocked")
    return blockers


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _markdown(report: dict[str, Any]) -> str:
    lines = ["# QIC State Of Council", ""]
    for key in (
        "total_known_edges",
        "confirmed_edges",
        "candidates",
        "rejected",
        "degraded",
        "pending_implementation",
        "pending_approval",
    ):
        lines.append(f"- {key}: {report.get(key)}")
    lines.append(f"- open_blockers: {', '.join(report.get('open_blockers') or []) or 'none'}")
    lines.append("")
    lines.append("## Agent Accuracy")
    for name, score in (report.get("agent_accuracy") or {}).items():
        lines.append(f"- {name}: {score}")
    return "\n".join(lines) + "\n"
