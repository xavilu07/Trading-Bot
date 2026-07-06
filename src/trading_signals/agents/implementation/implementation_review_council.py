from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.agents.implementation.code_safety_director import code_safety_review
from trading_signals.agents.implementation.deployment_director import deployment_director_review
from trading_signals.agents.implementation.implementation_director import implementation_director_review
from trading_signals.agents.implementation.implementation_store import append_implementation_record
from trading_signals.agents.implementation.monitoring_director import monitoring_director_review
from trading_signals.agents.implementation.rollback_plan import build_rollback_plan
from trading_signals.agents.implementation.test_director import test_director_review
from trading_signals.agents.proposal_store import load_proposals
from trading_signals.agents.strategy_knowledge_base import (
    DEFAULT_KNOWLEDGE_BASE_PATH,
    load_strategy_knowledge_base,
    save_strategy_knowledge_base,
)


def run_implementation_review(
    proposal: dict[str, Any],
    *,
    output_path: Path = Path("reports") / "qic",
    knowledge_base_path: Path = DEFAULT_KNOWLEDGE_BASE_PATH,
    store_path: Path = Path("data") / "qic" / "implementation_reviews.jsonl",
) -> dict[str, Any]:
    implementation = implementation_director_review(proposal)
    plan = implementation["plan"]
    rollback = build_rollback_plan(proposal, plan)
    safety = code_safety_review(proposal, plan, rollback)
    tests = test_director_review(plan)
    deployment = deployment_director_review(plan)
    monitoring = monitoring_director_review(proposal)
    blockers = sorted(set(implementation.get("blockers", []) + safety.get("blockers", []) + tests.get("blockers", [])))
    allowed = all(item.get("allowed") for item in (implementation, safety, tests, deployment, monitoring)) and not blockers
    if float(proposal.get("trade_reduction_pct") or 0) > 60:
        allowed = False
        if "trade_reduction_above_60" not in blockers:
            blockers.append("trade_reduction_above_60")
    decision = "IMPLEMENTATION_ALLOWED" if allowed else "MANUAL_REVIEW_REQUIRED"
    if "unsupported_proposal_template" in blockers or "trade_reduction_above_60" in blockers:
        decision = "NEEDS_MORE_RESEARCH"
    review = {
        "proposal_id": proposal.get("id"),
        "knowledge_item_id": proposal.get("knowledge_item_id"),
        "created_at": datetime.now(tz=UTC).isoformat(),
        "decision": decision,
        "allowed_to_generate_patch": allowed,
        "blockers": blockers,
        "required_feature_flags": plan.get("required_feature_flags", []),
        "required_tests": tests.get("required_tests", []),
        "validation_commands": tests.get("validation_commands", []),
        "implementation_plan": plan,
        "rollback_plan": rollback,
        "monitoring_plan": monitoring.get("monitoring_plan", {}),
        "agent_reviews": {
            "implementation_director": implementation,
            "code_safety_director": safety,
            "test_director": tests,
            "deployment_director": deployment,
            "monitoring_director": monitoring,
            "cio": {"decision": decision, "allowed": allowed},
        },
    }
    write_implementation_review_reports(review, output_path=output_path)
    append_implementation_record(review, path=store_path)
    _update_knowledge_implementation_status(review, knowledge_base_path=knowledge_base_path)
    return review


def run_implementation_review_for_proposal_id(
    proposal_id: str,
    *,
    proposal_store_path: Path = Path("data") / "agent_proposals" / "proposals.jsonl",
    output_path: Path = Path("reports") / "qic",
    knowledge_base_path: Path = DEFAULT_KNOWLEDGE_BASE_PATH,
) -> dict[str, Any]:
    proposal = next((item for item in load_proposals(proposal_store_path) if item.get("id") == proposal_id), None)
    if not proposal:
        review = {
            "proposal_id": proposal_id,
            "created_at": datetime.now(tz=UTC).isoformat(),
            "decision": "REJECT_IMPLEMENTATION",
            "allowed_to_generate_patch": False,
            "blockers": ["proposal_not_found"],
        }
        write_implementation_review_reports(review, output_path=output_path)
        return review
    return run_implementation_review(proposal, output_path=output_path, knowledge_base_path=knowledge_base_path)


def write_implementation_review_reports(review: dict[str, Any], *, output_path: Path) -> dict[str, Path]:
    output_path.mkdir(parents=True, exist_ok=True)
    review_json = output_path / "implementation_review.json"
    review_md = output_path / "implementation_review.md"
    plan_json = output_path / "implementation_plan.json"
    plan_md = output_path / "implementation_plan.md"
    review_json.write_text(json.dumps(review, indent=2, sort_keys=True), encoding="utf-8")
    review_md.write_text(_review_markdown(review), encoding="utf-8")
    plan = review.get("implementation_plan", {})
    plan_json.write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")
    plan_md.write_text(_plan_markdown(plan, review), encoding="utf-8")
    rollback = review.get("rollback_plan", {})
    (output_path / "rollback_plan.json").write_text(json.dumps(rollback, indent=2, sort_keys=True), encoding="utf-8")
    (output_path / "rollback_plan.md").write_text(_rollback_markdown(rollback), encoding="utf-8")
    return {"json": review_json, "markdown": review_md}


def _update_knowledge_implementation_status(review: dict[str, Any], *, knowledge_base_path: Path) -> None:
    item_id = str(review.get("knowledge_item_id") or "")
    if not item_id:
        return
    kb = load_strategy_knowledge_base(knowledge_base_path)
    item = kb.get("items", {}).get(item_id)
    if not isinstance(item, dict):
        return
    item["implementation_status"] = "implementation_allowed" if review.get("allowed_to_generate_patch") else "approved_for_review"
    history = list(item.get("implementation_history") or [])
    history.append({"timestamp": review.get("created_at"), "event": "implementation_review", "decision": review.get("decision")})
    item["implementation_history"] = history[-50:]
    save_strategy_knowledge_base(kb, knowledge_base_path)


def _review_markdown(review: dict[str, Any]) -> str:
    lines = ["# QIC Implementation Review", ""]
    for key in ("proposal_id", "knowledge_item_id", "decision", "allowed_to_generate_patch"):
        lines.append(f"- {key}: {review.get(key)}")
    lines.append(f"- blockers: {review.get('blockers', [])}")
    lines.append("")
    lines.append("## Required Feature Flags")
    for flag in review.get("required_feature_flags", []):
        lines.append(f"- {flag.get('name')} default={flag.get('default')}")
    lines.append("")
    lines.append("## Required Tests")
    for test in review.get("required_tests", []):
        lines.append(f"- {test}")
    return "\n".join(lines) + "\n"


def _plan_markdown(plan: dict[str, Any], review: dict[str, Any]) -> str:
    lines = ["# QIC Implementation Plan", "", f"- summary: {plan.get('summary')}", f"- decision: {review.get('decision')}", ""]
    lines.append("## Steps")
    for step in plan.get("implementation_steps", []):
        lines.append(f"- {step}")
    return "\n".join(lines) + "\n"


def _rollback_markdown(rollback: dict[str, Any]) -> str:
    lines = ["# QIC Rollback Plan", ""]
    for step in rollback.get("steps", []):
        lines.append(f"- {step}")
    return "\n".join(lines) + "\n"
