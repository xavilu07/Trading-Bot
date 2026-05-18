from __future__ import annotations


CONFIDENCE_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
SOFT_GATE_MODE = "SOFT"


def evaluate_performance_gate(performance_intelligence: dict[str, object]) -> dict[str, object]:
    """Classify performance intelligence before publish without changing behavior."""
    meta_decision = _dict(performance_intelligence.get("meta_decision"))
    trade_quality = _dict(performance_intelligence.get("trade_quality"))
    historical_edge = _dict(performance_intelligence.get("historical_edge"))

    confidence = _combined_confidence(meta_decision, trade_quality, historical_edge)
    scores = {
        "meta_decision_score": _float(meta_decision.get("meta_decision_score"), 0.0),
        "trade_quality_score": _float(trade_quality.get("trade_quality_score"), 0.0),
        "historical_edge_score": _float(historical_edge.get("historical_edge_score"), 0.0),
    }
    context = {
        "meta_decision": str(meta_decision.get("meta_decision") or "UNKNOWN").upper(),
        "trade_quality_grade": str(trade_quality.get("trade_quality_grade") or "UNKNOWN").upper(),
        "historical_confidence": str(historical_edge.get("historical_confidence") or "LOW").upper(),
        "matched_patterns_count": int(_float(historical_edge.get("matched_patterns_count"), 0.0)),
        "matched_profit_factor": _float(historical_edge.get("matched_profit_factor"), 0.0),
        "matched_avg_r": _float(historical_edge.get("matched_avg_r"), 0.0),
        "capital_preservation_mode": bool(meta_decision.get("capital_preservation_mode")),
        "aggressive_mode": bool(meta_decision.get("aggressive_mode")),
    }

    reasons = []
    risks = []
    action = "ALLOW"

    if _would_block(context, scores, confidence, risks):
        action = "WOULD_BLOCK"
    elif _would_prioritize(context, scores, confidence, reasons):
        action = "PRIORITIZE"
    elif _should_use_caution(context, scores, confidence, risks):
        action = "CAUTION"
    else:
        reasons.append("performance gate allows current behavior")

    return {
        "mode": SOFT_GATE_MODE,
        "action": action,
        "would_block": action == "WOULD_BLOCK",
        "would_prioritize": action == "PRIORITIZE",
        "confidence": confidence,
        "reasons": reasons,
        "risks": risks,
        "scores": scores,
        "context": context,
    }


def _would_block(context: dict[str, object], scores: dict[str, float], confidence: str, risks: list[str]) -> bool:
    if not _confidence_at_least(confidence, "MEDIUM"):
        return False

    if context["capital_preservation_mode"] is True:
        risks.append("capital preservation mode active")
    if context["meta_decision"] == "REJECT":
        risks.append("meta decision rejected")
    if context["trade_quality_grade"] == "TRASH":
        risks.append("trade quality trash")
    if scores["historical_edge_score"] < 40 and _confidence_at_least(str(context["historical_confidence"]), "MEDIUM"):
        risks.append("historical edge negative with sufficient confidence")
    if (
        float(context["matched_profit_factor"]) > 0
        and float(context["matched_profit_factor"]) < 1
        and float(context["matched_avg_r"]) < 0
        and _confidence_at_least(str(context["historical_confidence"]), "MEDIUM")
    ):
        risks.append("historical profit factor and avgR are negative")

    return bool(risks)


def _would_prioritize(context: dict[str, object], scores: dict[str, float], confidence: str, reasons: list[str]) -> bool:
    if not _confidence_at_least(confidence, "MEDIUM"):
        return False

    strong_meta = context["meta_decision"] in {"SEND", "STRONG_SEND"}
    strong_quality = context["trade_quality_grade"] in {"A", "A+"}
    strong_history = scores["historical_edge_score"] >= 65
    if strong_meta and strong_quality and strong_history:
        reasons.extend(["meta decision send", "trade quality strong", "historical edge strong"])
    if context["aggressive_mode"] is True and strong_quality:
        reasons.append("aggressive mode with strong trade quality")

    return bool(reasons)


def _should_use_caution(context: dict[str, object], scores: dict[str, float], confidence: str, risks: list[str]) -> bool:
    if context["meta_decision"] in {"NEUTRAL", "WEAK_REJECT", "REJECT"}:
        risks.append(f"meta decision {context['meta_decision']}")
    if context["trade_quality_grade"] in {"C", "TRASH"}:
        risks.append(f"trade quality {context['trade_quality_grade']}")
    if 40 <= scores["historical_edge_score"] <= 55:
        risks.append("historical edge neutral to weak")
    if confidence == "LOW":
        risks.append("low confidence performance context")
    if float(context["matched_profit_factor"]) > 0 and float(context["matched_profit_factor"]) < 1:
        risks.append("historical profit factor below 1")
    if float(context["matched_avg_r"]) < 0:
        risks.append("historical avgR negative")

    return bool(risks)


def _combined_confidence(
    meta_decision: dict[str, object],
    trade_quality: dict[str, object],
    historical_edge: dict[str, object],
) -> str:
    values = [
        str(meta_decision.get("meta_confidence") or "LOW").upper(),
        str(trade_quality.get("quality_confidence") or "LOW").upper(),
        str(historical_edge.get("historical_confidence") or "LOW").upper(),
    ]
    return max(values, key=lambda value: CONFIDENCE_RANK.get(value, 0))


def _confidence_at_least(value: str, minimum: str) -> bool:
    return CONFIDENCE_RANK.get(value.upper(), 0) >= CONFIDENCE_RANK[minimum]


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
