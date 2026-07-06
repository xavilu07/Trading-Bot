from __future__ import annotations

from typing import Any


FORBIDDEN_PATH_TOKENS = ("scheduler", "telegram_public", "risk_plan", "live_trading")


def code_safety_review(proposal: dict[str, Any], plan: dict[str, Any], rollback_plan: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    flags = plan.get("required_feature_flags") if isinstance(plan.get("required_feature_flags"), list) else []
    if not flags:
        blockers.append("missing_feature_flag")
    for flag in flags:
        if str(flag.get("required_default", flag.get("default", ""))).lower() == "true":
            blockers.append("feature_flag_default_true")
    files = [str(item) for item in plan.get("files_to_touch") or []]
    for file_path in files:
        if any(token in file_path for token in FORBIDDEN_PATH_TOKENS):
            blockers.append(f"forbidden_file_scope:{file_path}")
    if len(plan.get("rule_conditions") or []) != 1:
        blockers.append("multiple_strategy_rules_not_allowed")
    if not rollback_plan.get("steps"):
        blockers.append("missing_rollback_plan")
    if float(proposal.get("trade_reduction_pct") or 0) > 60:
        blockers.append("trade_reduction_above_60")
    if str(proposal.get("risk_level") or "").upper() == "HIGH":
        warnings.append("high_trade_reduction_requires_manual_shadow")
    return {
        "agent": "code_safety_director",
        "decision": "PASS" if not blockers else "BLOCK",
        "allowed": not blockers,
        "blockers": sorted(set(blockers)),
        "warnings": warnings,
    }
