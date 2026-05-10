from __future__ import annotations

from trading_signals.app.settings import Settings
from trading_signals.domain.entities.risk_plan import RiskPlan
from trading_signals.domain.entities.signal_decision import SignalDecision
from trading_signals.domain.entities.strategy_evaluation import StrategyEvaluation
from trading_signals.strategy.decision_engine_selector import select_signal_decision


def evaluation() -> StrategyEvaluation:
    return StrategyEvaluation(
        id="eval_test",
        scan_run_id="run_test",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="BTCUSDT",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id="snap_1h",
        higher_snapshot_id="snap_4h",
        decision="long",
        decision_trace=["primary_sweep_setup"],
        rejection_reasons=[],
        passed_filters=["primary_sweep_setup"],
        failed_filters=[],
        setup_score=90.0,
        confidence=0.9,
        created_at="2026-01-01T00:00:00+00:00",
    )


def risk_plan() -> RiskPlan:
    return RiskPlan(
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


def test_selector_defaults_to_legacy_when_flag_false() -> None:
    selected = select_signal_decision(
        use_modular_decision_engine=False,
        symbol="BTCUSDT",
        evaluation=evaluation(),
        risk_plan=risk_plan(),
        setup_type="MAIN_SIGNAL",
        module_diagnostics={},
    )

    assert selected.selected_engine == "legacy"
    assert selected.signal_decision.source_engine == "liquidity_sweep_mtf_v1"
    assert selected.signal_decision.decision == "SEND"
    assert selected.signal_decision.total_score == 90.0


def test_selector_returns_signal_decision_for_modular_flag_true() -> None:
    selected = select_signal_decision(
        use_modular_decision_engine=True,
        symbol="BTCUSDT",
        evaluation=evaluation(),
        risk_plan=risk_plan(),
        setup_type="MAIN_SIGNAL",
        module_diagnostics={
            "trend": {
                "ok": True,
                "score": 90.0,
                "reason": "trend_aligned",
                "details": {"trend_entry": "bullish", "trend_higher": "bullish"},
            },
            "momentum": {
                "ok": True,
                "score": 85.0,
                "reason": "momentum_confirmed",
                "details": {"direction": "long"},
            },
            "liquidity": {
                "ok": True,
                "score": 85.0,
                "reason": "liquidity_distance_ok",
                "details": {},
            },
            "market_regime": {
                "ok": True,
                "score": 80.0,
                "reason": "market_regime_trending",
                "details": {},
            },
            "risk": {
                "ok": False,
                "score": 0.0,
                "reason": "risk_plan_missing",
                "details": {},
            },
            "telegram": {
                "ok": False,
                "score": 0.0,
                "reason": "telegram_not_configured",
                "details": {},
            },
            "signal_builder": {
                "ok": False,
                "score": 0.0,
                "reason": "signal_not_ready",
                "details": {},
            },
            "strategy_gate": {
                "ok": False,
                "score": 0.0,
                "reason": "strategy_gate_blocked",
                "details": {},
            },
        },
    )

    assert selected.selected_engine == "modular"
    assert isinstance(selected.signal_decision, SignalDecision)
    assert selected.signal_decision.source_engine == "modular_decision_engine"
    assert selected.signal_decision.decision == "SEND"
    assert selected.signal_decision.total_score == 85.0
    assert selected.signal_decision.direction == "long"
    assert selected.signal_decision.entry_price == 100.0
    assert selected.signal_decision.stop_loss == 95.0
    assert selected.signal_decision.take_profit == 110.0
    assert selected.signal_decision.module_scores == {
        "trend": 90.0,
        "momentum": 85.0,
        "liquidity": 85.0,
        "market_regime": 80.0,
    }
    assert "risk_plan_missing" not in selected.signal_decision.rejection_reasons
    assert "telegram_not_configured" not in selected.signal_decision.rejection_reasons
    assert "signal_not_ready" not in selected.signal_decision.rejection_reasons
    assert "strategy_gate_blocked" not in selected.signal_decision.rejection_reasons


def test_selector_uses_settings_modular_flag(monkeypatch) -> None:
    monkeypatch.setenv("USE_MODULAR_DECISION_ENGINE", "true")
    settings = Settings()

    selected = select_signal_decision(
        use_modular_decision_engine=settings.use_modular_decision_engine,
        symbol="BTCUSDT",
        evaluation=evaluation(),
        risk_plan=risk_plan(),
        setup_type="MAIN_SIGNAL",
        module_diagnostics={
            "trend": {
                "ok": True,
                "score": 70.0,
                "reason": "trend_aligned",
                "details": {"trend_entry": "bullish", "trend_higher": "bullish"},
            },
            "momentum": {
                "ok": True,
                "score": 70.0,
                "reason": "momentum_confirmed",
                "details": {"direction": "long"},
            },
            "liquidity": {
                "ok": False,
                "score": 60.0,
                "reason": "distance_to_liquidity_penalty",
                "details": {},
            },
            "market_regime": {
                "ok": True,
                "score": 70.0,
                "reason": "market_regime_trending",
                "details": {},
            },
        },
    )

    assert selected.selected_engine == "modular"
    assert selected.signal_decision.source_engine == "modular_decision_engine"
    assert selected.signal_decision.decision == "PAPER_ONLY"
