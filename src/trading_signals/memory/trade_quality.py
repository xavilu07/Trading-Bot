from __future__ import annotations


def classify_trade_quality(inputs: dict[str, object]) -> dict[str, object]:
    historical_edge = _dict(inputs.get("historical_edge"))
    adaptive = _dict(inputs.get("adaptive_thresholds"))
    edge_confirmation = _dict(inputs.get("edge_confirmation"))
    direction = str(inputs.get("direction") or "").upper()
    setup_type = str(inputs.get("setup_type") or "").upper()
    market_regime = str(inputs.get("market_regime") or "").upper()
    entry_context = str(inputs.get("entry_context") or "").upper()
    htf_trend = str(inputs.get("htf_trend") or "").lower()
    ltf_trend = str(inputs.get("ltf_trend") or "").lower()
    warnings = _tokens(inputs.get("warnings"))
    penalties = _tokens(inputs.get("penalties"))
    rr = _float(inputs.get("rr"), 0.0)
    edge_score = _float(historical_edge.get("historical_edge_score"), 50.0)
    edge_confidence = str(historical_edge.get("historical_confidence") or "LOW").upper()
    matches = int(_float(historical_edge.get("matched_patterns_count"), 0.0))
    winrate = _float(historical_edge.get("matched_winrate"), 0.0)
    avg_r = _float(historical_edge.get("matched_avg_r"), 0.0)
    profit_factor = _float(historical_edge.get("matched_profit_factor"), 0.0)
    confirmation_score = _float(edge_confirmation.get("edge_confirmation_score"), 50.0)
    confirmation_level = str(edge_confirmation.get("edge_confirmation_level") or "MEDIUM").upper()
    adaptive_delta = _float(adaptive.get("threshold_delta"), 0.0)
    score = 50.0
    reasons: list[str] = []
    risks: list[str] = []

    score += _plus(market_regime == "HIGH_VOLATILITY", 7, "HIGH_VOLATILITY", reasons)
    score += _plus(entry_context == "BREAKOUT", 7, "BREAKOUT", reasons)
    score += _plus(entry_context == "IMPULSE", 6, "IMPULSE", reasons)
    score += _plus(setup_type == "MAIN_SIGNAL", 6, "MAIN_SIGNAL", reasons)
    score += _plus(direction == "LONG" and _trend_aligned(direction, htf_trend, ltf_trend), 6, "LONG aligned", reasons)
    score += _plus(rr >= 1.5, 8, f"RR válido ({rr})", reasons)
    score += _plus(confirmation_level == "HIGH", 9, "edge_confirmation HIGH", reasons)
    score += _plus(edge_confidence == "HIGH" and edge_score >= 70, 8, "historical edge HIGH", reasons)
    score += _plus(profit_factor > 1.5, 7, f"PF > 1.5 ({profit_factor})", reasons)
    score += _plus(avg_r > 0, min(7.0, avg_r * 5.0), f"avgR positivo ({avg_r})", reasons)
    score += _plus(winrate > 50, min(6.0, (winrate - 50.0) / 5.0), f"WR > 50% ({winrate}%)", reasons)
    score += _plus(_has_token(inputs, "momentum_strong"), 5, "momentum fuerte", reasons)
    score += _plus(_has_token(inputs, "volume_strong"), 5, "volumen fuerte", reasons)
    score += _plus(_has_token(inputs, "liquidity_distance_ok"), 5, "liquidity distance OK", reasons)
    score += _plus(not warnings, 4, "sin warnings", reasons)
    score += _plus(not penalties, 4, "sin penalties", reasons)
    score += _plus(_trend_aligned(direction, htf_trend, ltf_trend), 5, "trend aligned", reasons)
    score += _plus(adaptive_delta < 0, min(5.0, abs(adaptive_delta) / 2.0), "adaptive threshold favorable", reasons)

    score -= _minus(entry_context == "CHOPPY_RANGE", 10, "CHOPPY_RANGE", risks)
    score -= _minus(market_regime == "RANGING", 8, "RANGING", risks)
    score -= _minus(setup_type == "SECONDARY_SIGNAL" and direction == "SHORT", 12, "SECONDARY short", risks)
    score -= _minus(_has_token(inputs, "against_htf") or not _trend_aligned(direction, htf_trend, ltf_trend), 8, "against HTF", risks)
    score -= _minus(_has_token(inputs, "low_volume"), 7, "low_volume", risks)
    score -= _minus(_has_token(inputs, "body_ratio_below_threshold"), 7, "body_ratio_below_threshold", risks)
    score -= _minus(edge_confidence == "LOW" or edge_score < 40, 7, "historical edge LOW", risks)
    score -= _minus(profit_factor > 0 and profit_factor < 1, 8, f"PF < 1 ({profit_factor})", risks)
    score -= _minus(avg_r < 0, min(8.0, abs(avg_r) * 5.0), f"avgR negativo ({avg_r})", risks)
    score -= _minus(rr > 0 and rr < 1.5, 10, f"RR inválido ({rr})", risks)
    score -= _minus(rr <= 0, 8, "RR ausente/inválido", risks)
    score -= _minus(len(warnings) >= 3, 8, "demasiados warnings", risks)
    score -= _minus(len(penalties) >= 3, 8, "demasiadas penalties", risks)
    score -= _minus(_has_token(inputs, "weak_momentum"), 7, "weak momentum", risks)
    score -= _minus(matches < 10, 7, f"low matches históricos ({matches})", risks)
    score -= _minus(confirmation_score < 40, 7, "edge confirmation débil", risks)
    score -= _minus(adaptive_delta > 0, min(5.0, adaptive_delta / 2.0), "adaptive threshold defensivo", risks)

    final_score = round(max(0.0, min(100.0, score)), 2)
    return {
        "trade_quality_score": final_score,
        "trade_quality_grade": _grade(final_score),
        "quality_confidence": _confidence(matches, edge_confidence, confirmation_level),
        "quality_bias": _bias(final_score),
        "quality_reasons": reasons,
        "quality_risks": risks,
        "historical_quality_alignment": {
            "historical_edge_score": edge_score,
            "historical_confidence": edge_confidence,
            "edge_confirmation_score": confirmation_score,
            "edge_confirmation_level": confirmation_level,
            "adaptive_threshold": adaptive.get("adaptive_threshold"),
            "matched_patterns_count": matches,
            "matched_winrate": winrate,
            "matched_avg_r": avg_r,
            "matched_profit_factor": profit_factor,
            "rr": rr,
            "direction": direction,
            "setup_type": setup_type,
            "market_regime": market_regime,
            "entry_context": entry_context,
        },
    }


def _grade(score: float) -> str:
    if score >= 90:
        return "A+"
    if score >= 75:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    return "TRASH"


def _confidence(matches: int, edge_confidence: str, confirmation_level: str) -> str:
    if matches >= 30 and edge_confidence == "HIGH" and confirmation_level == "HIGH":
        return "HIGH"
    if matches >= 10 and edge_confidence in {"MEDIUM", "HIGH"}:
        return "MEDIUM"
    return "LOW"


def _bias(score: float) -> str:
    if score >= 65:
        return "POSITIVE"
    if score < 45:
        return "NEGATIVE"
    return "NEUTRAL"


def _trend_aligned(direction: str, htf_trend: str, ltf_trend: str) -> bool:
    if direction == "LONG":
        return htf_trend == "bullish" and ltf_trend == "bullish"
    if direction == "SHORT":
        return htf_trend == "bearish" and ltf_trend == "bearish"
    return False


def _has_token(inputs: dict[str, object], token: str) -> bool:
    needle = token.lower()
    values = []
    for key in ("warnings", "penalties", "blocking_reasons", "quality_reasons", "quality_risks"):
        values.extend(_tokens(inputs.get(key)))
    return needle in {value.lower() for value in values}


def _plus(condition: bool, value: float, reason: str, reasons: list[str]) -> float:
    if not condition or value <= 0:
        return 0.0
    reasons.append(reason)
    return float(value)


def _minus(condition: bool, value: float, reason: str, risks: list[str]) -> float:
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

