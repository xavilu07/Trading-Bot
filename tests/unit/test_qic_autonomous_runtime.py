from __future__ import annotations

import json
from pathlib import Path

from trading_signals.agents.autonomous_orchestrator import AutonomousQICOrchestrator
from trading_signals.agents.debate_engine import run_debate_engine
from trading_signals.agents.notification_center import QICNotificationCenter
from trading_signals.agents.qic_runtime import ProcessLock, atomic_write_json, read_json_safe
from trading_signals.agents.system_health import calculate_autonomous_score


class Settings:
    qic_phase_timeout_seconds = 5
    qic_phase_max_retries = 0
    qic_lock_stale_minutes = 120
    qic_autonomous_dry_run = True
    qic_autonomous_enabled = False
    qic_notification_cooldown_seconds = 900
    qic_notification_rate_limit_per_hour = 20
    qic_telegram_enabled = False
    qic_telegram_send_no_actionable = True
    qic_telegram_min_priority = "MEDIUM"
    agent_telegram_approval_enabled = False
    qic_auto_apply_low_risk = False
    qic_auto_apply_medium_risk = False
    qic_live_trading_changes_allowed = False
    qic_change_allowlist = ["tests", "Planning"]
    qic_change_denylist = [".env"]


def test_atomic_json_recovers_last_good(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    atomic_write_json(path, {"value": 1})
    atomic_write_json(path, {"value": 2})
    path.write_text("{broken", encoding="utf-8")

    assert read_json_safe(path, {}, recover=True) == {"value": 1}


def test_process_lock_prevents_concurrent_owner(tmp_path: Path) -> None:
    first = ProcessLock(tmp_path / "qic.lock")
    second = ProcessLock(tmp_path / "qic.lock")

    assert first.acquire() is True
    assert second.acquire() is False
    first.release()
    assert second.acquire() is True
    second.release()


def test_orchestrator_records_phase_and_history(tmp_path: Path, monkeypatch) -> None:
    orchestrator = AutonomousQICOrchestrator(
        settings=Settings(),
        data_path=tmp_path / "data",
        reports_root=tmp_path / "reports",
        output_path=tmp_path / "reports" / "qic",
        logs_path=tmp_path / "logs",
    )
    monkeypatch.setattr(orchestrator, "_phase_operation", lambda phase: lambda: {"phase": phase, "ok": True})

    report = orchestrator.run(phases=["events", "health"], dry_run=True)

    assert report["status"] == "completed"
    assert report["stages_executed"] == ["events", "health"]
    assert (tmp_path / "data" / "qic" / "autonomous_runs.jsonl").exists()
    assert json.loads((tmp_path / "reports" / "qic" / "autonomous_run.json").read_text())["run_id"] == report["run_id"]


def test_orchestrator_lock_skips_duplicate_process(tmp_path: Path) -> None:
    orchestrator = AutonomousQICOrchestrator(
        settings=Settings(),
        data_path=tmp_path / "data",
        reports_root=tmp_path / "reports",
        output_path=tmp_path / "reports" / "qic",
        logs_path=tmp_path / "logs",
    )
    lock = ProcessLock(orchestrator.lock_path)
    assert lock.acquire()
    try:
        report = orchestrator.run(phases=["health"], dry_run=True)
    finally:
        lock.release()

    assert report["status"] == "skipped_locked"


def test_notification_center_deduplicates(tmp_path: Path) -> None:
    center = QICNotificationCenter(data_path=tmp_path, enabled=False, cooldown_seconds=900)

    first = center.publish("QIC_STARTED", title="Run", message="Started", dedupe_key="same")
    second = center.publish("QIC_STARTED", title="Run", message="Started", dedupe_key="same")

    assert first["status"] == "recorded"
    assert second["status"] == "suppressed"
    assert second["reason"] == "cooldown"
    assert second["grouped_repetitions"] == 1


def test_autonomous_score_is_deterministic() -> None:
    healthy = {"status": "HEALTHY"}
    score, breakdown = calculate_autonomous_score(
        components={
            "trading_scheduler": healthy,
            "telegram_listener": healthy,
            "qic_scheduler": healthy,
            "reports": healthy,
            "json_integrity": healthy,
        },
        activity={"agents": {name: {"executions_last_24h": 1} for name in ("research", "strategy", "risk", "simulation")}},
        memory={"updated_at": "now"},
        proposals=1,
        errors=0,
    )

    assert score == 100
    assert sum(breakdown.values()) == 100


def test_health_transition_notifications_are_recorded_without_telegram(tmp_path: Path) -> None:
    orchestrator = AutonomousQICOrchestrator(
        settings=Settings(),
        data_path=tmp_path / "data",
        reports_root=tmp_path / "reports",
        output_path=tmp_path / "reports" / "qic",
        logs_path=tmp_path / "logs",
    )
    result = orchestrator.notify_health(
        {
            "status": "DEGRADED",
            "state_transition": True,
            "components": {
                "telegram_listener": {"status": "UNHEALTHY", "reason": "stale"},
            },
        }
    )

    assert result["count"] == 1
    assert result["notifications"][0]["event_type"] == "TELEGRAM_LISTENER_DOWN"
    assert result["notifications"][0]["status"] == "recorded"


def test_disabled_agent_is_skipped_without_execution(tmp_path: Path) -> None:
    report = run_debate_engine(
        reports_root=tmp_path / "reports",
        activity_path=tmp_path / "activity.json",
        enabled_agents=["research_director", "strategy_director", "simulation_director"],
    )

    risk = next(item for item in report["interventions"] if item["agent"] == "risk_director")
    assert risk["stage"] == "disabled"
    assert risk["data"]["disabled"] is True


def test_lock_held_by_a_living_process_is_not_stale(tmp_path: Path) -> None:
    """Age alone said nothing about whether a lock was abandoned.

    A long-lived singleton holds its lock for as long as it runs, so the health
    report sat at DEGRADED/stale_locks purely because the telegram listener had
    been up for more than two hours.
    """
    import json as _json
    import os as _os
    import time as _time

    from trading_signals.agents.system_health import _lock_status

    locks = tmp_path / "locks"
    locks.mkdir()
    alive = locks / "telegram_listener.lock"
    alive.write_text(_json.dumps({"pid": _os.getpid(), "created_at": "2026-08-19T06:56:26+00:00"}), encoding="utf-8")
    dead = locks / "abandoned.lock"
    dead.write_text(_json.dumps({"pid": 2 ** 22, "created_at": "2026-08-19T06:56:26+00:00"}), encoding="utf-8")
    old = _time.time() - 86400
    for item in (alive, dead):
        _os.utime(item, (old, old))

    status = _lock_status(locks)

    assert status["active"] == 2
    assert status["stale"] == 1
    assert status["status"] == "DEGRADED"


def test_lock_status_is_healthy_when_every_holder_is_alive(tmp_path: Path) -> None:
    import json as _json
    import os as _os
    import time as _time

    from trading_signals.agents.system_health import _lock_status

    locks = tmp_path / "locks"
    locks.mkdir()
    item = locks / "telegram_listener.lock"
    item.write_text(_json.dumps({"pid": _os.getpid()}), encoding="utf-8")
    old = _time.time() - 86400
    _os.utime(item, (old, old))

    status = _lock_status(locks)

    assert status["stale"] == 0
    assert status["reason"] == "ok"
