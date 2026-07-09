from __future__ import annotations

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
        "reason": _reason(
            enabled=bool(enabled),
            mode=normalized_mode,
            htf_alignment=normalized_alignment,
            blocked=blocked,
            would_block=would_block,
        ),
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
