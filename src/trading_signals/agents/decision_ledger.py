from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.agents.strategy_knowledge_base import normalize_conditions
from trading_signals.agents.qic_runtime import atomic_write_json, atomic_write_text

DEFAULT_DECISION_LEDGER_PATH = Path("data") / "qic" / "decision_ledger.jsonl"


def append_decision_ledger_entry(
    proposal: dict[str, Any] | None,
    *,
    path: Path = DEFAULT_DECISION_LEDGER_PATH,
    final_decision: str = "",
    human_action: str = "",
    implementation_status: str = "",
    notes: str = "",
    later_outcome: str = "",
) -> dict[str, Any]:
    proposal = proposal or {}
    entry = {
        "decision_id": f"decision_{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S%f')}",
        "proposal_id": proposal.get("id"),
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "action": proposal.get("action"),
        "conditions": normalize_conditions((proposal.get("context") or {}).get("conditions") if isinstance(proposal.get("context"), dict) else proposal.get("conditions") or []),
        "edge_type": proposal.get("edge_type") or (proposal.get("context") or {}).get("edge_type") if isinstance(proposal.get("context"), dict) else proposal.get("edge_type"),
        "expected_metrics": {
            "pf": proposal.get("expected_pf"),
            "total_r": proposal.get("expected_total_r"),
            "trade_reduction_pct": proposal.get("trade_reduction_pct"),
            "evidence": proposal.get("evidence"),
        },
        "final_decision": final_decision or proposal.get("action") or "NO_ACTIONABLE_PROPOSAL",
        "human_action": human_action,
        "implementation_status": implementation_status or proposal.get("status") or "",
        # Populated by scripts/run_qic_reconciliation.py once real closed trades exist to
        # verify this proposal's claim against — empty until then, never mutated in place
        # (JSONL is append-only; reconciliation appends a *new* entry with this filled in).
        "later_outcome": later_outcome,
        "notes": notes,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def load_decision_ledger(path: Path = DEFAULT_DECISION_LEDGER_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(raw, dict):
            entries.append(raw)
    return entries


def write_decision_ledger_reports(
    *,
    ledger_path: Path = DEFAULT_DECISION_LEDGER_PATH,
    output_path: Path = Path("reports") / "qic",
) -> dict[str, Path]:
    entries = load_decision_ledger(ledger_path)
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "decision_ledger.json"
    md_path = output_path / "decision_ledger.md"
    atomic_write_json(json_path, {"decisions": entries})
    atomic_write_text(md_path, _markdown(entries))
    return {"json": json_path, "markdown": md_path}


def _markdown(entries: list[dict[str, Any]]) -> str:
    lines = ["# QIC Decision Ledger", "", f"Decisions: {len(entries)}", ""]
    if not entries:
        lines.append("No decisions recorded.")
        return "\n".join(lines) + "\n"
    lines.append("| timestamp | proposal_id | final_decision | human_action | implementation_status |")
    lines.append("| --- | --- | --- | --- | --- |")
    for item in entries[-50:]:
        lines.append(
            f"| {_md(item.get('timestamp'))} | {_md(item.get('proposal_id'))} | {_md(item.get('final_decision'))} | "
            f"{_md(item.get('human_action'))} | {_md(item.get('implementation_status'))} |"
        )
    return "\n".join(lines) + "\n"


def _md(value: Any) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, sort_keys=True)
    return str(value).replace("|", "\\|")
