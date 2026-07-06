from __future__ import annotations

from typing import Any

from trading_signals.agents.implementation.implementation_plan import build_implementation_plan


def implementation_director_review(proposal: dict[str, Any]) -> dict[str, Any]:
    plan = build_implementation_plan(proposal)
    supported = plan.get("change_type") != "manual_research_required"
    return {
        "agent": "implementation_director",
        "decision": "PLAN_CREATED" if supported else "MANUAL_RESEARCH_REQUIRED",
        "allowed": supported,
        "plan": plan,
        "blockers": [] if supported else ["unsupported_proposal_template"],
    }
