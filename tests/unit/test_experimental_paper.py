from __future__ import annotations

from trading_signals.application.use_cases.experimental_paper import (
    ExperimentalSignalStore,
    build_experimental_signal_row,
    evaluate_experimental_outcome,
    format_experimental_summary,
    mature_winrate,
    prices_are_similar,
)
from tests.unit.test_strategy_and_risk import build_snapshot


def test_experimental_signal_store_saves_and_summarizes_separate_csv(tmp_path) -> None:
    store = ExperimentalSignalStore(tmp_path)
    row = {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "symbol": "WIFUSDT",
        "direction": "long",
        "entry_price": 1.23,
        "score": 82.0,
        "original_block": "long_primary_sweep",
        "experimental_reason": "experimental_accepts_without_primary_sweep",
        "real_reason": "directional_confluence_failed",
        "market_regime": "TRENDING",
        "entry_context": "BREAKOUT",
        "rsi": 66.0,
        "body_ratio": 0.5,
        "volume_ratio": 1.3,
    }

    assert store.upsert_signal(row) is True
    assert store.upsert_signal(row) is False

    rows = store.list_signals()
    assert len(rows) == 1
    assert rows[0]["outcome"] == "pending"
    assert rows[0]["max_favorable_move"] == "0"
    assert rows[0]["max_adverse_move"] == "0"
    assert rows[0]["candles_elapsed"] == "0"
    assert (tmp_path / "paper_trading" / "experimental_signals.csv").exists()

    summary = store.build_summary()
    assert summary["experimental_detected"] == 1
    assert summary["by_direction"] == {"long": 1}
    assert summary["by_original_block"] == {"long_primary_sweep": 1}
    assert summary["by_score"] == {"80-89": 1}
    assert "Detectadas: 1" in format_experimental_summary(summary)


def test_experimental_signal_store_deduplicates_pending_similar_price(tmp_path) -> None:
    store = ExperimentalSignalStore(tmp_path, price_tolerance_pct=0.001)
    row = {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "symbol": "WIFUSDT",
        "direction": "long",
        "entry_price": 1.0,
        "score": 82.0,
        "original_block": "long_primary_sweep",
        "experimental_reason": "experimental_accepts_without_primary_sweep",
        "real_reason": "directional_confluence_failed",
        "market_regime": "TRENDING",
        "entry_context": "BREAKOUT",
        "rsi": 66.0,
        "body_ratio": 0.5,
        "volume_ratio": 1.3,
    }
    duplicate = {**row, "timestamp": "2026-01-01T01:00:00+00:00", "entry_price": 1.0005}
    far_price = {**row, "timestamp": "2026-01-01T02:00:00+00:00", "entry_price": 1.01}

    assert store.upsert_signal(row) is True
    assert store.upsert_signal(duplicate) is False
    assert store.duplicate_skipped_count == 1
    assert store.upsert_signal(far_price) is True
    assert len(store.list_signals()) == 2


def test_experimental_signal_store_allows_duplicate_after_outcome_not_pending(tmp_path) -> None:
    store = ExperimentalSignalStore(tmp_path, price_tolerance_pct=0.001)
    row = {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "symbol": "WIFUSDT",
        "direction": "long",
        "entry_price": 1.0,
        "score": 82.0,
        "original_block": "long_primary_sweep",
        "experimental_reason": "experimental_accepts_without_primary_sweep",
        "real_reason": "directional_confluence_failed",
        "market_regime": "TRENDING",
        "entry_context": "BREAKOUT",
        "rsi": 66.0,
        "body_ratio": 0.5,
        "volume_ratio": 1.3,
    }
    assert store.upsert_signal(row) is True
    rows = store.list_signals()
    rows[0]["outcome"] = "closed"
    store.save_signals(rows)

    assert store.upsert_signal({**row, "timestamp": "2026-01-01T01:00:00+00:00"}) is True
    assert len(store.list_signals()) == 2


def test_prices_are_similar_uses_percentage_tolerance() -> None:
    assert prices_are_similar(100.0, 100.09, tolerance_pct=0.001) is True
    assert prices_are_similar(100.0, 100.2, tolerance_pct=0.001) is False


def test_evaluate_experimental_outcome_marks_long_win() -> None:
    row = {"direction": "long", "entry_price": "100", "max_favorable_move": "0", "max_adverse_move": "0"}
    candles = [{"high": 102.0, "low": 99.5, "close_time": "2026-01-01T01:00:00+00:00"}]

    result = evaluate_experimental_outcome(row, candles, win_threshold=0.015, loss_threshold=0.01)

    assert result["outcome"] == "win"
    assert result["exit_reason"] == "favorable_move_reached"
    assert result["max_favorable_move"] == "0.020000"


def test_evaluate_experimental_outcome_marks_short_loss() -> None:
    row = {"direction": "short", "entry_price": "100", "max_favorable_move": "0", "max_adverse_move": "0"}
    candles = [{"high": 101.5, "low": 99.0, "close_time": "2026-01-01T01:00:00+00:00"}]

    result = evaluate_experimental_outcome(row, candles, win_threshold=0.015, loss_threshold=0.01)

    assert result["outcome"] == "loss"
    assert result["exit_reason"] == "adverse_move_reached"
    assert result["max_adverse_move"] == "0.015000"


def test_experimental_store_updates_pending_outcomes(tmp_path) -> None:
    class FakeMarketData:
        def fetch_ohlcv(self, symbol: str, interval: str, limit: int = 300):
            assert symbol == "WIFUSDT"
            assert interval == "1h"
            return [
                {
                    "open_time": "2026-01-01T00:00:00+00:00",
                    "close_time": "2026-01-01T01:00:00+00:00",
                    "high": 102.0,
                    "low": 99.5,
                }
            ]

    store = ExperimentalSignalStore(tmp_path)
    assert store.upsert_signal(
        {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "symbol": "WIFUSDT",
            "direction": "long",
            "entry_price": 100.0,
            "score": 82.0,
            "original_block": "long_primary_sweep",
            "experimental_reason": "experimental_accepts_without_primary_sweep",
            "real_reason": "directional_confluence_failed",
            "market_regime": "TRENDING",
            "entry_context": "BREAKOUT",
            "rsi": 66.0,
            "body_ratio": 0.5,
            "volume_ratio": 1.3,
        }
    )

    updated = store.update_pending_outcomes(
        FakeMarketData(),
        evaluated_at="2026-01-01T02:00:00+00:00",
    )

    assert len(updated) == 1
    row = store.list_signals()[0]
    assert row["outcome"] == "win"
    assert row["exit_reason"] == "favorable_move_reached"
    assert row["evaluated_at"] == "2026-01-01T02:00:00+00:00"


def test_mature_winrate_uses_candles_elapsed_thresholds() -> None:
    rows = [
        {"outcome": "win", "candles_elapsed": "5"},
        {"outcome": "loss", "candles_elapsed": "8"},
        {"outcome": "win", "candles_elapsed": "10"},
        {"outcome": "pending", "candles_elapsed": "12"},
        {"outcome": "loss", "candles_elapsed": "3"},
    ]

    assert mature_winrate(rows, min_candles=5) == {
        "min_candles": 5,
        "eligible": 4,
        "closed": 3,
        "wins": 2,
        "losses": 1,
        "winrate": 66.67,
    }
    assert mature_winrate(rows, min_candles=10) == {
        "min_candles": 10,
        "eligible": 2,
        "closed": 1,
        "wins": 1,
        "losses": 0,
        "winrate": 100.0,
    }


def test_build_experimental_signal_row_only_when_would_send() -> None:
    snapshot = build_snapshot(
        scan_run_id="run_test",
        symbol="WIFUSDT",
        timeframe="1h",
        trend="bullish",
        structure="bullish",
        sweep="none",
        score=90.0,
        distance=1.0,
    )
    diagnostics = {
        "experimental_decision_engine": {
            "details": {
                "would_send_signal": True,
                "direction": "long",
                "score": 82.0,
                "original_blocking_filter": "long_primary_sweep",
                "experimental_reason": "experimental_accepts_without_primary_sweep",
            }
        },
        "momentum": {"details": {"rsi": 66.0, "body_ratio": 0.5, "volume_ratio": 1.3}},
        "market_regime": {"details": {"market_regime": "TRENDING", "entry_context": "BREAKOUT"}},
        "strategy_gate": {"details": {"reason_final": "directional_confluence_failed"}},
    }

    row = build_experimental_signal_row(
        timestamp="2026-01-01T00:00:00+00:00",
        symbol="WIFUSDT",
        snapshot=snapshot,
        module_diagnostics=diagnostics,
    )

    assert row is not None
    assert row["symbol"] == "WIFUSDT"
    assert row["entry_price"] == snapshot.close
    assert row["original_block"] == "long_primary_sweep"

    diagnostics["experimental_decision_engine"]["details"]["would_send_signal"] = False
    assert build_experimental_signal_row(
        timestamp="2026-01-01T00:00:00+00:00",
        symbol="WIFUSDT",
        snapshot=snapshot,
        module_diagnostics=diagnostics,
    ) is None
