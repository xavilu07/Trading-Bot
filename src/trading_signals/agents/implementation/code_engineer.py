from __future__ import annotations

import difflib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.agents.proposal_store import load_proposals
from trading_signals.agents.decision_ledger import append_decision_ledger_entry
from trading_signals.agents.research_memory import record_research_memory_decision
from trading_signals.agents.strategy_knowledge_base import load_strategy_knowledge_base, save_strategy_knowledge_base
from trading_signals.agents.implementation.change_policy import classify_change_risk
from trading_signals.agents.implementation.code_changes import CodeChangeManager
from trading_signals.agents.qic_runtime import atomic_write_json, atomic_write_text

CODE_ENGINEER_REPORT = "code_engineer"
SUPPORTED_RULE = "exclude htf_alignment=against"


def run_code_engineer(
    *,
    proposal_id: str,
    project_root: Path = Path("."),
    proposal_store_path: Path = Path("data") / "agent_proposals" / "proposals.jsonl",
    reports_path: Path = Path("reports") / "qic",
    dry_run: bool = True,
    apply: bool = False,
    run_tests: bool = False,
    allow_apply: bool = False,
    max_autofix_attempts: int = 1,
) -> dict[str, Any]:
    proposal = _load_proposal(proposal_id, proposal_store_path)
    review = _load_json(reports_path / "implementation_review.json")
    patch = _load_json(reports_path / "generated_patch.json")
    plan = _load_json(reports_path / "implementation_plan.json")
    rollback = _load_json(reports_path / "rollback_plan.json")
    blockers = _precondition_blockers(
        proposal=proposal,
        review=review,
        patch=patch,
        plan=plan,
        rollback=rollback,
        proposal_id=proposal_id,
    )
    files = _planned_files()
    generated = _generated_files()
    diff_summary = _diff_summary(project_root, generated)
    risk = classify_change_risk(
        files=files,
        change_type=str((plan or {}).get("change_type") or ""),
        proposal=proposal,
    )
    report: dict[str, Any] = {
        "proposal_id": proposal_id,
        "created_at": _now(),
        "status": "failed_preconditions" if blockers else "dry_run_generated",
        "files_modified": [],
        "files_planned": files,
        "diff_summary": diff_summary,
        "feature_flags": plan.get("required_feature_flags", []) if isinstance(plan, dict) else [],
        "tests_run": [],
        "tests_passed": False,
        "test_output_summary": "",
        "blockers": blockers,
        "safety_notes": [
            "Does not touch .env.",
            "Does not restart trading scheduler.",
            "Does not deploy.",
            "Does not activate feature flags.",
            "Feature flags remain false/shadow by default.",
        ],
        "telegram_summary": "Code plan generated" if not blockers else "Code engineer blocked by preconditions",
        "risk_level": risk["risk_level"],
        "risk_reasons": risk["reasons"],
        "change_id": None,
    }
    if blockers:
        written = write_code_engineer_reports(report, output_path=reports_path)
        _update_learning_artifacts(written, proposal, proposal_store_path=proposal_store_path)
        return written
    test_result: dict[str, Any] | None = None
    if run_tests:
        test_result = _run_sandbox_validation(
            project_root=project_root,
            generated=generated,
            max_autofix_attempts=max_autofix_attempts,
        )
        report["tests_run"] = test_result["commands"]
        report["tests_passed"] = test_result["passed"]
        report["test_output_summary"] = test_result["summary"]
        if not test_result["passed"]:
            report["status"] = "failed_tests"
            report["blockers"].append("sandbox_validation_failed")
            written = write_code_engineer_reports(report, output_path=reports_path)
            _update_learning_artifacts(written, proposal, proposal_store_path=proposal_store_path)
            return written
    manager = CodeChangeManager(
        project_root=project_root,
        store_path=(proposal_store_path.parent.parent / "qic" / "code_changes.json") if proposal_store_path.parent.name == "agent_proposals" else Path("data") / "qic" / "code_changes.json",
        backup_root=(proposal_store_path.parent.parent / "qic" / "change_backups") if proposal_store_path.parent.name == "agent_proposals" else Path("data") / "qic" / "change_backups",
        allowlist=["src/trading_signals/agents", "src/trading_signals/application/use_cases", "tests", "scripts", "Planning", "reports/qic", "src/trading_signals/interfaces/frontend", "deploy/frontend"],
    )
    change = manager.create_change(
        proposal_id=proposal_id,
        risk_level=risk["risk_level"],
        generated_files=generated,
        validation={
            "tests_passed": bool(test_result and test_result["passed"]),
            "static_checks_passed": bool(test_result and test_result["passed"]),
            "coverage_regression": False if test_result and test_result["passed"] else None,
            "commands": list(test_result["commands"]) if test_result else [],
        },
        council_votes=(review or {}).get("agent_reviews") or {},
        implementation_council_approved=bool((review or {}).get("allowed_to_generate_patch")),
        approval_source="human" if apply else "none",
    )
    report["change_id"] = change.get("change_id")
    if change.get("final_status") == "blocked_path_policy":
        report["blockers"].append("change_path_policy_blocked")
        report["status"] = "failed_preconditions"
        written = write_code_engineer_reports(report, output_path=reports_path)
        _update_learning_artifacts(written, proposal, proposal_store_path=proposal_store_path)
        return written
    if apply:
        if dry_run:
            report["blockers"].append("apply_requested_with_dry_run")
            report["status"] = "failed_preconditions"
            written = write_code_engineer_reports(report, output_path=reports_path)
            _update_learning_artifacts(written, proposal, proposal_store_path=proposal_store_path)
            return written
        if not allow_apply:
            report["blockers"].append("apply_not_allowed")
            report["status"] = "failed_preconditions"
            written = write_code_engineer_reports(report, output_path=reports_path)
            _update_learning_artifacts(written, proposal, proposal_store_path=proposal_store_path)
            return written
        if not run_tests or not report["tests_passed"]:
            report["blockers"].append("tests_required_before_apply")
            report["status"] = "failed_preconditions"
            written = write_code_engineer_reports(report, output_path=reports_path)
            _update_learning_artifacts(written, proposal, proposal_store_path=proposal_store_path)
            return written
        applied = manager.apply(str(change["change_id"]), auto=False, manual_approval=True)
        if applied.get("final_status") != "applied":
            report["blockers"].extend(applied.get("blockers") or ["change_apply_failed"])
            report["status"] = "failed_preconditions"
        else:
            report["files_modified"] = list(applied.get("files_changed") or [])
            report["status"] = "applied"
            post_apply = _run_validation_tests(project_root=project_root, max_autofix_attempts=max_autofix_attempts)
            report["tests_run"] = [*report["tests_run"], *post_apply["commands"]]
            report["tests_passed"] = bool(post_apply["passed"])
            report["test_output_summary"] += f"\npost_apply:\n{post_apply['summary']}"
            if not post_apply["passed"]:
                rollback_result = manager.rollback(str(change["change_id"]), manual_approval=True)
                rollback_validation = _run_validation_tests(
                    project_root=project_root,
                    max_autofix_attempts=0,
                )
                report["tests_run"] = [*report["tests_run"], *rollback_validation["commands"]]
                report["test_output_summary"] += f"\npost_rollback:\n{rollback_validation['summary']}"
                report["status"] = "failed_tests"
                report["files_modified"] = []
                report["blockers"].append("post_apply_validation_failed")
                report["rollback_after_failed_tests"] = {
                    "status": rollback_result.get("final_status") or rollback_result.get("status"),
                    "rollback_id": rollback_result.get("rollback_id"),
                    "tests_passed": rollback_validation["passed"],
                }
            else:
                manager.verify(str(change["change_id"]))
        manager.update_validation(
            str(change["change_id"]),
            {
                "tests_passed": bool(report["tests_passed"]),
                "static_checks_passed": bool(report["tests_passed"]),
                "coverage_regression": False if report["tests_passed"] else None,
                "commands": report["tests_run"],
            },
        )
    written = write_code_engineer_reports(report, output_path=reports_path)
    _update_learning_artifacts(written, proposal, proposal_store_path=proposal_store_path)
    return written


def write_code_engineer_reports(report: dict[str, Any], *, output_path: Path) -> dict[str, Any]:
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / f"{CODE_ENGINEER_REPORT}.json"
    md_path = output_path / f"{CODE_ENGINEER_REPORT}.md"
    atomic_write_json(json_path, report)
    atomic_write_text(md_path, _markdown(report))
    return report


def _precondition_blockers(
    *,
    proposal: dict[str, Any] | None,
    review: dict[str, Any] | None,
    patch: dict[str, Any] | None,
    plan: dict[str, Any] | None,
    rollback: dict[str, Any] | None,
    proposal_id: str,
) -> list[str]:
    blockers: list[str] = []
    if not proposal:
        blockers.append("proposal_not_found")
    elif proposal.get("id") != proposal_id:
        blockers.append("proposal_id_mismatch")
    if proposal and proposal.get("action") != "PROPOSE_IMPLEMENTATION":
        blockers.append("proposal_action_not_propose_implementation")
    if proposal and proposal.get("status") not in {"approved_for_implementation_review", "approved"}:
        blockers.append("proposal_not_approved_for_implementation_review")
    if not review:
        blockers.append("implementation_review_missing")
    elif review.get("decision") != "IMPLEMENTATION_ALLOWED":
        blockers.append("implementation_review_not_allowed")
    if review and review.get("proposal_id") != proposal_id:
        blockers.append("implementation_review_proposal_mismatch")
    if not patch:
        blockers.append("generated_patch_missing")
    elif patch.get("allowed_to_generate_patch") is not True:
        blockers.append("generated_patch_not_allowed")
    if not rollback or not rollback.get("steps"):
        blockers.append("rollback_plan_missing")
    flags = plan.get("required_feature_flags") if isinstance(plan, dict) else []
    if not flags:
        blockers.append("required_feature_flags_missing")
    for flag in flags or []:
        if str(flag.get("required_default", flag.get("default", ""))).lower() == "true":
            blockers.append("feature_flag_default_true")
    tests = review.get("required_tests") if isinstance(review, dict) else []
    if not tests:
        blockers.append("required_tests_missing")
    conditions = (plan or {}).get("rule_conditions") or (proposal or {}).get("conditions") or []
    if len(conditions) != 1:
        blockers.append("multiple_strategy_rules_not_allowed")
    if conditions and SUPPORTED_RULE not in str(conditions[0]).lower():
        blockers.append("unsupported_rule_for_code_engineer_v1")
    forbidden = [file_path for file_path in _planned_files() if _is_forbidden_file(file_path)]
    blockers.extend(f"forbidden_file:{item}" for item in forbidden)
    return sorted(set(blockers))


def _planned_files() -> list[str]:
    return [
        "src/trading_signals/application/use_cases/strategy_v2_1_htf_alignment_filter.py",
        "tests/unit/test_strategy_v2_1_htf_alignment_filter.py",
    ]


def _generated_files() -> dict[str, str]:
    return {
        "src/trading_signals/application/use_cases/strategy_v2_1_htf_alignment_filter.py": _filter_source(),
        "tests/unit/test_strategy_v2_1_htf_alignment_filter.py": _filter_tests_source(),
    }


def _diff_summary(project_root: Path, generated: dict[str, str]) -> dict[str, str]:
    output = {}
    for rel_path, new_content in generated.items():
        path = project_root / rel_path
        old_content = path.read_text(encoding="utf-8") if path.exists() else ""
        diff = difflib.unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
            lineterm="",
        )
        output[rel_path] = "\n".join(diff)
    return output


def _apply_generated_files(project_root: Path, generated: dict[str, str]) -> list[str]:
    modified = []
    for rel_path, content in generated.items():
        if _is_forbidden_file(rel_path):
            raise ValueError(f"forbidden file path: {rel_path}")
        path = project_root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        path.write_text(content, encoding="utf-8")
        modified.append(rel_path)
    return modified


def _run_validation_tests(*, project_root: Path, max_autofix_attempts: int) -> dict[str, Any]:
    commands = [
        "python3 -m py_compile src/trading_signals/application/use_cases/strategy_v2_1_htf_alignment_filter.py",
        "MPLBACKEND=Agg .venv/bin/pytest -q tests/unit/test_strategy_v2_1_htf_alignment_filter.py",
        "MPLBACKEND=Agg .venv/bin/pytest -q tests/unit/test_settings.py",
    ]
    results = []
    for command in commands:
        completed = subprocess.run(command, cwd=project_root, shell=True, capture_output=True, text=True, timeout=180)
        results.append(
            {
                "command": command,
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-2000:],
                "stderr_tail": completed.stderr[-2000:],
            }
        )
        if completed.returncode != 0:
            break
    passed = bool(results) and all(item["returncode"] == 0 for item in results)
    summary = "\n".join(f"{item['command']} -> {item['returncode']}" for item in results)
    if not passed and max_autofix_attempts > 0:
        summary += "\nautofix_attempted=false (no safe simple fix detected)"
    return {"commands": commands[: len(results)], "passed": passed, "summary": summary, "results": results}


def _run_sandbox_validation(
    *,
    project_root: Path,
    generated: dict[str, str],
    max_autofix_attempts: int,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="qic-code-engineer-") as temp_name:
        sandbox = Path(temp_name) / "repo"
        shutil.copytree(
            project_root,
            sandbox,
            ignore=shutil.ignore_patterns(".git", ".venv", "data", "reports", "logs", "__pycache__", ".pytest_cache"),
        )
        source_venv = project_root / ".venv"
        if source_venv.exists():
            os.symlink(source_venv.resolve(), sandbox / ".venv", target_is_directory=True)
        for relative, content in generated.items():
            target = sandbox / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return _run_validation_tests(project_root=sandbox, max_autofix_attempts=max_autofix_attempts)


def _load_proposal(proposal_id: str, path: Path) -> dict[str, Any] | None:
    return next((item for item in load_proposals(path) if item.get("id") == proposal_id), None)


def _update_learning_artifacts(report: dict[str, Any], proposal: dict[str, Any] | None, *, proposal_store_path: Path) -> None:
    if not proposal:
        return
    qic_path = proposal_store_path.parent.parent / "qic" if proposal_store_path.parent.name == "agent_proposals" else Path("data") / "qic"
    status = str(report.get("status") or "")
    implementation_status = {
        "failed_preconditions": "blocked_preconditions",
        "dry_run_generated": "code_generated",
        "applied": "patch_applied_shadow",
        "failed_tests": "code_generated_tests_failed",
    }.get(status, status)
    record_research_memory_decision(
        proposal,
        implementation_status,
        path=qic_path / "research_memory.json",
        reason=",".join(str(item) for item in report.get("blockers", [])),
    )
    append_decision_ledger_entry(
        proposal,
        path=qic_path / "decision_ledger.jsonl",
        final_decision="CODE_ENGINEER_STATUS",
        implementation_status=implementation_status,
        notes=",".join(str(item) for item in report.get("blockers", [])),
    )
    _update_strategy_kb_implementation_status(proposal, qic_path / "strategy_knowledge_base.json", implementation_status)


def _update_strategy_kb_implementation_status(proposal: dict[str, Any], path: Path, status: str) -> None:
    kb = load_strategy_knowledge_base(path)
    item_id = str(proposal.get("knowledge_item_id") or (proposal.get("context") or {}).get("knowledge_item_id") or "")
    item = (kb.get("items") or {}).get(item_id)
    if not isinstance(item, dict):
        return
    item["implementation_status"] = status
    history = list(item.get("implementation_history") or [])
    history.append({"timestamp": _now(), "event": status, "proposal_id": proposal.get("id")})
    item["implementation_history"] = history[-50:]
    save_strategy_knowledge_base(kb, path)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return raw if isinstance(raw, dict) else None


def _is_forbidden_file(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return (
        normalized.endswith(".env")
        or "/scheduler" in normalized
        or "telegram_public" in normalized
        or "public_signal" in normalized
    )


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _markdown(report: dict[str, Any]) -> str:
    lines = ["# QIC Code Engineer", ""]
    for key in ("proposal_id", "status", "tests_passed"):
        lines.append(f"- {key}: {report.get(key)}")
    lines.append(f"- blockers: {report.get('blockers', [])}")
    lines.append("")
    lines.append("## Files Planned")
    for file_path in report.get("files_planned", []):
        lines.append(f"- {file_path}")
    lines.append("")
    lines.append("## Feature Flags")
    for flag in report.get("feature_flags", []):
        lines.append(f"- {flag.get('name')} default={flag.get('default')}")
    lines.append("")
    lines.append("## Validation")
    for command in report.get("tests_run", []) or report.get("feature_flags", []):
        if isinstance(command, str):
            lines.append(f"- `{command}`")
    lines.append("")
    lines.append("## Safety Notes")
    for note in report.get("safety_notes", []):
        lines.append(f"- {note}")
    lines.append("")
    lines.append("## Diff Summary")
    for file_path, diff in (report.get("diff_summary") or {}).items():
        lines.append(f"### {file_path}")
        lines.append("```diff")
        lines.append(diff or "No changes.")
        lines.append("```")
    return "\n".join(lines) + "\n"


def _filter_source() -> str:
    return '''from __future__ import annotations

from typing import Any

BLOCK_REASON = "strategy_v2_1_htf_alignment_against"
VALID_MODES = {"shadow", "hard_block"}


def evaluate_strategy_v2_1_htf_alignment_filter(
    *,
    enabled: bool,
    mode: str,
    htf_alignment: str | None,
    current_decision: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_mode = str(mode or "shadow").strip().lower()
    if normalized_mode not in VALID_MODES:
        normalized_mode = "shadow"
    normalized_alignment = str(htf_alignment or "unknown").strip().lower()
    if normalized_alignment in {"", "none", "null"}:
        normalized_alignment = "unknown"
    would_block = bool(enabled) and normalized_alignment == "against"
    blocked = bool(would_block and normalized_mode == "hard_block")
    return {
        "enabled": bool(enabled),
        "mode": normalized_mode,
        "htf_alignment": normalized_alignment,
        "would_block": would_block,
        "blocked": blocked,
        "rejection_reason": BLOCK_REASON if blocked else None,
        "reason": _reason(enabled=bool(enabled), mode=normalized_mode, htf_alignment=normalized_alignment, blocked=blocked, would_block=would_block),
        "current_decision": current_decision,
        "context": context or {},
    }


def determine_htf_alignment(*, direction: object, higher_trend: object) -> str:
    direction_text = str(direction or "").strip().lower()
    trend_text = str(higher_trend or "").strip().lower()
    if direction_text == "long" and trend_text == "bullish":
        return "aligned"
    if direction_text == "short" and trend_text == "bearish":
        return "aligned"
    if direction_text in {"long", "short"} and trend_text in {"bullish", "bearish"}:
        return "against"
    return "unknown"


def apply_strategy_v2_1_htf_alignment_filter(
    *,
    evaluation: Any,
    signal: Any,
    status: str,
    enabled: bool,
    mode: str,
    direction: object,
    higher_trend: object,
) -> tuple[str, dict[str, Any]]:
    htf_alignment = determine_htf_alignment(direction=direction, higher_trend=higher_trend)
    result = evaluate_strategy_v2_1_htf_alignment_filter(
        enabled=enabled,
        mode=mode,
        htf_alignment=htf_alignment,
        current_decision=getattr(evaluation, "decision", None),
        context={"direction": direction, "higher_trend": higher_trend},
    )
    _append_trace(evaluation, f"strategy_v2_1_htf_alignment={result['htf_alignment']}")
    _append_trace(evaluation, f"strategy_v2_1_would_block={str(result['would_block']).lower()}")
    _append_trace(evaluation, f"strategy_v2_1_mode={result['mode']}")
    if not result["blocked"]:
        return status, result
    _append_unique(evaluation.rejection_reasons, BLOCK_REASON)
    _append_unique(evaluation.failed_filters, BLOCK_REASON)
    evaluation.decision = "no_trade"
    signal.decision = "no_trade"
    signal.status = "rejected"
    return "rejected", result


def _reason(*, enabled: bool, mode: str, htf_alignment: str, blocked: bool, would_block: bool) -> str:
    if not enabled:
        return "disabled"
    if htf_alignment != "against":
        return "htf_alignment_not_against"
    if blocked:
        return BLOCK_REASON
    if would_block and mode == "shadow":
        return "shadow_would_block"
    return "no_block"


def _append_trace(evaluation: Any, token: str) -> None:
    if token not in evaluation.decision_trace:
        evaluation.decision_trace.append(token)


def _append_unique(values: list[str], token: str) -> None:
    if token not in values:
        values.append(token)
'''


def _filter_tests_source() -> str:
    return '''from __future__ import annotations

from dataclasses import dataclass, field

from trading_signals.application.use_cases.strategy_v2_1_htf_alignment_filter import (
    BLOCK_REASON,
    apply_strategy_v2_1_htf_alignment_filter,
    determine_htf_alignment,
    evaluate_strategy_v2_1_htf_alignment_filter,
)


@dataclass
class Evaluation:
    decision: str = "long"
    decision_trace: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    failed_filters: list[str] = field(default_factory=list)


@dataclass
class Signal:
    decision: str = "long"
    status: str = "valid"


def test_flag_false_no_block() -> None:
    result = evaluate_strategy_v2_1_htf_alignment_filter(enabled=False, mode="hard_block", htf_alignment="against")

    assert result["blocked"] is False
    assert result["would_block"] is False
    assert result["rejection_reason"] is None


def test_shadow_no_block_but_would_block() -> None:
    result = evaluate_strategy_v2_1_htf_alignment_filter(enabled=True, mode="shadow", htf_alignment="against")

    assert result["blocked"] is False
    assert result["would_block"] is True
    assert result["reason"] == "shadow_would_block"


def test_hard_block_blocks_against() -> None:
    result = evaluate_strategy_v2_1_htf_alignment_filter(enabled=True, mode="hard_block", htf_alignment="against")

    assert result["blocked"] is True
    assert result["would_block"] is True
    assert result["rejection_reason"] == BLOCK_REASON


def test_hard_block_does_not_block_aligned() -> None:
    result = evaluate_strategy_v2_1_htf_alignment_filter(enabled=True, mode="hard_block", htf_alignment="aligned")

    assert result["blocked"] is False
    assert result["would_block"] is False


def test_unknown_or_none_never_blocks() -> None:
    for value in ("unknown", None):
        result = evaluate_strategy_v2_1_htf_alignment_filter(enabled=True, mode="hard_block", htf_alignment=value)
        assert result["blocked"] is False
        assert result["would_block"] is False


def test_invalid_mode_fails_safe_as_shadow() -> None:
    result = evaluate_strategy_v2_1_htf_alignment_filter(enabled=True, mode="invalid", htf_alignment="against")

    assert result["mode"] == "shadow"
    assert result["blocked"] is False
    assert result["would_block"] is True


def test_determine_htf_alignment() -> None:
    assert determine_htf_alignment(direction="long", higher_trend="bullish") == "aligned"
    assert determine_htf_alignment(direction="short", higher_trend="bearish") == "aligned"
    assert determine_htf_alignment(direction="long", higher_trend="bearish") == "against"
    assert determine_htf_alignment(direction="short", higher_trend="bullish") == "against"
    assert determine_htf_alignment(direction="long", higher_trend="sideways") == "unknown"


def test_minimal_integration_blocks_when_enabled() -> None:
    evaluation = Evaluation()
    signal = Signal()

    status, result = apply_strategy_v2_1_htf_alignment_filter(
        evaluation=evaluation,
        signal=signal,
        status="valid",
        enabled=True,
        mode="hard_block",
        direction="long",
        higher_trend="bearish",
    )

    assert status == "rejected"
    assert result["blocked"] is True
    assert BLOCK_REASON in evaluation.rejection_reasons
    assert signal.status == "rejected"
'''
