from __future__ import annotations

from trading_signals.memory.adaptive_thresholds import calculate_adaptive_thresholds


def base_inputs(**overrides) -> dict[str, object]:
    data = {
        "historical_edge_score": 50,
        "historical_confidence": "LOW",
        "matched_winrate": 50,
        "matched_avg_r": 0.0,
        "matched_profit_factor": 1.0,
        "matched_patterns_count": 0,
        "direction": "LONG",
        "setup_type": "MAIN_SIGNAL",
        "market_regime": "TRENDING",
        "session": "LONDON",
        "entry_context": "BREAKOUT",
        "trade_location": "near_support",
        "warnings": [],
        "penalties": [],
    }
    data.update(overrides)
    return data


def test_positive_edge_reduces_threshold() -> None:
    result = calculate_adaptive_thresholds(
        base_inputs(
            historical_edge_score=82,
            historical_confidence="MEDIUM",
            matched_winrate=65,
            matched_avg_r=0.8,
            matched_profit_factor=2.0,
            matched_patterns_count=12,
            market_regime="HIGH_VOLATILITY",
            entry_context="BREAKOUT",
        )
    )

    assert result["adaptive_threshold"] < result["base_threshold"]
    assert result["adaptive_bias"] == "BULLISH"
    assert any("reduce threshold" in reason for reason in result["adaptive_reasoning"])


def test_negative_edge_increases_threshold() -> None:
    result = calculate_adaptive_thresholds(
        base_inputs(
            historical_edge_score=25,
            historical_confidence="MEDIUM",
            matched_winrate=25,
            matched_avg_r=-0.7,
            matched_profit_factor=0.5,
            matched_patterns_count=12,
            market_regime="RANGING",
            entry_context="CHOPPY_RANGE",
            warnings=["a", "b", "c"],
        )
    )

    assert result["adaptive_threshold"] > result["base_threshold"]
    assert result["adaptive_bias"] == "NEUTRAL"
    assert any("aumenta threshold" in reason for reason in result["adaptive_reasoning"])


def test_threshold_limits_min_and_max_work() -> None:
    low = calculate_adaptive_thresholds(
        base_inputs(
            historical_edge_score=95,
            historical_confidence="HIGH",
            matched_winrate=90,
            matched_avg_r=3.0,
            matched_profit_factor=5.0,
            matched_patterns_count=40,
            market_regime="HIGH_VOLATILITY",
            entry_context="IMPULSE",
        )
    )
    high = calculate_adaptive_thresholds(
        base_inputs(
            historical_edge_score=5,
            historical_confidence="HIGH",
            matched_winrate=5,
            matched_avg_r=-3.0,
            matched_profit_factor=0.1,
            matched_patterns_count=40,
            market_regime="RANGING",
            entry_context="CHOPPY_RANGE",
            warnings=["a", "b", "c", "d"],
        )
    )

    assert low["adaptive_threshold"] == 30
    assert high["adaptive_threshold"] == 70


def test_high_confidence_affects_more_than_low_confidence() -> None:
    low = calculate_adaptive_thresholds(
        base_inputs(
            historical_edge_score=80,
            historical_confidence="LOW",
            matched_winrate=70,
            matched_avg_r=1.0,
            matched_profit_factor=2.0,
            matched_patterns_count=8,
        )
    )
    high = calculate_adaptive_thresholds(
        base_inputs(
            historical_edge_score=80,
            historical_confidence="HIGH",
            matched_winrate=70,
            matched_avg_r=1.0,
            matched_profit_factor=2.0,
            matched_patterns_count=35,
        )
    )

    assert abs(int(high["threshold_delta"])) > abs(int(low["threshold_delta"]))


def test_without_history_keeps_low_confidence_and_safe_output() -> None:
    result = calculate_adaptive_thresholds(base_inputs(matched_patterns_count=0))

    assert result["adaptive_confidence"] == "LOW"
    assert 30 <= int(result["adaptive_threshold"]) <= 70
    assert "sin historial suficiente" in result["adaptive_reasoning"][0]

