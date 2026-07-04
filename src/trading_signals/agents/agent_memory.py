from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_MEMORY_PATH = Path("data") / "agent_proposals" / "agent_memory.json"


def load_agent_memory(path: Path = DEFAULT_MEMORY_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"agents": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"agents": {}}
    return raw if isinstance(raw, dict) else {"agents": {}}


def update_agent_memory(
    interventions: list[dict[str, Any]],
    proposal: dict[str, Any] | None,
    *,
    path: Path = DEFAULT_MEMORY_PATH,
) -> dict[str, Any]:
    memory = load_agent_memory(path)
    agents = memory.setdefault("agents", {})
    proposal_status = str((proposal or {}).get("status") or "pending")
    for intervention in interventions:
        agent = str(intervention.get("agent") or "unknown_agent")
        item = agents.setdefault(
            agent,
            {
                "hypotheses": [],
                "proposals_accepted": 0,
                "proposals_rejected": 0,
                "proposals_pending": 0,
                "historical_precision": 0.0,
                "total_interventions": 0,
            },
        )
        item["total_interventions"] = int(item.get("total_interventions", 0)) + 1
        content = str(intervention.get("content") or "")
        if content and content not in item["hypotheses"]:
            item["hypotheses"].append(content)
            item["hypotheses"] = item["hypotheses"][-50:]
        if proposal_status == "approved":
            item["proposals_accepted"] = int(item.get("proposals_accepted", 0)) + 1
        elif proposal_status == "rejected":
            item["proposals_rejected"] = int(item.get("proposals_rejected", 0)) + 1
        else:
            item["proposals_pending"] = int(item.get("proposals_pending", 0)) + 1
        accepted = int(item.get("proposals_accepted", 0))
        rejected = int(item.get("proposals_rejected", 0))
        item["historical_precision"] = round(accepted / (accepted + rejected), 4) if accepted + rejected else 0.0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(memory, indent=2, sort_keys=True), encoding="utf-8")
    return memory
