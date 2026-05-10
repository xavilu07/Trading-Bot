from __future__ import annotations

from trading_signals.memory.insights import build_pattern_memory_insights


def record(
    *,
    direction: str = "long",
    entry_context: str = "BREAKOUT",
    market_regime: str = "TRENDING",
    trade_location: str = "near_support",
    outcome: str = "win",
    r_result: float = 1.0,
    warning: str = "low_volume",
    penalty: str = "distance_to_liquidity_penalty",
    block: str = "directional_confluence_failed",
) -> dict[str, object]:
    return {
        "direction": direction,
        "setup_type": "MAIN_SIGNAL",
        "market_regime": market_regime,
        "session": "LONDON",
        "entry_context": entry_context,
        "trade_location": trade_location,
        "htf_trend": "bullish" if direction == "long" else "bearish",
        "ltf_trend": "bullish" if direction == "long" else "bearish",
        "warnings": [warning],
        "penalties": [penalty],
        "blocking_reasons": [block],
        "outcome": outcome,
        "r_result": r_result,
    }


def test_pattern_memory_insights_detects_positive_pattern() -> None:
    records = [record(outcome="win", r_result=1.2) for _ in range(4)] + [record(outcome="loss", r_result=-0.5)]

    insights = build_pattern_memory_insights(records)

    assert insights["has_sufficient_data"] is True
    assert insights["positive_patterns"]
    assert insights["positive_patterns"][0]["cases"] == 5
    assert insights["positive_patterns"][0]["historical_winrate"] == 80.0
    assert insights["positive_patterns"][0]["historical_avg_r"] > 0


def test_pattern_memory_insights_detects_negative_pattern() -> None:
    records = [
        record(direction="short", trade_location="near_resistance", outcome="loss", r_result=-1.0)
        for _ in range(4)
    ] + [record(direction="short", trade_location="near_resistance", outcome="win", r_result=0.5)]

    insights = build_pattern_memory_insights(records)

    assert insights["has_sufficient_data"] is True
    assert insights["negative_patterns"]
    assert insights["negative_patterns"][0]["cases"] == 5
    assert insights["negative_patterns"][0]["historical_winrate"] == 20.0
    assert insights["negative_patterns"][0]["historical_avg_r"] < 0


def test_pattern_memory_insights_reports_insufficient_memory() -> None:
    records = [record(outcome="win", r_result=1.0) for _ in range(4)]

    insights = build_pattern_memory_insights(records)

    assert insights == {
        "positive_patterns": [],
        "negative_patterns": [],
        "has_sufficient_data": False,
    }


def test_pattern_memory_insights_limits_results() -> None:
    records = []
    for idx in range(5):
        records.extend(
            record(entry_context=f"BREAKOUT_{idx}", warning=f"warning_{idx}", outcome="win", r_result=1.0)
            for _ in range(5)
        )

    insights = build_pattern_memory_insights(records, limit=3)

    assert len(insights["positive_patterns"]) == 3
