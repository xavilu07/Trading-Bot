from __future__ import annotations

from pathlib import Path

from trading_signals.application.use_cases.publish_signal import clear_relaxed_public_shadow_dedupe, publish_signal
from trading_signals.application.use_cases.relaxation_shadow_v1 import (
    RelaxationShadowV1Store,
    build_relaxation_shadow_candidate,
    build_relaxation_shadow_summary,
    safe_relaxation_filter_result,
    write_relaxation_shadow_reports,
)
from trading_signals.domain.entities.risk_plan import RiskPlan
from trading_signals.domain.entities.strategy_evaluation import StrategyEvaluation
from trading_signals.domain.entities.trade_signal import TradeSignal
from tests.unit.test_publish_signal import RecordingSignalRepo, RoutingNotifier
from tests.unit.test_strategy_and_risk import build_snapshot


def test_safe_relaxation_filter_detection() -> None:
    result = safe_relaxation_filter_result(["breakout_bad_location", "against_htf"])

    assert result["eligible"] is True
    assert result["safe_filters"] == ["breakout_bad_location", "against_htf"]
    assert result["unsafe_filters"] == []


def test_unsafe_relaxation_filter_rejected() -> None:
    result = safe_relaxation_filter_result(["breakout_bad_location", "kill_switch_active"])

    assert result["eligible"] is False
    assert result["safe_filters"] == ["breakout_bad_location"]
    assert result["unsafe_filters"] == ["kill_switch_active"]


def test_relaxation_shadow_trade_creation_and_deduplication(tmp_path: Path) -> None:
    store = RelaxationShadowV1Store(tmp_path)
    entry, higher, evaluation, risk_plan, signal, setup_context = _case()
    candidate = build_relaxation_shadow_candidate(
        signal=signal,
        evaluation=evaluation,
        risk_plan=risk_plan,
        entry_snapshot=entry,
        higher_snapshot=higher,
        setup_context=setup_context,
        current_policy={"block_reasons": ["breakout_bad_location"], "policy_version": "v1"},
        opened_at=entry.created_at,
    )

    assert candidate is not None
    assert store.upsert_candidate(candidate) is True
    assert store.upsert_candidate(candidate) is False
    trades = store.list_trades()
    assert len(trades) == 1
    assert trades[0]["symbol"] == "BTCUSDT"
    assert trades[0]["relaxed_filters"]


def test_relaxation_shadow_update_tp_sl_and_expiry(tmp_path: Path) -> None:
    store = RelaxationShadowV1Store(tmp_path)
    entry, higher, evaluation, risk_plan, signal, setup_context = _case()
    tp_candidate = build_relaxation_shadow_candidate(
        signal=signal,
        evaluation=evaluation,
        risk_plan=risk_plan,
        entry_snapshot=entry,
        higher_snapshot=higher,
        setup_context=setup_context,
        current_policy={"block_reasons": ["breakout_bad_location"]},
        opened_at=entry.created_at,
    )
    assert tp_candidate is not None
    store.upsert_candidate(tp_candidate)
    hit_tp = build_snapshot(scan_run_id="run", symbol="BTCUSDT", timeframe="1h", trend="bullish", structure="bullish", sweep="none", score=80, distance=1.0)
    hit_tp.high = 111.0
    hit_tp.low = 99.0
    updates = store.update_open_trades_for_snapshot(hit_tp, updated_at="2026-01-01T11:00:00+00:00")
    assert updates[0]["status"] == "tp2_hit"

    entry2, higher2, evaluation2, risk_plan2, signal2, setup_context2 = _case(symbol="ETHUSDT")
    sl_candidate = build_relaxation_shadow_candidate(
        signal=signal2,
        evaluation=evaluation2,
        risk_plan=risk_plan2,
        entry_snapshot=entry2,
        higher_snapshot=higher2,
        setup_context=setup_context2,
        current_policy={"block_reasons": ["against_htf"]},
        opened_at=entry2.created_at,
    )
    assert sl_candidate is not None
    store.upsert_candidate(sl_candidate)
    hit_sl = build_snapshot(scan_run_id="run", symbol="ETHUSDT", timeframe="1h", trend="bullish", structure="bullish", sweep="none", score=80, distance=1.0)
    hit_sl.high = 101.0
    hit_sl.low = 94.0
    updates = store.update_open_trades_for_snapshot(hit_sl, updated_at="2026-01-01T12:00:00+00:00")
    assert updates[0]["status"] == "sl_hit"

    entry3, higher3, evaluation3, risk_plan3, signal3, setup_context3 = _case(symbol="SOLUSDT")
    exp_candidate = build_relaxation_shadow_candidate(
        signal=signal3,
        evaluation=evaluation3,
        risk_plan=risk_plan3,
        entry_snapshot=entry3,
        higher_snapshot=higher3,
        setup_context=setup_context3,
        current_policy={"block_reasons": ["edge_activation_requires_trending"]},
        opened_at=entry3.created_at,
        expires_after_candles=1,
    )
    assert exp_candidate is not None
    store.upsert_candidate(exp_candidate)
    flat = build_snapshot(scan_run_id="run", symbol="SOLUSDT", timeframe="1h", trend="bullish", structure="bullish", sweep="none", score=80, distance=1.0)
    flat.high = 102.0
    flat.low = 98.0
    updates = store.update_open_trades_for_snapshot(flat, updated_at="2026-01-01T13:00:00+00:00")
    assert updates[0]["status"] == "expired"


def test_relaxation_shadow_summary_metrics_and_reports(tmp_path: Path) -> None:
    store = RelaxationShadowV1Store(tmp_path)
    entry, higher, evaluation, risk_plan, signal, setup_context = _case()
    candidate = build_relaxation_shadow_candidate(
        signal=signal,
        evaluation=evaluation,
        risk_plan=risk_plan,
        entry_snapshot=entry,
        higher_snapshot=higher,
        setup_context=setup_context,
        current_policy={"block_reasons": ["breakout_bad_location"]},
        opened_at=entry.created_at,
    )
    assert candidate is not None
    store.upsert_candidate(candidate)
    hit_tp = build_snapshot(scan_run_id="run", symbol="BTCUSDT", timeframe="1h", trend="bullish", structure="bullish", sweep="none", score=80, distance=1.0)
    hit_tp.high = 111.0
    hit_tp.low = 99.0
    store.update_open_trades_for_snapshot(hit_tp, updated_at="2026-01-01T11:00:00+00:00")

    summary = build_relaxation_shadow_summary(tmp_path)
    paths = write_relaxation_shadow_reports(tmp_path, tmp_path / "reports")

    assert summary["closed_trades"] == 1
    assert summary["metrics"]["total_r"] == 2.0
    assert summary["by_relaxed_filter"]["breakout_bad_location"]["closed_trades"] == 1
    assert paths["summary_md"].exists()
    assert paths["trades_csv"].exists()


def test_publish_signal_sends_relaxation_shadow_to_dev_only(tmp_path: Path) -> None:
    clear_relaxed_public_shadow_dedupe()
    store = RelaxationShadowV1Store(tmp_path)
    repo = RecordingSignalRepo()
    notifier = RoutingNotifier()
    entry, higher, evaluation, risk_plan, signal, setup_context = _case()

    deliveries = publish_signal(
        repo,
        notifier,
        signal,
        entry,
        higher,
        evaluation,
        risk_plan,
        setup_context=setup_context,
        relaxation_shadow_store=store,
    )

    channels = {delivery.channel for delivery in deliveries}
    assert "telegram_public" not in channels
    assert "telegram_dev" in channels
    assert "telegram_dev_relaxation_shadow_v1" in channels
    assert any("🧪 RELAXATION SHADOW V1" in message for message in notifier.dev_messages)
    assert notifier.public_messages == []
    assert len(store.list_trades()) == 1


def _case(symbol: str = "BTCUSDT"):
    entry = build_snapshot(scan_run_id="run", symbol=symbol, timeframe="1h", trend="bullish", structure="bullish", sweep="bullish_sweep", score=80, distance=1.0)
    entry.timestamp = "2026-01-01T10:00:00+00:00"
    entry.open = 99.0
    entry.high = 101.0
    entry.low = 98.0
    entry.close = 100.0
    higher = build_snapshot(scan_run_id="run", symbol=symbol, timeframe="4h", trend="bullish", structure="bullish", sweep="none", score=80, distance=1.0)
    evaluation = StrategyEvaluation(
        id=f"eval_{symbol}",
        scan_run_id="run",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol=symbol,
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id=entry.id,
        higher_snapshot_id=higher.id,
        decision="long",
        decision_trace=[],
        rejection_reasons=[],
        passed_filters=["primary_sweep_setup", "quality_score"],
        failed_filters=[],
        setup_score=80.0,
        confidence=0.8,
        created_at=entry.created_at,
    )
    risk_plan = RiskPlan(
        id=f"risk_{symbol}",
        evaluation_id=evaluation.id,
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
    signal = TradeSignal(
        id=f"sig_{symbol}",
        scan_run_id="run",
        evaluation_id=evaluation.id,
        risk_plan_id=risk_plan.id,
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol=symbol,
        decision="long",
        status="valid",
        dedupe_key=f"dedupe_{symbol}",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id=entry.id,
        higher_snapshot_id=higher.id,
        created_at=entry.created_at,
    )
    setup_context = {
        "setup_type": "MAIN_SIGNAL",
        "session": "OVERLAP",
        "market_regime": "TRENDING",
        "entry_context": "BREAKOUT",
        "trade_location": "near_support",
        "market_structure": "bullish",
        "liquidity_sweep": "bullish_sweep",
        "trend_entry": "bullish",
        "trend_higher": "bullish",
        "rr_valid": True,
        "avoidance_warnings": [],
        "warnings": [],
        "penalties": [],
    }
    return entry, higher, evaluation, risk_plan, signal, setup_context
