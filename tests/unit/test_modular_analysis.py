from __future__ import annotations

from trading_signals.analysis.liquidity import analyze_liquidity
from trading_signals.analysis.market_regime import analyze_market_regime
from trading_signals.analysis.momentum import analyze_momentum
from trading_signals.analysis.risk import analyze_risk
from trading_signals.analysis.trend import analyze_trend
from trading_signals.data.market_data import market_data_status
from trading_signals.notifications.telegram import telegram_status
from trading_signals.strategy.signal_builder import build_signal_diagnostic
from trading_signals.strategy.strategy_gate import analyze_strategy_gate
from tests.unit.test_paper_trading import build_risk_plan
from tests.unit.test_strategy_and_risk import build_snapshot


class DummyNotifier:
    bot_token = "token"
    chat_ids = ["123"]


class DummyEvaluation:
    decision = "long"
    setup_score = 80.0
    passed_filters = ["quality_score"]
    failed_filters = []
    rejection_reasons = []


def snapshot(trend: str = "bullish"):
    item = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend=trend,
        structure="bullish",
        sweep="none",
        score=80.0,
        distance=1.0,
        volume_ratio=1.5,
        rsi=55.0,
    )
    item.body_ratio = 0.7
    return item


def test_modular_analysis_returns_standard_shape() -> None:
    entry = snapshot("bullish")
    higher = snapshot("bullish")
    risk_plan = build_risk_plan("long")
    results = [
        market_data_status("BTCUSDT", entry, higher),
        analyze_trend(entry, higher),
        analyze_momentum(entry, min_body_ratio=0.35, direction="long"),
        analyze_liquidity(entry, max_distance_to_liquidity_atr=2.5),
        analyze_market_regime(entry, atr_min_threshold=0.002),
        analyze_risk(risk_plan, min_rr=2.0),
        telegram_status(DummyNotifier()),
        build_signal_diagnostic("BTCUSDT", DummyEvaluation(), risk_plan, setup_type="MAIN_SIGNAL"),
    ]

    for result in results:
        assert set(result) == {"ok", "score", "reason", "details"}
        assert isinstance(result["details"], dict)


def test_trend_module_detects_timeframe_mismatch() -> None:
    result = analyze_trend(snapshot("bullish"), snapshot("bearish"))

    assert result["ok"] is True
    assert result["reason"] == "trend_timeframe_mismatch"
    assert result["score"] == 50.0


def test_risk_module_rejects_missing_risk_plan() -> None:
    result = analyze_risk(None, min_rr=2.0)

    assert result == {
        "ok": False,
        "score": 0.0,
        "reason": "risk_plan_missing",
        "details": {"min_rr": 2.0},
    }


def test_momentum_module_includes_candle_diagnostics() -> None:
    entry = snapshot("bullish")
    entry.body_ratio = 0.2

    result = analyze_momentum(entry, min_body_ratio=0.35, direction="long")

    assert result["ok"] is False
    assert result["reason"] == "body_ratio_below_threshold"
    assert result["details"]["body_ratio"] == 0.2
    assert result["details"]["MIN_BODY_RATIO"] == 0.35
    assert result["details"]["candle_body"] == 1.0
    assert result["details"]["candle_range"] == 4.0
    assert result["details"]["volume_ratio"] == 1.5
    assert result["details"]["rsi"] == 55.0
    assert result["details"]["direction"] == "long"


def test_strategy_gate_reports_exact_failed_condition() -> None:
    class Analysis:
        entry_snapshot = snapshot("bullish")
        higher_snapshot = snapshot("bearish")

    class Settings:
        atr_min_threshold = 0.002
        min_body_ratio = 0.35
        setup_score_threshold = 45.0
        max_distance_to_liquidity_atr = 2.5

    class Evaluation:
        decision = "no_trade"
        setup_score = 70.0
        rejection_reasons = ["timeframe_alignment_penalty"]

    result = analyze_strategy_gate(Settings(), Analysis(), Evaluation())

    assert result["ok"] is False
    assert result["reason"] == "strategy_gate_blocked"
    assert result["details"]["condition_failed"] is not None
    assert "failed_conditions" in result["details"]
