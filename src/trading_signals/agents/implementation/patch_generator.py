from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def generate_patch_report(
    review: dict[str, Any],
    *,
    output_path: Path = Path("reports") / "qic",
    apply_patch: bool = False,
) -> dict[str, Any]:
    allowed = bool(review.get("allowed_to_generate_patch"))
    plan = review.get("implementation_plan") if isinstance(review.get("implementation_plan"), dict) else {}
    report = {
        "proposal_id": review.get("proposal_id"),
        "knowledge_item_id": review.get("knowledge_item_id"),
        "created_at": datetime.now(tz=UTC).isoformat(),
        "apply_patch_requested": apply_patch,
        "patch_applied": False,
        "allowed_to_generate_patch": allowed,
        "status": "patch_report_generated" if allowed else "blocked",
        "blockers": [] if allowed else ["implementation_review_not_allowed"],
        "files_to_touch": plan.get("files_to_touch", []),
        "feature_flags": plan.get("required_feature_flags", []),
        "suggested_diff": _suggested_diff(plan) if allowed else "",
        "tests_suggested": review.get("validation_commands", []),
        "validation_commands": review.get("validation_commands", []),
        "rollback_plan": review.get("rollback_plan", {}),
    }
    if apply_patch:
        report["status"] = "apply_patch_not_supported_in_v1"
        report["blockers"].append("v1_report_only_default")
    write_patch_reports(report, output_path=output_path)
    return report


def write_patch_reports(report: dict[str, Any], *, output_path: Path) -> dict[str, Path]:
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "generated_patch.json"
    md_path = output_path / "generated_patch.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_patch_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def _suggested_diff(plan: dict[str, Any]) -> str:
    flags = plan.get("required_feature_flags") or []
    if not flags:
        return ""
    return """```diff
+ STRATEGY_V2_1_HTF_ALIGNMENT_FILTER_ENABLED=false
+ STRATEGY_V2_1_HTF_ALIGNMENT_FILTER_MODE=shadow
+
+ if enabled and mode == "hard_block" and htf_alignment == "against":
+     reject candidate with reason "strategy_v2_1_htf_alignment_against"
+ else:
+     keep current decision unchanged
```
"""


def _patch_markdown(report: dict[str, Any]) -> str:
    lines = ["# QIC Generated Patch", ""]
    for key in ("proposal_id", "status", "patch_applied", "allowed_to_generate_patch"):
        lines.append(f"- {key}: {report.get(key)}")
    lines.append("")
    lines.append("## Files To Touch")
    for file_path in report.get("files_to_touch", []):
        lines.append(f"- {file_path}")
    lines.append("")
    lines.append("## Suggested Diff")
    lines.append(report.get("suggested_diff") or "No diff generated.")
    lines.append("")
    lines.append("## Validation Commands")
    for command in report.get("validation_commands", []):
        lines.append(f"- `{command}`")
    return "\n".join(lines) + "\n"
