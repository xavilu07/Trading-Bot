from __future__ import annotations

from types import SimpleNamespace

from trading_signals.application.use_cases.modular_paper import (
    ModularSignalStore,
    build_modular_signal_row,
)
from trading_signals.domain.entities.signal_decision import SignalDecision


def modular_decision(decision: str = "SEND", entry: float | None = None) -> SignalDecision:
    return SignalDecision(
        symbol="BTCUSDT",
        direction="long",
        decision=decision,
        setup_type="MODULAR_SIGNAL",
        entry_price=entry,
        stop_loss=None,
        take_profit=None,
        total_score=83.75,
        module_scores={"trend": 100.0, "momentum": 85.0, "liquidity": 80.0, "market_regime": 70.0},
        rejection_reasons=[],
        source_engine="modular_decision_engine",
    )


def legacy_decision() -> SignalDecision:
    return SignalDecision(
        symbol="BTCUSDT",
        direction="no_trade",
        decision="REJECT",
        setup_type="NO_SIGNAL",
        entry_price=None,
        stop_loss=None,
        take_profit=None,
        total_score=40.0,
        module_scores={"strategy": 40.0},
        rejection_reasons=["quality_score_failed"],
        source_engine="liquidity_sweep_mtf_v1",
    )


def module_diagnostics() -> dict[str, dict[str, object]]:
    return {
        "trend": {"ok": True, "score": 100.0, "reason": "trend_aligned", "details": {}},
        "momentum": {
            "ok": True,
            "score": 85.0,
            "reason": "momentum_confirmed",
            "details": {"rsi": 55.0, "body_ratio": 0.62, "volume_ratio": 1.4},
        },
        "liquidity": {"ok": True, "score": 80.0, "reason": "liquidity_distance_ok", "details": {}},
        "market_regime": {
            "ok": True,
            "score": 70.0,
            "reason": "market_regime_high_volatility",
            "details": {"market_regime": "HIGH_VOLATILITY"},
        },
    }


def test_build_modular_signal_row_only_tracks_send_or_paper_only() -> None:
    snapshot = SimpleNamespace(close=100.0)

    row = build_modular_signal_row(
        timestamp="2026-01-01T00:00:00+00:00",
        symbol="BTCUSDT",
        snapshot=snapshot,
        modular_decision=modular_decision("SEND"),
        legacy_decision=legacy_decision(),
        module_diagnostics=module_diagnostics(),
    )

    assert row is not None
    assert row["modular_decision"] == "SEND"
    assert row["legacy_decision"] == "REJECT"
    assert row["entry_price"] == 100.0
    assert row["trend_ok"] is True
    assert row["rsi"] == 55.0

    rejected = build_modular_signal_row(
        timestamp="2026-01-01T00:00:00+00:00",
        symbol="BTCUSDT",
        snapshot=snapshot,
        modular_decision=modular_decision("REJECT"),
        legacy_decision=legacy_decision(),
        module_diagnostics=module_diagnostics(),
    )

    assert rejected is None


def test_modular_signal_store_deduplicates_pending_similar_entries(tmp_path) -> None:
    store = ModularSignalStore(tmp_path, price_tolerance_pct=0.001)
    base = {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "symbol": "BTCUSDT",
        "direction": "long",
        "entry_price": 100.0,
        "modular_decision": "PAPER_ONLY",
        "modular_score": 73.75,
        "legacy_decision": "REJECT",
        "module_scores": "{}",
        "trend_ok": True,
        "momentum_ok": True,
        "liquidity_ok": True,
        "market_regime": "HIGH_VOLATILITY",
        "rsi": 55.0,
        "body_ratio": 0.62,
        "volume_ratio": 1.4,
    }

    assert store.upsert_signal(base) is True
    assert store.upsert_signal({**base, "entry_price": 100.05}) is False
    assert store.duplicate_skipped_count == 1
    assert len(store.list_signals()) == 1

    summary = store.build_summary()
    assert summary["modular_detected"] == 1
    assert summary["by_modular_decision"] == {"PAPER_ONLY": 1}
    assert summary["by_direction"] == {"long": 1}
    assert summary["by_score"] == {"65-79": 1}
