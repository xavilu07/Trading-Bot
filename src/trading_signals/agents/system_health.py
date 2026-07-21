from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.agents.agent_activity import load_agent_activity
from trading_signals.agents.qic_runtime import atomic_write_json, atomic_write_text, file_age_seconds, read_json_safe, utc_now
from trading_signals.agents.research_memory import load_research_memory


HEALTHY = "HEALTHY"
DEGRADED = "DEGRADED"
UNHEALTHY = "UNHEALTHY"
UNKNOWN = "UNKNOWN"


def build_system_health(
    *,
    data_path: Path = Path("data"),
    reports_path: Path = Path("reports"),
    runtime_path: Path = Path(".runtime"),
    qic_enabled: bool = False,
    telegram_configured: bool = False,
    data_freshness_hours: float = 12,
    report_freshness_hours: float = 12,
    disk_warning_pct: float = 90,
    memory_warning_pct: float = 90,
    output_path: Path | None = None,
) -> dict[str, Any]:
    qic_reports = output_path or reports_path / "qic"
    scheduler_heartbeat = data_path / "runtime" / "scheduler_heartbeat.json"
    autonomous_report = qic_reports / "autonomous_run.json"
    listener_report = qic_reports / "telegram_listener.json"
    trades_path = data_path / "paper_trading" / "trades.csv"
    agent_activity = load_agent_activity(data_path / "qic" / "agent_activity.json")
    memory = load_research_memory(data_path / "qic" / "research_memory.json")
    proposals = _count_jsonl(data_path / "agent_proposals" / "proposals.jsonl")
    errors = _recent_error_count(qic_reports / "autonomous_runs.jsonl")
    components = {
        "trading_scheduler": _freshness_status(scheduler_heartbeat, 0.5),
        "qic_scheduler": _freshness_status(autonomous_report, report_freshness_hours) if qic_enabled else {"status": UNKNOWN, "reason": "qic_disabled"},
        "telegram_listener": _freshness_status(listener_report, 0.25) if telegram_configured else {"status": UNKNOWN, "reason": "telegram_not_configured"},
        "paper_data": _freshness_status(trades_path, data_freshness_hours),
        "reports": _freshness_status(qic_reports / "state_of_council.json", report_freshness_hours),
        "dashboard": _dashboard_status(data_path, reports_path),
        "locks": _lock_status(data_path / "qic" / "locks"),
        "json_integrity": _json_integrity(qic_reports),
        "disk": _disk_status(Path.cwd(), warning_pct=disk_warning_pct),
        "memory": _memory_status(warning_pct=memory_warning_pct),
    }
    overall = _overall_status(components)
    autonomous_score, score_breakdown = calculate_autonomous_score(
        components=components,
        activity=agent_activity,
        memory=memory,
        proposals=proposals,
        errors=errors,
    )
    previous = read_json_safe(data_path / "qic" / "health_state.json", {})
    report = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "status": overall,
        "previous_status": previous.get("status") if isinstance(previous, dict) else None,
        "state_transition": bool(previous and previous.get("status") != overall),
        "autonomous_score": autonomous_score,
        "autonomous_score_breakdown": score_breakdown,
        "components": components,
        "recent_errors": errors,
        "agent_count": len(agent_activity.get("agents") or {}),
        "active_agents_24h": sum(1 for item in (agent_activity.get("agents") or {}).values() if int(item.get("executions_last_24h", 0)) > 0),
        "research_experiments": len(memory.get("experiments") or {}),
        "proposal_records": proposals,
    }
    atomic_write_json(data_path / "qic" / "health_state.json", {"status": overall, "updated_at": report["generated_at"]})
    write_system_health_reports(report, output_path=qic_reports)
    return report


def calculate_autonomous_score(
    *,
    components: dict[str, dict[str, Any]],
    activity: dict[str, Any],
    memory: dict[str, Any],
    proposals: int,
    errors: int,
) -> tuple[int, dict[str, int]]:
    active_agents = sum(1 for item in (activity.get("agents") or {}).values() if int(item.get("executions_last_24h", 0)) > 0)
    expected_agents = 4
    breakdown = {
        "scheduler_health": 15 if components.get("trading_scheduler", {}).get("status") == HEALTHY else 0,
        "listener_health": 15 if components.get("telegram_listener", {}).get("status") in {HEALTHY, UNKNOWN} else 0,
        "qic_cycle_freshness": 15 if components.get("qic_scheduler", {}).get("status") in {HEALTHY, UNKNOWN} else 0,
        "active_agents": round(15 * min(active_agents, expected_agents) / expected_agents),
        "memory_updated": 10 if memory.get("updated_at") else 0,
        "revalidation_fresh": 10 if components.get("reports", {}).get("status") == HEALTHY else 0,
        "proposals_recorded": 5 if proposals > 0 else 0,
        "validation_health": 10 if components.get("json_integrity", {}).get("status") == HEALTHY else 0,
        "error_budget": 5 if errors == 0 else max(0, 5 - min(errors, 5)),
    }
    return min(100, sum(breakdown.values())), breakdown


def write_system_health_reports(report: dict[str, Any], *, output_path: Path = Path("reports") / "qic") -> dict[str, Path]:
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "system_health.json"
    md_path = output_path / "system_health.md"
    atomic_write_json(json_path, report)
    lines = [
        "# QIC System Health",
        "",
        f"- status: {report.get('status')}",
        f"- autonomous_score: {report.get('autonomous_score')}/100",
        f"- generated_at: {report.get('generated_at')}",
        f"- state_transition: {report.get('state_transition')}",
        "",
        "## Components",
        "",
        "| component | status | reason | age_seconds |",
        "| --- | --- | --- | --- |",
    ]
    for name, item in (report.get("components") or {}).items():
        lines.append(f"| {name} | {item.get('status')} | {item.get('reason', '')} | {item.get('age_seconds', '')} |")
    lines.extend(["", "## Autonomous Score Formula", ""])
    for name, value in (report.get("autonomous_score_breakdown") or {}).items():
        lines.append(f"- {name}: {value}")
    atomic_write_text(md_path, "\n".join(lines) + "\n")
    return {"json": json_path, "markdown": md_path}


def _freshness_status(path: Path, max_age_hours: float) -> dict[str, Any]:
    age = file_age_seconds(path)
    if age is None:
        return {"status": UNKNOWN, "reason": "missing", "path": str(path), "age_seconds": None}
    status = HEALTHY if age <= max_age_hours * 3600 else DEGRADED
    return {"status": status, "reason": "fresh" if status == HEALTHY else "stale", "path": str(path), "age_seconds": round(age, 1)}


def _lock_status(path: Path) -> dict[str, Any]:
    locks = list(path.glob("*.lock")) if path.exists() else []
    stale = [item for item in locks if (file_age_seconds(item) or 0) > 7200]
    return {"status": DEGRADED if stale else HEALTHY, "reason": "stale_locks" if stale else "ok", "active": len(locks), "stale": len(stale)}


def _dashboard_status(data_path: Path, reports_path: Path) -> dict[str, Any]:
    heartbeat = data_path / "runtime" / "dashboard_heartbeat.json"
    if heartbeat.exists():
        return _freshness_status(heartbeat, 0.25)
    generated = reports_path / "dashboard.html"
    if generated.exists():
        return {"status": UNKNOWN, "reason": "static_dashboard_present_process_not_observable", "path": str(generated), "age_seconds": file_age_seconds(generated)}
    return {"status": UNKNOWN, "reason": "dashboard_process_not_observable", "path": None, "age_seconds": None}


def _json_integrity(path: Path) -> dict[str, Any]:
    corrupt = []
    if path.exists():
        for file_path in path.glob("*.json"):
            try:
                json.loads(file_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                corrupt.append(str(file_path))
    return {"status": UNHEALTHY if corrupt else HEALTHY, "reason": "corrupt_json" if corrupt else "ok", "corrupt_files": corrupt}


def _disk_status(path: Path, *, warning_pct: float) -> dict[str, Any]:
    usage = shutil.disk_usage(path)
    used_pct = round((usage.used / usage.total) * 100, 2) if usage.total else 0.0
    status = DEGRADED if used_pct >= warning_pct else HEALTHY
    return {"status": status, "reason": "disk_warning" if status == DEGRADED else "ok", "used_pct": used_pct}


def _memory_status(*, warning_pct: float) -> dict[str, Any]:
    used_pct = _memory_used_pct()
    if used_pct is None:
        return {"status": UNKNOWN, "reason": "not_observable", "used_pct": None}
    status = DEGRADED if used_pct >= warning_pct else HEALTHY
    return {"status": status, "reason": "memory_warning" if status == DEGRADED else "ok", "used_pct": used_pct}


def _memory_used_pct() -> float | None:
    path = Path("/proc/meminfo")
    if not path.exists():
        return None
    values: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        try:
            values[key] = float(raw.strip().split()[0])
        except (ValueError, IndexError):
            continue
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    return round((1 - available / total) * 100, 2) if total else None


def _overall_status(components: dict[str, dict[str, Any]]) -> str:
    statuses = [item.get("status") for item in components.values()]
    if UNHEALTHY in statuses:
        return UNHEALTHY
    if DEGRADED in statuses:
        return DEGRADED
    if all(status == UNKNOWN for status in statuses):
        return UNKNOWN
    return HEALTHY


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def _recent_error_count(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-100:]:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("status") in {"failed", "partial_failure"}:
            count += 1
    return count
