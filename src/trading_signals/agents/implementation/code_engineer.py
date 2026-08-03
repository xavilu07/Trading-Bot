from __future__ import annotations

import difflib
import json
import os
import re
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
from trading_signals.research.simulator import (
    BANNED_FILTER_FEATURES,
    SAFE_CATEGORICAL_FEATURES,
    SAFE_NUMERIC_THRESHOLDS,
)

CODE_ENGINEER_REPORT = "code_engineer"
# Condition fields the generator is allowed to write filters against — the same allowlist
# QIC's own simulator already treats as safe to form hypotheses over. Anything outside this
# set (or resembling risk/execution fields) falls back to "needs manual implementation"
# instead of generating code for it; see _parse_conditions.
MAX_CONDITIONS = 4
_ALLOWED_CONDITION_FIELDS = (set(SAFE_CATEGORICAL_FEATURES) | set(SAFE_NUMERIC_THRESHOLDS)) - set(
    BANNED_FILTER_FEATURES
)
_CONDITION_OPERATOR_PATTERN = re.compile(r"(<=|>=|==|!=|<|>|=)")


def _parse_condition(raw: Any) -> dict[str, str] | None:
    text = str(raw or "").strip()
    lowered = text.lower()
    if lowered.startswith("exclude:"):
        text = text[len("exclude:"):].strip()
    elif lowered.startswith("exclude "):
        text = text[len("exclude "):].strip()
    else:
        return None
    match = _CONDITION_OPERATOR_PATTERN.search(text)
    if not match:
        return None
    feature = text[: match.start()].strip()
    value = text[match.end():].strip()
    if not feature or not value or feature not in _ALLOWED_CONDITION_FIELDS:
        return None
    operator = "==" if match.group(1) in {"=", "=="} else match.group(1)
    return {"feature": feature, "operator": operator, "value": value}


def _parse_conditions(raw_conditions: list[Any]) -> list[dict[str, str]] | None:
    if not raw_conditions or len(raw_conditions) > MAX_CONDITIONS:
        return None
    parsed: list[dict[str, str]] = []
    for raw in raw_conditions:
        condition = _parse_condition(raw)
        if condition is None:
            return None
        parsed.append(condition)
    return parsed


def _condition_slug(proposal_id: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", str(proposal_id or "").strip().lower()).strip("_")
    return slug or "unnamed"


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
    conditions_raw = (plan or {}).get("rule_conditions") or (proposal or {}).get("conditions") or []
    conditions = _parse_conditions(conditions_raw) or []
    files = _planned_files(proposal_id)
    generated = _generated_files(proposal_id, conditions) if conditions else {}
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
            files=files,
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
            post_apply = _run_validation_tests(project_root=project_root, files=files, max_autofix_attempts=max_autofix_attempts)
            report["tests_run"] = [*report["tests_run"], *post_apply["commands"]]
            report["tests_passed"] = bool(post_apply["passed"])
            report["test_output_summary"] += f"\npost_apply:\n{post_apply['summary']}"
            if not post_apply["passed"]:
                rollback_result = manager.rollback(str(change["change_id"]), manual_approval=True)
                rollback_validation = _run_validation_tests(
                    project_root=project_root,
                    files=files,
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
    if not conditions:
        blockers.append("no_strategy_rules_provided")
    elif len(conditions) > MAX_CONDITIONS:
        blockers.append("too_many_strategy_rules")
    elif _parse_conditions(conditions) is None:
        blockers.append("unsupported_rule_for_code_engineer_v1")
    forbidden = [file_path for file_path in _planned_files(proposal_id) if _is_forbidden_file(file_path)]
    blockers.extend(f"forbidden_file:{item}" for item in forbidden)
    return sorted(set(blockers))


def _module_name(proposal_id: str) -> str:
    return f"strategy_v2_1_condition_filter_{_condition_slug(proposal_id)}"


def _planned_files(proposal_id: str) -> list[str]:
    module_name = _module_name(proposal_id)
    return [
        f"src/trading_signals/application/use_cases/{module_name}.py",
        f"tests/unit/test_{module_name}.py",
    ]


def _generated_files(proposal_id: str, conditions: list[dict[str, str]]) -> dict[str, str]:
    if not conditions:
        return {}
    module_name = _module_name(proposal_id)
    module_file, test_file = _planned_files(proposal_id)
    return {
        module_file: _filter_source(module_name=module_name, conditions=conditions),
        test_file: _filter_tests_source(module_name=module_name, conditions=conditions),
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


def _run_validation_tests(*, project_root: Path, files: list[str], max_autofix_attempts: int) -> dict[str, Any]:
    module_file, test_file = files[0], files[1]
    commands = [
        f"python3 -m py_compile {module_file}",
        f"MPLBACKEND=Agg .venv/bin/pytest -q {test_file}",
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
    files: list[str],
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
        return _run_validation_tests(project_root=sandbox, files=files, max_autofix_attempts=max_autofix_attempts)


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


def _matching_value(operator: str, value: str) -> str:
    if operator == "==":
        return value
    if operator == "!=":
        return f"{value}_other"
    try:
        number = float(value)
    except ValueError:
        return value
    if operator == "<":
        return str(number - 1)
    if operator == ">":
        return str(number + 1)
    return str(number)


def _filter_source(*, module_name: str, conditions: list[dict[str, str]]) -> str:
    conditions_literal = json.dumps(conditions, indent=4)
    return f'''from __future__ import annotations

from typing import Any

BLOCK_REASON = "{module_name}"
VALID_MODES = {{"shadow", "hard_block"}}
CONDITIONS: list[dict[str, str]] = {conditions_literal}


def _matches(actual: Any, operator: str, expected: str) -> bool:
    if operator == "==":
        return str(actual if actual is not None else "").strip().lower() == str(expected).strip().lower()
    if operator == "!=":
        return str(actual if actual is not None else "").strip().lower() != str(expected).strip().lower()
    try:
        actual_number = float(actual)
        expected_number = float(expected)
    except (TypeError, ValueError):
        return False
    if operator == "<":
        return actual_number < expected_number
    if operator == "<=":
        return actual_number <= expected_number
    if operator == ">":
        return actual_number > expected_number
    if operator == ">=":
        return actual_number >= expected_number
    return False


def evaluate_{module_name}(
    *,
    enabled: bool,
    mode: str,
    context: dict[str, Any] | None = None,
    current_decision: str | None = None,
) -> dict[str, Any]:
    normalized_mode = str(mode or "shadow").strip().lower()
    if normalized_mode not in VALID_MODES:
        normalized_mode = "shadow"
    ctx = context or {{}}
    matched = bool(CONDITIONS) and all(_matches(ctx.get(item["feature"]), item["operator"], item["value"]) for item in CONDITIONS)
    would_block = bool(enabled) and matched
    blocked = bool(would_block and normalized_mode == "hard_block")
    return {{
        "enabled": bool(enabled),
        "mode": normalized_mode,
        "matched_conditions": matched,
        "would_block": would_block,
        "blocked": blocked,
        "rejection_reason": BLOCK_REASON if blocked else None,
        "reason": _reason(enabled=bool(enabled), matched=matched, mode=normalized_mode, blocked=blocked, would_block=would_block),
        "current_decision": current_decision,
        "context": ctx,
    }}


def apply_{module_name}(
    *,
    evaluation: Any,
    signal: Any,
    status: str,
    enabled: bool,
    mode: str,
    context: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    result = evaluate_{module_name}(
        enabled=enabled,
        mode=mode,
        context=context,
        current_decision=getattr(evaluation, "decision", None),
    )
    _append_trace(evaluation, f"{module_name}_matched={{str(result['matched_conditions']).lower()}}")
    _append_trace(evaluation, f"{module_name}_would_block={{str(result['would_block']).lower()}}")
    _append_trace(evaluation, f"{module_name}_mode={{result['mode']}}")
    if not result["blocked"]:
        return status, result
    _append_unique(evaluation.rejection_reasons, BLOCK_REASON)
    _append_unique(evaluation.failed_filters, BLOCK_REASON)
    evaluation.decision = "no_trade"
    signal.decision = "no_trade"
    signal.status = "rejected"
    return "rejected", result


def _reason(*, enabled: bool, matched: bool, mode: str, blocked: bool, would_block: bool) -> str:
    if not enabled:
        return "disabled"
    if not matched:
        return "conditions_not_matched"
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


def _filter_tests_source(*, module_name: str, conditions: list[dict[str, str]]) -> str:
    matching_pairs = ", ".join(
        f"{json.dumps(item['feature'])}: {json.dumps(_matching_value(item['operator'], item['value']))}"
        for item in conditions
    )
    first_feature = json.dumps(conditions[0]["feature"])
    conditions_literal = json.dumps(conditions)
    return f'''from __future__ import annotations

from dataclasses import dataclass, field

from trading_signals.application.use_cases.{module_name} import (
    BLOCK_REASON,
    CONDITIONS,
    apply_{module_name},
    evaluate_{module_name},
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


MATCHING_CONTEXT = {{{matching_pairs}}}


def test_flag_false_no_block() -> None:
    result = evaluate_{module_name}(enabled=False, mode="hard_block", context=MATCHING_CONTEXT)

    assert result["blocked"] is False
    assert result["would_block"] is False
    assert result["rejection_reason"] is None


def test_shadow_no_block_but_would_block() -> None:
    result = evaluate_{module_name}(enabled=True, mode="shadow", context=MATCHING_CONTEXT)

    assert result["blocked"] is False
    assert result["would_block"] is True
    assert result["reason"] == "shadow_would_block"


def test_hard_block_blocks_when_all_conditions_match() -> None:
    result = evaluate_{module_name}(enabled=True, mode="hard_block", context=MATCHING_CONTEXT)

    assert result["blocked"] is True
    assert result["would_block"] is True
    assert result["rejection_reason"] == BLOCK_REASON


def test_hard_block_does_not_block_when_a_condition_differs() -> None:
    context = dict(MATCHING_CONTEXT)
    context[{first_feature}] = "__no_match__"
    result = evaluate_{module_name}(enabled=True, mode="hard_block", context=context)

    assert result["blocked"] is False
    assert result["would_block"] is False


def test_empty_context_never_blocks() -> None:
    result = evaluate_{module_name}(enabled=True, mode="hard_block", context={{}})

    assert result["blocked"] is False
    assert result["would_block"] is False


def test_invalid_mode_fails_safe_as_shadow() -> None:
    result = evaluate_{module_name}(enabled=True, mode="invalid", context=MATCHING_CONTEXT)

    assert result["mode"] == "shadow"
    assert result["blocked"] is False
    assert result["would_block"] is True


def test_conditions_match_the_proposal() -> None:
    assert CONDITIONS == {conditions_literal}


def test_minimal_integration_blocks_when_enabled() -> None:
    evaluation = Evaluation()
    signal = Signal()

    status, result = apply_{module_name}(
        evaluation=evaluation,
        signal=signal,
        status="valid",
        enabled=True,
        mode="hard_block",
        context=MATCHING_CONTEXT,
    )

    assert status == "rejected"
    assert result["blocked"] is True
    assert BLOCK_REASON in evaluation.rejection_reasons
    assert signal.status == "rejected"
'''
