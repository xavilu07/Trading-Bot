"""Refuse setups whose final score sits below a threshold.

The candle-by-candle replay of 2026-08-24 (`scripts/replay_harness.py`) found
that the strategy has no directional edge as a whole - P(touch +1R) 31.2% vs
P(SL) 29.1%, a ratio of 51.75% against the >52% needed just to cover friction -
and that exactly one subpopulation does: `score >= 90`, PF net 1.2406 over 238
trades, positive in all four months. It is also the only refinement that
survived walk-forward (PF 1.2888 in-sample -> 1.2482 out-of-sample); removing
the TP cap and excluding BTCUSDT both gave back most of their advantage.

Which threshold is right is *not* settled by that data: 85 and 95 both look
better out of sample than in, on 77 and 29 trades respectively. So this ships in
`shadow` mode, where it records the setups it would have refused without
refusing them, and the threshold stays configurable. Flip it to `hard_block`
only once enough trades have accumulated above the threshold to choose from new
data rather than from the May-July record it was discovered in.
"""
from __future__ import annotations

from typing import Any

BLOCK_REASON = "setup_score_below_threshold"
SHADOW_MARKER = "setup_score_below_threshold_shadow"
TRACE_PREFIX = "setup_score_threshold_filter_"
VALID_MODES = {"shadow", "hard_block"}
TRADE_DECISIONS = {"long", "short"}
DEFAULT_MIN_SCORE = 90.0


def _normalized_mode(mode: str | None) -> str:
    normalized = str(mode or "shadow").strip().lower()
    return normalized if normalized in VALID_MODES else "shadow"


def _normalized_min_score(min_score: Any) -> float:
    try:
        value = float(min_score)
    except (TypeError, ValueError):
        return DEFAULT_MIN_SCORE
    # A threshold outside the score range would silently turn the filter into
    # "block everything" or "block nothing"; neither is ever intended.
    if not 0.0 <= value <= 100.0:
        return DEFAULT_MIN_SCORE
    return value


def evaluate_setup_score_threshold_filter(
    *,
    enabled: bool,
    mode: str,
    min_score: Any,
    setup_score: Any,
    current_decision: str | None = None,
) -> dict[str, Any]:
    normalized_mode = _normalized_mode(mode)
    threshold = _normalized_min_score(min_score)
    try:
        score = float(setup_score)
    except (TypeError, ValueError):
        score = None
    decision = str(current_decision or "").strip().lower()
    is_candidate = decision in TRADE_DECISIONS
    below_threshold = score is not None and score < threshold
    would_block = bool(enabled) and is_candidate and below_threshold
    blocked = bool(would_block and normalized_mode == "hard_block")
    return {
        "enabled": bool(enabled),
        "mode": normalized_mode,
        "min_score": threshold,
        "setup_score": score,
        "is_candidate": is_candidate,
        "below_threshold": below_threshold,
        "would_block": would_block,
        "blocked": blocked,
        "rejection_reason": BLOCK_REASON if blocked else None,
        "reason": _reason(
            enabled=bool(enabled),
            is_candidate=is_candidate,
            score=score,
            below_threshold=below_threshold,
            mode=normalized_mode,
            blocked=blocked,
            would_block=would_block,
        ),
        "current_decision": current_decision,
    }


def apply_setup_score_threshold_filter(
    *,
    evaluation: Any,
    signal: Any,
    status: str,
    enabled: bool,
    mode: str,
    min_score: Any,
) -> tuple[str, dict[str, Any]]:
    result = evaluate_setup_score_threshold_filter(
        enabled=enabled,
        mode=mode,
        min_score=min_score,
        setup_score=getattr(evaluation, "setup_score", None),
        current_decision=getattr(evaluation, "decision", None),
    )
    _append_trace(evaluation, f"{TRACE_PREFIX}mode={result['mode']}")
    _append_trace(evaluation, f"{TRACE_PREFIX}min_score={result['min_score']:g}")
    _append_trace(evaluation, f"{TRACE_PREFIX}would_block={str(result['would_block']).lower()}")
    if not result["would_block"]:
        return status, result
    if not result["blocked"]:
        # Shadow: the counterfactual has to be readable off the stored trade
        # record, and `conditions_failed` is the column that carries it.
        _append_unique(evaluation.failed_filters, SHADOW_MARKER)
        return status, result
    _append_unique(evaluation.rejection_reasons, BLOCK_REASON)
    _append_unique(evaluation.failed_filters, BLOCK_REASON)
    evaluation.decision = "no_trade"
    signal.decision = "no_trade"
    signal.status = "rejected"
    return "rejected", result


def _reason(
    *,
    enabled: bool,
    is_candidate: bool,
    score: float | None,
    below_threshold: bool,
    mode: str,
    blocked: bool,
    would_block: bool,
) -> str:
    if not enabled:
        return "disabled"
    if score is None:
        return "score_unavailable"
    if not is_candidate:
        return "no_candidate"
    if not below_threshold:
        return "score_above_threshold"
    if blocked:
        return BLOCK_REASON
    if would_block and mode == "shadow":
        return "shadow_would_block"
    return "no_block"


def _append_trace(evaluation: Any, token: str) -> None:
    trace = getattr(evaluation, "decision_trace", None)
    if trace is None:
        return
    if token not in trace:
        trace.append(token)


def _append_unique(values: list[str], token: str) -> None:
    if token not in values:
        values.append(token)
