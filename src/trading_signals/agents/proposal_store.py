from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_PROPOSALS_PATH = Path("data") / "agent_proposals" / "proposals.jsonl"


def load_proposals(path: Path = DEFAULT_PROPOSALS_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    proposals = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            proposals.append(item)
    return proposals


def save_proposals(proposals: list[dict[str, Any]], path: Path = DEFAULT_PROPOSALS_PATH) -> list[dict[str, Any]]:
    existing = {str(item.get("id")): item for item in load_proposals(path) if item.get("id")}
    for proposal in proposals:
        duplicate_id = _pending_duplicate_id(existing.values(), proposal)
        proposal_id = duplicate_id or str(proposal["id"])
        existing[proposal_id] = {**existing.get(proposal_id, {}), **proposal, "id": proposal_id}
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(existing.values(), key=lambda item: str(item.get("created_at", "")))
    path.write_text("\n".join(json.dumps(item, sort_keys=True) for item in ordered) + ("\n" if ordered else ""), encoding="utf-8")
    return ordered


def update_proposal_status(
    proposal_id: str,
    status: str,
    *,
    path: Path = DEFAULT_PROPOSALS_PATH,
    actor: str = "telegram_dev",
    approval_metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    normalized = status.lower()
    if normalized not in {"pending", "approved", "rejected", "expired", "implemented"}:
        raise ValueError(f"invalid proposal status: {status}")
    proposals = load_proposals(path)
    updated = None
    for proposal in proposals:
        if proposal.get("id") == proposal_id:
            proposal["status"] = normalized
            proposal["reviewed_at"] = datetime.now(tz=UTC).isoformat()
            proposal["reviewed_by"] = actor
            metadata = dict(proposal.get("approval_metadata") or {})
            metadata.update(approval_metadata or {})
            metadata["last_action"] = normalized
            metadata["actor"] = actor
            proposal["approval_metadata"] = metadata
            updated = proposal
            break
    if updated is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(item, sort_keys=True) for item in proposals) + "\n", encoding="utf-8")
    return updated


def _pending_duplicate_id(existing: Any, proposal: dict[str, Any]) -> str | None:
    proposal_conditions = _normalized_conditions(proposal)
    proposal_day = str(proposal.get("created_at") or "")[:10]
    if not proposal_conditions or not proposal_day:
        return None
    for item in existing:
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "pending") != "pending":
            continue
        if str(item.get("created_at") or "")[:10] != proposal_day:
            continue
        if _normalized_conditions(item) == proposal_conditions:
            return str(item.get("id"))
    return None


def _normalized_conditions(proposal: dict[str, Any]) -> tuple[str, ...]:
    context = proposal.get("context") if isinstance(proposal.get("context"), dict) else {}
    raw = context.get("normalized_conditions") or context.get("conditions") or proposal.get("conditions") or []
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, list):
        values = [json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item) for item in raw]
    else:
        values = []
    return tuple(sorted(value.strip().lower() for value in values if value))
