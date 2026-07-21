from __future__ import annotations

from pathlib import Path

import scripts.run_qic_approval_worker as worker_script
from trading_signals.agents.implementation import approval_pipeline
from trading_signals.agents.implementation.approval_pipeline import (
    approval_auto_apply_config,
    enqueue_approved_proposal_pipeline,
    format_approval_pipeline_message,
    run_approved_proposal_pipeline,
)
from trading_signals.agents.proposal_store import load_proposals, save_proposals, update_proposal_status
from trading_signals.agents.telegram_approval import format_proposal_message, handle_approval_callback


def test_approve_disabled_preserves_previous_behavior(monkeypatch, tmp_path: Path) -> None:
    _disable_auto_apply(monkeypatch)
    store = tmp_path / "data" / "agent_proposals" / "proposals.jsonl"
    save_proposals([_proposal()], store)
    calls: list[str] = []
    monkeypatch.setattr(approval_pipeline, "enqueue_approved_proposal_pipeline", lambda **_: calls.append("queued"))

    result = handle_approval_callback(
        "agent:approve:p1",
        proposal_store_path=store,
        knowledge_base_path=tmp_path / "kb.json",
        qic_output_path=tmp_path / "reports" / "qic",
        actor="123",
        chat_id="123",
    )

    assert result["status"] == "approved_for_implementation_review"
    assert result["notification_text"] == "Propuesta aprobada, pero la aplicación automática está desactivada."
    assert load_proposals(store)[0]["status"] == "approved_for_implementation_review"
    assert calls == []
    assert "No se ejecutará ningún cambio automáticamente." in format_proposal_message(_proposal())


def test_approve_enabled_records_approval_and_queues_worker(monkeypatch, tmp_path: Path) -> None:
    _enable_auto_apply(monkeypatch)
    store = tmp_path / "data" / "agent_proposals" / "proposals.jsonl"
    save_proposals([_proposal()], store)
    captured: dict[str, object] = {}

    def fake_enqueue(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"status": "implementation_queued", "queued": True, "proposal_id": "p1"}

    monkeypatch.setattr(approval_pipeline, "enqueue_approved_proposal_pipeline", fake_enqueue)

    result = handle_approval_callback(
        "agent:approve:p1",
        proposal_store_path=store,
        knowledge_base_path=tmp_path / "kb.json",
        qic_output_path=tmp_path / "reports" / "qic",
        actor="123",
        chat_id="123",
    )

    assert result["status"] == "implementation_queued"
    assert result["notification_text"].startswith("⏳")
    assert captured["actor"] == "123"
    assert captured["chat_id"] == "123"
    assert load_proposals(store)[0]["status"] == "approved_for_implementation_review"
    assert "se revisará, probará y aplicará automáticamente" in format_proposal_message(_proposal())


def test_pipeline_handles_missing_and_already_implemented_proposals(monkeypatch, tmp_path: Path) -> None:
    _enable_auto_apply(monkeypatch)
    store = tmp_path / "data" / "agent_proposals" / "proposals.jsonl"
    reports = tmp_path / "reports" / "qic"

    missing = run_approved_proposal_pipeline(
        proposal_id="missing",
        proposal_store_path=store,
        knowledge_base_path=tmp_path / "kb.json",
        reports_path=reports,
        actor="123",
        project_root=tmp_path,
    )
    save_proposals([{**_proposal(), "status": "implemented"}], store)
    implemented = run_approved_proposal_pipeline(
        proposal_id="p1",
        proposal_store_path=store,
        knowledge_base_path=tmp_path / "kb.json",
        reports_path=reports,
        actor="123",
        project_root=tmp_path,
    )

    assert missing["status"] == "proposal_not_found"
    assert implemented["status"] == "already_implemented"


def test_pipeline_stops_when_implementation_review_blocks(monkeypatch, tmp_path: Path) -> None:
    store, reports = _approved_fixture(tmp_path)
    _enable_auto_apply(monkeypatch)
    monkeypatch.setattr(
        approval_pipeline,
        "run_implementation_review_for_proposal_id",
        lambda *_, **__: {
            "decision": "NEEDS_MORE_RESEARCH",
            "allowed_to_generate_patch": False,
            "blockers": ["trade_reduction_above_60"],
        },
    )

    result = _run_pipeline(store, reports, tmp_path)

    assert result["status"] == "blocked"
    assert result["stage"] == "implementation_review"
    assert result["blockers"] == ["trade_reduction_above_60"]
    assert load_proposals(store)[0]["status"] == "approved_for_implementation_review"


def test_pipeline_stops_when_patch_generation_blocks(monkeypatch, tmp_path: Path) -> None:
    store, reports = _approved_fixture(tmp_path)
    _enable_auto_apply(monkeypatch)
    _mock_allowed_review(monkeypatch)
    monkeypatch.setattr(
        approval_pipeline,
        "generate_patch_report",
        lambda *_, **__: {"status": "blocked", "allowed_to_generate_patch": False, "blockers": ["patch_blocked"]},
    )

    result = _run_pipeline(store, reports, tmp_path)

    assert result["status"] == "blocked"
    assert result["stage"] == "patch_generation"
    assert result["blockers"] == ["patch_blocked"]


def test_sandbox_test_failure_does_not_mark_implemented(monkeypatch, tmp_path: Path) -> None:
    store, reports = _approved_fixture(tmp_path)
    _enable_auto_apply(monkeypatch)
    _mock_allowed_review(monkeypatch)
    _mock_allowed_patch(monkeypatch)
    monkeypatch.setattr(
        approval_pipeline,
        "run_code_engineer",
        lambda **_: {
            "status": "failed_tests",
            "files_modified": [],
            "files_planned": ["tests/unit/test_generated.py"],
            "tests_run": ["pytest sandbox"],
            "tests_passed": False,
            "blockers": ["sandbox_validation_failed"],
            "risk_level": "LOW",
            "change_id": None,
        },
    )

    result = _run_pipeline(store, reports, tmp_path)

    assert result["status"] == "tests_failed"
    assert result["stage"] == "sandbox_validation"
    assert result["files_modified"] == []
    assert load_proposals(store)[0]["status"] == "approved_for_implementation_review"


def test_successful_apply_marks_proposal_implemented(monkeypatch, tmp_path: Path) -> None:
    store, reports = _approved_fixture(tmp_path)
    _enable_auto_apply(monkeypatch)
    _mock_allowed_review(monkeypatch)
    _mock_allowed_patch(monkeypatch)
    monkeypatch.setattr(
        approval_pipeline,
        "run_code_engineer",
        lambda **_: {
            "status": "applied",
            "files_modified": ["tests/unit/test_generated.py"],
            "files_planned": ["tests/unit/test_generated.py"],
            "tests_run": ["pytest sandbox", "pytest post-apply"],
            "tests_passed": True,
            "blockers": [],
            "risk_level": "LOW",
            "change_id": "change_1",
        },
    )

    result = _run_pipeline(store, reports, tmp_path)

    assert result["status"] == "applied"
    assert result["change_id"] == "change_1"
    assert result["bot_operational"] is True
    assert load_proposals(store)[0]["status"] == "implemented"
    assert "✅ CAMBIO APLICADO" in format_approval_pipeline_message(result)
    assert (reports / "approval_pipeline_p1.json").exists()


def test_post_apply_failure_reports_rollback_and_does_not_mark_implemented(monkeypatch, tmp_path: Path) -> None:
    store, reports = _approved_fixture(tmp_path)
    _enable_auto_apply(monkeypatch)
    _mock_allowed_review(monkeypatch)
    _mock_allowed_patch(monkeypatch)
    monkeypatch.setattr(
        approval_pipeline,
        "run_code_engineer",
        lambda **_: {
            "status": "failed_tests",
            "files_modified": [],
            "files_planned": ["tests/unit/test_generated.py"],
            "tests_run": ["pytest sandbox", "pytest post-apply", "pytest post-rollback"],
            "tests_passed": False,
            "blockers": ["post_apply_validation_failed"],
            "risk_level": "LOW",
            "change_id": "change_1",
            "rollback_after_failed_tests": {"status": "rolled_back", "rollback_id": "rollback_1", "tests_passed": True},
        },
    )

    result = _run_pipeline(store, reports, tmp_path)

    assert result["status"] == "rolled_back"
    assert result["rollback"]["status"] == "rolled_back"
    assert result["bot_operational"] is True
    assert load_proposals(store)[0]["status"] == "approved_for_implementation_review"
    assert "↩️ CAMBIO REVERTIDO" in format_approval_pipeline_message(result)


def test_incomplete_flags_block_pipeline(monkeypatch, tmp_path: Path) -> None:
    store, reports = _approved_fixture(tmp_path)
    monkeypatch.setenv("QIC_AUTO_APPLY_ON_APPROVAL", "true")
    monkeypatch.setenv("QIC_CODE_ENGINEER_ENABLED", "true")
    monkeypatch.setenv("QIC_CODE_ENGINEER_ALLOW_APPLY", "false")

    result = _run_pipeline(store, reports, tmp_path)

    assert approval_auto_apply_config()["enabled"] is False
    assert result["status"] == "auto_apply_disabled"
    assert "disabled:QIC_CODE_ENGINEER_ALLOW_APPLY" in result["blockers"]


def test_worker_launch_failure_keeps_approval_registered(monkeypatch, tmp_path: Path) -> None:
    store, reports = _approved_fixture(tmp_path)
    monkeypatch.setattr(approval_pipeline.subprocess, "Popen", lambda *_, **__: (_ for _ in ()).throw(OSError("launch failed")))

    result = enqueue_approved_proposal_pipeline(
        proposal_id="p1",
        proposal_store_path=store,
        knowledge_base_path=tmp_path / "kb.json",
        reports_path=reports,
        actor="123",
        chat_id="123",
        project_root=Path.cwd(),
    )

    assert result["status"] == "worker_launch_failed"
    assert load_proposals(store)[0]["status"] == "approved_for_implementation_review"


def test_existing_running_job_is_idempotent(tmp_path: Path) -> None:
    store, reports = _approved_fixture(tmp_path)
    job = tmp_path / "data" / "qic" / "approval_jobs" / "p1.json"
    job.parent.mkdir(parents=True)
    job.write_text('{"status":"running"}', encoding="utf-8")

    result = enqueue_approved_proposal_pipeline(
        proposal_id="p1",
        proposal_store_path=store,
        knowledge_base_path=tmp_path / "kb.json",
        reports_path=reports,
        actor="123",
        chat_id="123",
    )

    assert result["status"] == "already_running"
    assert result["queued"] is False


def test_worker_persists_result_without_real_telegram(monkeypatch, tmp_path: Path) -> None:
    job_path = tmp_path / "data" / "qic" / "approval_jobs" / "p1.json"
    calls: list[str] = []
    monkeypatch.setattr(
        worker_script,
        "run_approved_proposal_pipeline",
        lambda **_: {"proposal_id": "p1", "status": "applied", "bot_operational": True},
    )
    monkeypatch.setattr(worker_script, "_notify", lambda report, **_: calls.append(str(report["status"])) or {"status": "sent"})

    rc = worker_script.main(
        [
            "--proposal-id",
            "p1",
            "--proposal-store",
            str(tmp_path / "proposals.jsonl"),
            "--knowledge-base",
            str(tmp_path / "kb.json"),
            "--reports-path",
            str(tmp_path / "reports"),
            "--project-root",
            str(tmp_path),
            "--actor",
            "123",
            "--chat-id",
            "123",
            "--job-path",
            str(job_path),
        ]
    )

    assert rc == 0
    assert calls == ["applied"]
    assert '"status": "applied"' in job_path.read_text(encoding="utf-8")


def _proposal() -> dict[str, object]:
    return {
        "id": "p1",
        "title": "CIO proposal: exclude htf_alignment=against",
        "action": "PROPOSE_IMPLEMENTATION",
        "conditions": ["exclude htf_alignment=against"],
        "risk_level": "LOW",
        "status": "pending",
    }


def _approved_fixture(tmp_path: Path) -> tuple[Path, Path]:
    store = tmp_path / "data" / "agent_proposals" / "proposals.jsonl"
    reports = tmp_path / "reports" / "qic"
    save_proposals([_proposal()], store)
    update_proposal_status("p1", "approved_for_implementation_review", path=store, actor="123")
    return store, reports


def _run_pipeline(store: Path, reports: Path, project_root: Path) -> dict[str, object]:
    return run_approved_proposal_pipeline(
        proposal_id="p1",
        proposal_store_path=store,
        knowledge_base_path=project_root / "kb.json",
        reports_path=reports,
        actor="123",
        project_root=project_root,
    )


def _enable_auto_apply(monkeypatch) -> None:
    for name in approval_pipeline.AUTO_APPLY_FLAGS:
        monkeypatch.setenv(name, "true")


def _disable_auto_apply(monkeypatch) -> None:
    for name in approval_pipeline.AUTO_APPLY_FLAGS:
        monkeypatch.setenv(name, "false")


def _mock_allowed_review(monkeypatch) -> None:
    monkeypatch.setattr(
        approval_pipeline,
        "run_implementation_review_for_proposal_id",
        lambda *_, **__: {
            "decision": "IMPLEMENTATION_ALLOWED",
            "allowed_to_generate_patch": True,
            "blockers": [],
        },
    )


def _mock_allowed_patch(monkeypatch) -> None:
    monkeypatch.setattr(
        approval_pipeline,
        "generate_patch_report",
        lambda *_, **__: {"status": "patch_report_generated", "allowed_to_generate_patch": True, "blockers": []},
    )
