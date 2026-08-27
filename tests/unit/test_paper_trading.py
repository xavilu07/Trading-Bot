from __future__ import annotations

import pytest

from trading_signals.application.use_cases.paper_trading import (
    PaperTradingStore,
    build_paper_candidate_from_decision,
    build_paper_candidate_from_signal,
    evaluate_trade_status,
    format_paper_daily_summary_for_telegram,
    paper_level,
    paper_market_is_tradeable,
)
from trading_signals.domain.entities.risk_plan import RiskPlan
from trading_signals.domain.entities.signal_decision import SignalDecision
from trading_signals.domain.entities.strategy_evaluation import StrategyEvaluation
from tests.unit.test_strategy_and_risk import build_snapshot


SETUP_CONTEXT = {
    "market_regime": "TRENDING",
    "session": "LONDON",
    "entry_context": "BREAKOUT",
    "trade_location": "discount_zone",
    "rr_valid": True,
    "sl_distance_atr": 1.0,
    "tp_distance_atr": 2.0,
    "late_entry_from_bos": False,
    "avoidance_warnings": ["low_volume"],
}


def build_risk_plan(direction: str = "long") -> RiskPlan:
    if direction == "long":
        entry = 100.0
        stop_loss = 95.0
        take_profit = 110.0
    else:
        entry = 100.0
        stop_loss = 105.0
        take_profit = 90.0
    return RiskPlan(
        id="risk_test",
        evaluation_id="eval_test",
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward=2.0,
        risk_amount=10.0,
        position_size=2.0,
        sl_method="test",
        tp_method="test",
        created_at="2026-01-01T00:00:00+00:00",
    )


def test_paper_store_creates_trade_once(tmp_path) -> None:
    store = PaperTradingStore(tmp_path)
    snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=70.0,
        distance=1.0,
    )
    candidate = build_paper_candidate_from_signal(
        symbol="BTCUSDT",
        direction="long",
        setup_type="MAIN_SIGNAL",
        score=80.0,
        risk_plan=build_risk_plan("long"),
        opened_at="2026-01-01T00:00:00+00:00",
        entry_reasons=["primary_sweep_setup"],
        conditions_passed=["quality_score"],
        conditions_failed=[],
        source_key="BTCUSDT|long|test",
        snapshot=snapshot,
        higher_trend="bullish",
        entry_or_rejection_reason="paper_tradeable",
        expires_after_candles=24,
        setup_context=SETUP_CONTEXT,
    )
    assert candidate is not None

    assert store.upsert_candidate(candidate) is True
    assert store.upsert_candidate(candidate) is False

    trades = store.list_trades()
    assert len(trades) == 1
    assert trades[0]["symbol"] == "BTCUSDT"
    assert trades[0]["take_profit_1"] == "105.0"
    assert trades[0]["take_profit_2"] == "110.0"
    assert trades[0]["paper_level"] == "HIGH"
    assert trades[0]["risk_reward_tp1"] == "1.0"
    assert trades[0]["risk_reward_tp2"] == "2.0"
    assert trades[0]["market_regime"] == "TRENDING"
    assert trades[0]["entry_context"] == "BREAKOUT"
    assert "low_volume" in trades[0]["avoidance_warnings"]


def test_paper_candidate_supports_short_direction() -> None:
    snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="XRPUSDT",
        timeframe="1h",
        trend="bearish",
        structure="bearish",
        sweep="bearish_sweep",
        score=80.0,
        distance=1.0,
    )

    candidate = build_paper_candidate_from_signal(
        symbol="XRPUSDT",
        direction="short",
        setup_type="MAIN_SIGNAL",
        score=80.0,
        risk_plan=build_risk_plan("short"),
        opened_at="2026-01-01T00:00:00+00:00",
        entry_reasons=["primary_sweep_setup"],
        conditions_passed=["quality_score"],
        conditions_failed=[],
        source_key="XRPUSDT|short|test",
        snapshot=snapshot,
        higher_trend="bearish",
        entry_or_rejection_reason="paper_tradeable",
        expires_after_candles=24,
        setup_context=SETUP_CONTEXT,
    )

    assert candidate is not None
    assert candidate.direction == "short"
    assert candidate.entry_price == 100.0
    assert candidate.stop_loss == 105.0
    assert candidate.take_profit_1 == 95.0
    assert candidate.take_profit_2 == 90.0
    assert candidate.risk_reward_tp2 == 2.0
    assert candidate.setup_type == "MAIN_SIGNAL"
    assert candidate.liquidity_sweep == "bearish_sweep"
    assert candidate.market_structure == "bearish"


def test_paper_secondary_without_sweep_persists_analysis_fields(tmp_path) -> None:
    store = PaperTradingStore(tmp_path)
    snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="OPUSDT",
        timeframe="1h",
        trend="bullish",
        structure="range",
        sweep="none",
        score=80.0,
        distance=1.0,
    )
    candidate = build_paper_candidate_from_signal(
        symbol="OPUSDT",
        direction="long",
        setup_type="SECONDARY_SIGNAL",
        score=80.0,
        risk_plan=build_risk_plan("long"),
        opened_at="2026-01-01T00:00:00+00:00",
        entry_reasons=["penalties=distance_to_liquidity_penalty:10"],
        conditions_passed=["secondary_setup"],
        conditions_failed=["distance_to_liquidity_penalty"],
        penalties=["distance_to_liquidity_penalty:10"],
        source_key="OPUSDT|long|secondary",
        snapshot=snapshot,
        higher_trend="bullish",
        entry_or_rejection_reason="paper_tradeable",
        expires_after_candles=24,
        setup_context=SETUP_CONTEXT,
    )
    assert candidate is not None

    assert store.upsert_candidate(candidate) is True
    trade = store.list_trades()[0]

    assert trade["setup_type"] == "SECONDARY_SIGNAL"
    assert trade["liquidity_sweep"] == "none"
    assert trade["market_structure"] == "range"
    assert "distance_to_liquidity_penalty:10" in trade["penalties"]


def test_paper_candidate_accepts_signal_decision_without_changing_candidate() -> None:
    snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=80.0,
        distance=1.0,
    )
    risk_plan = build_risk_plan("long")
    evaluation = StrategyEvaluation(
        id="eval_test",
        scan_run_id="run_test",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="BTCUSDT",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id=snapshot.id,
        higher_snapshot_id="snap_4h",
        decision="long",
        decision_trace=["trace_a", "trace_b"],
        rejection_reasons=[],
        passed_filters=["quality_score"],
        failed_filters=["distance_to_liquidity_penalty"],
        setup_score=80.0,
        confidence=0.8,
        created_at=snapshot.created_at,
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
        warnings=[],
        passed_filters=["quality_score"],
        failed_filters=["distance_to_liquidity_penalty"],
        decision_trace=["trace_a", "trace_b"],
        source_engine="liquidity_sweep_mtf_v1",
    )

    from_evaluation = build_paper_candidate_from_decision(
        symbol="BTCUSDT",
        direction="long",
        setup_type="MAIN_SIGNAL",
        evaluation_or_decision=evaluation,
        risk_plan=risk_plan,
        opened_at="2026-01-01T00:00:00+00:00",
        source_key="BTCUSDT|long|test",
        snapshot=snapshot,
        higher_trend="bullish",
        entry_or_rejection_reason="paper_tradeable",
        expires_after_candles=24,
        setup_context=SETUP_CONTEXT,
    )
    from_signal_decision = build_paper_candidate_from_decision(
        symbol="BTCUSDT",
        direction="long",
        setup_type="MAIN_SIGNAL",
        evaluation_or_decision=signal_decision,
        risk_plan=risk_plan,
        opened_at="2026-01-01T00:00:00+00:00",
        source_key="BTCUSDT|long|test",
        snapshot=snapshot,
        higher_trend="bullish",
        entry_or_rejection_reason="paper_tradeable",
        expires_after_candles=24,
        setup_context=SETUP_CONTEXT,
    )

    assert from_evaluation == from_signal_decision
    assert from_signal_decision is not None
    assert from_signal_decision.entry_reasons == ["trace_a", "trace_b"]
    assert from_signal_decision.conditions_passed == ["quality_score"]
    assert from_signal_decision.conditions_failed == ["distance_to_liquidity_penalty"]


def test_paper_trade_status_hits_tp1_then_tp2(tmp_path) -> None:
    store = PaperTradingStore(tmp_path)
    base_snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=70.0,
        distance=1.0,
    )
    candidate = build_paper_candidate_from_signal(
        symbol="BTCUSDT",
        direction="long",
        setup_type="MAIN_SIGNAL",
        score=80.0,
        risk_plan=build_risk_plan("long"),
        opened_at="2026-01-01T00:00:00+00:00",
        entry_reasons=[],
        conditions_passed=[],
        conditions_failed=[],
        source_key="BTCUSDT|long|test",
        snapshot=base_snapshot,
        higher_trend="bullish",
        entry_or_rejection_reason="paper_tradeable",
        expires_after_candles=24,
        setup_context=SETUP_CONTEXT,
    )
    assert candidate is not None
    store.upsert_candidate(candidate)
    tp1_snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=70.0,
        distance=1.0,
    )
    tp1_snapshot.high = 106.0
    tp1_snapshot.low = 99.0

    updates = store.update_open_trades_for_snapshot(tp1_snapshot, "2026-01-01T01:00:00+00:00")

    assert updates[0]["status"] == "tp1_hit"
    # marked to market, not to TP1: the position is still fully open here
    assert updates[0]["result_r"] == "0.2000"
    assert updates[0]["mfe_r"] == "1.2000"
    assert updates[0]["mae_r"] == "-0.2000"

    tp2_snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=70.0,
        distance=1.0,
    )
    tp2_snapshot.high = 111.0
    tp2_snapshot.low = 100.0
    updates = store.update_open_trades_for_snapshot(tp2_snapshot, "2026-01-01T02:00:00+00:00")

    assert updates[0]["status"] == "tp2_hit"
    assert updates[0]["result_r"] == "2.0000"


def test_paper_trade_status_hits_sl() -> None:
    trade = {
        "direction": "short",
        "entry_price": "100",
        "stop_loss": "105",
        "take_profit_1": "95",
        "take_profit_2": "90",
        "status": "open",
    }
    snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bearish",
        structure="bearish",
        sweep="none",
        score=70.0,
        distance=1.0,
    )
    snapshot.high = 106.0

    assert evaluate_trade_status(trade, snapshot) == ("sl_hit", -1.0, 0.4, -1.2)


def _tp1_trade(direction: str = "long") -> dict[str, str]:
    if direction == "long":
        return {
            "direction": "long",
            "entry_price": "100",
            "stop_loss": "95",
            "take_profit_1": "105",
            "take_profit_2": "110",
            "status": "tp1_hit",
        }
    return {
        "direction": "short",
        "entry_price": "100",
        "stop_loss": "105",
        "take_profit_1": "95",
        "take_profit_2": "90",
        "status": "tp1_hit",
    }


def _snapshot_at(close: float, high: float, low: float):
    snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=70.0,
        distance=1.0,
    )
    snapshot.close = close
    snapshot.high = high
    snapshot.low = low
    return snapshot


def test_a_trade_sitting_at_tp1_is_marked_to_market_not_to_tp1() -> None:
    """Nothing is sold at TP1, so its R is what the market pays now."""
    status, result_r, _, _ = evaluate_trade_status(_tp1_trade(), _snapshot_at(close=101.0, high=104.0, low=100.0))

    assert status == "tp1_hit"
    assert result_r == pytest.approx(0.2)


def test_a_trade_that_fell_back_below_entry_after_tp1_records_a_loss() -> None:
    """The case that fabricated 40 winners: recorded +1R, actually negative."""
    status, result_r, _, _ = evaluate_trade_status(_tp1_trade(), _snapshot_at(close=98.0, high=99.0, low=97.0))

    assert status == "tp1_hit"
    assert result_r == pytest.approx(-0.4)


def test_a_short_sitting_at_tp1_is_marked_to_market_too() -> None:
    status, result_r, _, _ = evaluate_trade_status(_tp1_trade("short"), _snapshot_at(close=102.0, high=103.0, low=96.0))

    assert status == "tp1_hit"
    assert result_r == pytest.approx(-0.4)


def test_tp1_then_sl_still_records_a_full_loss() -> None:
    status, result_r, _, _ = evaluate_trade_status(_tp1_trade(), _snapshot_at(close=94.0, high=96.0, low=94.0))

    assert status == "sl_hit"
    assert result_r == -1.0


def test_tp1_then_tp2_still_records_the_full_target() -> None:
    status, result_r, _, _ = evaluate_trade_status(_tp1_trade(), _snapshot_at(close=110.5, high=111.0, low=104.0))

    assert status == "tp2_hit"
    assert result_r == pytest.approx(2.0)


def test_expiring_at_tp1_no_longer_books_a_profit_never_taken(tmp_path) -> None:
    store = PaperTradingStore(tmp_path)
    trade = _tp1_trade()
    trade.update({
        "trade_id": "t1",
        "symbol": "BTCUSDT",
        "candles_held": "23",
        "expires_after_candles": "24",
        "mfe_r": "1.0",
        "mae_r": "0.0",
    })
    store.save_trades([trade])

    updates = store.update_open_trades_for_snapshot(
        _snapshot_at(close=99.0, high=100.0, low=98.5), "2026-01-01T02:00:00+00:00"
    )

    assert updates[0]["status"] == "expired"
    assert updates[0]["result_r"] == "-0.2000"
    assert updates[0]["closed_at"] == "2026-01-01T02:00:00+00:00"
    # touching TP1 is still on the record, it just no longer sets the price
    assert float(updates[0]["mfe_r"]) >= 1.0


def test_paper_daily_summary(tmp_path) -> None:
    store = PaperTradingStore(tmp_path)
    base_snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=70.0,
        distance=1.0,
    )
    candidate = build_paper_candidate_from_signal(
        symbol="BTCUSDT",
        direction="long",
        setup_type="MAIN_SIGNAL",
        score=80.0,
        risk_plan=build_risk_plan("long"),
        opened_at="2026-01-01T00:00:00+00:00",
        entry_reasons=[],
        conditions_passed=[],
        conditions_failed=[],
        source_key="BTCUSDT|long|test",
        snapshot=base_snapshot,
        higher_trend="bullish",
        entry_or_rejection_reason="paper_tradeable",
        expires_after_candles=24,
        setup_context=SETUP_CONTEXT,
    )
    assert candidate is not None
    store.upsert_candidate(candidate)
    snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=70.0,
        distance=1.0,
    )
    snapshot.high = 111.0
    snapshot.low = 99.0
    store.update_open_trades_for_snapshot(snapshot, "2026-01-01T02:00:00+00:00")

    summary = store.build_daily_summary("2026-01-01")

    assert summary["simulated_trades"] == 1
    assert summary["won"] == 1
    assert summary["lost"] == 0
    assert summary["winrate"] == 100.0
    assert summary["best_setup"] == "MAIN_SIGNAL"
    assert summary["by_level"]["HIGH"]["profit_factor"] == 2.0
    assert summary["best_symbol"] == "BTCUSDT"
    assert summary["by_market_regime"]["TRENDING"]["avg_r"] == 2.0
    assert summary["by_session"]["LONDON"]["profit_factor"] == 2.0
    assert summary["by_entry_context"]["BREAKOUT"]["winrate"] == 100.0
    assert summary["by_trade_location"]["discount_zone"]["trades"] == 1

    message = format_paper_daily_summary_for_telegram(summary)
    assert "Performance por market_regime" in message
    assert "- TRENDING: trades 1 | WR 100.0% | PF 2.0 | avgR 2.0" in message
    assert "Performance por session" in message
    assert "- LONDON: trades 1 | WR 100.0% | PF 2.0 | avgR 2.0" in message
    assert "Performance por entry_context" in message
    assert "- BREAKOUT: trades 1 | WR 100.0% | PF 2.0 | avgR 2.0" in message
    assert "Performance por trade_location" in message
    assert "- discount_zone: trades 1 | WR 100.0% | PF 2.0 | avgR 2.0" in message


def test_paper_levels() -> None:
    assert paper_level(45) == "HIGH"
    assert paper_level(40) == "MEDIUM"
    assert paper_level(35) == "LOW"
    assert paper_level(34.99) is None


def test_paper_trade_expires_after_timeout(tmp_path) -> None:
    store = PaperTradingStore(tmp_path)
    base_snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=70.0,
        distance=1.0,
    )
    candidate = build_paper_candidate_from_signal(
        symbol="BTCUSDT",
        direction="long",
        setup_type="LOW_TEST",
        score=35.0,
        risk_plan=build_risk_plan("long"),
        opened_at="2026-01-01T00:00:00+00:00",
        entry_reasons=[],
        conditions_passed=[],
        conditions_failed=[],
        source_key="BTCUSDT|long|timeout",
        snapshot=base_snapshot,
        higher_trend="bullish",
        entry_or_rejection_reason="paper_tradeable",
        expires_after_candles=1,
        setup_context=SETUP_CONTEXT,
    )
    assert candidate is not None
    store.upsert_candidate(candidate)
    flat_snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=70.0,
        distance=1.0,
    )
    flat_snapshot.high = 101.0
    flat_snapshot.low = 99.0
    flat_snapshot.close = 101.0

    updates = store.update_open_trades_for_snapshot(flat_snapshot, "2026-01-01T01:00:00+00:00")

    assert updates[0]["status"] == "expired"
    assert updates[0]["result_r"] == "0.2000"


def test_paper_market_tradeable_filters_bad_conditions() -> None:
    snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="BTCUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=70.0,
        distance=1.0,
    )
    snapshot.atr = 0.01

    assert paper_market_is_tradeable(snapshot, atr_min_threshold=0.002, max_spread_atr=1.8) == (
        False,
        "paper_rejected_atr_too_low",
    )
