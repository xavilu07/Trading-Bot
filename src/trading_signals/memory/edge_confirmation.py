from __future__ import annotations


def calculate_edge_confirmation(inputs: dict[str, object]) -> dict[str, object]:
    historical_edge = _dict(inputs.get("historical_edge"))
    adaptive = _dict(inputs.get("adaptive_thresholds"))
    direction = str(inputs.get("direction") or "").upper()
    setup_type = str(inputs.get("setup_type") or "").upper()
    market_regime = str(inputs.get("market_regime") or "").upper()
    session = str(inputs.get("session") or "").upper()
    entry_context = str(inputs.get("entry_context") or "").upper()
    edge_score = _float(historical_edge.get("historical_edge_score"), 50.0)
    historical_confidence = str(historical_edge.get("historical_confidence") or "LOW").upper()
    matches = int(_float(historical_edge.get("matched_patterns_count"), 0.0))
    winrate = _float(historical_edge.get("matched_winrate"), 0.0)
    avg_r = _float(historical_edge.get("matched_avg_r"), 0.0)
    profit_factor = _float(historical_edge.get("matched_profit_factor"), 0.0)
    adaptive_bias = str(adaptive.get("adaptive_bias") or "NEUTRAL").upper()
    adaptive_delta = _float(adaptive.get("threshold_delta"), 0.0)

    score = 50.0
    boost = 0.0
    penalty = 0.0
    confirmation_reasons: list[str] = []
    risk_reasons: list[str] = []

    boost += _positive(edge_score >= 70 and historical_confidence == "HIGH", 12, "historical edge HIGH", confirmation_reasons)
    boost += _positive(avg_r > 0, min(12.0, avg_r * 8.0), f"avgR positivo ({avg_r})", confirmation_reasons)
    boost += _positive(profit_factor > 1.2, min(12.0, (profit_factor - 1.2) * 6.0), f"PF > 1.2 ({profit_factor})", confirmation_reasons)
    boost += _positive(winrate > 50, min(10.0, (winrate - 50.0) / 4.0), f"WR > 50% ({winrate}%)", confirmation_reasons)
    boost += _positive(direction == "LONG" and market_regime == "HIGH_VOLATILITY", 6, "LONG en HIGH_VOLATILITY", confirmation_reasons)
    boost += _positive(entry_context == "BREAKOUT" and avg_r > 0, 5, "BREAKOUT rentable", confirmation_reasons)
    boost += _positive(setup_type == "MAIN_SIGNAL" and avg_r > 0, 5, "MAIN_SIGNAL rentable", confirmation_reasons)
    boost += _positive(edge_score > 60, 4, "contexto históricamente ganador", confirmation_reasons)
    boost += _positive(adaptive_bias in {"BULLISH", "BEARISH"} and adaptive_delta < 0, 4, "adaptive threshold favorable", confirmation_reasons)
    boost += _positive(bool(session) and avg_r > 0 and winrate > 50, 3, f"session rentable ({session})", confirmation_reasons)

    penalty += _negative(direction == "SHORT" and market_regime == "RANGING", 12, "SHORT + RANGING", risk_reasons)
    penalty += _negative(setup_type == "SECONDARY_SIGNAL" and entry_context == "CHOPPY_RANGE", 12, "SECONDARY_SIGNAL + CHOPPY_RANGE", risk_reasons)
    penalty += _negative(profit_factor > 0 and profit_factor < 1, min(12.0, (1.0 - profit_factor) * 12.0), f"PF < 1 ({profit_factor})", risk_reasons)
    penalty += _negative(avg_r < 0, min(12.0, abs(avg_r) * 8.0), f"avgR negativo ({avg_r})", risk_reasons)
    penalty += _negative(winrate > 0 and winrate < 40, min(10.0, (40.0 - winrate) / 4.0), f"WR < 40% ({winrate}%)", risk_reasons)
    penalty += _negative(historical_confidence == "LOW", 5, "historical edge LOW", risk_reasons)
    penalty += _negative(matches < 10, 8, f"pocos matches históricos ({matches})", risk_reasons)
    penalty += _negative(edge_score < 40, 8, "setup históricamente perdedor", risk_reasons)
    penalty += _negative(adaptive_delta > 0, min(8.0, adaptive_delta / 2.0), "adaptive threshold defensivo", risk_reasons)

    final_score = round(max(0.0, min(100.0, score + boost - penalty)), 2)
    return {
        "edge_confirmation_score": final_score,
        "edge_confirmation_level": _level(final_score),
        "edge_bias": _bias(final_score, boost, penalty),
        "confidence_boost": round(boost, 4),
        "confidence_penalty": round(penalty, 4),
        "confirmation_reasons": confirmation_reasons,
        "risk_reasons": risk_reasons,
        "historical_alignment": {
            "historical_edge_score": edge_score,
            "historical_confidence": historical_confidence,
            "matched_patterns_count": matches,
            "matched_winrate": winrate,
            "matched_avg_r": avg_r,
            "matched_profit_factor": profit_factor,
            "adaptive_threshold": adaptive.get("adaptive_threshold"),
            "adaptive_bias": adaptive_bias,
            "direction": direction,
            "setup_type": setup_type,
            "market_regime": market_regime,
            "session": session,
            "entry_context": entry_context,
        },
    }


def _positive(condition: bool, value: float, reason: str, reasons: list[str]) -> float:
    if not condition or value <= 0:
        return 0.0
    reasons.append(reason)
    return float(value)


def _negative(condition: bool, value: float, reason: str, reasons: list[str]) -> float:
    if not condition or value <= 0:
        return 0.0
    reasons.append(reason)
    return float(value)


def _level(score: float) -> str:
    if score >= 70:
        return "HIGH"
    if score >= 45:
        return "MEDIUM"
    return "LOW"


def _bias(score: float, boost: float, penalty: float) -> str:
    if score >= 65 and boost > penalty:
        return "POSITIVE"
    if score <= 40 and penalty > boost:
        return "NEGATIVE"
    return "NEUTRAL"


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

