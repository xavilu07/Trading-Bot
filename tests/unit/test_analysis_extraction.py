from __future__ import annotations

from trading_signals.analysis.liquidity import detect_liquidity_sweep, get_liquidity_levels, liquidity_context
from trading_signals.analysis.market_regime import (
    detect_entry_context,
    detect_market_regime,
    detect_session,
    detect_trade_location,
)
from trading_signals.analysis.momentum import compute_rsi, volume_profile
from trading_signals.analysis.risk import (
    avoidance_warnings,
    calculate_risk_plan,
    distance_to_sl_atr,
    distance_to_tp_atr,
    late_entry_from_bos,
    rr_is_valid,
)
from trading_signals.analysis.trend import detect_break_of_structure, detect_trend, ema
from trading_signals.domain.entities.risk_plan import RiskPlan
from trading_signals.domain.services import liquidity_service, risk_service, trend_service
from tests.fixtures.market_data import generate_trend_dataset
from tests.unit.test_strategy_and_risk import build_snapshot


def test_trend_analysis_owns_trend_detection() -> None:
    dataset = generate_trend_dataset(direction="up")
    closes = [float(item["close"]) for item in dataset]

    trend, meta = detect_trend(closes)

    assert trend == "bullish"
    assert meta["ema20"] > meta["ema50"]


def test_trend_service_is_wrapper_for_analysis_trend() -> None:
    assert trend_service.detect_trend is detect_trend
    assert trend_service.ema is ema


def test_momentum_analysis_owns_rsi_and_volume_profile() -> None:
    closes = [100, 101, 102, 101, 103, 104, 105, 104, 106, 107, 108, 109, 110, 111, 112]
    volumes = [10.0] * 19 + [20.0]

    rsi = compute_rsi([float(item) for item in closes])
    profile = volume_profile(volumes)

    assert 0 <= rsi <= 100
    assert profile == {"current": 20.0, "average": 10.5, "ratio": 1.9047619047619047}


def test_trend_analysis_owns_break_of_structure_detection() -> None:
    dataset = generate_trend_dataset(direction="up")
    recent_high = max(float(item["high"]) for item in dataset[-9:-1])
    recent_close_high = max(float(item["close"]) for item in dataset[-9:-1])
    previous_twenty_high = max(float(item["high"]) for item in dataset[-21:-1])
    dataset[-1]["open"] = recent_close_high + 0.05
    dataset[-1]["close"] = recent_close_high + 0.2
    dataset[-1]["high"] = recent_high + 0.2

    assert float(dataset[-1]["close"]) < previous_twenty_high
    assert detect_break_of_structure(dataset) == "bullish_bos"


def test_liquidity_analysis_owns_levels_sweep_and_context() -> None:
    dataset = generate_trend_dataset(direction="up")
    highs = [float(item["high"]) for item in dataset]
    lows = [float(item["low"]) for item in dataset]
    liquidity_high, liquidity_low = get_liquidity_levels(highs, lows)

    context = liquidity_context(
        close_price=float(dataset[-1]["close"]),
        trend="bullish",
        liquidity_high=liquidity_high,
        liquidity_low=liquidity_low,
        atr=2.0,
    )

    assert liquidity_high > liquidity_low
    assert detect_liquidity_sweep(dataset) == "bullish_sweep"
    assert context["directional_liquidity_level"] == liquidity_low
    assert context["directional_liquidity_side"] == "below"
    assert float(context["distance_to_liquidity_atr"]) >= 0


def test_liquidity_service_is_wrapper_for_analysis_liquidity() -> None:
    assert liquidity_service.get_liquidity_levels is get_liquidity_levels
    assert liquidity_service.detect_liquidity_sweep is detect_liquidity_sweep


def test_market_regime_analysis_owns_setup_context_classifiers() -> None:
    snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="range",
        sweep="none",
        score=70.0,
        distance=1.0,
        rsi=72.0,
        volume_ratio=0.5,
        break_of_structure="bullish_bos",
    )
    snapshot.timestamp = "2026-01-01T14:00:00+00:00"
    snapshot.metadata["nearest_distance_to_liquidity_atr"] = 0.5
    snapshot.metadata["nearest_liquidity_side"] = "below"

    assert detect_market_regime(snapshot, atr_min_threshold=0.002) == "HIGH_VOLATILITY"
    assert detect_session(snapshot.timestamp) == "OVERLAP"
    assert detect_entry_context(snapshot) == "CHOPPY_RANGE"
    assert detect_trade_location(snapshot) == "near_support"


def test_risk_analysis_owns_context_risk_helpers() -> None:
    snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=70.0,
        distance=6.0,
        rsi=55.0,
        volume_ratio=0.5,
        break_of_structure="bullish_bos",
    )
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

    warnings = avoidance_warnings(
        snapshot=snapshot,
        higher_trend="bearish",
        direction="long",
        max_distance_to_liquidity_atr=2.5,
        atr_min_threshold=0.002,
        max_spread_atr=1.8,
    )

    assert rr_is_valid(risk_plan) is True
    assert distance_to_sl_atr(snapshot, risk_plan) == 2.0
    assert distance_to_tp_atr(snapshot, risk_plan) == 4.0
    assert late_entry_from_bos(snapshot) is True
    assert "low_volume" in warnings
    assert "against_htf" in warnings
    assert "price_far_from_liquidity" in warnings


def test_risk_analysis_owns_risk_plan_calculation() -> None:
    snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="bullish_sweep",
        score=90.0,
        distance=1.0,
    )

    risk_plan = calculate_risk_plan(
        risk_plan_id="risk_test",
        evaluation_id="eval_test",
        decision="long",
        snapshot=snapshot,
        min_rr=2.0,
        risk_per_trade=0.01,
        account_balance_reference=1000.0,
        created_at=snapshot.created_at,
    )

    assert risk_plan is not None
    assert risk_plan.entry == 101.0
    assert risk_plan.stop_loss == 94.8
    assert risk_plan.take_profit == 113.4
    assert risk_plan.risk_reward == 2.0
    assert risk_plan.risk_amount == 10.0
    assert risk_plan.sl_method == "liquidity_plus_atr_buffer"


def test_risk_service_is_wrapper_for_analysis_risk() -> None:
    assert risk_service.calculate_risk_plan is calculate_risk_plan
