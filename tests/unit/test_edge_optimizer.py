from __future__ import annotations

from trading_signals.intelligence.edge_optimizer import optimize_edge_context, optimizer_bias


def test_optimizer_positive_edge_caps_to_max_adjustment() -> None:
    result = optimize_edge_context(
        {"direction": "short", "session": "LONDON"},
        current_score=80,
        knowledge=_knowledge([_edge("positive", {"direction": "short", "session": "LONDON"}, 30, "HIGH", 100)]),
    )

    assert result["optimizer_adjustment"] == 15
    assert result["hypothetical_score"] == 95
    assert result["hypothetical_bias"] == "STRONG_PRIORITIZE"
    assert len(result["matched_positive_edges"]) == 1
    assert result["matched_negative_edges"] == []


def test_optimizer_negative_edge_caps_to_max_adjustment() -> None:
    result = optimize_edge_context(
        {"direction": "long", "entry_context": "BREAKOUT"},
        current_score=80,
        knowledge=_knowledge([_edge("negative", {"direction": "long", "entry_context": "BREAKOUT"}, -30, "HIGH", 100)]),
    )

    assert result["optimizer_adjustment"] == -15
    assert result["hypothetical_score"] == 65
    assert result["hypothetical_bias"] == "STRONG_AVOID"
    assert len(result["matched_negative_edges"]) == 1


def test_low_confidence_limits_adjustment_to_three() -> None:
    result = optimize_edge_context(
        {"trade_location": "premium_zone"},
        current_score=70,
        knowledge=_knowledge([_edge("low", {"trade_location": "premium_zone"}, 20, "LOW", 100)]),
    )

    assert result["optimizer_adjustment"] == 3
    assert "low_confidence_cap" in result["caps_applied"]
    assert result["hypothetical_bias"] == "NEUTRAL"


def test_low_sample_limits_adjustment_to_five() -> None:
    result = optimize_edge_context(
        {"symbol": "SOLUSDT", "direction": "long"},
        current_score=70,
        knowledge=_knowledge([_edge("sample", {"symbol": "SOLUSDT", "direction": "long"}, 20, "HIGH", 12)]),
    )

    assert result["optimizer_adjustment"] == 5
    assert "low_sample_cap" in result["caps_applied"]
    assert result["hypothetical_bias"] == "PRIORITIZE"


def test_conflicting_positive_and_negative_edges_reduce_adjustment() -> None:
    result = optimize_edge_context(
        {"direction": "long", "session": "LONDON", "entry_context": "BREAKOUT"},
        current_score=80,
        knowledge=_knowledge(
            [
                _edge("positive", {"direction": "long", "session": "LONDON"}, 12, "HIGH", 100),
                _edge("negative", {"direction": "long", "entry_context": "BREAKOUT"}, -10, "HIGH", 100),
            ]
        ),
    )

    assert result["conflict_reduced"] is True
    assert abs(result["optimizer_adjustment"]) < 5
    assert result["hypothetical_bias"] == "NEUTRAL"


def test_optimizer_bias_thresholds() -> None:
    assert optimizer_bias(10) == "STRONG_PRIORITIZE"
    assert optimizer_bias(5) == "PRIORITIZE"
    assert optimizer_bias(0) == "NEUTRAL"
    assert optimizer_bias(-5) == "CAUTION"
    assert optimizer_bias(-10) == "STRONG_AVOID"


def _knowledge(edges: list[dict[str, object]]) -> dict[str, object]:
    return {"edges": edges}


def _edge(
    unique_id: str,
    context: dict[str, str],
    weight: float,
    confidence: str,
    evidence_count: int,
) -> dict[str, object]:
    return {
        "unique_id": unique_id,
        "category": "priority_edges" if weight > 0 else "avoid_edges",
        "context": context,
        "statistical_weight": weight,
        "confidence": confidence,
        "evidence_count": evidence_count,
        "metrics": {"profit_factor": 2.0 if weight > 0 else 0.5},
    }
