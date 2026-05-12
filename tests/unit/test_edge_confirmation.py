from __future__ import annotations

from trading_signals.memory.edge_confirmation import calculate_edge_confirmation


def inputs(**overrides) -> dict[str, object]:
    data = {
        "direction": "LONG",
        "setup_type": "MAIN_SIGNAL",
        "market_regime": "HIGH_VOLATILITY",
        "session": "LONDON",
        "entry_context": "BREAKOUT",
        "trade_location": "near_support",
        "historical_edge": {
            "historical_edge_score": 75,
            "historical_confidence": "HIGH",
            "matched_patterns_count": 35,
            "matched_winrate": 62,
            "matched_avg_r": 0.8,
            "matched_profit_factor": 2.0,
        },
        "adaptive_thresholds": {
            "adaptive_threshold": 36,
            "adaptive_bias": "BULLISH",
            "threshold_delta": -9,
        },
    }
    data.update(overrides)
    return data


def test_positive_context_increases_confirmation_score() -> None:
    result = calculate_edge_confirmation(inputs())

    assert result["edge_confirmation_score"] > 70
    assert result["edge_confirmation_level"] == "HIGH"
    assert result["edge_bias"] == "POSITIVE"
    assert result["confidence_boost"] > result["confidence_penalty"]
    assert "historical edge HIGH" in result["confirmation_reasons"]


def test_negative_context_lowers_confirmation_score() -> None:
    result = calculate_edge_confirmation(
        inputs(
            direction="SHORT",
            setup_type="SECONDARY_SIGNAL",
            market_regime="RANGING",
            entry_context="CHOPPY_RANGE",
            historical_edge={
                "historical_edge_score": 25,
                "historical_confidence": "MEDIUM",
                "matched_patterns_count": 15,
                "matched_winrate": 25,
                "matched_avg_r": -0.8,
                "matched_profit_factor": 0.5,
            },
            adaptive_thresholds={"adaptive_threshold": 62, "adaptive_bias": "NEUTRAL", "threshold_delta": 17},
        )
    )

    assert result["edge_confirmation_score"] < 40
    assert result["edge_bias"] == "NEGATIVE"
    assert result["confidence_penalty"] > result["confidence_boost"]
    assert "SHORT + RANGING" in result["risk_reasons"]
    assert "SECONDARY_SIGNAL + CHOPPY_RANGE" in result["risk_reasons"]


def test_few_matches_penalize_confirmation() -> None:
    result = calculate_edge_confirmation(
        inputs(
            historical_edge={
                "historical_edge_score": 55,
                "historical_confidence": "LOW",
                "matched_patterns_count": 3,
                "matched_winrate": 50,
                "matched_avg_r": 0.0,
                "matched_profit_factor": 1.0,
            }
        )
    )

    assert "pocos matches históricos (3)" in result["risk_reasons"]
    assert result["confidence_penalty"] > 0


def test_historical_edge_high_favors_confirmation() -> None:
    result = calculate_edge_confirmation(inputs(historical_edge={**inputs()["historical_edge"], "historical_edge_score": 85}))

    assert result["edge_confirmation_score"] > 70
    assert "historical edge HIGH" in result["confirmation_reasons"]


def test_low_profit_factor_penalizes_confirmation() -> None:
    result = calculate_edge_confirmation(
        inputs(
            historical_edge={
                "historical_edge_score": 45,
                "historical_confidence": "MEDIUM",
                "matched_patterns_count": 20,
                "matched_winrate": 45,
                "matched_avg_r": -0.1,
                "matched_profit_factor": 0.8,
            }
        )
    )

    assert any(reason.startswith("PF < 1") for reason in result["risk_reasons"])
    assert result["confidence_penalty"] > 0

