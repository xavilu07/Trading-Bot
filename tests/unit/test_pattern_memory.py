from __future__ import annotations

from trading_signals.memory.pattern_memory import build_pattern_record, evaluate_pattern_memory
from trading_signals.memory.pattern_store import PatternMemoryStore
from trading_signals.memory.similarity import compare_with_history, confidence_level


def test_pattern_store_appends_jsonl_records(tmp_path) -> None:
    store = PatternMemoryStore(tmp_path)
    record = {"symbol": "BTCUSDT", "direction": "long", "score": 90}

    store.append(record)

    assert store.list_records() == [record]
    assert (tmp_path / "pattern_memory" / "patterns.jsonl").exists()


def test_similarity_finds_similar_patterns_and_stats() -> None:
    candidate = {
        "direction": "long",
        "setup_type": "MAIN_SIGNAL",
        "market_regime": "TRENDING",
        "entry_context": "BREAKOUT",
        "trade_location": "near_support",
        "htf_trend": "bullish",
        "ltf_trend": "bullish",
        "warnings": ["low_volume"],
        "penalties": ["distance_to_liquidity_penalty:10"],
    }
    history = [
        {
            **candidate,
            "symbol": "ETHUSDT",
            "outcome": "win",
            "r_result": 2.0,
        },
        {
            **candidate,
            "symbol": "SOLUSDT",
            "outcome": "loss",
            "r_result": -1.0,
        },
        {
            **candidate,
            "symbol": "XRPUSDT",
            "outcome": "open",
            "r_result": None,
        },
        {
            **candidate,
            "direction": "short",
            "symbol": "ADAUSDT",
            "outcome": "win",
            "r_result": 2.0,
        },
    ]

    result = compare_with_history(candidate, history)

    assert result["similar_count"] == 3
    assert result["historical_winrate"] == 50.0
    assert result["historical_avg_r"] == 0.5
    assert result["repeated_warnings"] == ["low_volume"]
    assert result["repeated_penalties"] == ["distance_to_liquidity_penalty:10"]
    assert result["confidence_level"] == "LOW"


def test_confidence_level_thresholds() -> None:
    assert confidence_level(4) == "LOW"
    assert confidence_level(5) == "MEDIUM"
    assert confidence_level(15) == "MEDIUM"
    assert confidence_level(16) == "HIGH"


def test_build_and_evaluate_pattern_record() -> None:
    risk_plan = type("RiskPlan", (), {"entry": 100.0, "stop_loss": 95.0, "take_profit": 110.0, "risk_reward": 2.0})()
    setup_context = {
        "market_regime": "TRENDING",
        "session": "LONDON",
        "entry_context": "BREAKOUT",
        "trade_location": "near_support",
        "avoidance_warnings": ["low_volume"],
    }
    record = build_pattern_record(
        timestamp="2026-01-01T00:00:00+00:00",
        symbol="BTCUSDT",
        direction="long",
        setup_type="MAIN_SIGNAL",
        score=90.0,
        setup_context=setup_context,
        htf_trend="bullish",
        ltf_trend="bullish",
        timeframe_alignment=True,
        penalties=["distance_to_liquidity_penalty:10"],
        blocking_reasons=[],
        risk_plan=risk_plan,
        final_status="sent_signal",
        outcome="open",
        r_result=None,
    )
    summary = evaluate_pattern_memory(record, [record, record, record])

    assert record["entry"] == 100.0
    assert record["rr"] == 2.0
    assert summary["similar_count"] == 3
    assert summary["has_sufficient_memory"] is True
