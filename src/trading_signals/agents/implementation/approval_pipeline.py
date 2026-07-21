from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from trading_signals.agents.implementation.code_engineer import run_code_engineer
from trading_signals.agents.implementation.implementation_review_council import (
    run_implementation_review_for_proposal_id,
)
from trading_signals.agents.implementation.patch_generator import generate_patch_report
from trading_signals.agents.proposal_store import load_proposals, update_proposal_status
from trading_signals.agents.qic_runtime import ProcessLock, atomic_write_json, atomic_write_text, read_json_safe, utc_now


AUTO_APPLY_FLAGS = (
    "QIC_AUTO_APPLY_ON_APPROVAL",
    "QIC_CODE_ENGINEER_ENABLED",
    "QIC_CODE_ENGINEER_ALLOW_APPLY",
)


def approval_auto_apply_config(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    env = os.environ if environ is None else environ
    values = {name: _as_bool(env.get(name, "false")) for name in AUTO_APPLY_FLAGS}
    missing = [name for name, enabled in values.items() if not enabled]
    return {"enabled": not missing, "flags": values, "missing_flags": missing}


def enqueue_approved_proposal_pipeline(
    *,
    proposal_id: str,
    proposal_store_path: Path,
    knowledge_base_path: Path,
    reports_path: Path,
    actor: str,
    chat_id: str,
    project_root: Path | None = None,
) -> dict[str, Any]:
    proposal = _load_proposal(proposal_id, proposal_store_path)
    if proposal is None:
        return {"status": "proposal_not_found", "proposal_id": proposal_id, "queued": False}
    if proposal.get("status") == "implemented":
        return {"status": "already_implemented", "proposal_id": proposal_id, "queued": False}

    runtime_root = _runtime_root(proposal_store_path)
    safe_id = _safe_id(proposal_id)
    job_path = runtime_root / "approval_jobs" / f"{safe_id}.json"
    existing = read_json_safe(job_path, {})
    if isinstance(existing, dict) and existing.get("status") in {"queued", "running"}:
        return {
            "status": "already_running",
            "proposal_id": proposal_id,
            "queued": False,
            "job_path": str(job_path),
        }

    root = (project_root or Path.cwd()).resolve()
    worker_script = root / "scripts" / "run_qic_approval_worker.py"
    python = root / ".venv" / "bin" / "python"
    if not python.exists():
        python = Path(sys.executable)
    log_path = reports_path / f"approval_pipeline_{safe_id}.log"
    job = {
        "schema_version": 1,
        "proposal_id": proposal_id,
        "title": proposal.get("title"),
        "status": "queued",
        "actor": actor,
        "chat_id": str(chat_id),
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "proposal_store_path": str(proposal_store_path.resolve()),
        "knowledge_base_path": str(knowledge_base_path.resolve()),
        "reports_path": str(reports_path.resolve()),
        "project_root": str(root),
        "log_path": str(log_path.resolve()),
    }
    atomic_write_json(job_path, job)
    command = [
        str(python),
        str(worker_script),
        "--proposal-id",
        proposal_id,
        "--proposal-store",
        str(proposal_store_path.resolve()),
        "--knowledge-base",
        str(knowledge_base_path.resolve()),
        "--reports-path",
        str(reports_path.resolve()),
        "--project-root",
        str(root),
        "--actor",
        actor,
        "--chat-id",
        str(chat_id),
        "--job-path",
        str(job_path.resolve()),
    ]
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("ab") as log_handle:
            process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
                command,
                cwd=root,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                shell=False,
            )
    except (OSError, ValueError) as exc:
        job.update({"status": "launch_failed", "updated_at": utc_now(), "error": str(exc)})
        atomic_write_json(job_path, job)
        return {
            "status": "worker_launch_failed",
            "proposal_id": proposal_id,
            "queued": False,
            "job_path": str(job_path),
            "error": str(exc),
        }
    current = read_json_safe(job_path, job)
    if isinstance(current, dict) and current.get("status") == "queued":
        current.update({"pid": process.pid, "updated_at": utc_now()})
        atomic_write_json(job_path, current)
    return {
        "status": "implementation_queued",
        "proposal_id": proposal_id,
        "queued": True,
        "pid": process.pid,
        "job_path": str(job_path),
        "log_path": str(log_path),
    }


def run_approved_proposal_pipeline(
    *,
    proposal_id: str,
    proposal_store_path: Path,
    knowledge_base_path: Path,
    reports_path: Path,
    actor: str,
    project_root: Path = Path("."),
) -> dict[str, Any]:
    started_at = utc_now()
    proposal = _load_proposal(proposal_id, proposal_store_path)
    base = _base_result(proposal_id, proposal, actor=actor, started_at=started_at)
    if proposal is None:
        return _finish(base, status="proposal_not_found", stage="preconditions", blockers=["proposal_not_found"], reports_path=reports_path)
    if proposal.get("status") == "implemented":
        return _finish(base, status="already_implemented", stage="preconditions", reports_path=reports_path)
    if proposal.get("status") not in {"approved", "approved_for_implementation_review"}:
        return _finish(
            base,
            status="blocked",
            stage="preconditions",
            blockers=["proposal_not_approved_for_implementation_review"],
            reports_path=reports_path,
        )
    if proposal.get("status") == "approved":
        proposal = update_proposal_status(
            proposal_id,
            "approved_for_implementation_review",
            path=proposal_store_path,
            actor=actor,
            approval_metadata={"auto_apply_pipeline": True},
        ) or proposal
        base["proposal_status"] = proposal.get("status")
    gate = approval_auto_apply_config()
    if not gate["enabled"]:
        return _finish(
            base,
            status="auto_apply_disabled",
            stage="preconditions",
            blockers=[f"disabled:{name}" for name in gate["missing_flags"]],
            reports_path=reports_path,
        )

    lock_path = _runtime_root(proposal_store_path) / "locks" / f"approval_pipeline_{_safe_id(proposal_id)}.lock"
    lock = ProcessLock(lock_path, stale_after_seconds=7200)
    if not lock.acquire():
        return {**base, "status": "already_running", "stage": "lock", "lock_path": str(lock_path)}
    try:
        proposal = _load_proposal(proposal_id, proposal_store_path)
        if proposal and proposal.get("status") == "implemented":
            return _finish(base, status="already_implemented", stage="preconditions", reports_path=reports_path)
        work_path = reports_path / "approval_pipeline_work" / _safe_id(proposal_id)
        review = run_implementation_review_for_proposal_id(
            proposal_id,
            proposal_store_path=proposal_store_path,
            knowledge_base_path=knowledge_base_path,
            output_path=work_path,
        )
        base["implementation_review"] = {
            "decision": review.get("decision"),
            "allowed_to_generate_patch": review.get("allowed_to_generate_patch"),
            "blockers": review.get("blockers", []),
        }
        if review.get("decision") != "IMPLEMENTATION_ALLOWED" or not review.get("allowed_to_generate_patch"):
            return _finish(
                base,
                status="blocked",
                stage="implementation_review",
                blockers=list(review.get("blockers") or ["implementation_review_not_allowed"]),
                reports_path=reports_path,
            )

        patch = generate_patch_report(review, output_path=work_path, apply_patch=False)
        base["patch"] = {"status": patch.get("status"), "blockers": patch.get("blockers", [])}
        if patch.get("status") != "patch_report_generated" or patch.get("allowed_to_generate_patch") is not True:
            return _finish(
                base,
                status="blocked",
                stage="patch_generation",
                blockers=list(patch.get("blockers") or ["patch_generation_blocked"]),
                reports_path=reports_path,
            )

        engineer = run_code_engineer(
            proposal_id=proposal_id,
            project_root=project_root,
            proposal_store_path=proposal_store_path,
            reports_path=work_path,
            dry_run=False,
            apply=True,
            run_tests=True,
            allow_apply=True,
        )
        base.update(
            {
                "code_engineer_status": engineer.get("status"),
                "files_modified": list(engineer.get("files_modified") or []),
                "files_planned": list(engineer.get("files_planned") or []),
                "tests_run": list(engineer.get("tests_run") or []),
                "tests_passed": bool(engineer.get("tests_passed")),
                "test_output_summary": engineer.get("test_output_summary", ""),
                "blockers": list(engineer.get("blockers") or []),
                "risk_level": engineer.get("risk_level") or proposal.get("risk_level"),
                "change_id": engineer.get("change_id"),
                "rollback": engineer.get("rollback_after_failed_tests"),
            }
        )
        if engineer.get("status") == "applied" and engineer.get("tests_passed"):
            updated = update_proposal_status(
                proposal_id,
                "implemented",
                path=proposal_store_path,
                actor=actor,
                approval_metadata={"change_id": engineer.get("change_id"), "auto_apply_pipeline": True},
            )
            base["proposal_status"] = updated.get("status") if updated else None
            return _finish(base, status="applied", stage="completed", bot_operational=True, reports_path=reports_path)
        if engineer.get("rollback_after_failed_tests"):
            rollback = engineer["rollback_after_failed_tests"]
            return _finish(
                base,
                status="rolled_back",
                stage="post_apply_validation",
                bot_operational=bool(rollback.get("tests_passed")),
                reports_path=reports_path,
            )
        status = "tests_failed" if engineer.get("status") == "failed_tests" else "blocked"
        stage = "sandbox_validation" if status == "tests_failed" else "code_engineer"
        return _finish(base, status=status, stage=stage, bot_operational=True, reports_path=reports_path)
    except Exception as exc:  # Safety boundary: persist failure and leave approval pending.
        return _finish(
            base,
            status="internal_error",
            stage="internal_error",
            blockers=[f"{type(exc).__name__}:{exc}"],
            bot_operational=False,
            reports_path=reports_path,
        )
    finally:
        lock.release()


def format_approval_pipeline_message(report: dict[str, Any]) -> str:
    status = str(report.get("status") or "unknown")
    if status == "applied":
        heading = "✅ CAMBIO APLICADO"
    elif status == "rolled_back":
        heading = "↩️ CAMBIO REVERTIDO"
    else:
        heading = "⛔ CAMBIO NO APLICADO"
    files = report.get("files_modified") or report.get("files_planned") or []
    tests = report.get("tests_run") or []
    blockers = report.get("blockers") or []
    rollback = report.get("rollback") or {}
    lines = [
        heading,
        f"ID: {report.get('proposal_id')}",
        f"Título: {report.get('title') or 'n/a'}",
        f"Resultado: {status}",
        f"Etapa: {report.get('stage')}",
        f"Riesgo: {report.get('risk_level') or 'UNKNOWN'}",
        f"Change ID: {report.get('change_id') or 'n/a'}",
        f"Archivos: {', '.join(str(item) for item in files) or 'ninguno'}",
        f"Pruebas: {len(tests)} ejecutadas; {'OK' if report.get('tests_passed') else 'NO OK'}",
        f"Blockers: {', '.join(str(item) for item in blockers) or 'ninguno'}",
        f"Rollback: {rollback.get('status') or 'no'}; tests={rollback.get('tests_passed', 'n/a')}",
        f"Bot operativo: {'SÍ' if report.get('bot_operational') else 'NO/REQUIERE REVISIÓN'}",
    ]
    return "\n".join(lines)[:3900]


def update_approval_job(job_path: Path, **updates: Any) -> dict[str, Any]:
    job = read_json_safe(job_path, {})
    if not isinstance(job, dict):
        job = {}
    job.update(updates)
    job["updated_at"] = utc_now()
    atomic_write_json(job_path, job)
    return job


def _base_result(
    proposal_id: str,
    proposal: dict[str, Any] | None,
    *,
    actor: str,
    started_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "proposal_id": proposal_id,
        "title": (proposal or {}).get("title"),
        "actor": actor,
        "started_at": started_at,
        "finished_at": None,
        "status": "running",
        "stage": "starting",
        "proposal_status": (proposal or {}).get("status"),
        "risk_level": (proposal or {}).get("risk_level"),
        "files_modified": [],
        "files_planned": [],
        "tests_run": [],
        "tests_passed": False,
        "blockers": [],
        "change_id": None,
        "rollback": None,
        "bot_operational": True,
    }


def _finish(
    report: dict[str, Any],
    *,
    status: str,
    stage: str,
    reports_path: Path,
    blockers: list[str] | None = None,
    bot_operational: bool | None = None,
) -> dict[str, Any]:
    report["status"] = status
    report["stage"] = stage
    report["finished_at"] = utc_now()
    if blockers is not None:
        report["blockers"] = blockers
    if bot_operational is not None:
        report["bot_operational"] = bot_operational
    _write_pipeline_reports(report, reports_path)
    return report


def _write_pipeline_reports(report: dict[str, Any], reports_path: Path) -> None:
    safe_id = _safe_id(str(report.get("proposal_id") or "unknown"))
    atomic_write_json(reports_path / f"approval_pipeline_{safe_id}.json", report)
    atomic_write_text(reports_path / f"approval_pipeline_{safe_id}.md", _pipeline_markdown(report))


def _pipeline_markdown(report: dict[str, Any]) -> str:
    lines = ["# QIC Approval Pipeline", ""]
    for key in (
        "proposal_id",
        "title",
        "status",
        "stage",
        "risk_level",
        "change_id",
        "tests_passed",
        "bot_operational",
        "started_at",
        "finished_at",
    ):
        lines.append(f"- {key}: {report.get(key)}")
    lines.extend([f"- files_modified: {report.get('files_modified', [])}", f"- tests_run: {report.get('tests_run', [])}", f"- blockers: {report.get('blockers', [])}", f"- rollback: {report.get('rollback')}"])
    return "\n".join(lines) + "\n"


def _load_proposal(proposal_id: str, path: Path) -> dict[str, Any] | None:
    return next((item for item in load_proposals(path) if str(item.get("id")) == proposal_id), None)


def _runtime_root(proposal_store_path: Path) -> Path:
    if proposal_store_path.parent.name == "agent_proposals":
        return proposal_store_path.parent.parent / "qic"
    return proposal_store_path.parent / "qic"


def _safe_id(proposal_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", proposal_id)[:120] or "unknown"


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}
