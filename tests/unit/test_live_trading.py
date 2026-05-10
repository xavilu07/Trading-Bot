from __future__ import annotations

from trading_signals.application.use_cases.live_trading import (
    LiveTradingStore,
    build_live_candidate_from_decision,
    build_live_candidate_from_signal,
    format_live_daily_summary_for_telegram,
    format_public_live_trade_event_for_telegram,
    format_live_trade_event_for_telegram,
)
from trading_signals.domain.entities.signal_decision import SignalDecision
from trading_signals.domain.entities.strategy_evaluation import StrategyEvaluation
from trading_signals.domain.entities.trade_signal import TradeSignal
from tests.unit.test_paper_trading import SETUP_CONTEXT, build_risk_plan
from tests.unit.test_strategy_and_risk import build_snapshot


def build_signal(direction: str = "long") -> TradeSignal:
    return TradeSignal(
        id="sig_test",
        scan_run_id="run_test",
        evaluation_id="eval_test",
        risk_plan_id="risk_test",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="BTCUSDT",
        decision=direction,
        status="published",
        dedupe_key=f"BTCUSDT|{direction}|test",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id="snap_1h",
        higher_snapshot_id="snap_4h",
        created_at="2026-01-01T00:00:00+00:00",
        published_at="2026-01-01T00:00:00+00:00",
        signal_type="NEW",
    )


def create_live_trade(store: LiveTradingStore, direction: str = "long", public_published: bool = False) -> None:
    candidate = build_live_candidate_from_signal(
        signal=build_signal(direction),
        setup_type="MAIN_SIGNAL",
        score=80.0,
        risk_plan=build_risk_plan(direction),
        setup_context=SETUP_CONTEXT,
        reasons=["primary_sweep_setup", "quality_score"],
        public_published=public_published,
    )
    assert store.upsert_candidate(candidate) is True


def test_live_trade_created_when_real_signal_is_published(tmp_path) -> None:
    store = LiveTradingStore(tmp_path)
    create_live_trade(store)

    trades = store.list_trades()
    assert len(trades) == 1
    assert trades[0]["symbol"] == "BTCUSDT"
    assert trades[0]["status"] == "open"
    assert trades[0]["signal_type"] == "NEW"
    assert trades[0]["setup_type"] == "MAIN_SIGNAL"
    assert trades[0]["risk_reward"] == "2.0"
    assert trades[0]["public_published"] == "false"
    assert trades[0]["liquidity_sweep"] == "UNKNOWN"
    assert trades[0]["market_structure"] == "UNKNOWN"
    assert "primary_sweep_setup" in trades[0]["reasons"]


def test_live_trade_persists_secondary_analysis_fields(tmp_path) -> None:
    store = LiveTradingStore(tmp_path)
    context = {
        **SETUP_CONTEXT,
        "liquidity_sweep": "none",
        "market_structure": "range",
        "penalties": ["distance_to_liquidity_penalty:10"],
    }
    candidate = build_live_candidate_from_signal(
        signal=build_signal("long"),
        setup_type="SECONDARY_SIGNAL",
        score=82.0,
        risk_plan=build_risk_plan("long"),
        setup_context=context,
        reasons=["secondary_setup"],
        penalties=["distance_to_liquidity_penalty:10"],
    )

    assert store.upsert_candidate(candidate) is True
    trade = store.list_trades()[0]

    assert trade["setup_type"] == "SECONDARY_SIGNAL"
    assert trade["liquidity_sweep"] == "none"
    assert trade["market_structure"] == "range"
    assert "distance_to_liquidity_penalty:10" in trade["penalties"]


def test_live_candidate_accepts_signal_decision_without_changing_candidate() -> None:
    signal = build_signal("long")
    risk_plan = build_risk_plan("long")
    evaluation = StrategyEvaluation(
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
        decision_trace=["primary_sweep_setup", "quality_score"],
        rejection_reasons=[],
        passed_filters=["primary_sweep_setup", "quality_score"],
        failed_filters=[],
        setup_score=80.0,
        confidence=0.8,
        created_at="2026-01-01T00:00:00+00:00",
    )
    signal_decision = SignalDecision(
        symbol="BTCUSDT",
        direction="long",
        decision="SEND",
        setup_type="MAIN_SIGNAL",
        entry_price=risk_plan.entry,
        stop_loss=risk_plan.stop_loss,
        take_profit=risk_plan.take_profit,
        total_score=80.0,
        rejection_reasons=[],
        decision_trace=["primary_sweep_setup", "quality_score"],
        source_engine="liquidity_sweep_mtf_v1",
    )

    from_evaluation = build_live_candidate_from_decision(
        signal=signal,
        setup_type="MAIN_SIGNAL",
        evaluation_or_decision=evaluation,
        risk_plan=risk_plan,
        setup_context=SETUP_CONTEXT,
    )
    from_signal_decision = build_live_candidate_from_decision(
        signal=signal,
        setup_type="MAIN_SIGNAL",
        evaluation_or_decision=signal_decision,
        risk_plan=risk_plan,
        setup_context=SETUP_CONTEXT,
    )

    assert from_signal_decision == from_evaluation
    assert from_signal_decision.reasons == ["primary_sweep_setup", "quality_score"]
    assert from_signal_decision.score == 80.0


def test_live_trade_closes_by_tp(tmp_path) -> None:
    store = LiveTradingStore(tmp_path)
    create_live_trade(store)
    snapshot = build_snapshot(scan_run_id="run_test", symbol="BTCUSDT", timeframe="1h", trend="bullish", structure="bullish", sweep="none", score=80.0, distance=1.0)
    snapshot.high = 111.0
    snapshot.low = 99.0
    snapshot.close = 110.0

    events = store.update_open_trades_for_snapshot(
        snapshot,
        updated_at="2026-01-01T01:00:00+00:00",
        breakeven_enabled=True,
        breakeven_trigger_r=1.0,
        partial_tp_enabled=True,
        partial_tp_trigger_r=1.5,
    )

    assert events[0]["event_type"] == "tp_hit"
    assert store.list_trades()[0]["status"] == "tp_hit"
    assert store.list_trades()[0]["result_r"] == "2.0000"
    assert "✅ TP alcanzado" in format_live_trade_event_for_telegram(events[0])


def test_public_tp_update_only_for_public_trade(tmp_path) -> None:
    store = LiveTradingStore(tmp_path)
    create_live_trade(store, public_published=True)
    snapshot = build_snapshot(scan_run_id="run_test", symbol="BTCUSDT", timeframe="1h", trend="bullish", structure="bullish", sweep="none", score=80.0, distance=1.0)
    snapshot.high = 111.0
    snapshot.low = 99.0
    snapshot.close = 110.0

    events = store.update_open_trades_for_snapshot(
        snapshot,
        updated_at="2026-01-01T01:00:00+00:00",
        breakeven_enabled=True,
        breakeven_trigger_r=1.0,
        partial_tp_enabled=True,
        partial_tp_trigger_r=1.5,
    )

    message = format_public_live_trade_event_for_telegram(events[0])

    assert "✅ TP1 ALCANZADO" in message
    assert "🟢 BTC/USDT" in message
    assert "🎯 TP1: 110.0" in message


def test_public_sl_update_only_for_public_trade(tmp_path) -> None:
    store = LiveTradingStore(tmp_path)
    create_live_trade(store, public_published=True)
    snapshot = build_snapshot(scan_run_id="run_test", symbol="BTCUSDT", timeframe="1h", trend="bullish", structure="bullish", sweep="none", score=80.0, distance=1.0)
    snapshot.high = 101.0
    snapshot.low = 94.0
    snapshot.close = 95.0

    events = store.update_open_trades_for_snapshot(
        snapshot,
        updated_at="2026-01-01T01:00:00+00:00",
        breakeven_enabled=True,
        breakeven_trigger_r=1.0,
        partial_tp_enabled=True,
        partial_tp_trigger_r=1.5,
    )

    message = format_public_live_trade_event_for_telegram(events[0])

    assert "🛑 STOP LOSS TOCADO" in message
    assert "Operación cerrada por SL." in message


def test_public_breakeven_update_only_for_public_trade(tmp_path) -> None:
    store = LiveTradingStore(tmp_path)
    create_live_trade(store, public_published=True)
    snapshot = build_snapshot(scan_run_id="run_test", symbol="BTCUSDT", timeframe="1h", trend="bullish", structure="bullish", sweep="none", score=80.0, distance=1.0)
    snapshot.high = 106.0
    snapshot.low = 100.0
    snapshot.close = 105.0

    events = store.update_open_trades_for_snapshot(
        snapshot,
        updated_at="2026-01-01T01:00:00+00:00",
        breakeven_enabled=True,
        breakeven_trigger_r=1.0,
        partial_tp_enabled=False,
        partial_tp_trigger_r=1.5,
    )

    message = format_public_live_trade_event_for_telegram(events[0])

    assert "🛡️ BREAK EVEN" in message
    assert "SL recomendado a precio de entrada." in message


def test_dev_only_trade_does_not_format_public_update(tmp_path) -> None:
    store = LiveTradingStore(tmp_path)
    create_live_trade(store, public_published=False)
    snapshot = build_snapshot(scan_run_id="run_test", symbol="BTCUSDT", timeframe="1h", trend="bullish", structure="bullish", sweep="none", score=80.0, distance=1.0)
    snapshot.high = 111.0
    snapshot.low = 99.0
    snapshot.close = 110.0

    events = store.update_open_trades_for_snapshot(
        snapshot,
        updated_at="2026-01-01T01:00:00+00:00",
        breakeven_enabled=True,
        breakeven_trigger_r=1.0,
        partial_tp_enabled=True,
        partial_tp_trigger_r=1.5,
    )

    assert format_public_live_trade_event_for_telegram(events[0]) == ""


def test_public_update_event_is_not_duplicated(tmp_path) -> None:
    store = LiveTradingStore(tmp_path)
    create_live_trade(store, public_published=True)
    snapshot = build_snapshot(scan_run_id="run_test", symbol="BTCUSDT", timeframe="1h", trend="bullish", structure="bullish", sweep="none", score=80.0, distance=1.0)
    snapshot.high = 106.0
    snapshot.low = 100.0
    snapshot.close = 105.0

    first = store.update_open_trades_for_snapshot(
        snapshot,
        updated_at="2026-01-01T01:00:00+00:00",
        breakeven_enabled=True,
        breakeven_trigger_r=1.0,
        partial_tp_enabled=False,
        partial_tp_trigger_r=1.5,
    )
    second = store.update_open_trades_for_snapshot(
        snapshot,
        updated_at="2026-01-01T02:00:00+00:00",
        breakeven_enabled=True,
        breakeven_trigger_r=1.0,
        partial_tp_enabled=False,
        partial_tp_trigger_r=1.5,
    )

    assert len([format_public_live_trade_event_for_telegram(event) for event in first if format_public_live_trade_event_for_telegram(event)]) == 1
    assert second == []


def test_live_trade_closes_by_sl(tmp_path) -> None:
    store = LiveTradingStore(tmp_path)
    create_live_trade(store)
    snapshot = build_snapshot(scan_run_id="run_test", symbol="BTCUSDT", timeframe="1h", trend="bullish", structure="bullish", sweep="none", score=80.0, distance=1.0)
    snapshot.high = 101.0
    snapshot.low = 94.0
    snapshot.close = 95.0

    events = store.update_open_trades_for_snapshot(
        snapshot,
        updated_at="2026-01-01T01:00:00+00:00",
        breakeven_enabled=True,
        breakeven_trigger_r=1.0,
        partial_tp_enabled=True,
        partial_tp_trigger_r=1.5,
    )

    assert events[0]["event_type"] == "sl_hit"
    assert store.list_trades()[0]["status"] == "sl_hit"
    assert store.list_trades()[0]["result_r"] == "-1.0000"
    assert "❌ SL alcanzado" in format_live_trade_event_for_telegram(events[0])


def test_breakeven_alert_only_once(tmp_path) -> None:
    store = LiveTradingStore(tmp_path)
    create_live_trade(store)
    snapshot = build_snapshot(scan_run_id="run_test", symbol="BTCUSDT", timeframe="1h", trend="bullish", structure="bullish", sweep="none", score=80.0, distance=1.0)
    snapshot.high = 106.0
    snapshot.low = 100.0
    snapshot.close = 105.0

    first = store.update_open_trades_for_snapshot(
        snapshot,
        updated_at="2026-01-01T01:00:00+00:00",
        breakeven_enabled=True,
        breakeven_trigger_r=1.0,
        partial_tp_enabled=False,
        partial_tp_trigger_r=1.5,
    )
    second = store.update_open_trades_for_snapshot(
        snapshot,
        updated_at="2026-01-01T02:00:00+00:00",
        breakeven_enabled=True,
        breakeven_trigger_r=1.0,
        partial_tp_enabled=False,
        partial_tp_trigger_r=1.5,
    )

    assert [event["event_type"] for event in first] == ["breakeven"]
    assert second == []
    assert store.list_trades()[0]["breakeven_triggered"] == "true"


def test_partial_tp_alert_only_once(tmp_path) -> None:
    store = LiveTradingStore(tmp_path)
    create_live_trade(store)
    snapshot = build_snapshot(scan_run_id="run_test", symbol="BTCUSDT", timeframe="1h", trend="bullish", structure="bullish", sweep="none", score=80.0, distance=1.0)
    snapshot.high = 108.0
    snapshot.low = 100.0
    snapshot.close = 107.5

    first = store.update_open_trades_for_snapshot(
        snapshot,
        updated_at="2026-01-01T01:00:00+00:00",
        breakeven_enabled=False,
        breakeven_trigger_r=1.0,
        partial_tp_enabled=True,
        partial_tp_trigger_r=1.5,
    )
    second = store.update_open_trades_for_snapshot(
        snapshot,
        updated_at="2026-01-01T02:00:00+00:00",
        breakeven_enabled=False,
        breakeven_trigger_r=1.0,
        partial_tp_enabled=True,
        partial_tp_trigger_r=1.5,
    )

    assert [event["event_type"] for event in first] == ["partial_tp"]
    assert second == []
    assert store.list_trades()[0]["partial_tp_suggested"] == "true"
    assert "💰 TP parcial sugerido" in format_live_trade_event_for_telegram(first[0], partial_percentage="30-50")


def test_live_daily_summary(tmp_path) -> None:
    store = LiveTradingStore(tmp_path)
    create_live_trade(store)
    snapshot = build_snapshot(scan_run_id="run_test", symbol="BTCUSDT", timeframe="1h", trend="bullish", structure="bullish", sweep="none", score=80.0, distance=1.0)
    snapshot.high = 111.0
    snapshot.low = 99.0
    snapshot.close = 110.0
    store.update_open_trades_for_snapshot(
        snapshot,
        updated_at="2026-01-01T01:00:00+00:00",
        breakeven_enabled=True,
        breakeven_trigger_r=1.0,
        partial_tp_enabled=True,
        partial_tp_trigger_r=1.5,
    )

    summary = store.build_daily_summary("2026-01-01")

    assert summary["closed_trades"] == 1
    assert summary["won"] == 1
    assert summary["winrate"] == 100.0
    assert summary["avg_r"] == 2.0
    assert summary["best_setup"] == "MAIN_SIGNAL"
    assert "Resumen live trading diario" in format_live_daily_summary_for_telegram(summary)
