from __future__ import annotations

from pathlib import Path
from typing import Any

from trading_signals.agents.agent_self_evaluation import evaluate_agents
from trading_signals.agents.decision_ledger import append_decision_ledger_entry, write_decision_ledger_reports
from trading_signals.agents.research_memory import (
    load_research_memory,
    save_research_memory,
    should_skip_due_to_rejected_cooldown,
    update_research_memory_from_proposal,
    write_research_memory_reports,
)
from trading_signals.agents.revalidation_engine import run_revalidation_engine
from trading_signals.agents.state_of_council import build_state_of_council


def run_qic_learning_loop(
    *,
    proposal: dict[str, Any] | None,
    final_action: str,
    data_path: Path = Path("data"),
    reports_root: Path = Path("reports"),
    output_path: Path = Path("reports") / "qic",
    min_new_trades: int = 50,
    edge_confirmation_min_seen: int = 3,
    edge_reproposal_cooldown_days: int = 14,
    edge_degradation_pf_drop_pct: float = 15.0,
) -> dict[str, Any]:
    qic_data_path = data_path / "qic"
    research_memory_path = qic_data_path / "research_memory.json"
    knowledge_base_path = qic_data_path / "strategy_knowledge_base.json"
    proposal_store_path = data_path / "agent_proposals" / "proposals.jsonl"
    decision_ledger_path = qic_data_path / "decision_ledger.jsonl"
    if proposal:
        update_research_memory_from_proposal(proposal, path=research_memory_path)
    memory = load_research_memory(research_memory_path)
    memory = _promote_confirmed_edges(memory, min_seen=edge_confirmation_min_seen)
    save_research_memory(memory, research_memory_path)
    write_research_memory_reports(memory=memory, output_path=output_path)
    ledger_entry = append_decision_ledger_entry(
        proposal,
        path=decision_ledger_path,
        final_decision=final_action,
        implementation_status=str((proposal or {}).get("status") or ""),
    )
    write_decision_ledger_reports(ledger_path=decision_ledger_path, output_path=output_path)
    revalidation = run_revalidation_engine(
        knowledge_base_path=knowledge_base_path,
        research_memory_path=research_memory_path,
        reports_root=reports_root,
        output_path=output_path,
        min_new_trades=min_new_trades,
        degradation_pf_drop_pct=edge_degradation_pf_drop_pct,
    )
    agent_eval = evaluate_agents(
        agent_memory_path=qic_data_path / "agent_memory.json",
        revalidation_report_path=output_path / "revalidation.json",
        output_path=output_path,
    )
    state = build_state_of_council(
        knowledge_base_path=knowledge_base_path,
        research_memory_path=research_memory_path,
        proposal_store_path=proposal_store_path,
        agent_self_evaluation_path=output_path / "agent_self_evaluation.json",
        decision_ledger_path=decision_ledger_path,
        output_path=output_path,
    )
    return {
        "research_memory": memory,
        "decision_ledger_entry": ledger_entry,
        "revalidation": revalidation,
        "agent_self_evaluation": agent_eval,
        "state_of_council": state,
        "settings": {
            "min_new_trades": min_new_trades,
            "edge_confirmation_min_seen": edge_confirmation_min_seen,
            "edge_reproposal_cooldown_days": edge_reproposal_cooldown_days,
            "edge_degradation_pf_drop_pct": edge_degradation_pf_drop_pct,
        },
    }


def should_discard_repeated_rejected_proposal(
    proposal: dict[str, Any],
    *,
    research_memory: dict[str, Any],
    cooldown_days: int = 14,
) -> dict[str, Any]:
    return should_skip_due_to_rejected_cooldown(
        proposal,
        memory=research_memory,
        cooldown_days=cooldown_days,
    )


def _promote_confirmed_edges(memory: dict[str, Any], *, min_seen: int) -> dict[str, Any]:
    for item in (memory.get("experiments") or {}).values():
        if not isinstance(item, dict):
            continue
        if int(item.get("times_seen", 0)) >= min_seen and _float(item.get("last_pf")) > 1.05 and _float(item.get("last_total_r")) > 0:
            if item.get("current_status") not in {"degraded", "retired", "rejected"}:
                item["current_status"] = "candidate"
                item["last_revalidation_result"] = item.get("last_revalidation_result") or {"result": "edge_still_valid"}
    return memory


def _float(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0
