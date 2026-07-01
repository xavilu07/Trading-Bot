from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from trading_signals.application.use_cases.edge_knowledge_shadow_v1 import (
    build_edge_knowledge_context,
    evaluate_edge_knowledge_shadow_v1,
)
from trading_signals.domain.entities.risk_plan import RiskPlan
from trading_signals.domain.entities.strategy_evaluation import StrategyEvaluation


def test_context_builder_includes_expected_fields() -> None:
    context = build_edge_knowledge_context(
        symbol="BTCUSDT",
        analysis=_analysis(),
        evaluation=_evaluation(score=92),
        risk_plan=_risk_plan(),
        setup_context=_setup_context(),
        setup_type="SECONDARY_SIGNAL",
        direction="long",
        now=datetime(2026, 6, 1, 11, tzinfo=UTC),
    )

    assert context["symbol"] == "BTCUSDT"
    assert context["direction"] == "long"
    assert context["setup_type"] == "SECONDARY_SIGNAL"
    assert context["market_regime"] == "HIGH_VOLATILITY"
    assert context["session"] == "LONDON"
    assert context["entry_context"] == "BREAKOUT"
    assert context["trade_location"] == "near_resistance"
    assert context["score_bucket"] == "90-100"
    assert context["score_exact"] == "92"
    assert context["trend_1h"] == "bullish"
    assert context["trend_4h"] == "bullish"
    assert context["liquidity_sweep"] == "bearish_sweep"
    assert context["break_of_structure"] == "bullish_bos"
    assert context["rr_valid"] == "true"
    assert context["late_entry_from_bos"] == "false"
    assert context["opened_hour_utc"] == "11"
    assert context["opened_weekday"] == "monday"
    assert context["volume_ratio_bucket"] == "1.5-2.0"
    assert context["rsi_bucket"] == "60-70"
    assert context["nearest_distance_to_liquidity_atr_bucket"] == "0.5-1"
    assert context["directional_distance_to_liquidity_atr_bucket"] == "1-2"


def test_shadow_evaluation_does_not_change_decision_or_score() -> None:
    evaluation = _evaluation(score=91, decision="long")
    original_decision = evaluation.decision
    original_score = evaluation.setup_score

    result = evaluate_edge_knowledge_shadow_v1(
        symbol="BTCUSDT",
        analysis=_analysis(),
        evaluation=evaluation,
        risk_plan=_risk_plan(),
        setup_context=_setup_context(),
        signal_decision=SimpleNamespace(decision="SEND"),
        setup_type="SECONDARY_SIGNAL",
        direction="long",
        knowledge={"edges": []},
    )

    assert evaluation.decision == original_decision
    assert evaluation.setup_score == original_score
    assert result.current_decision == "SEND"
    assert result.current_score == original_score
    assert result.hypothetical_score == original_score
    assert result.shadow_only is True


def test_positive_bonus_generates_prioritize_bias() -> None:
    result = evaluate_edge_knowledge_shadow_v1(
        symbol="BTCUSDT",
        analysis=_analysis(),
        evaluation=_evaluation(score=82),
        risk_plan=_risk_plan(),
        setup_context=_setup_context(),
        signal_decision=SimpleNamespace(decision="REJECT"),
        setup_type="SECONDARY_SIGNAL",
        direction="long",
        knowledge=_knowledge(weight=20),
    )

    assert result.ekb_bonus >= 8
    assert result.hypothetical_bias == "PRIORITIZE"
    assert result.matched_edges_count == 1


def test_negative_bonus_generates_avoid_bias() -> None:
    result = evaluate_edge_knowledge_shadow_v1(
        symbol="BTCUSDT",
        analysis=_analysis(),
        evaluation=_evaluation(score=82),
        risk_plan=_risk_plan(),
        setup_context=_setup_context(),
        signal_decision=SimpleNamespace(decision="SEND"),
        setup_type="SECONDARY_SIGNAL",
        direction="long",
        knowledge=_knowledge(weight=-20),
    )

    assert result.ekb_bonus <= -8
    assert result.hypothetical_bias == "AVOID"
    assert result.matched_edges_count == 1


def _analysis():
    entry = SimpleNamespace(
        trend="bullish",
        liquidity_sweep="bearish_sweep",
        market_structure="bullish",
        distance_to_liquidity_atr=1.4,
        metadata={
            "break_of_structure": "bullish_bos",
            "volume_ratio_vs_average_20": 1.7,
            "rsi": 62,
            "nearest_distance_to_liquidity_atr": 0.8,
        },
    )
    higher = SimpleNamespace(trend="bullish")
    return SimpleNamespace(entry_snapshot=entry, higher_snapshot=higher)


def _setup_context() -> dict[str, object]:
    return {
        "market_regime": "HIGH_VOLATILITY",
        "session": "LONDON",
        "entry_context": "BREAKOUT",
        "trade_location": "near_resistance",
        "liquidity_sweep": "bearish_sweep",
        "rr_valid": True,
        "late_entry_from_bos": False,
    }


def _evaluation(*, score: float = 90, decision: str = "long") -> StrategyEvaluation:
    return StrategyEvaluation(
        id="eval_1",
        scan_run_id="scan_1",
        strategy_id="strategy",
        strategy_version="v1",
        symbol="BTCUSDT",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id="entry_1",
        higher_snapshot_id="higher_1",
        decision=decision,
        decision_trace=[],
        rejection_reasons=[],
        passed_filters=[],
        failed_filters=[],
        setup_score=score,
        confidence=0.8,
        created_at="2026-06-01T00:00:00+00:00",
    )


def _risk_plan() -> RiskPlan:
    return RiskPlan(
        id="risk_1",
        evaluation_id="eval_1",
        entry=100.0,
        stop_loss=99.0,
        take_profit=102.0,
        risk_reward=2.0,
        risk_amount=1.0,
        position_size=1.0,
        sl_method="test",
        tp_method="test",
        created_at="2026-06-01T00:00:00+00:00",
    )


def _knowledge(*, weight: float) -> dict[str, object]:
    return {
        "edges": [
            {
                "unique_id": "edge_test",
                "category": "priority_edges" if weight > 0 else "avoid_edges",
                "context": {"direction": "long", "session": "LONDON"},
                "statistical_weight": weight,
                "confidence": "HIGH",
                "evidence_count": 100,
                "metrics": {"profit_factor": 2.0 if weight > 0 else 0.5},
            }
        ]
    }
