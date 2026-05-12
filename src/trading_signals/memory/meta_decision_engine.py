from __future__ import annotations


def evaluate_meta_decision(inputs: dict[str, object]) -> dict[str, object]:
    historical_edge = _dict(inputs.get("historical_edge"))
    adaptive = _dict(inputs.get("adaptive_thresholds"))
    edge_confirmation = _dict(inputs.get("edge_confirmation"))
    trade_quality = _dict(inputs.get("trade_quality"))
    outcome = _dict(inputs.get("outcome_intelligence"))
    direction = str(inputs.get("direction") or "").upper()
    setup_type = str(inputs.get("setup_type") or "").upper()
    market_regime = str(inputs.get("market_regime") or "").upper()
    entry_context = str(inputs.get("entry_context") or "").upper()
    warnings = _tokens(inputs.get("warnings"))
    penalties = _tokens(inputs.get("penalties"))
    rr = _float(inputs.get("rr"), 0.0)
    htf_trend = str(inputs.get("htf_trend") or "").lower()
    ltf_trend = str(inputs.get("ltf_trend") or "").lower()
    operational_score = _float(inputs.get("score") or inputs.get("setup_score") or inputs.get("setup_score_final"), 50.0)
    hist_confidence = str(historical_edge.get("historical_confidence") or "LOW").upper()
    hist_score = _float(historical_edge.get("historical_edge_score"), 50.0)
    hist_pf = _float(historical_edge.get("matched_profit_factor"), 0.0)
    hist_avg_r = _float(historical_edge.get("matched_avg_r"), 0.0)
    edge_level = str(edge_confirmation.get("edge_confirmation_level") or "MEDIUM").upper()
    edge_confirm_score = _float(edge_confirmation.get("edge_confirmation_score"), 50.0)
    quality_grade = str(trade_quality.get("trade_quality_grade") or "C").upper()
    quality_score = _float(trade_quality.get("trade_quality_score"), 50.0)
    outcome_type = str(outcome.get("outcome_type") or "").upper()
    outcome_score = _float(outcome.get("outcome_quality_score"), 50.0)
    adaptive_delta = _float(adaptive.get("threshold_delta"), 0.0)
    score = 50.0
    reasons: list[str] = []
    risks: list[str] = []

    score += _positive(hist_confidence == "HIGH" and hist_score >= 70, 10, "historical edge HIGH", reasons)
    score += _positive(quality_grade in {"A", "A+"}, 12, f"trade quality {quality_grade}", reasons)
    score += _positive(outcome_type in {"CLEAN_WIN", "DIRTY_WIN"} or outcome_score >= 70, 8, "outcome intelligence positiva", reasons)
    score += _positive(edge_level == "HIGH", 9, "edge confirmation HIGH", reasons)
    score += _positive(adaptive_delta < 0, min(7.0, abs(adaptive_delta) / 2.0), "adaptive threshold favorable", reasons)
    score += _positive(hist_pf > 1.5, 7, f"PF histórico > 1.5 ({hist_pf})", reasons)
    score += _positive(hist_avg_r > 0, min(7.0, hist_avg_r * 5.0), f"avgR positivo ({hist_avg_r})", reasons)
    score += _positive(len(warnings) <= 1, 4, "warnings bajos", reasons)
    score += _positive(len(penalties) <= 1, 4, "penalties bajas", reasons)
    score += _positive(setup_type == "MAIN_SIGNAL" and hist_avg_r > 0, 5, "MAIN_SIGNAL rentable", reasons)
    score += _positive(direction == "LONG" and hist_score >= 65, 5, "LONG con edge histórico fuerte", reasons)
    score += _positive(hist_score > 60, 4, "contexto históricamente ganador", reasons)
    score += _positive(_has_token(inputs, "momentum_strong"), 4, "momentum fuerte", reasons)
    score += _positive(_trend_aligned(direction, htf_trend, ltf_trend), 5, "trend alignment", reasons)
    score += _positive(rr >= 1.5, 6, f"RR válido ({rr})", reasons)
    score += _positive(operational_score >= 75, 5, f"score operativo alto ({operational_score})", reasons)

    score -= _negative(hist_confidence == "LOW" or hist_score < 40, 9, "historical edge LOW", risks)
    score -= _negative(quality_grade in {"TRASH", "C"}, 12, f"trade quality {quality_grade}", risks)
    score -= _negative(outcome_type in {"BAD_LOSS", "TIMEOUT"} or outcome_score < 40, 8, "outcome intelligence negativa", risks)
    score -= _negative(len(warnings) >= 3, 8, "many warnings", risks)
    score -= _negative(len(penalties) >= 3, 8, "many penalties", risks)
    score -= _negative(_has_token(inputs, "low_volume"), 6, "low volume", risks)
    score -= _negative(entry_context == "CHOPPY_RANGE", 8, "CHOPPY_RANGE", risks)
    score -= _negative(setup_type == "SECONDARY_SIGNAL" and direction == "SHORT" and hist_score < 55, 10, "SECONDARY short histórico malo", risks)
    score -= _negative(hist_pf > 0 and hist_pf < 1, 8, f"PF < 1 ({hist_pf})", risks)
    score -= _negative(hist_avg_r < 0, min(8.0, abs(hist_avg_r) * 5.0), f"avgR negativo ({hist_avg_r})", risks)
    score -= _negative(rr > 0 and rr < 1.5, 9, f"RR inválido ({rr})", risks)
    score -= _negative(rr <= 0, 7, "RR ausente/inválido", risks)
    score -= _negative(_has_token(inputs, "against_htf") or not _trend_aligned(direction, htf_trend, ltf_trend), 7, "against HTF", risks)
    score -= _negative(_has_token(inputs, "weak_momentum"), 6, "weak momentum", risks)
    score -= _negative(_low_confidence_contexts(historical_edge, edge_confirmation, trade_quality), 7, "low confidence contexts", risks)
    score -= _negative(adaptive_delta > 0, min(6.0, adaptive_delta / 2.0), "adaptive threshold defensivo", risks)

    final_score = round(max(0.0, min(100.0, score)), 2)
    positive_count = len(reasons)
    negative_count = len(risks)
    return {
        "meta_decision_score": final_score,
        "meta_decision": _decision(final_score),
        "meta_confidence": _confidence(historical_edge, edge_confirmation, trade_quality),
        "capital_preservation_mode": negative_count >= 4 and negative_count > positive_count,
        "aggressive_mode": positive_count >= 5 and final_score >= 75 and positive_count > negative_count,
        "meta_reasons": reasons,
        "meta_risks": risks,
        "system_alignment": {
            "operational_score": operational_score,
            "historical_edge_score": hist_score,
            "historical_confidence": hist_confidence,
            "edge_confirmation_score": edge_confirm_score,
            "edge_confirmation_level": edge_level,
            "trade_quality_score": quality_score,
            "trade_quality_grade": quality_grade,
            "outcome_quality_score": outcome_score,
            "outcome_type": outcome_type or "UNKNOWN",
            "adaptive_threshold": adaptive.get("adaptive_threshold"),
            "adaptive_delta": adaptive_delta,
            "direction": direction,
            "setup_type": setup_type,
            "market_regime": market_regime,
            "entry_context": entry_context,
        },
    }


def _decision(score: float) -> str:
    if score >= 85:
        return "STRONG_SEND"
    if score >= 70:
        return "SEND"
    if score >= 58:
        return "WEAK_SEND"
    if score >= 45:
        return "NEUTRAL"
    if score >= 30:
        return "WEAK_REJECT"
    return "REJECT"


def _confidence(historical_edge: dict[str, object], edge_confirmation: dict[str, object], trade_quality: dict[str, object]) -> str:
    high_votes = 0
    medium_votes = 0
    if str(historical_edge.get("historical_confidence", "")).upper() == "HIGH":
        high_votes += 1
    if str(edge_confirmation.get("edge_confirmation_level", "")).upper() == "HIGH":
        high_votes += 1
    if str(trade_quality.get("quality_confidence", "")).upper() == "HIGH":
        high_votes += 1
    if str(historical_edge.get("historical_confidence", "")).upper() == "MEDIUM":
        medium_votes += 1
    if str(edge_confirmation.get("edge_confirmation_level", "")).upper() == "MEDIUM":
        medium_votes += 1
    if str(trade_quality.get("quality_confidence", "")).upper() == "MEDIUM":
        medium_votes += 1
    if high_votes >= 2:
        return "HIGH"
    if high_votes + medium_votes >= 2:
        return "MEDIUM"
    return "LOW"


def _low_confidence_contexts(historical_edge: dict[str, object], edge_confirmation: dict[str, object], trade_quality: dict[str, object]) -> bool:
    return (
        str(historical_edge.get("historical_confidence", "")).upper() == "LOW"
        and str(edge_confirmation.get("edge_confirmation_level", "")).upper() == "LOW"
        and str(trade_quality.get("quality_confidence", "")).upper() == "LOW"
    )


def _trend_aligned(direction: str, htf_trend: str, ltf_trend: str) -> bool:
    if direction == "LONG":
        return htf_trend == "bullish" and ltf_trend == "bullish"
    if direction == "SHORT":
        return htf_trend == "bearish" and ltf_trend == "bearish"
    return False


def _has_token(inputs: dict[str, object], token: str) -> bool:
    needle = token.lower()
    values = []
    for key in ("warnings", "penalties", "blocking_reasons", "quality_risks", "meta_risks"):
        values.extend(_tokens(inputs.get(key)))
    return needle in {value.lower() for value in values}


def _positive(condition: bool, value: float, reason: str, reasons: list[str]) -> float:
    if not condition or value <= 0:
        return 0.0
    reasons.append(reason)
    return float(value)


def _negative(condition: bool, value: float, reason: str, risks: list[str]) -> float:
    if not condition or value <= 0:
        return 0.0
    risks.append(reason)
    return float(value)


def _tokens(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).replace("|", ",").split(",") if item.strip()]


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

