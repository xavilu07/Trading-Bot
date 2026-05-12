from __future__ import annotations

from trading_signals.memory.meta_decision_engine import evaluate_meta_decision


def positive_inputs(**overrides) -> dict[str, object]:
    data = {
        "score": 88,
        "direction": "LONG",
        "setup_type": "MAIN_SIGNAL",
        "market_regime": "HIGH_VOLATILITY",
        "session": "LONDON",
        "entry_context": "BREAKOUT",
        "trade_location": "near_support",
        "htf_trend": "bullish",
        "ltf_trend": "bullish",
        "warnings": [],
        "penalties": [],
        "rr": 2.0,
        "historical_edge": {
            "historical_edge_score": 82,
            "historical_confidence": "HIGH",
            "matched_profit_factor": 2.0,
            "matched_avg_r": 0.8,
        },
        "adaptive_thresholds": {"adaptive_threshold": 35, "threshold_delta": -10},
        "edge_confirmation": {"edge_confirmation_score": 82, "edge_confirmation_level": "HIGH"},
        "trade_quality": {"trade_quality_score": 90, "trade_quality_grade": "A+", "quality_confidence": "HIGH"},
        "outcome_intelligence": {"outcome_quality_score": 85, "outcome_type": "CLEAN_WIN"},
    }
    data.update(overrides)
    return data


def test_multiple_positive_layers_produce_strong_send() -> None:
    result = evaluate_meta_decision(positive_inputs())

    assert result["meta_decision"] == "STRONG_SEND"
    assert result["meta_decision_score"] >= 85
    assert result["meta_confidence"] == "HIGH"
    assert result["aggressive_mode"] is True
    assert result["capital_preservation_mode"] is False


def test_multiple_negative_layers_produce_reject() -> None:
    result = evaluate_meta_decision(
        positive_inputs(
            score=35,
            direction="SHORT",
            setup_type="SECONDARY_SIGNAL",
            market_regime="RANGING",
            entry_context="CHOPPY_RANGE",
            htf_trend="bullish",
            ltf_trend="bearish",
            warnings=["low_volume", "dirty_sideways_market", "body_ratio_below_threshold"],
            penalties=["against_htf", "distance_to_liquidity_penalty", "market_structure_range_penalty"],
            rr=1.0,
            historical_edge={"historical_edge_score": 25, "historical_confidence": "LOW", "matched_profit_factor": 0.5, "matched_avg_r": -0.8},
            adaptive_thresholds={"adaptive_threshold": 66, "threshold_delta": 21},
            edge_confirmation={"edge_confirmation_score": 25, "edge_confirmation_level": "LOW"},
            trade_quality={"trade_quality_score": 25, "trade_quality_grade": "TRASH", "quality_confidence": "LOW"},
            outcome_intelligence={"outcome_quality_score": 20, "outcome_type": "BAD_LOSS"},
        )
    )

    assert result["meta_decision"] == "REJECT"
    assert result["capital_preservation_mode"] is True
    assert result["aggressive_mode"] is False
    assert "trade quality TRASH" in result["meta_risks"]


def test_mixed_context_produces_neutral_or_weak_send() -> None:
    result = evaluate_meta_decision(
        positive_inputs(
            score=62,
            warnings=["low_volume"],
            rr=1.6,
            historical_edge={"historical_edge_score": 55, "historical_confidence": "MEDIUM", "matched_profit_factor": 1.1, "matched_avg_r": 0.1},
            adaptive_thresholds={"adaptive_threshold": 45, "threshold_delta": 0},
            edge_confirmation={"edge_confirmation_score": 55, "edge_confirmation_level": "MEDIUM"},
            trade_quality={"trade_quality_score": 62, "trade_quality_grade": "B", "quality_confidence": "MEDIUM"},
            outcome_intelligence={"outcome_quality_score": 50, "outcome_type": "UNKNOWN"},
        )
    )

    assert result["meta_decision"] in {"NEUTRAL", "WEAK_SEND"}
    assert result["capital_preservation_mode"] is False
    assert result["aggressive_mode"] is False


def test_preservation_mode_activates_with_multiple_negative_layers() -> None:
    result = evaluate_meta_decision(
        positive_inputs(
            warnings=["low_volume", "a", "b"],
            penalties=["against_htf", "x", "y"],
            rr=0.8,
            historical_edge={"historical_edge_score": 35, "historical_confidence": "LOW", "matched_profit_factor": 0.8, "matched_avg_r": -0.2},
            edge_confirmation={"edge_confirmation_score": 35, "edge_confirmation_level": "LOW"},
            trade_quality={"trade_quality_score": 40, "trade_quality_grade": "C", "quality_confidence": "LOW"},
        )
    )

    assert result["capital_preservation_mode"] is True


def test_aggressive_mode_activates_with_multiple_positive_layers() -> None:
    result = evaluate_meta_decision(positive_inputs())

    assert result["aggressive_mode"] is True
    assert result["meta_reasons"]

