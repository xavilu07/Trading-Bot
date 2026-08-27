from __future__ import annotations

from typing import Any

BLOCK_REASON = "strategy_v2_1_condition_filter_cio_805ad892d491"
VALID_MODES = {"shadow", "hard_block"}
CONDITIONS: list[dict[str, str]] = [
    {
        "feature": "liquidity_distance_bucket",
        "operator": "==",
        "value": "2-4atr"
    }
]


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


def evaluate_strategy_v2_1_condition_filter_cio_805ad892d491(
    *,
    enabled: bool,
    mode: str,
    context: dict[str, Any] | None = None,
    current_decision: str | None = None,
) -> dict[str, Any]:
    normalized_mode = str(mode or "shadow").strip().lower()
    if normalized_mode not in VALID_MODES:
        normalized_mode = "shadow"
    ctx = context or {}
    matched = bool(CONDITIONS) and all(_matches(ctx.get(item["feature"]), item["operator"], item["value"]) for item in CONDITIONS)
    would_block = bool(enabled) and matched
    blocked = bool(would_block and normalized_mode == "hard_block")
    return {
        "enabled": bool(enabled),
        "mode": normalized_mode,
        "matched_conditions": matched,
        "would_block": would_block,
        "blocked": blocked,
        "rejection_reason": BLOCK_REASON if blocked else None,
        "reason": _reason(enabled=bool(enabled), matched=matched, mode=normalized_mode, blocked=blocked, would_block=would_block),
        "current_decision": current_decision,
        "context": ctx,
    }


def apply_strategy_v2_1_condition_filter_cio_805ad892d491(
    *,
    evaluation: Any,
    signal: Any,
    status: str,
    enabled: bool,
    mode: str,
    context: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    result = evaluate_strategy_v2_1_condition_filter_cio_805ad892d491(
        enabled=enabled,
        mode=mode,
        context=context,
        current_decision=getattr(evaluation, "decision", None),
    )
    _append_trace(evaluation, f"strategy_v2_1_condition_filter_cio_805ad892d491_matched={str(result['matched_conditions']).lower()}")
    _append_trace(evaluation, f"strategy_v2_1_condition_filter_cio_805ad892d491_would_block={str(result['would_block']).lower()}")
    _append_trace(evaluation, f"strategy_v2_1_condition_filter_cio_805ad892d491_mode={result['mode']}")
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
