from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any


RISK_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "EXTREME": 4}
EXTREME_TOKENS = (".env", "credential", "wallet", "secret", "private_key", "api_key")
HIGH_TOKENS = (
    "run_market_scan",
    "live_trading",
    "risk_plan",
    "position_sizing",
    "stop_loss",
    "take_profit",
    "telegram_public",
    "deploy/nginx",
    "docker-compose",
)
MEDIUM_TOKENS = ("agents/", "shadow", "notification", "memory", "intelligence", "scheduler")
LOW_PREFIXES = ("tests/", "planning/", "reports/qic/", "src/trading_signals/interfaces/frontend/", "deploy/frontend/")


def classify_change_risk(*, files: list[str], change_type: str = "", proposal: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = [_normalize_path(item).lower() for item in files]
    reasons: list[str] = []
    risk = "LOW"
    for path in normalized:
        if any(_path_has(path, token) for token in EXTREME_TOKENS):
            risk = _max_risk(risk, "EXTREME")
            reasons.append(f"secret_or_credential_scope:{path}")
        if any(token in path for token in HIGH_TOKENS):
            risk = _max_risk(risk, "HIGH")
            reasons.append(f"production_sensitive_scope:{path}")
        elif any(token in path for token in MEDIUM_TOKENS) and not path.startswith(LOW_PREFIXES):
            risk = _max_risk(risk, "MEDIUM")
            reasons.append(f"behavioral_internal_scope:{path}")
    proposal = proposal or {}
    if str(proposal.get("edge_type") or "").upper() in {"STRUCTURAL_EDGE", "TACTICAL_EDGE"}:
        risk = _max_risk(risk, "HIGH")
        reasons.append("strategy_rule_change")
    if "strategy" in change_type.lower() or "filter" in change_type.lower():
        risk = _max_risk(risk, "HIGH")
        reasons.append("strategy_or_filter_change")
    return {"risk_level": risk, "reasons": sorted(set(reasons)) or ["low_risk_scope"]}


def validate_change_paths(
    files: list[str],
    *,
    allowlist: list[str],
    denylist: list[str],
) -> dict[str, Any]:
    blocked = []
    outside_allowlist = []
    for raw in files:
        path = _normalize_path(raw)
        lower = path.lower()
        if any(_matches(lower, pattern.lower()) for pattern in denylist):
            blocked.append(path)
        if allowlist and not any(_matches(lower, pattern.lower()) for pattern in allowlist):
            outside_allowlist.append(path)
    return {
        "allowed": not blocked and not outside_allowlist,
        "blocked_paths": sorted(set(blocked)),
        "outside_allowlist": sorted(set(outside_allowlist)),
    }


def evaluate_auto_apply_policy(
    change: dict[str, Any],
    *,
    auto_apply_low_risk: bool,
    auto_apply_medium_risk: bool = False,
    live_trading_changes_allowed: bool = False,
    max_files: int = 8,
    max_changed_lines: int = 400,
) -> dict[str, Any]:
    blockers = []
    risk = str(change.get("risk_level") or "EXTREME").upper()
    files = list(change.get("files_changed") or change.get("files_planned") or [])
    changed_lines = int((change.get("diff_stats") or {}).get("changed_lines") or 0)
    if risk == "LOW" and not auto_apply_low_risk:
        blockers.append("auto_apply_low_risk_disabled")
    elif risk == "MEDIUM" and not auto_apply_medium_risk:
        blockers.append("auto_apply_medium_risk_disabled")
    elif risk in {"HIGH", "EXTREME"}:
        blockers.append("human_approval_required_for_high_risk")
    if not live_trading_changes_allowed and any("live_trading" in str(path).lower() for path in files):
        blockers.append("live_trading_changes_forbidden")
    if len(files) > max_files:
        blockers.append("file_limit_exceeded")
    if changed_lines > max_changed_lines:
        blockers.append("changed_line_limit_exceeded")
    if not change.get("implementation_council_approved"):
        blockers.append("implementation_council_not_approved")
    if not change.get("rollback_available"):
        blockers.append("rollback_missing")
    validation = change.get("validation") if isinstance(change.get("validation"), dict) else {}
    if validation.get("tests_passed") is not True:
        blockers.append("tests_not_passed")
    if validation.get("static_checks_passed") is not True:
        blockers.append("static_checks_not_passed")
    if validation.get("coverage_regression") is True:
        blockers.append("coverage_regression")
    return {"allowed": not blockers, "blockers": sorted(set(blockers)), "risk_level": risk}


def _matches(path: str, pattern: str) -> bool:
    clean = _normalize_path(pattern)
    if any(char in clean for char in "*?["):
        return fnmatch.fnmatch(path, clean)
    return path == clean or path.startswith(clean.rstrip("/") + "/") or clean in path


def _path_has(path: str, token: str) -> bool:
    return path == token or path.startswith(token + "/") or f"/{token}" in path


def _normalize_path(value: str) -> str:
    path = value.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def _max_risk(left: str, right: str) -> str:
    return left if RISK_RANK[left] >= RISK_RANK[right] else right
