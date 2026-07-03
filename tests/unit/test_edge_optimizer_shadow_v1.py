from __future__ import annotations

from types import SimpleNamespace

from trading_signals.application.use_cases.edge_optimizer_shadow_v1 import evaluate_edge_optimizer_shadow_v1
from trading_signals.domain.entities.risk_plan import RiskPlan
from trading_signals.domain.entities.strategy_evaluation import StrategyEvaluation


def test_shadow_optimizer_uses_context_and_does_not_mutate_decision() -> None:
    evaluation = _evaluation(score=88, decision="long")
    result = evaluate_edge_optimizer_shadow_v1(
        symbol="SOLUSDT",
        analysis=_analysis(),
        evaluation=evaluation,
        risk_plan=_risk_plan(),
        setup_context=_setup_context(),
        signal_decision=SimpleNamespace(decision="REJECT"),
        setup_type="SECONDARY_SIGNAL",
        direction="long",
        knowledge={
            "edges": [
                {
                    "unique_id": "sol_long",
                    "category": "priority_edges",
                    "context": {"symbol": "SOLUSDT", "direction": "long"},
                    "statistical_weight": 12,
                    "confidence": "HIGH",
                    "evidence_count": 60,
                    "metrics": {"profit_factor": 1.5},
                }
            ]
        },
    )

    assert evaluation.decision == "long"
    assert evaluation.setup_score == 88
    assert result.current_decision == "REJECT"
    assert result.current_score == 88
    assert result.optimizer_adjustment > 0
    assert result.hypothetical_score > 88
    assert result.context["symbol"] == "SOLUSDT"
    assert result.context["score_bucket"] == "80-89"
    assert result.shadow_only is True


def test_shadow_optimizer_negative_edge_generates_caution_or_strong_avoid() -> None:
    result = evaluate_edge_optimizer_shadow_v1(
        symbol="XRPUSDT",
        analysis=_analysis(),
        evaluation=_evaluation(score=80, decision="long"),
        risk_plan=_risk_plan(),
        setup_context=_setup_context(),
        signal_decision=SimpleNamespace(decision="SEND"),
        setup_type="MAIN_SIGNAL",
        direction="long",
        knowledge={
            "edges": [
                {
                    "unique_id": "xrp_long",
                    "category": "avoid_edges",
                    "context": {"symbol": "XRPUSDT", "direction": "long"},
                    "statistical_weight": -12,
                    "confidence": "HIGH",
                    "evidence_count": 60,
                    "metrics": {"profit_factor": 0.5},
                }
            ]
        },
    )

    assert result.optimizer_adjustment < 0
    assert result.hypothetical_bias in {"CAUTION", "STRONG_AVOID"}
    assert len(result.matched_negative_edges) == 1


def _analysis():
    entry = SimpleNamespace(
        trend="bullish",
        liquidity_sweep="none",
        market_structure="bullish",
        distance_to_liquidity_atr=1.2,
        metadata={
            "break_of_structure": "bullish_bos",
            "volume_ratio_vs_average_20": 1.3,
            "rsi": 55,
            "nearest_distance_to_liquidity_atr": 0.9,
        },
    )
    higher = SimpleNamespace(trend="bullish")
    return SimpleNamespace(entry_snapshot=entry, higher_snapshot=higher)


def _setup_context() -> dict[str, object]:
    return {
        "market_regime": "HIGH_VOLATILITY",
        "session": "LONDON",
        "entry_context": "PULLBACK",
        "trade_location": "premium_zone",
        "liquidity_sweep": "none",
        "rr_valid": True,
        "late_entry_from_bos": False,
    }


def _evaluation(*, score: float, decision: str) -> StrategyEvaluation:
    return StrategyEvaluation(
        id="eval_1",
        scan_run_id="scan_1",
        strategy_id="strategy",
        strategy_version="v1",
        symbol="SOLUSDT",
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
