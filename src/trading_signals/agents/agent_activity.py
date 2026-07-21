from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from trading_signals.agents.qic_runtime import atomic_write_json, read_json_safe, utc_now


DEFAULT_AGENT_ACTIVITY_PATH = Path("data") / "qic" / "agent_activity.json"


def record_agent_execution(
    agent: str,
    *,
    started_at: str,
    completed_at: str | None = None,
    status: str = "completed",
    duration_ms: float = 0.0,
    inputs_processed: int = 0,
    outputs_generated: int = 0,
    supported: int = 0,
    opposed: int = 0,
    proposals_generated: int = 0,
    proposals_blocked: int = 0,
    simulations_run: int = 0,
    path: Path = DEFAULT_AGENT_ACTIVITY_PATH,
) -> dict[str, Any]:
    state = read_json_safe(path, {"schema_version": 1, "agents": {}, "executions": []})
    if not isinstance(state, dict):
        state = {"schema_version": 1, "agents": {}, "executions": []}
    agents = state.setdefault("agents", {})
    item = agents.setdefault(agent, _empty_agent())
    previous_total = int(item.get("executions_total", 0))
    item.update(
        {
            "executions_total": previous_total + 1,
            "last_started_at": started_at,
            "last_completed_at": completed_at or utc_now(),
            "last_status": status,
            "failures_total": int(item.get("failures_total", 0)) + (0 if status == "completed" else 1),
            "average_duration_ms": round(
                ((float(item.get("average_duration_ms", 0)) * previous_total) + max(0.0, duration_ms)) / (previous_total + 1),
                3,
            ),
            "inputs_processed": int(item.get("inputs_processed", 0)) + max(0, inputs_processed),
            "outputs_generated": int(item.get("outputs_generated", 0)) + max(0, outputs_generated),
            "hypotheses_supported": int(item.get("hypotheses_supported", 0)) + max(0, supported),
            "hypotheses_opposed": int(item.get("hypotheses_opposed", 0)) + max(0, opposed),
            "proposals_generated": int(item.get("proposals_generated", 0)) + max(0, proposals_generated),
            "proposals_blocked": int(item.get("proposals_blocked", 0)) + max(0, proposals_blocked),
            "simulations_run": int(item.get("simulations_run", 0)) + max(0, simulations_run),
        }
    )
    execution = {
        "agent": agent,
        "started_at": started_at,
        "completed_at": completed_at or utc_now(),
        "status": status,
        "duration_ms": round(max(0.0, duration_ms), 3),
    }
    executions = list(state.get("executions") or [])
    executions.append(execution)
    state["executions"] = executions[-2000:]
    _refresh_windows(state)
    state["updated_at"] = utc_now()
    atomic_write_json(path, state)
    return item


def load_agent_activity(path: Path = DEFAULT_AGENT_ACTIVITY_PATH) -> dict[str, Any]:
    state = read_json_safe(path, {"schema_version": 1, "agents": {}, "executions": []})
    if not isinstance(state, dict):
        return {"schema_version": 1, "agents": {}, "executions": []}
    _refresh_windows(state)
    return state


def _refresh_windows(state: dict[str, Any]) -> None:
    now = datetime.now(tz=UTC)
    last_day = now - timedelta(hours=24)
    last_week = now - timedelta(days=7)
    executions = [item for item in state.get("executions", []) if isinstance(item, dict)]
    for name, item in (state.get("agents") or {}).items():
        matching = [row for row in executions if row.get("agent") == name]
        item["executions_last_24h"] = sum(1 for row in matching if (_parse_dt(row.get("started_at")) or datetime.min.replace(tzinfo=UTC)) >= last_day)
        item["executions_last_7d"] = sum(1 for row in matching if (_parse_dt(row.get("started_at")) or datetime.min.replace(tzinfo=UTC)) >= last_week)


def _empty_agent() -> dict[str, Any]:
    return {
        "executions_total": 0,
        "executions_last_24h": 0,
        "executions_last_7d": 0,
        "last_started_at": None,
        "last_completed_at": None,
        "last_status": "no_data",
        "failures_total": 0,
        "average_duration_ms": 0.0,
        "inputs_processed": 0,
        "outputs_generated": 0,
        "hypotheses_supported": 0,
        "hypotheses_opposed": 0,
        "proposals_generated": 0,
        "proposals_blocked": 0,
        "simulations_run": 0,
        "accuracy_score": 0.0,
        "confidence_calibration": "NO_DATA",
        "current_bias_notes": [],
    }


def _parse_dt(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
