from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_KNOWLEDGE_BASE_PATH = Path("data") / "qic" / "strategy_knowledge_base.json"


def load_strategy_knowledge_base(path: Path = DEFAULT_KNOWLEDGE_BASE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"items": {}, "updated_at": None}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"items": {}, "updated_at": None}
    if not isinstance(raw, dict):
        return {"items": {}, "updated_at": None}
    raw.setdefault("items", {})
    return raw


def save_strategy_knowledge_base(kb: dict[str, Any], path: Path = DEFAULT_KNOWLEDGE_BASE_PATH) -> dict[str, Any]:
    kb["updated_at"] = _now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(kb, indent=2, sort_keys=True), encoding="utf-8")
    return kb


def normalize_conditions(conditions: Any) -> list[str]:
    normalized = []
    for condition in _condition_strings(conditions):
        value = condition.strip().lower()
        value = re.sub(r"\s+", " ", value)
        value = re.sub(r"\s*=\s*", "=", value)
        value = value.replace(" = ", "=").replace("==", "=")
        value = value.replace("exclude ", "exclude:")
        normalized.append(value)
    return sorted(dict.fromkeys(item for item in normalized if item))


def knowledge_item_id(conditions: Any) -> str:
    normalized = normalize_conditions(conditions)
    digest = hashlib.sha1("|".join(normalized).encode("utf-8")).hexdigest()[:12]
    return f"edge_{digest}"


def find_knowledge_item(kb: dict[str, Any], conditions: Any) -> dict[str, Any] | None:
    item_id = knowledge_item_id(conditions)
    item = kb.get("items", {}).get(item_id)
    return item if isinstance(item, dict) else None


def classify_edge(proposal: dict[str, Any]) -> dict[str, Any]:
    context = proposal.get("context") if isinstance(proposal.get("context"), dict) else {}
    complexity = _int(context.get("complexity"), default=1)
    evidence = _int(proposal.get("evidence"))
    expected_pf = _float(proposal.get("expected_pf"))
    expected_total_r = _float(proposal.get("expected_total_r"))
    trade_reduction_pct = _float(proposal.get("trade_reduction_pct"))
    source = str(context.get("source") or proposal.get("source") or "")
    structural_score = 0.0
    overfit_score = 0.0

    if complexity == 1:
        structural_score += 30
    if evidence >= 300:
        structural_score += 25
    elif evidence >= 100:
        structural_score += 10
    if expected_pf >= 1.05:
        structural_score += min((expected_pf - 1.0) * 80, 25)
    if expected_total_r > 0:
        structural_score += 15
    if trade_reduction_pct <= 60:
        structural_score += 10
    if source == "single_filter":
        structural_score += 10

    if complexity >= 2:
        overfit_score += 25
    if trade_reduction_pct > 60:
        overfit_score += min((trade_reduction_pct - 60) * 1.5, 35)
    if evidence < 100:
        overfit_score += 35
    if expected_pf > 1.8 and evidence < 300:
        overfit_score += 10

    if expected_pf < 1.05 or expected_total_r <= 0:
        edge_type = "REJECTED_EDGE"
        priority = "REJECT"
    elif overfit_score >= 35:
        edge_type = "OVERFIT_RISK"
        priority = "LOW"
    elif complexity == 1 and evidence >= 300 and trade_reduction_pct <= 60:
        edge_type = "STRUCTURAL_EDGE"
        priority = "HIGH"
    elif evidence >= 100:
        edge_type = "TACTICAL_EDGE"
        priority = "MEDIUM"
    else:
        edge_type = "OVERFIT_RISK"
        priority = "LOW"

    return {
        "edge_type": edge_type,
        "structural_score": round(min(structural_score, 100), 4),
        "overfit_score": round(min(overfit_score, 100), 4),
        "implementation_priority": priority,
    }


def enrich_proposal_with_knowledge(
    proposal: dict[str, Any],
    kb: dict[str, Any],
) -> dict[str, Any]:
    enriched = dict(proposal)
    context = dict(enriched.get("context") if isinstance(enriched.get("context"), dict) else {})
    conditions = context.get("conditions") or enriched.get("conditions") or []
    normalized = normalize_conditions(conditions)
    item_id = knowledge_item_id(normalized)
    classification = classify_edge(enriched)
    known = find_knowledge_item(kb, normalized)
    known_status = str((known or {}).get("status") or "new")
    action = str(enriched.get("action") or "")

    if classification["edge_type"] == "REJECTED_EDGE":
        action = "REQUIRES_MANUAL_RESEARCH"
    elif known_status in {"candidate", "needs_revalidation", "confirmed"} and _is_consistently_positive(enriched, known):
        action = "PROMOTE_TO_CONFIRMED_EDGE"
    elif known_status == "rejected":
        previous_evidence = _int((known or {}).get("last_evidence"))
        current_evidence = _int(enriched.get("evidence"))
        if current_evidence >= max(previous_evidence + 50, int(previous_evidence * 1.25)):
            action = "REVALIDATE_KNOWN_EDGE"
        else:
            action = "REQUIRES_MANUAL_RESEARCH"

    context.update(
        {
            "conditions": conditions,
            "normalized_conditions": normalized,
            "knowledge_item_id": item_id,
            "known_edge_status": known_status,
            **classification,
        }
    )
    enriched.update(
        {
            "conditions": conditions,
            "knowledge_item_id": item_id,
            "known_edge_status": known_status,
            "source": context.get("source"),
            "composite_score": context.get("composite_score"),
            "complexity": context.get("complexity"),
            "baseline_pf": context.get("baseline_pf"),
            "baseline_total_r": context.get("baseline_total_r"),
            **classification,
            "context": context,
        }
    )
    if action:
        enriched["action"] = action
    return enriched


def upsert_knowledge_from_proposal(
    proposal: dict[str, Any],
    *,
    path: Path = DEFAULT_KNOWLEDGE_BASE_PATH,
    notes: str = "",
) -> dict[str, Any]:
    kb = load_strategy_knowledge_base(path)
    items = kb.setdefault("items", {})
    context = proposal.get("context") if isinstance(proposal.get("context"), dict) else {}
    conditions = context.get("conditions") or proposal.get("conditions") or []
    normalized = normalize_conditions(conditions)
    item_id = str(proposal.get("knowledge_item_id") or knowledge_item_id(normalized))
    now = _now()
    existing = items.get(item_id) if isinstance(items.get(item_id), dict) else {}
    classification = classify_edge(proposal)
    previous_status = str(existing.get("status") or "candidate")
    status = previous_status
    if status == "retired":
        status = "needs_revalidation"
    elif classification["edge_type"] == "REJECTED_EDGE":
        status = "rejected"
    elif str(proposal.get("action")) == "PROMOTE_TO_CONFIRMED_EDGE":
        status = "confirmed"
    elif not existing:
        status = "candidate"

    history = list(existing.get("revalidation_history") or [])
    history.append(
        {
            "timestamp": now,
            "expected_pf": proposal.get("expected_pf"),
            "expected_total_r": proposal.get("expected_total_r"),
            "trade_reduction_pct": proposal.get("trade_reduction_pct"),
            "evidence": proposal.get("evidence"),
            "action": proposal.get("action"),
        }
    )
    proposal_ids = list(existing.get("qic_proposal_ids") or [])
    proposal_id = str(proposal.get("id") or "")
    if proposal_id and proposal_id not in proposal_ids:
        proposal_ids.append(proposal_id)
    item = {
        "id": item_id,
        "title": proposal.get("title") or ", ".join(normalized),
        "rule_conditions": normalized,
        "source": context.get("source") or proposal.get("source"),
        "status": status,
        "first_seen_at": existing.get("first_seen_at") or now,
        "last_seen_at": now,
        "times_seen": int(existing.get("times_seen", 0)) + 1,
        "times_proposed": int(existing.get("times_proposed", 0)) + 1,
        "times_approved": int(existing.get("times_approved", 0)),
        "times_rejected": int(existing.get("times_rejected", 0)),
        "last_expected_pf": proposal.get("expected_pf"),
        "last_expected_total_r": proposal.get("expected_total_r"),
        "last_trade_reduction_pct": proposal.get("trade_reduction_pct"),
        "last_evidence": proposal.get("evidence"),
        "confidence": proposal.get("confidence"),
        "risk_level": proposal.get("risk_level"),
        "risk_objections": proposal.get("risk_objections") or [],
        "edge_type": proposal.get("edge_type") or classification["edge_type"],
        "implementation_priority": proposal.get("implementation_priority") or classification["implementation_priority"],
        "notes": notes or existing.get("notes", ""),
        "qic_proposal_ids": proposal_ids[-50:],
        "revalidation_history": history[-50:],
    }
    items[item_id] = item
    save_strategy_knowledge_base(kb, path)
    return item


def record_proposal_review(
    proposal: dict[str, Any],
    status: str,
    *,
    path: Path = DEFAULT_KNOWLEDGE_BASE_PATH,
    rejection_reason: str = "",
) -> dict[str, Any] | None:
    kb = load_strategy_knowledge_base(path)
    item_id = str(proposal.get("knowledge_item_id") or (proposal.get("context") or {}).get("knowledge_item_id") or "")
    if not item_id:
        item_id = knowledge_item_id((proposal.get("context") or {}).get("conditions") or proposal.get("conditions") or [])
    item = kb.get("items", {}).get(item_id)
    if not isinstance(item, dict):
        item = upsert_knowledge_from_proposal(proposal, path=path)
        kb = load_strategy_knowledge_base(path)
        item = kb.get("items", {}).get(item_id)
    if not isinstance(item, dict):
        return None
    normalized = status.lower()
    if normalized == "approved":
        item["times_approved"] = int(item.get("times_approved", 0)) + 1
        if item.get("edge_type") == "STRUCTURAL_EDGE" or int(item.get("times_approved", 0)) >= 1:
            item["status"] = "confirmed"
    elif normalized == "rejected":
        item["times_rejected"] = int(item.get("times_rejected", 0)) + 1
        item["status"] = "rejected"
        if rejection_reason:
            item["notes"] = f"rejected: {rejection_reason}"
    item["last_reviewed_at"] = _now()
    save_strategy_knowledge_base(kb, path)
    return item


def write_strategy_knowledge_reports(
    *,
    kb: dict[str, Any],
    output_path: Path = Path("reports") / "qic",
) -> dict[str, Path]:
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "strategy_knowledge_base.json"
    md_path = output_path / "strategy_knowledge_base.md"
    json_path.write_text(json.dumps(kb, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(format_strategy_knowledge_markdown(kb), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def format_strategy_knowledge_markdown(kb: dict[str, Any]) -> str:
    lines = ["# QIC Strategy Knowledge Base", ""]
    items = list((kb.get("items") or {}).values())
    lines.append(f"Items: {len(items)}")
    lines.append("")
    if not items:
        lines.append("No knowledge items.")
        return "\n".join(lines) + "\n"
    columns = [
        "id",
        "status",
        "edge_type",
        "implementation_priority",
        "times_seen",
        "times_approved",
        "times_rejected",
        "last_expected_pf",
        "last_expected_total_r",
        "last_trade_reduction_pct",
    ]
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join("---" for _ in columns) + " |")
    for item in sorted(items, key=lambda row: str(row.get("last_seen_at", "")), reverse=True):
        lines.append("| " + " | ".join(_md(item.get(column, "")) for column in columns) + " |")
    return "\n".join(lines) + "\n"


def _condition_strings(conditions: Any) -> list[str]:
    if isinstance(conditions, str):
        return [conditions]
    if isinstance(conditions, list):
        output = []
        for item in conditions:
            if isinstance(item, dict):
                feature = item.get("feature") or item.get("label") or ""
                operator = item.get("operator") or "=="
                value = item.get("value") or item.get("context") or ""
                output.append(f"{feature}{operator}{value}")
            else:
                output.append(str(item))
        return output
    return []


def _is_consistently_positive(proposal: dict[str, Any], item: dict[str, Any] | None) -> bool:
    if not item:
        return False
    if _float(proposal.get("expected_pf")) < 1.05 or _float(proposal.get("expected_total_r")) <= 0:
        return False
    return int(item.get("times_seen", 0)) >= 2 or str(item.get("status")) == "confirmed"


def _float(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any, *, default: int = 0) -> int:
    try:
        return int(float(value or default))
    except (TypeError, ValueError):
        return default


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _md(value: Any) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, sort_keys=True)
    return str(value).replace("|", "\\|")
