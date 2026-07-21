from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from trading_signals.agents.agent_activity import load_agent_activity
from trading_signals.agents.decision_ledger import load_decision_ledger
from trading_signals.agents.implementation.code_changes import CodeChangeManager
from trading_signals.agents.notification_center import read_notification_history
from trading_signals.agents.proposal_store import load_proposals
from trading_signals.agents.qic_runtime import read_json_safe
from trading_signals.agents.research_memory import load_research_memory
from trading_signals.agents.strategy_knowledge_base import load_strategy_knowledge_base
from trading_signals.app.settings import Settings


def build_qic_control_center(
    *,
    data_path: Path = Path("data"),
    reports_path: Path = Path("reports"),
    limit: int = 50,
) -> dict[str, Any]:
    qic_reports = reports_path / "qic"
    qic_data = data_path / "qic"
    health = _dict(read_json_safe(qic_reports / "system_health.json", {}))
    run = _dict(read_json_safe(qic_reports / "autonomous_run.json", {}))
    state = _dict(read_json_safe(qic_reports / "state_of_council.json", {}))
    activity = load_agent_activity(qic_data / "agent_activity.json")
    self_evaluation = _dict(read_json_safe(qic_reports / "agent_self_evaluation.json", {}))
    agents = _merge_agent_metrics(activity.get("agents") or {}, self_evaluation.get("agents") or {})
    proposals = load_proposals(data_path / "agent_proposals" / "proposals.jsonl")
    memory = load_research_memory(qic_data / "research_memory.json")
    kb = load_strategy_knowledge_base(qic_data / "strategy_knowledge_base.json")
    notifications = read_notification_history(qic_data / "notification_history.jsonl", limit=limit)
    changes = CodeChangeManager(store_path=qic_data / "code_changes.json", backup_root=qic_data / "change_backups").list_changes()
    ledger = load_decision_ledger(qic_data / "decision_ledger.jsonl")
    performance = _performance(reports_path)
    settings = Settings()
    variant_search = _dict(read_json_safe(qic_reports / "variant_search.json", {}))
    return {
        "schema_version": 1,
        "status": {
            "autonomous_score": health.get("autonomous_score", state.get("autonomous_score", 0)),
            "health": health.get("status", "UNKNOWN"),
            "last_cycle": run.get("finished_at"),
            "next_execution": _next_execution(run.get("finished_at"), float(settings.qic_scheduler_interval_hours)),
            "last_run_id": run.get("run_id"),
            "last_run_status": run.get("status", "UNKNOWN"),
            "scheduler": (health.get("components") or {}).get("qic_scheduler", {}),
            "trading_scheduler": (health.get("components") or {}).get("trading_scheduler", {}),
            "telegram": (health.get("components") or {}).get("telegram_listener", {}),
            "code_engineer": {
                **_dict(read_json_safe(qic_reports / "code_engineer.json", {})),
                "enabled": settings.qic_code_engineer_enabled,
            },
            "auto_apply": {
                "low_risk": settings.qic_auto_apply_low_risk,
                "medium_risk": settings.qic_auto_apply_medium_risk,
                "live_trading_changes_allowed": settings.qic_live_trading_changes_allowed,
            },
            "autonomous_enabled": settings.qic_autonomous_enabled,
            "dry_run": run.get("dry_run", True),
        },
        "activity": {
            "investigations_today": int((agents.get("research_director") or {}).get("executions_last_24h") or 0),
            "hypotheses": run.get("hypotheses", 0),
            "variants": len(variant_search.get("variants") or variant_search.get("evaluated_variants") or []),
            "simulations": sum(int(item.get("simulations_run") or 0) for item in agents.values()),
            "proposals": len(proposals),
            "blocked": sum(int(item.get("proposals_blocked") or 0) for item in agents.values()),
            "pending": sum(1 for item in proposals if item.get("status") in {"pending", "postponed"}),
            "approved": sum(1 for item in proposals if str(item.get("status", "")).startswith("approved")),
            "code_changes": len(changes),
            "applied_changes": sum(1 for item in changes if item.get("final_status") == "applied"),
            "rollbacks": sum(1 for item in changes if item.get("final_status") == "rolled_back"),
            "revalidations": len((_dict(read_json_safe(qic_reports / "revalidation.json", {}))).get("results") or []),
            "decisions": len(ledger),
        },
        "agents": agents,
        "performance": performance,
        "memory": {
            "known_edges": len(kb.get("items") or {}),
            "confirmed": _count_values(kb.get("items") or {}, "status", "confirmed"),
            "candidates": _count_values(kb.get("items") or {}, "status", "candidate"),
            "degraded": _count_values(memory.get("experiments") or {}, "current_status", "degraded"),
            "rejected": _count_values(memory.get("experiments") or {}, "current_status", "rejected"),
            "experiments": len(memory.get("experiments") or {}),
            "updated_at": memory.get("updated_at"),
        },
        "proposals": proposals[-limit:],
        "timeline": [*_ledger_timeline(ledger[-limit:]), *notifications][-limit:],
        "changes": changes[:limit],
        "runs": _read_jsonl(qic_data / "autonomous_runs.jsonl", limit=limit),
        "errors": _errors(run, health, notifications),
        "actions_enabled": False,
        "actions_disabled_reason": "secure_admin_auth_not_configured",
    }


def _performance(reports_path: Path) -> dict[str, Any]:
    performance = _dict(read_json_safe(reports_path / "performance_intelligence_report_v2.json", {}))
    global_metrics = performance.get("global_performance") or performance.get("global") or performance.get("summary") or {}
    return {
        "global": global_metrics,
        "periods": performance.get("periods") or {},
        "paper_vs_shadow": performance.get("paper_vs_shadow") or {},
    }


def _next_execution(value: Any, interval_hours: float) -> str | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return (parsed + timedelta(hours=max(0.1, interval_hours))).isoformat()


def _merge_agent_metrics(activity: dict[str, Any], evaluation: dict[str, Any]) -> dict[str, Any]:
    names = sorted(set(activity) | set(evaluation))
    output: dict[str, Any] = {}
    for name in names:
        item = dict(activity.get(name) or {})
        reviewed = evaluation.get(name) or {}
        if reviewed:
            item["accuracy_score"] = reviewed.get("accuracy_score", item.get("accuracy_score", 0))
            item["current_bias_notes"] = reviewed.get("bias_notes") or item.get("current_bias_notes") or []
            item["confidence_calibration"] = "CALIBRATED" if reviewed.get("last_self_review") else item.get("confidence_calibration", "NO_DATA")
        item["activity_state"] = _agent_state(item)
        output[name] = item
    return output


def _agent_state(item: dict[str, Any]) -> str:
    if not int(item.get("executions_total") or 0):
        return "NO_DATA"
    if item.get("last_status") not in {"completed", "ok"}:
        return "FAILING" if int(item.get("failures_total") or 0) else "DEGRADED"
    if int(item.get("executions_last_24h") or 0) > 0:
        return "ACTIVE"
    return "INACTIVE"


def _ledger_timeline(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "event_type": "CIO_DECISION",
            "priority": "INFO",
            "created_at": item.get("timestamp"),
            "title": item.get("final_decision"),
            "context": {"proposal_id": item.get("proposal_id"), "human_action": item.get("human_action")},
        }
        for item in rows
    ]


def _errors(run: dict[str, Any], health: dict[str, Any], notifications: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for item in run.get("errors") or []:
        output.append({"component": item.get("phase", "qic"), "severity": "ERROR", "message": item.get("error"), "last_seen": run.get("finished_at")})
    for event in notifications:
        if event.get("priority") == "CRITICAL" or event.get("status") == "partial":
            output.append({"component": event.get("event_type"), "severity": event.get("priority"), "message": event.get("message"), "last_seen": event.get("created_at")})
    for name, item in (health.get("components") or {}).items():
        if item.get("status") in {"DEGRADED", "UNHEALTHY"}:
            output.append({"component": name, "severity": item.get("status"), "message": item.get("reason"), "last_seen": health.get("generated_at")})
    return output[-50:]


def _count_values(items: dict[str, Any], key: str, value: str) -> int:
    return sum(1 for item in items.values() if isinstance(item, dict) and item.get(key) == value)


def _read_jsonl(path: Path, *, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    output = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            output.append(item)
    return output


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
