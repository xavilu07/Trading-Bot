from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from trading_signals.agents.implementation.code_engineer import _module_name, _parse_conditions


def build_implementation_plan(proposal: dict[str, Any]) -> dict[str, Any]:
    conditions = _conditions(proposal)
    parsed = _parse_conditions(conditions)
    if parsed is None:
        return {
            "proposal_id": proposal.get("id"),
            "knowledge_item_id": proposal.get("knowledge_item_id"),
            "created_at": _now(),
            "change_type": "manual_research_required",
            "summary": "No safe implementation template exists for this proposal in V1.",
            "rule_conditions": conditions,
            "required_feature_flags": [],
            "required_rejection_reasons": [],
            "files_to_touch": [],
            "implementation_steps": ["Manual technical design required before patch generation."],
            "production_activation": "not_allowed",
        }
    module_name = _module_name(str(proposal.get("id") or ""))
    flag_prefix = module_name.upper()
    condition_summary = ", ".join(f"{item['feature']}{item['operator']}{item['value']}" for item in parsed)
    return {
        "proposal_id": proposal.get("id"),
        "knowledge_item_id": proposal.get("knowledge_item_id"),
        "created_at": _now(),
        "change_type": "feature_flagged_strategy_filter",
        "summary": f"Block candidates matching {condition_summary} behind a disabled feature flag.",
        "rule_conditions": conditions,
        "required_feature_flags": [
            {
                "name": f"{flag_prefix}_ENABLED",
                "default": "false",
                "required_default": "false",
            },
            {
                "name": f"{flag_prefix}_MODE",
                "default": "shadow",
                "allowed_values": ["shadow", "hard_block"],
            },
        ],
        "required_rejection_reasons": [module_name],
        "files_to_touch": [
            "src/trading_signals/app/settings.py",
            f"src/trading_signals/application/use_cases/{module_name}.py",
            "src/trading_signals/application/use_cases/run_market_scan.py",
            f"tests/unit/test_{module_name}.py",
        ],
        "implementation_steps": [
            "Add feature flag settings with disabled/shadow defaults.",
            f"Evaluate conditions ({condition_summary}) using existing pre-trade candidate fields.",
            f"If enabled and mode=hard_block, add rejection_reason {module_name}.",
            "If mode=shadow, log would_block without changing final decision.",
            "Persist diagnostics to signals_log/pattern memory if available.",
            "Add unit tests for disabled, shadow, hard_block, matching and non-matching cases.",
        ],
        "production_activation": "manual_feature_flag_only",
    }


def _conditions(proposal: dict[str, Any]) -> list[str]:
    context = proposal.get("context") if isinstance(proposal.get("context"), dict) else {}
    raw = context.get("conditions") or proposal.get("conditions") or []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return []


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()
