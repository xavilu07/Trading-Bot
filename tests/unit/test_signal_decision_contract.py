from __future__ import annotations

from trading_signals.domain.entities.risk_plan import RiskPlan
from trading_signals.domain.entities.signal_decision import SignalDecision
from trading_signals.domain.entities.strategy_evaluation import StrategyEvaluation
from trading_signals.strategy.decision_engine import (
    build_signal_decision_from_modules,
    build_signal_decision_from_strategy_evaluation,
)
from trading_signals.strategy.signal_decision_adapter import (
    signal_decision_from_modules,
    signal_decision_from_strategy_evaluation,
)


def test_signal_decision_contract_serializes_and_exposes_state_helpers() -> None:
    decision = SignalDecision(
        symbol="BTCUSDT",
        direction="long",
        decision="SEND",
        setup_type="SECONDARY_SIGNAL",
        entry_price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        total_score=82.5,
        module_scores={"trend": 100.0},
        rejection_reasons=[],
        warnings=["against_htf"],
        source_engine="parallel_decision_engine",
    )

    assert decision.is_send is True
    assert decision.is_rejected is False
    assert decision.is_paper_only is False
    assert decision.to_dict()["symbol"] == "BTCUSDT"
    assert decision.to_dict()["module_scores"] == {"trend": 100.0}


def test_build_signal_decision_from_modules() -> None:
    module_results = {
        "trend": {"ok": True, "score": 100.0, "reason": "trend_aligned", "details": {}},
        "signal_builder": {
            "ok": True,
            "score": 80.0,
            "reason": "signal_candidate_ready",
            "details": {"direction": "short", "setup_type": "MAIN_SIGNAL"},
        },
        "decision_engine": {
            "ok": True,
            "score": 90.0,
            "reason": "parallel_decision_diagnostic",
            "details": {
                "total_score": 90.0,
                "final_direction": "short",
                "decision": "SEND",
                "rejection_reasons": [],
            },
        },
    }
    contract = build_signal_decision_from_modules(
        symbol="ETHUSDT",
        entry_price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        module_results=module_results,
    )
    direct_contract = signal_decision_from_modules(
        symbol="ETHUSDT",
        entry_price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        module_results=module_results,
    )

    assert contract.symbol == "ETHUSDT"
    assert contract.direction == "short"
    assert contract.decision == "SEND"
    assert contract.setup_type == "MAIN_SIGNAL"
    assert contract.total_score == 90.0
    assert contract.module_scores == {"trend": 100.0, "signal_builder": 80.0}
    assert contract.source_engine == "parallel_decision_engine"
    assert contract.to_dict() == direct_contract.to_dict()


def test_build_signal_decision_from_strategy_evaluation() -> None:
    evaluation = StrategyEvaluation(
        id="eval_test",
        scan_run_id="run_test",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="TAOUSDT",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id="snap_1h",
        higher_snapshot_id="snap_4h",
        decision="long",
        decision_trace=[],
        rejection_reasons=[],
        passed_filters=["secondary_setup"],
        failed_filters=[],
        setup_score=90.0,
        confidence=0.9,
        created_at="2026-01-01T00:00:00+00:00",
    )
    risk_plan = RiskPlan(
        id="risk_test",
        evaluation_id="eval_test",
        entry=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        risk_reward=2.0,
        risk_amount=10.0,
        position_size=2.0,
        sl_method="test",
        tp_method="test",
        created_at="2026-01-01T00:00:00+00:00",
    )

    contract = build_signal_decision_from_strategy_evaluation(
        evaluation=evaluation,
        risk_plan=risk_plan,
        setup_type="SECONDARY_SIGNAL",
        warnings=["high_spread"],
    )
    direct_contract = signal_decision_from_strategy_evaluation(
        evaluation=evaluation,
        risk_plan=risk_plan,
        setup_type="SECONDARY_SIGNAL",
        warnings=["high_spread"],
    )

    assert contract.source_engine == "liquidity_sweep_mtf_v1"
    assert contract.decision == "SEND"
    assert contract.direction == "long"
    assert contract.entry_price == 100.0
    assert contract.warnings == ["high_spread"]
    assert contract.to_dict() == direct_contract.to_dict()
