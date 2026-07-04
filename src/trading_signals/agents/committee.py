from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trading_signals.agents.coordinator_agent import coordinate_committee_proposals
from trading_signals.agents.proposal_store import DEFAULT_PROPOSALS_PATH, save_proposals
from trading_signals.agents.research_agent import generate_research_proposals, load_research_reports
from trading_signals.agents.simulator_agent import generate_simulator_proposals
from trading_signals.agents.strategy_agent import generate_strategy_proposals
from trading_signals.agents.telegram_approval import send_proposals_for_approval


def run_agent_committee(
    *,
    reports_root: Path = Path("reports"),
    data_path: Path = Path("data"),
    output_path: Path = Path("reports") / "agent_committee",
    enabled: bool = False,
    min_confidence: str = "MEDIUM",
    telegram_enabled: bool = False,
    telegram_bot_token: str = "",
    telegram_chat_id: str = "",
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if not enabled and not force:
        result = {
            "enabled": False,
            "proposals": [],
            "telegram_results": [],
            "reason": "agent_committee_disabled",
        }
        write_latest_reports(output_path, result)
        return result

    reports = load_research_reports(reports_root)
    drafts = [
        *generate_research_proposals(reports),
        *generate_strategy_proposals(reports),
        *generate_simulator_proposals(reports),
    ]
    proposals = coordinate_committee_proposals(drafts, min_confidence=min_confidence)
    proposal_path = data_path / "agent_proposals" / "proposals.jsonl"
    save_proposals(proposals, proposal_path)
    telegram_results = []
    if telegram_enabled:
        telegram_results = send_proposals_for_approval(
            proposals,
            bot_token=telegram_bot_token,
            chat_id=telegram_chat_id,
            dry_run=dry_run,
        )
    result = {
        "enabled": True,
        "proposal_count": len(proposals),
        "proposals": proposals,
        "proposal_store": str(proposal_path),
        "telegram_results": telegram_results,
    }
    write_latest_reports(output_path, result)
    return result


def write_latest_reports(output_path: Path, result: dict[str, Any]) -> dict[str, Path]:
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "latest_proposals.json"
    md_path = output_path / "latest_proposals.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(format_latest_proposals(result), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def format_latest_proposals(result: dict[str, Any]) -> str:
    lines = ["# Agent Committee Latest Proposals", ""]
    if not result.get("enabled"):
        lines.append(f"Status: disabled ({result.get('reason')})")
        return "\n".join(lines) + "\n"
    proposals = result.get("proposals") if isinstance(result.get("proposals"), list) else []
    lines.append(f"Proposals: {len(proposals)}")
    lines.append("")
    lines.extend(_table(proposals[:100]))
    return "\n".join(lines) + "\n"


def _table(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["No proposals."]
    columns = ["id", "title", "expected_pf", "expected_total_r", "trades_lost", "confidence", "risk_level", "evidence", "status"]
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(_md(row.get(column, "")) for column in columns) + " |")
    return lines


def _md(value: Any) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, sort_keys=True)
    return str(value).replace("|", "\\|")
