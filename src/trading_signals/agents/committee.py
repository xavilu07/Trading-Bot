from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trading_signals.agents.agent_memory import DEFAULT_MEMORY_PATH, update_agent_memory
from trading_signals.agents.cio import build_cio_consensus, build_cio_hypothesis_candidates
from trading_signals.agents.coordinator_agent import coordinate_committee_proposals
from trading_signals.agents.debate_engine import run_debate_engine
from trading_signals.agents.learning_loop import run_qic_learning_loop, should_discard_repeated_rejected_proposal
from trading_signals.agents.proposal_store import DEFAULT_PROPOSALS_PATH, save_proposals
from trading_signals.agents.qic_reporting import write_hypothesis_ranking_report, write_qic_reports
from trading_signals.agents.qic_variant_search import apply_variant_to_proposal, run_qic_variant_search
from trading_signals.agents.research_memory import load_research_memory
from trading_signals.agents.research_agent import generate_research_proposals, load_research_reports
from trading_signals.agents.simulator_agent import generate_simulator_proposals
from trading_signals.agents.strategy_knowledge_base import (
    enrich_proposal_with_knowledge,
    load_strategy_knowledge_base,
    upsert_knowledge_from_proposal,
    write_strategy_knowledge_reports,
)
from trading_signals.agents.strategy_agent import generate_strategy_proposals
from trading_signals.agents.telegram_approval import send_cio_proposal_for_approval, send_proposals_for_approval


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
    telegram_send_no_actionable: bool = True,
    telegram_min_priority: str = "LOW",
    dry_run: bool = False,
    force: bool = False,
    use_qic_v2: bool = True,
    revalidation_min_new_trades: int = 50,
    edge_confirmation_min_seen: int = 3,
    edge_reproposal_cooldown_days: int = 14,
    edge_degradation_pf_drop_pct: float = 15.0,
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

    if use_qic_v2:
        return run_quantum_investment_council_v2(
            reports_root=reports_root,
            data_path=data_path,
            output_path=output_path,
            min_confidence=min_confidence,
            telegram_enabled=telegram_enabled,
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
            telegram_send_no_actionable=telegram_send_no_actionable,
            telegram_min_priority=telegram_min_priority,
            dry_run=dry_run,
            revalidation_min_new_trades=revalidation_min_new_trades,
            edge_confirmation_min_seen=edge_confirmation_min_seen,
            edge_reproposal_cooldown_days=edge_reproposal_cooldown_days,
            edge_degradation_pf_drop_pct=edge_degradation_pf_drop_pct,
        )

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


def run_quantum_investment_council_v2(
    *,
    reports_root: Path = Path("reports"),
    data_path: Path = Path("data"),
    output_path: Path = Path("reports") / "qic",
    min_confidence: str = "MEDIUM",
    telegram_enabled: bool = False,
    telegram_bot_token: str = "",
    telegram_chat_id: str = "",
    telegram_send_no_actionable: bool = True,
    telegram_min_priority: str = "LOW",
    dry_run: bool = False,
    revalidation_min_new_trades: int = 50,
    edge_confirmation_min_seen: int = 3,
    edge_reproposal_cooldown_days: int = 14,
    edge_degradation_pf_drop_pct: float = 15.0,
) -> dict[str, Any]:
    debate = run_debate_engine(reports_root=reports_root)
    consensus = build_cio_consensus(debate, min_confidence=min_confidence)
    knowledge_path = data_path / "qic" / "strategy_knowledge_base.json"
    knowledge_base = load_strategy_knowledge_base(knowledge_path)
    research_memory = load_research_memory(data_path / "qic" / "research_memory.json")
    selection = _select_actionable_qic_proposal(
        debate=debate,
        data_path=data_path,
        output_path=output_path,
        min_confidence=min_confidence,
        knowledge_base=knowledge_base,
        research_memory=research_memory,
        edge_reproposal_cooldown_days=edge_reproposal_cooldown_days,
    )
    proposal = selection.get("proposal")
    if isinstance(proposal, dict):
        upsert_knowledge_from_proposal(proposal, path=knowledge_path)
        knowledge_base = load_strategy_knowledge_base(knowledge_path)
    consensus["single_proposal"] = proposal if isinstance(proposal, dict) else None
    consensus["hypothesis_ranking"] = {
        "final_action": selection.get("final_action"),
        "selected_rank": selection.get("selected_rank"),
    }
    write_hypothesis_ranking_report(output_path, selection)
    write_strategy_knowledge_reports(kb=knowledge_base, output_path=output_path)
    proposals = [proposal] if isinstance(proposal, dict) else []
    proposal_path = data_path / "agent_proposals" / "proposals.jsonl"
    if proposals:
        save_proposals(proposals, proposal_path)
    memory = update_agent_memory(
        debate.get("interventions", []),
        proposal if isinstance(proposal, dict) else None,
        path=data_path / "qic" / "agent_memory.json",
    )
    learning = run_qic_learning_loop(
        proposal=proposal if isinstance(proposal, dict) else None,
        final_action=str(selection.get("final_action") or "NO_ACTIONABLE_PROPOSAL"),
        data_path=data_path,
        reports_root=reports_root,
        output_path=output_path,
        min_new_trades=revalidation_min_new_trades,
        edge_confirmation_min_seen=edge_confirmation_min_seen,
        edge_reproposal_cooldown_days=edge_reproposal_cooldown_days,
        edge_degradation_pf_drop_pct=edge_degradation_pf_drop_pct,
    )
    paths = write_qic_reports(
        output_path=output_path,
        debate=debate,
        consensus=consensus,
        proposal=proposal if isinstance(proposal, dict) else None,
        agent_memory=memory,
        strategy_knowledge_base=knowledge_base,
    )
    telegram_results = []
    if telegram_enabled:
        priority_ok = _priority_rank((proposal or {}).get("implementation_priority")) >= _priority_rank(telegram_min_priority) if isinstance(proposal, dict) else False
        telegram_results = send_cio_proposal_for_approval(
            proposal if isinstance(proposal, dict) and priority_ok else None,
            bot_token=telegram_bot_token,
            chat_id=telegram_chat_id,
            dry_run=dry_run,
            no_actionable_summary=selection if telegram_send_no_actionable and (not isinstance(proposal, dict) or not priority_ok) else None,
        )
    result = {
        "enabled": True,
        "qic_v2": True,
        "proposal_count": len(proposals),
        "proposals": proposals,
        "single_proposal": proposal,
        "proposal_store": str(proposal_path),
        "telegram_results": telegram_results,
        "learning_loop": {
            "revalidation_summary": (learning.get("revalidation") or {}).get("summary"),
            "state_of_council": learning.get("state_of_council"),
        },
        "reports": {name: {kind: str(path) for kind, path in report_paths.items()} for name, report_paths in paths.items()},
    }
    write_latest_reports(Path("reports") / "agent_committee", result)
    return result


def _select_actionable_qic_proposal(
    *,
    debate: dict[str, Any],
    data_path: Path,
    output_path: Path,
    min_confidence: str,
    knowledge_base: dict[str, Any] | None = None,
    research_memory: dict[str, Any] | None = None,
    edge_reproposal_cooldown_days: int = 14,
) -> dict[str, Any]:
    candidates = build_cio_hypothesis_candidates(debate, min_confidence=min_confidence)
    ranking_rows = []
    selected_proposal: dict[str, Any] | None = None
    selected_rank: int | None = None
    final_action = "NO_ACTIONABLE_PROPOSAL"
    last_variant_search: dict[str, Any] | None = None

    for candidate in candidates:
        proposal = candidate.get("proposal")
        row = _ranking_row(candidate)
        if isinstance(proposal, dict):
            proposal = enrich_proposal_with_knowledge(proposal, knowledge_base or {})
            candidate["proposal"] = proposal
            row.update(_proposal_summary(proposal))
        if selected_proposal is not None:
            row["status"] = "not_evaluated_after_selection"
            ranking_rows.append(row)
            continue
        if not isinstance(proposal, dict):
            ranking_rows.append(row)
            continue
        cooldown = should_discard_repeated_rejected_proposal(
            proposal,
            research_memory=research_memory or {},
            cooldown_days=edge_reproposal_cooldown_days,
        )
        if cooldown.get("skip"):
            row["status"] = "discarded"
            row["discard_reason"] = cooldown.get("reason") or "rejected_cooldown_active"
            row["reason"] = row["discard_reason"]
            ranking_rows.append(row)
            continue
        if proposal.get("action") == "REQUIRES_VARIANT_SEARCH":
            variant_search = run_qic_variant_search(proposal, data_path=data_path, reports_path=output_path)
            last_variant_search = variant_search
            if variant_search.get("status") == "variant_found":
                proposal = apply_variant_to_proposal(proposal, variant_search)
                proposal = enrich_proposal_with_knowledge(proposal, knowledge_base or {})
                row.update(_proposal_summary(proposal))
                row["status"] = "selected"
                row["discard_reason"] = ""
                row["reason"] = "valid_variant_selected"
                selected_proposal = proposal
                selected_rank = int(candidate.get("rank") or 0)
                final_action = str(proposal.get("action") or "PROPOSE_VARIANT")
                ranking_rows.append(row)
                continue
            row["status"] = "discarded"
            row["discard_reason"] = "no_valid_variant_found"
            row["reason"] = "extreme_candidate_without_profitable_variant"
            ranking_rows.append(row)
            continue
        if proposal.get("action") in {
            "IMPLEMENTATION_CANDIDATE",
            "SHADOW_VALIDATION_REQUIRED",
            "PROPOSE_VARIANT",
            "REVALIDATE_KNOWN_EDGE",
            "PROMOTE_TO_CONFIRMED_EDGE",
        }:
            if proposal.get("action") == "IMPLEMENTATION_CANDIDATE":
                proposal = dict(proposal)
                proposal["action"] = "PROPOSE_IMPLEMENTATION"
            row.update(_proposal_summary(proposal))
            row["status"] = "selected"
            row["reason"] = _selection_reason(proposal)
            selected_proposal = proposal
            selected_rank = int(candidate.get("rank") or 0)
            final_action = str(proposal.get("action") or "PROPOSE_IMPLEMENTATION")
            ranking_rows.append(row)
            continue
        row["status"] = "discarded"
        row["discard_reason"] = f"non_actionable:{proposal.get('action')}"
        row["reason"] = row["discard_reason"]
        ranking_rows.append(row)

    if selected_proposal is None and last_variant_search is None:
        run_qic_variant_search(None, data_path=data_path, reports_path=output_path)
    return {
        "final_action": final_action,
        "selected_rank": selected_rank,
        "proposal": selected_proposal,
        "candidates": ranking_rows,
        "variant_search": last_variant_search,
    }


def _ranking_row(candidate: dict[str, Any]) -> dict[str, Any]:
    proposal = candidate.get("proposal")
    row = {
        "rank": candidate.get("rank"),
        "status": candidate.get("status"),
        "discard_reason": candidate.get("discard_reason") or "",
        "reason": candidate.get("discard_reason") or "",
        "risk_level": candidate.get("risk_level"),
        "trade_reduction_pct": candidate.get("trade_reduction_pct"),
    }
    if isinstance(proposal, dict):
        row.update(_proposal_summary(proposal))
    return row


def _selection_reason(proposal: dict[str, Any]) -> str:
    edge_type = proposal.get("edge_type") or (proposal.get("context") or {}).get("edge_type")
    if edge_type == "STRUCTURAL_EDGE":
        return "structural_edge_with_positive_simulation"
    if proposal.get("action") == "PROMOTE_TO_CONFIRMED_EDGE":
        return "known_edge_repeated_and_consistent"
    if proposal.get("action") == "REVALIDATE_KNOWN_EDGE":
        return "known_edge_requires_revalidation"
    return "best_actionable_qic_candidate"


def _priority_rank(value: Any) -> int:
    return {"REJECT": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}.get(str(value or "MEDIUM").upper(), 2)


def _proposal_summary(proposal: dict[str, Any]) -> dict[str, Any]:
    context = proposal.get("context") if isinstance(proposal.get("context"), dict) else {}
    return {
        "action": proposal.get("action"),
        "edge_type": proposal.get("edge_type") or context.get("edge_type"),
        "implementation_priority": proposal.get("implementation_priority") or context.get("implementation_priority"),
        "known_edge_status": proposal.get("known_edge_status") or context.get("known_edge_status"),
        "expected_pf": proposal.get("expected_pf"),
        "expected_total_r": proposal.get("expected_total_r"),
        "trades_lost": proposal.get("trades_lost"),
        "evidence": proposal.get("evidence"),
        "source": context.get("source"),
        "composite_score": context.get("composite_score"),
        "complexity": context.get("complexity"),
    }


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
