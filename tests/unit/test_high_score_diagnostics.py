from __future__ import annotations

from trading_signals.application.dto.analysis_result import AnalysisResult
from trading_signals.application.use_cases.run_market_scan import _high_score_rejected_payload
from trading_signals.domain.entities.risk_plan import RiskPlan
from trading_signals.domain.entities.strategy_evaluation import StrategyEvaluation
from trading_signals.domain.entities.trade_signal import TradeSignal
from tests.unit.test_strategy_and_risk import build_snapshot


def test_high_score_rejected_payload_explains_directional_confluence_block() -> None:
    entry = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=100.0,
        distance=1.0,
        break_of_structure="none",
    )
    higher = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="4h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=80.0,
        distance=1.0,
    )
    analysis = AnalysisResult("BTCUSDT", "1h", "4h", entry, higher)
    evaluation = StrategyEvaluation(
        id="eval_test",
        scan_run_id="run_test",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="BTCUSDT",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id=entry.id,
        higher_snapshot_id=higher.id,
        decision="no_trade",
        decision_trace=[
            "final_setup_score=100.0",
            "penalties=timeframe_alignment_penalty:10,distance_to_liquidity_penalty:10",
            "setup_type=NO_SIGNAL",
        ],
        rejection_reasons=["secondary_setup_requirements_failed", "directional_confluence_failed"],
        passed_filters=["quality_score"],
        failed_filters=["secondary_setup_requirements_failed", "directional_confluence_failed"],
        setup_score=100.0,
        confidence=0.95,
        created_at=entry.created_at,
    )
    signal = TradeSignal(
        id="sig_test",
        scan_run_id="run_test",
        evaluation_id="eval_test",
        risk_plan_id="risk_test",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="BTCUSDT",
        decision="no_trade",
        status="rejected",
        dedupe_key="dedupe",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id=entry.id,
        higher_snapshot_id=higher.id,
        created_at=entry.created_at,
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
        created_at=entry.created_at,
    )

    payload = _high_score_rejected_payload(
        symbol="BTCUSDT",
        analysis=analysis,
        evaluation=evaluation,
        signal=signal,
        status="rejected",
        should_publish_decision=False,
        is_duplicate=False,
        setup_context={"avoidance_warnings": ["entrada contra HTF"]},
        risk_plan=risk_plan,
        publish_filter_reason=None,
        lifecycle=None,
    )

    assert payload is not None
    assert payload["symbol"] == "BTCUSDT"
    assert payload["score"] == 100.0
    assert payload["final_decision"] == "not_send"
    assert payload["directional_confluence_status"] == "failed"
    assert payload["htf_trend"] == "bullish"
    assert payload["ltf_trend"] == "bullish"
    assert payload["timeframe_alignment"] is True
    assert payload["warnings"] == ["entrada contra HTF"]
    assert payload["penalties"] == ["timeframe_alignment_penalty:10", "distance_to_liquidity_penalty:10"]
    assert payload["rr"] == 2.0
    assert payload["entry"] == 100.0
    assert payload["stop_loss"] == 95.0
    assert payload["take_profit"] == 110.0
    assert "directional_confluence_failed" in payload["blocking_reasons"]
