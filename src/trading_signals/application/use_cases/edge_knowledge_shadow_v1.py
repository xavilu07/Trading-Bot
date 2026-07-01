from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from trading_signals.intelligence.edge_knowledge import evaluate_context


@dataclass(frozen=True)
class EdgeKnowledgeShadowResult:
    symbol: str
    direction: str
    setup_type: str
    current_decision: str
    current_score: float
    ekb_bonus: int
    ekb_confidence: str
    matched_edges_count: int
    top_matched_edges: list[dict[str, Any]]
    hypothetical_score: float
    hypothetical_bias: str
    context: dict[str, str]
    shadow_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_edge_knowledge_context(
    *,
    symbol: str,
    analysis,
    evaluation,
    risk_plan,
    setup_context: dict[str, Any],
    setup_type: str,
    direction: str,
    now: datetime | None = None,
) -> dict[str, str]:
    entry = analysis.entry_snapshot
    metadata = getattr(entry, "metadata", {}) or {}
    timestamp = now or datetime.now(UTC)
    score = _float(getattr(evaluation, "setup_score", None))
    rr_valid = _rr_valid(risk_plan, setup_context)
    return {
        "symbol": _text(symbol),
        "direction": _text(direction),
        "setup_type": _text(setup_type),
        "market_regime": _text(setup_context.get("market_regime")),
        "session": _text(setup_context.get("session")),
        "entry_context": _text(setup_context.get("entry_context")),
        "trade_location": _text(setup_context.get("trade_location")),
        "score_bucket": score_bucket(score),
        "score_exact": _score_exact(score),
        "trend_1h": _text(getattr(entry, "trend", None)),
        "trend_4h": _text(getattr(analysis.higher_snapshot, "trend", None)),
        "liquidity_sweep": _text(setup_context.get("liquidity_sweep") or getattr(entry, "liquidity_sweep", None)),
        "break_of_structure": _text(metadata.get("break_of_structure")),
        "rr_valid": _bool_text(rr_valid),
        "late_entry_from_bos": _bool_text(setup_context.get("late_entry_from_bos")),
        "opened_hour_utc": str(timestamp.astimezone(UTC).hour),
        "opened_weekday": timestamp.astimezone(UTC).strftime("%A").lower(),
        "volume_ratio_bucket": volume_bucket(
            _float(metadata.get("volume_ratio_vs_average_20") or metadata.get("volume_ratio"))
        ),
        "rsi_bucket": rsi_bucket(_float(metadata.get("rsi"))),
        "nearest_distance_to_liquidity_atr_bucket": distance_bucket(
            _float(metadata.get("nearest_distance_to_liquidity_atr"))
        ),
        "directional_distance_to_liquidity_atr_bucket": distance_bucket(
            _float(getattr(entry, "distance_to_liquidity_atr", None))
        ),
    }


def evaluate_edge_knowledge_shadow_v1(
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
) -> EdgeKnowledgeShadowResult:
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
    edge_result = evaluate_context(context, knowledge=knowledge)
    bonus = int(edge_result.get("bonus") or 0)
    current_score = float(_float(getattr(evaluation, "setup_score", None)) or 0.0)
    matched_edges = edge_result.get("matched_edges", [])
    top_edges = _top_matched_edges(matched_edges if isinstance(matched_edges, list) else [])
    hypothetical_score = current_score + bonus
    return EdgeKnowledgeShadowResult(
        symbol=symbol,
        direction=direction,
        setup_type=setup_type,
        current_decision=str(getattr(signal_decision, "decision", getattr(evaluation, "decision", ""))),
        current_score=current_score,
        ekb_bonus=bonus,
        ekb_confidence=str(edge_result.get("confidence") or "LOW"),
        matched_edges_count=len(matched_edges) if isinstance(matched_edges, list) else 0,
        top_matched_edges=top_edges,
        hypothetical_score=round(hypothetical_score, 4),
        hypothetical_bias=hypothetical_bias(bonus),
        context=context,
    )


def hypothetical_bias(bonus: int | float) -> str:
    if bonus >= 8:
        return "PRIORITIZE"
    if bonus <= -8:
        return "AVOID"
    return "NEUTRAL"


def format_edge_knowledge_shadow_dev_note(result: EdgeKnowledgeShadowResult) -> str:
    edges = ", ".join(str(edge.get("unique_id") or edge.get("context")) for edge in result.top_matched_edges[:3])
    if not edges:
        edges = "sin matches"
    return "\n".join(
        [
            "EDGE KNOWLEDGE SHADOW",
            f"{result.symbol} {result.direction.upper()}",
            f"Setup: {result.setup_type}",
            f"Score actual: {result.current_score:g}",
            f"EKB bonus: {result.ekb_bonus:+d}",
            f"Hipotético: {result.hypothetical_score:g} ({result.hypothetical_bias})",
            f"Confianza: {result.ekb_confidence}",
            f"Matches: {result.matched_edges_count}",
            f"Top edges: {edges}",
            "Shadow only. No cambia decisión real.",
        ]
    )


def score_bucket(score: float | None) -> str:
    if score is None:
        return "UNKNOWN"
    if score < 50:
        return "0-49"
    if score < 60:
        return "50-59"
    if score < 70:
        return "60-69"
    if score < 80:
        return "70-79"
    if score < 90:
        return "80-89"
    return "90-100"


def distance_bucket(value: float | None) -> str:
    if value is None:
        return "UNKNOWN"
    if value < 0.5:
        return "<0.5"
    if value < 1:
        return "0.5-1"
    if value < 2:
        return "1-2"
    if value < 3:
        return "2-3"
    if value < 5:
        return "3-5"
    return "5+"


def volume_bucket(value: float | None) -> str:
    if value is None:
        return "UNKNOWN"
    if value < 0.8:
        return "<0.8"
    if value < 1:
        return "0.8-1.0"
    if value < 1.2:
        return "1.0-1.2"
    if value < 1.5:
        return "1.2-1.5"
    if value < 2:
        return "1.5-2.0"
    return "2.0+"


def rsi_bucket(value: float | None) -> str:
    if value is None:
        return "UNKNOWN"
    if value < 30:
        return "<30"
    if value < 40:
        return "30-40"
    if value < 50:
        return "40-50"
    if value < 60:
        return "50-60"
    if value < 70:
        return "60-70"
    return "70+"


def _top_matched_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_edges = sorted(edges, key=lambda edge: abs(_float(edge.get("statistical_weight")) or 0.0), reverse=True)
    top = []
    for edge in sorted_edges[:5]:
        top.append(
            {
                "unique_id": edge.get("unique_id"),
                "category": edge.get("category"),
                "context": edge.get("context", {}),
                "statistical_weight": edge.get("statistical_weight", 0),
                "confidence": edge.get("confidence", "LOW"),
                "evidence_count": edge.get("evidence_count", 0),
                "metrics": edge.get("metrics", {}),
            }
        )
    return top


def _rr_valid(risk_plan, setup_context: dict[str, Any]) -> bool:
    if "rr_valid" in setup_context:
        return _bool(setup_context.get("rr_valid"))
    if risk_plan is None:
        return False
    return (_float(getattr(risk_plan, "risk_reward", None)) or 0.0) > 0


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "passed", "valid"}


def _bool_text(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    raw = str(value or "").strip().lower()
    if raw in {"1", "true", "yes", "y", "passed", "valid"}:
        return "true"
    if raw in {"0", "false", "no", "n", "failed", "invalid"}:
        return "false"
    return "UNKNOWN" if raw == "" else raw


def _score_exact(score: float | None) -> str:
    if score is None:
        return "UNKNOWN"
    return str(int(score)) if score.is_integer() else str(round(score, 4))


def _text(value: object) -> str:
    text = str(value or "").strip()
    return text if text else "UNKNOWN"


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
