from __future__ import annotations

from trading_signals.application.use_cases.performance_gate import evaluate_performance_gate


def performance_intelligence(**overrides) -> dict[str, object]:
    data = {
        "meta_decision": {
            "meta_decision_score": 72,
            "meta_decision": "SEND",
            "meta_confidence": "MEDIUM",
            "capital_preservation_mode": False,
            "aggressive_mode": False,
        },
        "trade_quality": {
            "trade_quality_score": 66,
            "trade_quality_grade": "B",
            "quality_confidence": "MEDIUM",
        },
        "historical_edge": {
            "historical_edge_score": 58,
            "historical_confidence": "MEDIUM",
            "matched_patterns_count": 12,
            "matched_profit_factor": 1.2,
            "matched_avg_r": 0.1,
        },
    }
    for key, value in overrides.items():
        data[key] = {**data[key], **value}
    return data


def test_performance_gate_prioritize_for_strong_aligned_layers() -> None:
    result = evaluate_performance_gate(
        performance_intelligence(
            meta_decision={"meta_decision": "STRONG_SEND", "meta_decision_score": 90, "aggressive_mode": True},
            trade_quality={"trade_quality_grade": "A+", "trade_quality_score": 92, "quality_confidence": "HIGH"},
            historical_edge={"historical_edge_score": 78, "historical_confidence": "HIGH", "matched_profit_factor": 2.0},
        )
    )

    assert result["mode"] == "SOFT"
    assert result["action"] == "PRIORITIZE"
    assert result["would_prioritize"] is True
    assert result["would_block"] is False
    assert "historical edge strong" in result["reasons"]


def test_performance_gate_allow_for_neutral_acceptable_layers() -> None:
    result = evaluate_performance_gate(performance_intelligence())

    assert result["action"] == "ALLOW"
    assert result["would_prioritize"] is False
    assert result["would_block"] is False
    assert result["risks"] == []


def test_performance_gate_caution_for_low_confidence_or_weak_context() -> None:
    result = evaluate_performance_gate(
        performance_intelligence(
            meta_decision={"meta_decision": "NEUTRAL", "meta_confidence": "LOW"},
            trade_quality={"trade_quality_grade": "C", "quality_confidence": "LOW"},
            historical_edge={"historical_edge_score": 50, "historical_confidence": "LOW", "matched_patterns_count": 3},
        )
    )

    assert result["action"] == "CAUTION"
    assert result["would_prioritize"] is False
    assert result["would_block"] is False
    assert "low confidence performance context" in result["risks"]


def test_performance_gate_would_block_only_soft_for_confident_negative_layers() -> None:
    result = evaluate_performance_gate(
        performance_intelligence(
            meta_decision={
                "meta_decision": "REJECT",
                "meta_decision_score": 24,
                "meta_confidence": "HIGH",
                "capital_preservation_mode": True,
            },
            trade_quality={"trade_quality_grade": "TRASH", "trade_quality_score": 20, "quality_confidence": "HIGH"},
            historical_edge={
                "historical_edge_score": 25,
                "historical_confidence": "MEDIUM",
                "matched_profit_factor": 0.6,
                "matched_avg_r": -0.4,
            },
        )
    )

    assert result["mode"] == "SOFT"
    assert result["action"] == "WOULD_BLOCK"
    assert result["would_block"] is True
    assert result["would_prioritize"] is False
    assert "capital preservation mode active" in result["risks"]
