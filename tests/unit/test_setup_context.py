from __future__ import annotations

from trading_signals.application.use_cases.setup_context import build_setup_context, detect_session
from trading_signals.domain.entities.risk_plan import RiskPlan
from tests.unit.test_strategy_and_risk import build_snapshot


def test_setup_context_tags_objective_market_and_entry_context() -> None:
    snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=70.0,
        distance=6.0,
        rsi=72.0,
        volume_ratio=0.5,
        break_of_structure="bullish_bos",
    )
    snapshot.timestamp = "2026-01-01T14:00:00+00:00"
    snapshot.metadata["recent_close_high_before_bos"] = 99.0
    risk_plan = RiskPlan(
        id="risk_test",
        evaluation_id="eval_test",
        entry=101.0,
        stop_loss=99.0,
        take_profit=105.0,
        risk_reward=2.0,
        risk_amount=10.0,
        position_size=5.0,
        sl_method="test",
        tp_method="test",
        created_at="2026-01-01T14:00:00+00:00",
    )

    context = build_setup_context(
        snapshot=snapshot,
        higher_trend="bearish",
        risk_plan=risk_plan,
        direction="long",
        max_distance_to_liquidity_atr=2.5,
        atr_min_threshold=0.002,
        max_spread_atr=1.8,
    )

    assert context.market_regime == "HIGH_VOLATILITY"
    assert context.session == "OVERLAP"
    assert context.entry_context == "BREAKOUT"
    assert context.rr_valid is True
    assert context.sl_distance_atr == 2.0
    assert context.tp_distance_atr == 4.0
    assert context.late_entry_from_bos is True
    assert "low_volume" in context.avoidance_warnings
    assert "against_htf" in context.avoidance_warnings
    assert "price_far_from_liquidity" in context.avoidance_warnings


def test_session_classification() -> None:
    assert detect_session("2026-01-01T02:00:00+00:00") == "ASIA"
    assert detect_session("2026-01-01T08:00:00+00:00") == "LONDON"
    assert detect_session("2026-01-01T14:00:00+00:00") == "OVERLAP"
    assert detect_session("2026-01-01T18:00:00+00:00") == "NEW_YORK"
