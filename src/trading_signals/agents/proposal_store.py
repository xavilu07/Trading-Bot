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
        existing[str(proposal["id"])] = {**existing.get(str(proposal["id"]), {}), **proposal}
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
) -> dict[str, Any] | None:
    normalized = status.lower()
    if normalized not in {"pending", "approved", "rejected"}:
        raise ValueError(f"invalid proposal status: {status}")
    proposals = load_proposals(path)
    updated = None
    for proposal in proposals:
        if proposal.get("id") == proposal_id:
            proposal["status"] = normalized
            proposal["reviewed_at"] = datetime.now(tz=UTC).isoformat()
            proposal["reviewed_by"] = actor
            updated = proposal
            break
    if updated is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(item, sort_keys=True) for item in proposals) + "\n", encoding="utf-8")
    return updated
