from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.agents.strategy_knowledge_base import knowledge_item_id, normalize_conditions
from trading_signals.agents.qic_runtime import atomic_write_json, atomic_write_text

DEFAULT_RESEARCH_MEMORY_PATH = Path("data") / "qic" / "research_memory.json"


def load_research_memory(path: Path = DEFAULT_RESEARCH_MEMORY_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"experiments": {}, "updated_at": None}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"experiments": {}, "updated_at": None}
    if not isinstance(raw, dict):
        return {"experiments": {}, "updated_at": None}
    raw.setdefault("experiments", {})
    return raw


def save_research_memory(memory: dict[str, Any], path: Path = DEFAULT_RESEARCH_MEMORY_PATH) -> dict[str, Any]:
    memory["updated_at"] = _now()
    atomic_write_json(path, memory)
    return memory


def research_memory_id(conditions: Any) -> str:
    return knowledge_item_id(normalize_conditions(conditions)).replace("edge_", "research_")


def update_research_memory_from_proposal(
    proposal: dict[str, Any],
    *,
    path: Path = DEFAULT_RESEARCH_MEMORY_PATH,
    event: str = "qic_proposal_seen",
) -> dict[str, Any]:
    memory = load_research_memory(path)
    experiments = memory.setdefault("experiments", {})
    conditions = _proposal_conditions(proposal)
    normalized = normalize_conditions(conditions)
    item_id = str(proposal.get("research_memory_id") or research_memory_id(normalized))
    now = _now()
    existing = experiments.get(item_id) if isinstance(experiments.get(item_id), dict) else {}
    status = _status_from_proposal(proposal, existing)
    decision_history = list(existing.get("decision_history") or [])
    decision_history.append(
        {
            "timestamp": now,
            "event": event,
            "proposal_id": proposal.get("id"),
            "action": proposal.get("action"),
            "status": proposal.get("status"),
            "expected_pf": proposal.get("expected_pf"),
            "expected_total_r": proposal.get("expected_total_r"),
            "trade_reduction_pct": proposal.get("trade_reduction_pct"),
            "evidence": proposal.get("evidence"),
        }
    )
    evidence_history = list(existing.get("evidence_history") or [])
    evidence_history.append(
        {
            "timestamp": now,
            "pf": proposal.get("expected_pf"),
            "total_r": proposal.get("expected_total_r"),
            "trade_reduction_pct": proposal.get("trade_reduction_pct"),
            "evidence": proposal.get("evidence"),
        }
    )
    experiment = {
        "id": item_id,
        "normalized_conditions": normalized,
        "title": proposal.get("title") or ", ".join(normalized),
        "first_seen_at": existing.get("first_seen_at") or now,
        "last_seen_at": now,
        "times_seen": int(existing.get("times_seen", 0)) + 1,
        "times_simulated": int(existing.get("times_simulated", 0)) + 1,
        "times_proposed": int(existing.get("times_proposed", 0)) + 1,
        "times_approved": int(existing.get("times_approved", 0)),
        "times_rejected": int(existing.get("times_rejected", 0)),
        "times_implemented": int(existing.get("times_implemented", 0)),
        "times_rolled_back": int(existing.get("times_rolled_back", 0)),
        "current_status": status,
        "best_pf_seen": max(_float(existing.get("best_pf_seen")), _float(proposal.get("expected_pf"))),
        "last_pf": proposal.get("expected_pf"),
        "best_total_r_seen": max(_float(existing.get("best_total_r_seen")), _float(proposal.get("expected_total_r"))),
        "last_total_r": proposal.get("expected_total_r"),
        "best_trade_reduction_pct": _best_reduction(existing.get("best_trade_reduction_pct"), proposal.get("trade_reduction_pct")),
        "last_trade_reduction_pct": proposal.get("trade_reduction_pct"),
        "evidence_history": evidence_history[-100:],
        "decision_history": decision_history[-100:],
        "rejection_reasons": list(existing.get("rejection_reasons") or []),
        "rollback_reasons": list(existing.get("rollback_reasons") or []),
        "notes_by_agent": existing.get("notes_by_agent") or {},
        "last_revalidation_result": existing.get("last_revalidation_result"),
    }
    experiments[item_id] = experiment
    save_research_memory(memory, path)
    return experiment


def record_research_memory_decision(
    proposal: dict[str, Any],
    decision: str,
    *,
    path: Path = DEFAULT_RESEARCH_MEMORY_PATH,
    reason: str = "",
) -> dict[str, Any] | None:
    experiment = update_research_memory_from_proposal(proposal, path=path, event=f"decision:{decision}")
    memory = load_research_memory(path)
    stored = memory.get("experiments", {}).get(experiment["id"])
    if not isinstance(stored, dict):
        return None
    decision_lower = decision.lower()
    if decision_lower in {"approved", "approved_for_review"}:
        stored["times_approved"] = int(stored.get("times_approved", 0)) + 1
        stored["current_status"] = "approved_for_review"
    elif decision_lower == "rejected":
        stored["times_rejected"] = int(stored.get("times_rejected", 0)) + 1
        stored["current_status"] = "rejected"
        if reason:
            reasons = list(stored.get("rejection_reasons") or [])
            reasons.append(reason)
            stored["rejection_reasons"] = reasons[-50:]
    elif decision_lower:
        stored["current_status"] = decision_lower
    save_research_memory(memory, path)
    return stored


def should_skip_due_to_rejected_cooldown(
    proposal: dict[str, Any],
    *,
    memory: dict[str, Any] | None = None,
    cooldown_days: int = 14,
) -> dict[str, Any]:
    memory = memory or load_research_memory()
    item_id = research_memory_id(_proposal_conditions(proposal))
    experiment = (memory.get("experiments") or {}).get(item_id)
    if not isinstance(experiment, dict) or experiment.get("current_status") != "rejected":
        return {"skip": False, "reason": ""}
    previous_evidence = _latest_evidence(experiment)
    current_evidence = _float(proposal.get("evidence"))
    if current_evidence >= max(previous_evidence + 50, previous_evidence * 1.25):
        return {"skip": False, "reason": "new_evidence_significant"}
    last_seen = _parse_dt(experiment.get("last_seen_at"))
    if last_seen is None:
        return {"skip": True, "reason": "rejected_without_timestamp"}
    age_days = (datetime.now(tz=UTC) - last_seen).total_seconds() / 86400
    if age_days < cooldown_days:
        return {"skip": True, "reason": "rejected_cooldown_active"}
    return {"skip": False, "reason": "cooldown_elapsed"}


def write_research_memory_reports(
    *,
    memory: dict[str, Any],
    output_path: Path = Path("reports") / "qic",
) -> dict[str, Path]:
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "research_memory.json"
    md_path = output_path / "research_memory.md"
    atomic_write_json(json_path, memory)
    atomic_write_text(md_path, format_research_memory_markdown(memory))
    return {"json": json_path, "markdown": md_path}


def format_research_memory_markdown(memory: dict[str, Any]) -> str:
    experiments = list((memory.get("experiments") or {}).values())
    lines = ["# QIC Research Memory", "", f"Experiments: {len(experiments)}", ""]
    if not experiments:
        lines.append("No research memory yet.")
        return "\n".join(lines) + "\n"
    columns = ["id", "current_status", "times_seen", "times_proposed", "times_approved", "times_rejected", "best_pf_seen", "last_pf", "best_total_r_seen", "last_total_r"]
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join("---" for _ in columns) + " |")
    for item in sorted(experiments, key=lambda row: str(row.get("last_seen_at", "")), reverse=True):
        lines.append("| " + " | ".join(_md(item.get(column, "")) for column in columns) + " |")
    return "\n".join(lines) + "\n"


def _proposal_conditions(proposal: dict[str, Any]) -> Any:
    context = proposal.get("context") if isinstance(proposal.get("context"), dict) else {}
    return context.get("conditions") or proposal.get("conditions") or []


def _status_from_proposal(proposal: dict[str, Any], existing: dict[str, Any]) -> str:
    if proposal.get("status") == "approved_for_implementation_review":
        return "approved_for_review"
    if proposal.get("status") == "rejected":
        return "rejected"
    if proposal.get("action") == "PROMOTE_TO_CONFIRMED_EDGE":
        return "candidate"
    return str(existing.get("current_status") or "candidate")


def _best_reduction(previous: Any, current: Any) -> float:
    prev = _float(previous)
    cur = _float(current)
    if prev == 0:
        return cur
    if cur == 0:
        return prev
    return min(prev, cur)


def _latest_evidence(experiment: dict[str, Any]) -> float:
    history = experiment.get("evidence_history") if isinstance(experiment.get("evidence_history"), list) else []
    if history:
        return _float(history[-1].get("evidence"))
    return 0.0


def _parse_dt(value: Any) -> datetime | None:
    try:
        if not value:
            return None
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def _float(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _md(value: Any) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, sort_keys=True)
    return str(value).replace("|", "\\|")
