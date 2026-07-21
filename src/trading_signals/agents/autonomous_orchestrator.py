from __future__ import annotations

import csv
import hashlib
import json
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from trading_signals.agents.committee import run_agent_committee
from trading_signals.agents.implementation.code_engineer import run_code_engineer
from trading_signals.agents.implementation.code_changes import CodeChangeManager
from trading_signals.agents.implementation.implementation_review_council import run_implementation_review_for_proposal_id
from trading_signals.agents.notification_center import QICNotificationCenter
from trading_signals.agents.proposal_store import load_proposals
from trading_signals.agents.qic_autonomous_reports import write_autonomous_qic_reports
from trading_signals.agents.qic_event_detector import detect_qic_events
from trading_signals.agents.qic_runtime import ProcessLock, append_jsonl, atomic_write_json, atomic_write_text, read_json_safe, utc_now
from trading_signals.agents.revalidation_engine import run_revalidation_engine
from trading_signals.agents.state_of_council import build_state_of_council
from trading_signals.agents.system_health import build_system_health
from trading_signals.agents.telegram_approval import resolve_qic_telegram_config


PHASES = ("events", "research", "revalidation", "implementation", "health", "reports", "notifications")


class AutonomousQICOrchestrator:
    def __init__(
        self,
        *,
        settings: object,
        data_path: Path = Path("data"),
        reports_root: Path = Path("reports"),
        output_path: Path = Path("reports") / "qic",
        logs_path: Path = Path("logs"),
    ) -> None:
        self.settings = settings
        self.data_path = data_path
        self.reports_root = reports_root
        self.output_path = output_path
        self.logs_path = logs_path
        self.qic_data_path = data_path / "qic"
        self.lock_path = self.qic_data_path / "locks" / "autonomous.lock"
        self.history_path = self.qic_data_path / "autonomous_runs.jsonl"
        self.report_history_path = output_path / "autonomous_runs.jsonl"
        self.current_report_path = output_path / "autonomous_run.json"
        self.log_path = logs_path / "qic_autonomous.jsonl"
        self.timeout_seconds = max(1, int(getattr(settings, "qic_phase_timeout_seconds", 300)))
        self.max_retries = max(0, int(getattr(settings, "qic_phase_max_retries", 1)))
        telegram = resolve_qic_telegram_config(settings)
        self.telegram_config = telegram
        self.notifications = QICNotificationCenter(
            data_path=self.qic_data_path,
            bot_token=str(telegram.get("bot_token") or ""),
            chat_ids=list(telegram.get("chat_ids") or []),
            # Persistent credentials do not implicitly activate outbound notifications.
            enabled=bool(getattr(settings, "qic_telegram_enabled", False)) and bool(telegram.get("configured")),
            cooldown_seconds=int(getattr(settings, "qic_notification_cooldown_seconds", 900)),
            rate_limit_per_hour=int(getattr(settings, "qic_notification_rate_limit_per_hour", 20)),
        )
        self._context: dict[str, Any] = {}

    def run(
        self,
        *,
        phases: list[str] | None = None,
        dry_run: bool | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        selected = _normalize_phases(phases)
        run_dry = bool(getattr(self.settings, "qic_autonomous_dry_run", True)) if dry_run is None else bool(dry_run)
        stale_seconds = max(60, int(getattr(self.settings, "qic_lock_stale_minutes", 120)) * 60)
        lock = ProcessLock(self.lock_path, stale_after_seconds=stale_seconds)
        if not lock.acquire():
            return self._locked_report(selected, run_dry)
        run_id = "qic_" + datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S%fZ")
        started = time.perf_counter()
        report: dict[str, Any] = {
            "schema_version": 1,
            "run_id": run_id,
            "started_at": utc_now(),
            "finished_at": None,
            "duration_ms": None,
            "status": "running",
            "dry_run": run_dry,
            "phases_requested": selected,
            "stages_executed": [],
            "stages_skipped": [],
            "errors": [],
            "data_processed": {"paper_trade_rows": _csv_rows(self.data_path / "paper_trading" / "trades.csv")},
            "hypotheses": 0,
            "proposals": 0,
            "decisions": 0,
            "code_changes": 0,
            "notifications": 0,
            "phase_results": {},
        }
        self._context = {"run_id": run_id, "dry_run": run_dry, "report": report}
        self.notifications.dry_run = run_dry
        try:
            self._log("qic_autonomous_started", run_id=run_id, dry_run=run_dry, phases=selected)
            self.notifications.publish(
                "QIC_STARTED",
                title="QIC autonomous cycle started",
                message=f"Run {run_id} started in {'dry-run' if run_dry else 'enabled'} mode.",
                context={"run_id": run_id},
                dedupe_key=f"QIC_STARTED:{run_id}",
            )
            for phase in selected:
                if phase == "research" and not force and self._is_duplicate_research_run():
                    report["stages_skipped"].append({"phase": phase, "reason": "unchanged_input_idempotency_window"})
                    continue
                result = self._execute_phase(phase)
                report["phase_results"][phase] = _jsonable(result)
                if result.get("status") == "failed":
                    report["errors"].append({"phase": phase, "error": result.get("error"), "attempts": result.get("attempts")})
                else:
                    report["stages_executed"].append(phase)
                self._update_counts(report, phase, result)
            report["status"] = "completed" if not report["errors"] else "partial_failure"
        except Exception as exc:
            report["status"] = "failed"
            report["errors"].append({"phase": "orchestrator", "error": str(exc), "traceback": traceback.format_exc(limit=8)})
        finally:
            report["finished_at"] = utc_now()
            report["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
            report["input_fingerprint"] = self._input_fingerprint()
            self._write_run_report(report)
            lock.release()
        event_type = "QIC_COMPLETED" if report["status"] == "completed" else "QIC_FAILED"
        notification = self.notifications.publish(
            event_type,
            title=f"QIC cycle {report['status']}",
            message=(
                f"Run {run_id}: {len(report['stages_executed'])} stages, "
                f"{len(report['errors'])} errors, {report['proposals']} proposals."
            ),
            context={"run_id": run_id, "status": report["status"]},
            dedupe_key=f"{event_type}:{run_id}",
        )
        report["notifications"] += 1 if notification.get("status") not in {"suppressed"} else 0
        self._write_run_report(report, replace_history=False)
        return report

    def status(self) -> dict[str, Any]:
        report = read_json_safe(self.current_report_path, {})
        return report if isinstance(report, dict) else {}

    def health(self) -> dict[str, Any]:
        report = build_system_health(
            data_path=self.data_path,
            reports_path=self.reports_root,
            qic_enabled=bool(getattr(self.settings, "qic_autonomous_enabled", False)),
            telegram_configured=bool(self.telegram_config.get("configured")),
            data_freshness_hours=float(getattr(self.settings, "qic_data_freshness_hours", 12)),
            report_freshness_hours=float(getattr(self.settings, "qic_report_freshness_hours", 12)),
            output_path=self.output_path,
        )
        self._context["health"] = report
        return report

    def notify_health(self, report: dict[str, Any]) -> dict[str, Any]:
        self._context = {"health": report}
        return self._run_notifications()

    def _execute_phase(self, phase: str) -> dict[str, Any]:
        operation = self._phase_operation(phase)
        started_at = utc_now()
        started = time.perf_counter()
        last_error = ""
        for attempt in range(1, self.max_retries + 2):
            executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"qic-{phase}")
            future = executor.submit(operation)
            try:
                value = future.result(timeout=self.timeout_seconds)
                executor.shutdown(wait=True)
                return {
                    "status": "completed",
                    "phase": phase,
                    "started_at": started_at,
                    "finished_at": utc_now(),
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    "attempts": attempt,
                    "result": value,
                }
            except FutureTimeoutError:
                last_error = f"phase_timeout_after_{self.timeout_seconds}s"
                future.cancel()
                executor.shutdown(wait=False, cancel_futures=True)
            except Exception as exc:
                last_error = f"{type(exc).__name__}:{exc}"
                executor.shutdown(wait=True)
            self._log("qic_phase_retry", phase=phase, attempt=attempt, error=last_error)
            if attempt <= self.max_retries:
                time.sleep(min(2**attempt, 5))
        return {
            "status": "failed",
            "phase": phase,
            "started_at": started_at,
            "finished_at": utc_now(),
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "attempts": self.max_retries + 1,
            "error": last_error,
        }

    def _phase_operation(self, phase: str) -> Callable[[], Any]:
        operations: dict[str, Callable[[], Any]] = {
            "events": self._run_events,
            "research": self._run_research,
            "revalidation": self._run_revalidation,
            "implementation": self._run_implementation,
            "reports": self._run_reports,
            "health": self.health,
            "notifications": self._run_notifications,
        }
        return operations[phase]

    def _run_events(self) -> dict[str, Any]:
        result = detect_qic_events(
            trades_path=self.data_path / "paper_trading" / "trades.csv",
            research_memory_path=self.data_path / "qic" / "research_memory.json",
            code_engineer_report_path=self.output_path / "code_engineer.json",
        )
        self._context["events"] = result
        return result

    def _run_research(self) -> dict[str, Any]:
        result = run_agent_committee(
            reports_root=self.reports_root,
            data_path=self.data_path,
            output_path=self.output_path,
            enabled=True,
            min_confidence=str(getattr(self.settings, "agent_committee_min_confidence", "MEDIUM")),
            telegram_enabled=False,
            dry_run=bool(self._context["dry_run"]),
            force=True,
            revalidation_min_new_trades=int(getattr(self.settings, "qic_revalidation_min_new_trades", 50)),
            edge_confirmation_min_seen=int(getattr(self.settings, "qic_edge_confirmation_min_seen", 3)),
            edge_reproposal_cooldown_days=int(getattr(self.settings, "qic_edge_reproposal_cooldown_days", 14)),
            edge_degradation_pf_drop_pct=float(getattr(self.settings, "qic_edge_degradation_pf_drop_pct", 15)),
            enabled_agents=list(getattr(self.settings, "qic_enabled_agents", [])),
        )
        self._context["research"] = result
        return result

    def _run_revalidation(self) -> dict[str, Any]:
        result = run_revalidation_engine(
            knowledge_base_path=self.data_path / "qic" / "strategy_knowledge_base.json",
            research_memory_path=self.data_path / "qic" / "research_memory.json",
            reports_root=self.reports_root,
            output_path=self.output_path,
            min_new_trades=int(getattr(self.settings, "qic_revalidation_min_new_trades", 50)),
            degradation_pf_drop_pct=float(getattr(self.settings, "qic_edge_degradation_pf_drop_pct", 15)),
        )
        self._context["revalidation"] = result
        return result

    def _run_implementation(self) -> dict[str, Any]:
        proposals = load_proposals(self.data_path / "agent_proposals" / "proposals.jsonl")
        pending = [item for item in proposals if item.get("status") in {"approved", "approved_for_implementation_review"}]
        output = {"reviewed": [], "code_engineer": [], "auto_apply": []}
        for proposal in pending[:5]:
            proposal_id = str(proposal.get("id") or "")
            if not proposal_id:
                continue
            review = run_implementation_review_for_proposal_id(
                proposal_id,
                proposal_store_path=self.data_path / "agent_proposals" / "proposals.jsonl",
                knowledge_base_path=self.data_path / "qic" / "strategy_knowledge_base.json",
                output_path=self.output_path,
            )
            output["reviewed"].append({"proposal_id": proposal_id, "decision": review.get("decision"), "allowed": review.get("allowed_to_generate_patch")})
            if not review.get("allowed_to_generate_patch") or not bool(getattr(self.settings, "qic_code_engineer_enabled", False)):
                continue
            code = run_code_engineer(
                proposal_id=proposal_id,
                proposal_store_path=self.data_path / "agent_proposals" / "proposals.jsonl",
                reports_path=self.output_path,
                dry_run=True,
                apply=False,
                run_tests=False,
                allow_apply=False,
            )
            output["code_engineer"].append({"proposal_id": proposal_id, "status": code.get("status"), "files_planned": code.get("files_planned", [])})
        manager = CodeChangeManager(
            project_root=Path("."),
            store_path=self.data_path / "qic" / "code_changes.json",
            backup_root=self.data_path / "qic" / "change_backups",
            allowlist=list(getattr(self.settings, "qic_change_allowlist", [])),
            denylist=list(getattr(self.settings, "qic_change_denylist", [])),
        )
        if not self._context["dry_run"]:
            for change in manager.list_changes():
                if change.get("final_status") != "prepared":
                    continue
                if str(change.get("risk_level")) == "LOW" and bool(getattr(self.settings, "qic_auto_apply_low_risk", False)):
                    self.notifications.publish(
                        "CODE_READY_TO_APPLY",
                        title="Low-risk QIC change ready",
                        message=f"Change {change.get('change_id')} passed to auto-apply policy evaluation.",
                        context={"change_id": change.get("change_id"), "proposal_id": change.get("proposal_id")},
                        dedupe_key=f"CODE_READY_TO_APPLY:{change.get('change_id')}",
                    )
                applied = manager.apply(
                    str(change.get("change_id")),
                    auto=True,
                    auto_apply_low_risk=bool(getattr(self.settings, "qic_auto_apply_low_risk", False)),
                    auto_apply_medium_risk=bool(getattr(self.settings, "qic_auto_apply_medium_risk", False)),
                    live_trading_changes_allowed=bool(getattr(self.settings, "qic_live_trading_changes_allowed", False)),
                    max_files=int(getattr(self.settings, "qic_auto_apply_max_files", 8)),
                    max_changed_lines=int(getattr(self.settings, "qic_auto_apply_max_changed_lines", 400)),
                )
                output["auto_apply"].append({"change_id": change.get("change_id"), "status": applied.get("final_status"), "blockers": applied.get("blockers", [])})
                if applied.get("final_status") == "applied":
                    self.notifications.publish(
                        "CODE_AUTO_APPLIED",
                        title="Low-risk QIC change applied",
                        message=f"Change {change.get('change_id')} was applied after policy validation. Feature flags remain unchanged.",
                        priority="CRITICAL",
                        context={"change_id": change.get("change_id"), "proposal_id": change.get("proposal_id")},
                        dedupe_key=f"CODE_AUTO_APPLIED:{change.get('change_id')}",
                    )
        self._context["implementation"] = output
        return output

    def _run_reports(self) -> dict[str, Any]:
        events = (self._context.get("events") or {}).get("events", [])
        autonomous = write_autonomous_qic_reports(
            output_path=self.output_path,
            knowledge_base_path=self.data_path / "qic" / "strategy_knowledge_base.json",
            research_memory_path=self.data_path / "qic" / "research_memory.json",
            decision_ledger_path=self.data_path / "qic" / "decision_ledger.jsonl",
            events=events,
            daily_enabled=bool(getattr(self.settings, "qic_daily_brief_enabled", True)),
            weekly_enabled=bool(getattr(self.settings, "qic_weekly_research_review_enabled", True)),
        )
        state = build_state_of_council(
            knowledge_base_path=self.data_path / "qic" / "strategy_knowledge_base.json",
            research_memory_path=self.data_path / "qic" / "research_memory.json",
            proposal_store_path=self.data_path / "agent_proposals" / "proposals.jsonl",
            agent_self_evaluation_path=self.output_path / "agent_self_evaluation.json",
            decision_ledger_path=self.data_path / "qic" / "decision_ledger.jsonl",
            output_path=self.output_path,
            agent_activity_path=self.data_path / "qic" / "agent_activity.json",
            system_health_path=self.output_path / "system_health.json",
        )
        return {"autonomous_reports": autonomous, "state_of_council": state}

    def _run_notifications(self) -> dict[str, Any]:
        results = []
        research = self._context.get("research") or {}
        proposal = research.get("single_proposal") if isinstance(research, dict) else None
        if isinstance(proposal, dict):
            buttons = [[
                {"text": "✅ Approve", "callback_data": f"agent:approve:{proposal.get('id')}"},
                {"text": "❌ Reject", "callback_data": f"agent:reject:{proposal.get('id')}"},
                {"text": "📊 Details", "callback_data": f"agent:details:{proposal.get('id')}"},
            ]]
            results.append(
                self.notifications.publish(
                    "NEW_CIO_PROPOSAL",
                    title=str(proposal.get("title") or "New CIO proposal"),
                    message=(
                        f"Action {proposal.get('action')}; PF {proposal.get('expected_pf')}; "
                        f"TotalR {proposal.get('expected_total_r')}; risk {proposal.get('risk_level')}."
                    ),
                    context={"proposal_id": proposal.get("id"), "priority": proposal.get("implementation_priority")},
                    buttons=buttons,
                    dedupe_key=f"NEW_CIO_PROPOSAL:{proposal.get('id')}:{proposal.get('status')}",
                )
            )
        for event in (self._context.get("events") or {}).get("events", []):
            if str(event.get("severity") or "").lower() not in {"high", "critical"}:
                continue
            results.append(
                self.notifications.publish(
                    _event_notification_type(str(event.get("type") or "")),
                    title=f"Extraordinary QIC Meeting: {event.get('type')}",
                    message=json.dumps(event, ensure_ascii=False, sort_keys=True),
                    priority="CRITICAL",
                    context=event,
                )
            )
        health = self._context.get("health") or {}
        if health.get("state_transition"):
            components = health.get("components") or {}
            transition_events = {
                "trading_scheduler": "SCHEDULER_DOWN",
                "telegram_listener": "TELEGRAM_LISTENER_DOWN",
                "disk": "DISK_WARNING",
                "memory": "MEMORY_WARNING",
            }
            for component, event_type in transition_events.items():
                component_health = components.get(component) or {}
                if component_health.get("status") not in {"DEGRADED", "UNHEALTHY"}:
                    continue
                results.append(
                    self.notifications.publish(
                        event_type,
                        title=f"QIC health transition: {component}",
                        message=f"{component} is {component_health.get('status')}: {component_health.get('reason')}",
                        context={"component": component, **component_health},
                        dedupe_key=f"{event_type}:{health.get('status')}:{component_health.get('reason')}",
                    )
                )
        return {"notifications": results, "count": len(results)}

    def _is_duplicate_research_run(self) -> bool:
        current = self._input_fingerprint()
        previous = read_json_safe(self.current_report_path, {})
        if not isinstance(previous, dict) or previous.get("status") not in {"completed", "partial_failure"}:
            return False
        finished = _parse_dt(previous.get("finished_at"))
        if finished is None or (datetime.now(tz=UTC) - finished).total_seconds() > 3600:
            return False
        return previous.get("input_fingerprint") == current

    def _input_fingerprint(self) -> str:
        inputs = []
        for path in (
            self.data_path / "paper_trading" / "trades.csv",
            self.reports_root / "strategy_simulator" / "overview.json",
            self.reports_root / "quant_research" / "overview.json",
            self.reports_root / "historical_intelligence" / "overview.json",
        ):
            inputs.append((str(path), path.stat().st_size if path.exists() else 0, path.stat().st_mtime_ns if path.exists() else 0))
        return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode("utf-8")).hexdigest()

    def _update_counts(self, report: dict[str, Any], phase: str, result: dict[str, Any]) -> None:
        value = result.get("result") if isinstance(result.get("result"), dict) else {}
        if phase == "research":
            report["proposals"] = int(value.get("proposal_count") or 0)
            ranking = read_json_safe(self.output_path / "hypothesis_ranking.json", {})
            report["hypotheses"] = len(ranking.get("ranking") or ranking.get("candidates") or []) if isinstance(ranking, dict) else 0
        elif phase == "revalidation":
            report["decisions"] += len(value.get("results") or [])
        elif phase == "implementation":
            report["code_changes"] += len(value.get("code_engineer") or [])
        elif phase == "notifications":
            report["notifications"] += int(value.get("count") or 0)

    def _write_run_report(self, report: dict[str, Any], *, replace_history: bool = True) -> None:
        self.output_path.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.current_report_path, report)
        atomic_write_text(self.output_path / "autonomous_run.md", _run_markdown(report))
        if replace_history:
            append_jsonl(self.history_path, report)
            append_jsonl(self.report_history_path, report)

    def _locked_report(self, phases: list[str], dry_run: bool) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "run_id": None,
            "started_at": utc_now(),
            "finished_at": utc_now(),
            "status": "skipped_locked",
            "dry_run": dry_run,
            "phases_requested": phases,
            "stages_executed": [],
            "stages_skipped": [{"phase": "all", "reason": "concurrent_run_locked"}],
            "errors": [],
        }

    def _log(self, event: str, **fields: Any) -> None:
        append_jsonl(self.log_path, {"timestamp": utc_now(), "event": event, **fields})


def _normalize_phases(phases: list[str] | None) -> list[str]:
    if not phases:
        return list(PHASES)
    output = []
    for phase in phases:
        normalized = phase.strip().lower()
        if normalized not in PHASES:
            raise ValueError(f"unknown_qic_phase:{phase}")
        if normalized not in output:
            output.append(normalized)
    return output


def _csv_rows(path: Path) -> int:
    if not path.exists() or path.stat().st_size == 0:
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _parse_dt(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _event_notification_type(event_type: str) -> str:
    mapping = {
        "known_edge_degraded": "EDGE_DEGRADED",
        "confirmed_edge_invalidated": "EDGE_DEGRADED",
        "pf_degradation": "PERFORMANCE_DEGRADED",
        "drawdown_degradation": "DRAWDOWN_WARNING",
        "code_engineer_blocked": "CODE_VALIDATION_FAILED",
        "pending_proposal_stale": "PROPOSAL_PENDING_APPROVAL",
        "approved_proposal_pending_implementation": "PROPOSAL_APPROVED",
        "rollback_triggered": "CODE_ROLLED_BACK",
    }
    return mapping.get(event_type, "QIC_FAILED")


def _run_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# QIC Autonomous Run",
        "",
        f"- run_id: {report.get('run_id')}",
        f"- status: {report.get('status')}",
        f"- dry_run: {report.get('dry_run')}",
        f"- started_at: {report.get('started_at')}",
        f"- finished_at: {report.get('finished_at')}",
        f"- duration_ms: {report.get('duration_ms')}",
        f"- stages_executed: {', '.join(report.get('stages_executed') or []) or 'none'}",
        f"- stages_skipped: {len(report.get('stages_skipped') or [])}",
        f"- errors: {len(report.get('errors') or [])}",
        f"- hypotheses: {report.get('hypotheses')}",
        f"- proposals: {report.get('proposals')}",
        f"- decisions: {report.get('decisions')}",
        f"- code_changes: {report.get('code_changes')}",
        f"- notifications: {report.get('notifications')}",
        "",
        "## Phase Results",
        "",
    ]
    for phase, result in (report.get("phase_results") or {}).items():
        lines.append(f"- {phase}: {result.get('status')} ({result.get('duration_ms')} ms)")
    return "\n".join(lines) + "\n"
