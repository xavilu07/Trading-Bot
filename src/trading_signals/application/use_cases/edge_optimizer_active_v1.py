from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


CONFIDENCE_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
MIN_CROSSING_SCORE = 70.0


@dataclass(slots=True)
class EdgeOptimizerActiveResult:
    enabled: bool
    applied: bool
    original_score: float
    optimizer_adjustment: float
    active_adjustment: float
    adjusted_score: float
    confidence: str
    min_confidence: str
    matched_edges_count: int
    reasons: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def apply_edge_optimizer_active_v1(
    *,
    evaluation,
    signal_decision,
    edge_optimizer_shadow: Any,
    enabled: bool,
    max_adjustment: float = 2.0,
    min_confidence: str = "MEDIUM",
) -> EdgeOptimizerActiveResult:
    original_score = _float(getattr(evaluation, "setup_score", 0.0)) or 0.0
    optimizer_adjustment = _float(_get(edge_optimizer_shadow, "optimizer_adjustment")) or 0.0
    confidence = str(_get(edge_optimizer_shadow, "optimizer_confidence") or _get(edge_optimizer_shadow, "confidence") or "LOW").upper()
    matched_edges_count = int(_float(_get(edge_optimizer_shadow, "matched_edges_count")) or 0)
    reasons: list[str] = []
    active_adjustment = 0.0

    if not enabled:
        reasons.append("edge_optimizer_active_disabled")
    elif _confidence_rank(confidence) < _confidence_rank(min_confidence):
        reasons.append("confidence_below_minimum")
    else:
        active_adjustment = _cap(optimizer_adjustment, abs(float(max_adjustment)))
        if original_score < MIN_CROSSING_SCORE and active_adjustment > 0 and original_score + active_adjustment >= MIN_CROSSING_SCORE:
            active_adjustment = 0.0
            reasons.append("prevented_sub_70_threshold_cross")
        if active_adjustment == 0.0 and not reasons:
            reasons.append("zero_adjustment")

    adjusted_score = round(original_score + active_adjustment, 4)
    applied = enabled and active_adjustment != 0.0
    if applied:
        evaluation.setup_score = adjusted_score
        if hasattr(signal_decision, "total_score"):
            signal_decision.total_score = adjusted_score
        module_scores = getattr(signal_decision, "module_scores", None)
        if isinstance(module_scores, dict) and "strategy" in module_scores:
            module_scores["strategy"] = adjusted_score
        trace = getattr(evaluation, "decision_trace", None)
        if isinstance(trace, list):
            trace.extend(
                [
                    f"edge_optimizer_active_adjustment={active_adjustment}",
                    f"edge_optimizer_active_original_score={original_score}",
                    f"edge_optimizer_active_adjusted_score={adjusted_score}",
                ]
            )

    return EdgeOptimizerActiveResult(
        enabled=enabled,
        applied=applied,
        original_score=original_score,
        optimizer_adjustment=optimizer_adjustment,
        active_adjustment=round(active_adjustment, 4),
        adjusted_score=adjusted_score,
        confidence=confidence,
        min_confidence=min_confidence.upper(),
        matched_edges_count=matched_edges_count,
        reasons=reasons,
    )


def _confidence_rank(value: str) -> int:
    return CONFIDENCE_RANK.get(str(value or "LOW").upper(), 1)


def _cap(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


def _get(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
