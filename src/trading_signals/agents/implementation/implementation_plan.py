from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def build_implementation_plan(proposal: dict[str, Any]) -> dict[str, Any]:
    conditions = _conditions(proposal)
    is_htf_against = any("htf_alignment" in item and "against" in item for item in conditions)
    if is_htf_against:
        return {
            "proposal_id": proposal.get("id"),
            "knowledge_item_id": proposal.get("knowledge_item_id"),
            "created_at": _now(),
            "change_type": "feature_flagged_strategy_filter",
            "summary": "Block candidates where htf_alignment=against behind a disabled feature flag.",
            "rule_conditions": conditions,
            "required_feature_flags": [
                {
                    "name": "STRATEGY_V2_1_HTF_ALIGNMENT_FILTER_ENABLED",
                    "default": "false",
                    "required_default": "false",
                },
                {
                    "name": "STRATEGY_V2_1_HTF_ALIGNMENT_FILTER_MODE",
                    "default": "shadow",
                    "allowed_values": ["shadow", "hard_block"],
                },
            ],
            "required_rejection_reasons": ["strategy_v2_1_htf_alignment_against"],
            "files_to_touch": [
                "src/trading_signals/app/settings.py",
                "src/trading_signals/application/use_cases/strategy_v2_1_htf_alignment_filter.py",
                "src/trading_signals/application/use_cases/run_market_scan.py",
                "tests/unit/test_strategy_v2_1_htf_alignment_filter.py",
            ],
            "implementation_steps": [
                "Add feature flag settings with disabled/shadow defaults.",
                "Detect htf_alignment using existing pre-trade candidate fields.",
                "If enabled and mode=hard_block, add rejection_reason strategy_v2_1_htf_alignment_against.",
                "If mode=shadow, log would_block without changing final decision.",
                "Persist diagnostics to signals_log/pattern memory if available.",
                "Add unit tests for disabled, shadow, hard_block, aligned and unknown cases.",
            ],
            "production_activation": "manual_feature_flag_only",
        }
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
