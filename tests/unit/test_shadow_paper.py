from __future__ import annotations

import json

from trading_signals.application.use_cases.shadow_paper import (
    ShadowSignalStore,
    build_shadow_signal_row,
    format_shadow_summary,
)
from trading_signals.domain.entities.signal_decision import SignalDecision
from tests.unit.test_strategy_and_risk import build_snapshot


def shadow_row() -> dict[str, object]:
    return {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "symbol": "BCHUSDT",
        "direction": "short",
        "entry_price": 100.0,
        "shadow_decision": "SEND",
        "shadow_score": 86.25,
        "current_decision": "REJECT",
        "current_rejection_reasons": json.dumps(["directional_confluence_failed"]),
        "module_scores": json.dumps({"trend": 100, "momentum": 85, "liquidity": 80, "market_regime": 80}),
        "trend_ok": True,
        "momentum_ok": True,
        "liquidity_ok": True,
        "market_regime": "TRENDING",
        "rsi": 42.0,
        "body_ratio": 0.5,
        "volume_ratio": 1.4,
    }


def test_shadow_signal_store_saves_deduplicates_and_summarizes(tmp_path) -> None:
    store = ShadowSignalStore(tmp_path)
    row = shadow_row()

    assert store.upsert_signal(row) is True
    assert store.upsert_signal({**row, "timestamp": "2026-01-01T01:00:00+00:00", "entry_price": 100.05}) is False

    rows = store.list_signals()
    assert len(rows) == 1
    assert rows[0]["outcome"] == "pending"
    assert rows[0]["max_favorable_move"] == "0"
    assert rows[0]["candles_elapsed"] == "0"
    assert (tmp_path / "paper_trading" / "shadow_signals.csv").exists()

    summary = store.build_summary()
    assert summary["shadow_detected"] == 1
    assert summary["by_direction"] == {"short": 1}
    assert summary["by_shadow_decision"] == {"SEND": 1}
    assert summary["by_score"] == {"80-89": 1}
    assert "Detectadas: 1" in format_shadow_summary(summary)


def test_shadow_signal_store_allows_same_signal_after_closed_outcome(tmp_path) -> None:
    store = ShadowSignalStore(tmp_path)
    row = shadow_row()
    assert store.upsert_signal(row) is True
    rows = store.list_signals()
    rows[0]["outcome"] = "win"
    store.save_signals(rows)

    assert store.upsert_signal({**row, "timestamp": "2026-01-01T02:00:00+00:00"}) is True
    assert len(store.list_signals()) == 2


def test_build_shadow_signal_row_only_for_send_or_paper_only() -> None:
    snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="BCHUSDT",
        timeframe="1h",
        trend="bearish",
        structure="bearish",
        sweep="none",
        score=95.0,
        distance=1.0,
    )
    current = SignalDecision(
        symbol="BCHUSDT",
        direction="no_trade",
        decision="REJECT",
        setup_type="SIGNAL",
        entry_price=None,
        stop_loss=None,
        take_profit=None,
        total_score=95.0,
        rejection_reasons=["directional_confluence_failed"],
        source_engine="liquidity_sweep_mtf_v1",
    )
    diagnostics = {
        "decision_engine": {
            "details": {
                "shadow_decision": "SEND",
                "shadow_score": 86.25,
                "shadow_direction": "short",
            }
        },
        "trend": {"ok": True, "score": 100.0},
        "momentum": {"ok": True, "score": 85.0, "details": {"rsi": 42.0, "body_ratio": 0.5, "volume_ratio": 1.4}},
        "liquidity": {"ok": True, "score": 80.0},
        "market_regime": {"ok": True, "score": 80.0, "details": {"market_regime": "TRENDING"}},
    }

    row = build_shadow_signal_row(
        timestamp="2026-01-01T00:00:00+00:00",
        symbol="BCHUSDT",
        snapshot=snapshot,
        current_decision=current,
        module_diagnostics=diagnostics,
    )

    assert row is not None
    assert row["symbol"] == "BCHUSDT"
    assert row["direction"] == "short"
    assert row["entry_price"] == snapshot.close
    assert json.loads(str(row["current_rejection_reasons"])) == ["directional_confluence_failed"]

    diagnostics["decision_engine"]["details"]["shadow_decision"] = "REJECT"
    assert build_shadow_signal_row(
        timestamp="2026-01-01T00:00:00+00:00",
        symbol="BCHUSDT",
        snapshot=snapshot,
        current_decision=current,
        module_diagnostics=diagnostics,
    ) is None


def test_shadow_store_updates_pending_outcomes(tmp_path) -> None:
    class FakeMarketData:
        def fetch_ohlcv(self, symbol: str, interval: str, limit: int = 300):
            assert symbol == "BCHUSDT"
            assert interval == "1h"
            return [
                {
                    "open_time": "2026-01-01T00:00:00+00:00",
                    "close_time": "2026-01-01T01:00:00+00:00",
                    "high": 101.0,
                    "low": 98.0,
                }
            ]

    store = ShadowSignalStore(tmp_path)
    assert store.upsert_signal(shadow_row()) is True

    updated = store.update_pending_outcomes(FakeMarketData(), evaluated_at="2026-01-01T02:00:00+00:00")

    assert len(updated) == 1
    row = store.list_signals()[0]
    assert row["outcome"] == "win"
    assert row["exit_reason"] == "favorable_move_reached"
    assert row["evaluated_at"] == "2026-01-01T02:00:00+00:00"
