from __future__ import annotations

from trading_signals.application.use_cases.performance_intelligence import build_performance_intelligence


def test_build_performance_intelligence_returns_all_result_layers() -> None:
    pattern_record = {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "setup_type": "MAIN_SIGNAL",
        "score": 88,
        "market_regime": "HIGH_VOLATILITY",
        "session": "LONDON",
        "entry_context": "BREAKOUT",
        "trade_location": "near_support",
        "htf_trend": "bullish",
        "ltf_trend": "bullish",
        "timeframe_alignment": True,
        "warnings": [],
        "penalties": [],
        "blocking_reasons": [],
        "rr": 2.0,
        "outcome": "open",
        "r_result": None,
    }
    winning_history = [
        {
            **pattern_record,
            "symbol": f"ETH{i}USDT",
            "outcome": "win",
            "r_result": 1.5,
        }
        for i in range(12)
    ]

    result = build_performance_intelligence(
        pattern_record=pattern_record,
        pattern_history=winning_history,
    )

    assert result["has_sufficient_memory"] is True
    assert result["historical_edge"]["matched_patterns_count"] == 12
    assert result["adaptive_thresholds"]["adaptive_threshold"] < result["adaptive_thresholds"]["base_threshold"]
    assert result["edge_confirmation"]["edge_confirmation_level"] in {"MEDIUM", "HIGH"}
    assert result["trade_quality"]["trade_quality_grade"] in {"A", "A+"}
    assert result["meta_decision"]["meta_decision"] in {"SEND", "STRONG_SEND"}
    assert "insights" in result
