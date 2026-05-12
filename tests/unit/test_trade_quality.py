from __future__ import annotations

from trading_signals.memory.trade_quality import classify_trade_quality


def strong_inputs(**overrides) -> dict[str, object]:
    data = {
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
            "matched_patterns_count": 35,
            "matched_winrate": 64,
            "matched_avg_r": 0.9,
            "matched_profit_factor": 2.1,
        },
        "adaptive_thresholds": {"adaptive_threshold": 34, "threshold_delta": -11},
        "edge_confirmation": {
            "edge_confirmation_score": 82,
            "edge_confirmation_level": "HIGH",
            "edge_bias": "POSITIVE",
        },
    }
    data.update(overrides)
    return data


def test_strong_context_generates_a_grade() -> None:
    result = classify_trade_quality(strong_inputs())

    assert result["trade_quality_grade"] in {"A", "A+"}
    assert result["trade_quality_score"] >= 75
    assert result["quality_bias"] == "POSITIVE"
    assert "HIGH_VOLATILITY" in result["quality_reasons"]
    assert "RR válido (2.0)" in result["quality_reasons"]


def test_bad_context_generates_trash_or_c() -> None:
    result = classify_trade_quality(
        strong_inputs(
            direction="SHORT",
            setup_type="SECONDARY_SIGNAL",
            market_regime="RANGING",
            entry_context="CHOPPY_RANGE",
            htf_trend="bullish",
            ltf_trend="bearish",
            warnings=["low_volume", "body_ratio_below_threshold", "dirty_sideways_market"],
            penalties=["against_htf", "distance_to_liquidity_penalty", "market_structure_range_penalty"],
            rr=1.0,
            historical_edge={
                "historical_edge_score": 25,
                "historical_confidence": "LOW",
                "matched_patterns_count": 4,
                "matched_winrate": 20,
                "matched_avg_r": -0.8,
                "matched_profit_factor": 0.5,
            },
            adaptive_thresholds={"adaptive_threshold": 66, "threshold_delta": 21},
            edge_confirmation={"edge_confirmation_score": 25, "edge_confirmation_level": "LOW"},
        )
    )

    assert result["trade_quality_grade"] in {"TRASH", "C"}
    assert result["quality_bias"] == "NEGATIVE"
    assert "CHOPPY_RANGE" in result["quality_risks"]
    assert "SECONDARY short" in result["quality_risks"]


def test_warnings_reduce_grade() -> None:
    base = strong_inputs(
        historical_edge={
            "historical_edge_score": 65,
            "historical_confidence": "MEDIUM",
            "matched_patterns_count": 14,
            "matched_winrate": 55,
            "matched_avg_r": 0.3,
            "matched_profit_factor": 1.4,
        },
        edge_confirmation={"edge_confirmation_score": 62, "edge_confirmation_level": "MEDIUM"},
        adaptive_thresholds={"adaptive_threshold": 42, "threshold_delta": -3},
    )
    clean = classify_trade_quality(base)
    warned = classify_trade_quality({**base, "warnings": ["low_volume", "body_ratio_below_threshold", "dirty_sideways_market"]})

    assert warned["trade_quality_score"] < clean["trade_quality_score"]
    assert "demasiados warnings" in warned["quality_risks"]


def test_positive_historical_edge_improves_quality() -> None:
    positive = classify_trade_quality(strong_inputs())
    neutral = classify_trade_quality(
        strong_inputs(
            historical_edge={
                "historical_edge_score": 50,
                "historical_confidence": "LOW",
                "matched_patterns_count": 5,
                "matched_winrate": 50,
                "matched_avg_r": 0,
                "matched_profit_factor": 1,
            },
            edge_confirmation={"edge_confirmation_score": 50, "edge_confirmation_level": "MEDIUM"},
        )
    )

    assert positive["trade_quality_score"] > neutral["trade_quality_score"]
    assert "historical edge HIGH" in positive["quality_reasons"]


def test_invalid_rr_penalizes_quality() -> None:
    base = strong_inputs(
        historical_edge={
            "historical_edge_score": 65,
            "historical_confidence": "MEDIUM",
            "matched_patterns_count": 14,
            "matched_winrate": 55,
            "matched_avg_r": 0.3,
            "matched_profit_factor": 1.4,
        },
        edge_confirmation={"edge_confirmation_score": 62, "edge_confirmation_level": "MEDIUM"},
        adaptive_thresholds={"adaptive_threshold": 42, "threshold_delta": -3},
    )
    result = classify_trade_quality({**base, "rr": 1.0})

    assert "RR inválido (1.0)" in result["quality_risks"]
    assert result["trade_quality_score"] < classify_trade_quality({**base, "rr": 2.0})["trade_quality_score"]
