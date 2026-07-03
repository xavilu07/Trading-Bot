from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from trading_signals.application.use_cases.edge_knowledge_shadow_v1 import build_edge_knowledge_context
from trading_signals.intelligence.edge_optimizer import optimize_edge_context


@dataclass(frozen=True)
class EdgeOptimizerShadowResult:
    symbol: str
    direction: str
    setup_type: str
    current_decision: str
    current_score: float
    optimizer_adjustment: float
    optimizer_confidence: str
    matched_edges_count: int
    matched_positive_edges: list[dict[str, Any]]
    matched_negative_edges: list[dict[str, Any]]
    top_edges: list[dict[str, Any]]
    hypothetical_score: float
    hypothetical_bias: str
    context: dict[str, str]
    min_evidence_count: int
    conflict_reduced: bool
    caps_applied: list[str]
    shadow_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_edge_optimizer_shadow_v1(
    *,
    symbol: str,
    analysis,
    evaluation,
    risk_plan,
    setup_context: dict[str, Any],
    signal_decision,
    setup_type: str,
    direction: str,
    knowledge: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> EdgeOptimizerShadowResult:
    context = build_edge_knowledge_context(
        symbol=symbol,
        analysis=analysis,
        evaluation=evaluation,
        risk_plan=risk_plan,
        setup_context=setup_context,
        setup_type=setup_type,
        direction=direction,
        now=now,
    )
    current_score = float(_float(getattr(evaluation, "setup_score", None)) or 0.0)
    optimizer = optimize_edge_context(context, current_score=current_score, knowledge=knowledge)
    return EdgeOptimizerShadowResult(
        symbol=symbol,
        direction=direction,
        setup_type=setup_type,
        current_decision=str(getattr(signal_decision, "decision", getattr(evaluation, "decision", ""))),
        current_score=current_score,
        optimizer_adjustment=float(optimizer.get("optimizer_adjustment") or 0.0),
        optimizer_confidence=str(optimizer.get("confidence") or "LOW"),
        matched_edges_count=int(optimizer.get("matched_edges_count") or 0),
        matched_positive_edges=list(optimizer.get("matched_positive_edges") or []),
        matched_negative_edges=list(optimizer.get("matched_negative_edges") or []),
        top_edges=list(optimizer.get("top_edges") or []),
        hypothetical_score=float(optimizer.get("hypothetical_score") or current_score),
        hypothetical_bias=str(optimizer.get("hypothetical_bias") or "NEUTRAL"),
        context=context,
        min_evidence_count=int(optimizer.get("min_evidence_count") or 0),
        conflict_reduced=bool(optimizer.get("conflict_reduced")),
        caps_applied=list(optimizer.get("caps_applied") or []),
    )


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
