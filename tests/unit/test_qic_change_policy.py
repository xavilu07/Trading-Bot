from __future__ import annotations

from pathlib import Path

from trading_signals.agents.implementation.change_policy import classify_change_risk, evaluate_auto_apply_policy, validate_change_paths
from trading_signals.agents.implementation.code_changes import CodeChangeManager


def test_risk_classification_and_path_policy() -> None:
    assert classify_change_risk(files=["tests/unit/test_example.py"])["risk_level"] == "LOW"
    assert classify_change_risk(files=["src/trading_signals/application/use_cases/run_market_scan.py"])["risk_level"] == "HIGH"
    assert classify_change_risk(files=[".env"])["risk_level"] == "EXTREME"
    result = validate_change_paths(["tests/test_ok.py", ".env"], allowlist=["tests"], denylist=[".env"])
    assert result["allowed"] is False
    assert ".env" in result["blocked_paths"]


def test_auto_apply_requires_all_low_risk_guards() -> None:
    change = {
        "risk_level": "LOW",
        "files_changed": ["tests/test_ok.py"],
        "diff_stats": {"changed_lines": 10},
        "implementation_council_approved": True,
        "rollback_available": True,
        "validation": {"tests_passed": True, "static_checks_passed": True, "coverage_regression": False},
    }

    allowed = evaluate_auto_apply_policy(change, auto_apply_low_risk=True)
    blocked = evaluate_auto_apply_policy(change, auto_apply_low_risk=False)

    assert allowed["allowed"] is True
    assert blocked["allowed"] is False
    assert "auto_apply_low_risk_disabled" in blocked["blockers"]


def test_change_manager_apply_verify_and_rollback(tmp_path: Path) -> None:
    project = tmp_path / "project"
    target = project / "tests" / "sample.txt"
    target.parent.mkdir(parents=True)
    target.write_text("before\n", encoding="utf-8")
    manager = CodeChangeManager(
        project_root=project,
        store_path=tmp_path / "data" / "changes.json",
        backup_root=tmp_path / "backups",
        allowlist=["tests"],
        denylist=[".env"],
    )
    change = manager.create_change(
        proposal_id="proposal_1",
        risk_level="LOW",
        generated_files={"tests/sample.txt": "after\n"},
        validation={"tests_passed": True, "static_checks_passed": True, "coverage_regression": False},
        implementation_council_approved=True,
    )

    applied = manager.apply(change["change_id"], auto=True, auto_apply_low_risk=True)
    assert applied["final_status"] == "applied"
    assert target.read_text() == "after\n"
    assert manager.verify(change["change_id"])["status"] == "verified"

    rolled_back = manager.rollback(change["change_id"], manual_approval=True)
    assert rolled_back["final_status"] == "rolled_back"
    assert target.read_text() == "before\n"


def test_rollback_blocks_when_file_changed_after_apply(tmp_path: Path) -> None:
    project = tmp_path / "project"
    target = project / "tests" / "sample.txt"
    target.parent.mkdir(parents=True)
    target.write_text("before\n", encoding="utf-8")
    manager = CodeChangeManager(project_root=project, store_path=tmp_path / "changes.json", backup_root=tmp_path / "backup", allowlist=["tests"])
    change = manager.create_change(
        proposal_id="p",
        risk_level="LOW",
        generated_files={"tests/sample.txt": "after\n"},
        validation={"tests_passed": True, "static_checks_passed": True, "coverage_regression": False},
        implementation_council_approved=True,
    )
    manager.apply(change["change_id"], auto=True, auto_apply_low_risk=True)
    target.write_text("later change\n", encoding="utf-8")

    result = manager.rollback(change["change_id"], manual_approval=True)

    assert result["status"] == "blocked"
    assert "post_apply_changes_detected" in result["blockers"]


def test_manual_apply_cannot_bypass_validation(tmp_path: Path) -> None:
    project = tmp_path / "project"
    target = project / "tests" / "sample.txt"
    target.parent.mkdir(parents=True)
    target.write_text("before\n", encoding="utf-8")
    manager = CodeChangeManager(project_root=project, store_path=tmp_path / "changes.json", backup_root=tmp_path / "backup", allowlist=["tests"])
    change = manager.create_change(
        proposal_id="p",
        risk_level="LOW",
        generated_files={"tests/sample.txt": "after\n"},
        validation={"tests_passed": False, "static_checks_passed": False, "coverage_regression": None},
        implementation_council_approved=True,
    )

    result = manager.apply(change["change_id"], manual_approval=True)

    assert result["final_status"] == "blocked"
    assert "tests_not_passed" in result["blockers"]
    assert target.read_text(encoding="utf-8") == "before\n"
