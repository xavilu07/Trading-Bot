from __future__ import annotations

from typing import Any


def monitoring_director_review(proposal: dict[str, Any]) -> dict[str, Any]:
    baseline_pf = (proposal.get("context") or {}).get("baseline_pf") if isinstance(proposal.get("context"), dict) else proposal.get("baseline_pf")
    baseline_total_r = (proposal.get("context") or {}).get("baseline_total_r") if isinstance(proposal.get("context"), dict) else proposal.get("baseline_total_r")
    return {
        "agent": "monitoring_director",
        "decision": "MONITORING_PLAN_CREATED",
        "allowed": True,
        "monitoring_plan": {
            "baseline_metrics": {
                "profit_factor": baseline_pf,
                "total_r": baseline_total_r,
                "expected_profit_factor": proposal.get("expected_pf"),
                "expected_total_r": proposal.get("expected_total_r"),
            },
            "minimum_trades_required": 50,
            "monitoring_window_days": 14,
            "rollback_triggers": [
                "PF falls below baseline",
                "drawdown worsens by more than 20%",
                "expectancy worsens vs baseline",
                "5 consecutive losses attributed to the new rule",
                "insufficient trades after 14 days",
            ],
        },
    }
