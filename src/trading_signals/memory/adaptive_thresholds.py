from __future__ import annotations


BASE_THRESHOLD = 45
MIN_THRESHOLD = 30
MAX_THRESHOLD = 70


def calculate_adaptive_thresholds(inputs: dict[str, object]) -> dict[str, object]:
    confidence = str(inputs.get("historical_confidence") or "LOW").upper()
    edge_score = _float(inputs.get("historical_edge_score"), 50.0)
    winrate = _float(inputs.get("matched_winrate"), 0.0)
    avg_r = _float(inputs.get("matched_avg_r"), 0.0)
    profit_factor = _float(inputs.get("matched_profit_factor"), 0.0)
    matched_count = int(_float(inputs.get("matched_patterns_count"), 0.0))
    market_regime = str(inputs.get("market_regime") or "").upper()
    entry_context = str(inputs.get("entry_context") or "").upper()
    direction = str(inputs.get("direction") or "").upper()
    warnings = _tokens(inputs.get("warnings"))
    penalties = _tokens(inputs.get("penalties"))
    multiplier = _confidence_multiplier(confidence)
    adjustment = 0.0
    reasons: list[str] = []

    if matched_count == 0:
        reasons.append("sin historial suficiente: threshold base conservado")
    if profit_factor and profit_factor < 1:
        delta = 6 * multiplier
        adjustment += delta
        reasons.append(f"PF < 1 aumenta threshold (+{delta:g})")
    if avg_r < 0:
        delta = 6 * multiplier
        adjustment += delta
        reasons.append(f"AvgR negativo aumenta threshold (+{delta:g})")
    if winrate and winrate < 40:
        delta = 5 * multiplier
        adjustment += delta
        reasons.append(f"WR < 40% aumenta threshold (+{delta:g})")
    if market_regime == "RANGING":
        adjustment += 4
        reasons.append("market_regime RANGING aumenta threshold (+4)")
    if entry_context == "CHOPPY_RANGE":
        adjustment += 5
        reasons.append("entry_context CHOPPY_RANGE aumenta threshold (+5)")
    if len(warnings) >= 3:
        adjustment += 4
        reasons.append("many warnings aumenta threshold (+4)")
    if confidence == "HIGH" and edge_score < 40:
        adjustment += 8
        reasons.append("confidence HIGH con edge negativo aumenta threshold (+8)")

    if profit_factor > 1.5:
        delta = 6 * multiplier
        adjustment -= delta
        reasons.append(f"PF > 1.5 reduce threshold (-{delta:g})")
    if avg_r > 0:
        delta = 5 * multiplier
        adjustment -= delta
        reasons.append(f"AvgR positivo reduce threshold (-{delta:g})")
    if winrate > 55:
        delta = 5 * multiplier
        adjustment -= delta
        reasons.append(f"WR > 55% reduce threshold (-{delta:g})")
    if market_regime == "HIGH_VOLATILITY":
        adjustment -= 3
        reasons.append("HIGH_VOLATILITY reduce threshold (-3)")
    if entry_context in {"BREAKOUT", "IMPULSE"}:
        adjustment -= 4
        reasons.append(f"{entry_context} reduce threshold (-4)")
    if confidence == "HIGH" and edge_score > 65:
        adjustment -= 8
        reasons.append("confidence HIGH con edge positivo reduce threshold (-8)")

    adaptive_threshold = int(round(max(MIN_THRESHOLD, min(MAX_THRESHOLD, BASE_THRESHOLD + adjustment))))
    threshold_delta = adaptive_threshold - BASE_THRESHOLD
    return {
        "base_threshold": BASE_THRESHOLD,
        "adaptive_threshold": adaptive_threshold,
        "adaptive_confidence": _adaptive_confidence(confidence, matched_count),
        "adaptive_bias": _adaptive_bias(direction, edge_score, avg_r, profit_factor, winrate),
        "adaptive_reasoning": reasons or ["sin ajustes adaptativos relevantes"],
        "edge_adjustment": round(adjustment, 4),
        "threshold_delta": threshold_delta,
    }


def _confidence_multiplier(confidence: str) -> float:
    if confidence == "HIGH":
        return 1.5
    if confidence == "MEDIUM":
        return 1.0
    return 0.5


def _adaptive_confidence(confidence: str, matched_count: int) -> str:
    if matched_count == 0:
        return "LOW"
    if confidence in {"LOW", "MEDIUM", "HIGH"}:
        return confidence
    if matched_count >= 30:
        return "HIGH"
    if matched_count >= 10:
        return "MEDIUM"
    return "LOW"


def _adaptive_bias(direction: str, edge_score: float, avg_r: float, profit_factor: float, winrate: float) -> str:
    positive_edge = edge_score >= 60 and avg_r > 0 and profit_factor >= 1.2 and winrate >= 50
    negative_edge = edge_score <= 40 or avg_r < 0 or (profit_factor > 0 and profit_factor < 1) or (winrate > 0 and winrate < 40)
    if positive_edge and direction == "LONG":
        return "BULLISH"
    if positive_edge and direction == "SHORT":
        return "BEARISH"
    if negative_edge:
        return "NEUTRAL"
    return "NEUTRAL"


def _tokens(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).replace("|", ",").split(",") if item.strip()]


def _float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

