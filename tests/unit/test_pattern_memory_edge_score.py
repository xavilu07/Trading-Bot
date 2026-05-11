from __future__ import annotations

from trading_signals.memory.edge_score import calculate_historical_edge_score


def candidate() -> dict[str, object]:
    return {
        "direction": "long",
        "setup_type": "MAIN_SIGNAL",
        "market_regime": "TRENDING",
        "session": "LONDON",
        "entry_context": "BREAKOUT",
        "trade_location": "near_support",
        "liquidity_sweep": "yes",
        "market_structure": "bullish",
        "warnings": ["low_volume"],
        "penalties": ["distance_to_liquidity_penalty"],
    }


def history_row(r_result: float, outcome: str = "win") -> dict[str, object]:
    row = candidate()
    row.update({"r_result": r_result, "outcome": outcome})
    return row


def test_historical_edge_without_history_returns_low_neutral_score() -> None:
    result = calculate_historical_edge_score(candidate(), [])

    assert result["historical_edge_score"] == 50
    assert result["historical_confidence"] == "LOW"
    assert result["matched_patterns_count"] == 0
    assert "historial_insuficiente" in result["negative_edge_reasons"]


def test_positive_history_increases_score() -> None:
    history = [history_row(1.5) for _ in range(12)]

    result = calculate_historical_edge_score(candidate(), history)

    assert result["historical_edge_score"] > 50
    assert result["historical_confidence"] == "MEDIUM"
    assert result["matched_patterns_count"] == 12
    assert result["matched_winrate"] == 100.0
    assert result["matched_avg_r"] == 1.5
    assert result["positive_edge_reasons"]


def test_negative_history_lowers_score() -> None:
    history = [history_row(-1.0, outcome="loss") for _ in range(12)]

    result = calculate_historical_edge_score(candidate(), history)

    assert result["historical_edge_score"] < 50
    assert result["historical_confidence"] == "MEDIUM"
    assert result["matched_winrate"] == 0.0
    assert result["matched_avg_r"] == -1.0
    assert result["negative_edge_reasons"]


def test_few_matches_are_low_confidence() -> None:
    result = calculate_historical_edge_score(candidate(), [history_row(1.0) for _ in range(9)])

    assert result["matched_patterns_count"] == 9
    assert result["historical_confidence"] == "LOW"


def test_many_matches_are_high_confidence() -> None:
    result = calculate_historical_edge_score(candidate(), [history_row(0.5) for _ in range(30)])

    assert result["matched_patterns_count"] == 30
    assert result["historical_confidence"] == "HIGH"


def test_dissimilar_history_is_not_matched() -> None:
    row = history_row(2.0)
    row.update(
        {
            "direction": "short",
            "setup_type": "SECONDARY_SIGNAL",
            "market_regime": "RANGING",
            "session": "ASIA",
            "entry_context": "CHOPPY_RANGE",
            "trade_location": "premium_zone",
        }
    )

    result = calculate_historical_edge_score(candidate(), [row])

    assert result["matched_patterns_count"] == 0
    assert result["historical_edge_score"] == 50

