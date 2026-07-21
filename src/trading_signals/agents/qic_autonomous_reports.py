from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.agents.decision_ledger import load_decision_ledger
from trading_signals.agents.research_memory import load_research_memory
from trading_signals.agents.strategy_knowledge_base import load_strategy_knowledge_base
from trading_signals.agents.qic_runtime import atomic_write_json, atomic_write_text


def write_autonomous_qic_reports(
    *,
    output_path: Path = Path("reports") / "qic",
    knowledge_base_path: Path = Path("data") / "qic" / "strategy_knowledge_base.json",
    research_memory_path: Path = Path("data") / "qic" / "research_memory.json",
    decision_ledger_path: Path = Path("data") / "qic" / "decision_ledger.jsonl",
    events: list[dict[str, Any]] | None = None,
    daily_enabled: bool = True,
    weekly_enabled: bool = True,
) -> dict[str, Any]:
    output_path.mkdir(parents=True, exist_ok=True)
    kb = load_strategy_knowledge_base(knowledge_base_path)
    memory = load_research_memory(research_memory_path)
    ledger = load_decision_ledger(decision_ledger_path)
    result: dict[str, Any] = {"daily_brief": None, "weekly_research_review": None}
    if daily_enabled:
        result["daily_brief"] = _daily_brief(kb, memory, ledger, events or [])
        _write_pair(output_path / "daily_brief", result["daily_brief"], "QIC Daily Brief")
    if weekly_enabled:
        result["weekly_research_review"] = _weekly_review(kb, memory, ledger)
        _write_pair(output_path / "weekly_research_review", result["weekly_research_review"], "QIC Weekly Research Review")
    return result


def _daily_brief(kb: dict[str, Any], memory: dict[str, Any], ledger: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, Any]:
    experiments = list((memory.get("experiments") or {}).values())
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "new_edges": [item for item in experiments if int(item.get("times_seen", 0)) == 1][-10:],
        "degraded_edges": [item for item in experiments if item.get("current_status") == "degraded"],
        "pending_proposals": [item for item in (kb.get("items") or {}).values() if item.get("implementation_status") in {"approved_for_review", "implementation_allowed", "patch_generated"}],
        "events": events,
        "last_decision": ledger[-1] if ledger else None,
        "action_required": bool(events) or any(item.get("current_status") == "degraded" for item in experiments),
    }


def _weekly_review(kb: dict[str, Any], memory: dict[str, Any], ledger: list[dict[str, Any]]) -> dict[str, Any]:
    experiments = list((memory.get("experiments") or {}).values())
    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "best_hypotheses": sorted(experiments, key=lambda item: float(item.get("best_pf_seen") or 0), reverse=True)[:10],
        "discarded_hypotheses": [item for item in experiments if item.get("current_status") in {"rejected", "retired"}],
        "candidate_confirmations": [item for item in experiments if int(item.get("times_seen", 0)) >= 3 and float(item.get("last_pf") or 0) > 1.05],
        "candidate_retirements": [item for item in experiments if item.get("current_status") == "degraded"],
        "known_edges": len((kb.get("items") or {})),
        "decisions_recorded": len(ledger),
    }


def _write_pair(base_path: Path, payload: dict[str, Any], title: str) -> None:
    json_path = base_path.with_suffix(".json")
    md_path = base_path.with_suffix(".md")
    atomic_write_json(json_path, payload)
    atomic_write_text(md_path, _markdown(payload, title))


def _markdown(payload: dict[str, Any], title: str) -> str:
    lines = [f"# {title}", "", f"Generated at: {payload.get('generated_at')}", ""]
    for key, value in payload.items():
        if key == "generated_at":
            continue
        if isinstance(value, list):
            lines.append(f"- {key}: {len(value)}")
        else:
            lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"
