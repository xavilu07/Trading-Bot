from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from trading_signals.risk.protection_engine import ProtectionEngineConfig, evaluate_protection_engine


NOW = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def base_context(**overrides):
    context = {
        "market_regime": "TRENDING",
        "session": "LONDON",
        "entry_context": "BREAKOUT",
        "trade_location": "mid_range",
    }
    context.update(overrides)
    return context


def test_protection_engine_defaults_to_shadow_only_without_enforcement(tmp_path: Path) -> None:
    result = evaluate_protection_engine(
        data_path=tmp_path,
        symbol="BTCUSDT",
        direction="long",
        setup_type="MAIN_SIGNAL",
        setup_context=base_context(),
        now=NOW,
    )

    assert result["protection_mode"] == "shadow_only"
    assert result["protection_triggered"] is False
    assert result["protection_enforced"] is False


def test_symbol_loss_cooldown_triggers_after_recent_loss(tmp_path: Path) -> None:
    write_csv(
        tmp_path / "paper_trading" / "trades.csv",
        [
            {
                "symbol": "BTCUSDT",
                "direction": "long",
                "setup_type": "MAIN_SIGNAL",
                "status": "sl_hit",
                "result_r": "-1",
                "closed_at": (NOW - timedelta(hours=1)).isoformat(),
            }
        ],
    )

    result = evaluate_protection_engine(
        data_path=tmp_path,
        symbol="BTCUSDT",
        direction="long",
        setup_type="MAIN_SIGNAL",
        setup_context=base_context(),
        config=ProtectionEngineConfig(symbol_loss_cooldown_hours=6),
        now=NOW,
    )

    assert result["protection_triggered"] is True
    assert "symbol_loss_cooldown" in result["protection_reasons"]
    assert result["protection_enforced"] is False


def test_symbol_rejection_cooldown_triggers_after_repeated_rejections(tmp_path: Path) -> None:
    write_jsonl(
        tmp_path / "bot_activity" / "signals_log.jsonl",
        [
            {
                "symbol": "ETHUSDT",
                "status": "rejected",
                "timestamp": (NOW - timedelta(hours=2)).isoformat(),
            },
            {
                "symbol": "ETHUSDT",
                "status": "no_trade",
                "timestamp": (NOW - timedelta(hours=1)).isoformat(),
            },
        ],
    )

    result = evaluate_protection_engine(
        data_path=tmp_path,
        symbol="ETHUSDT",
        direction="short",
        setup_type="MAIN_SIGNAL",
        setup_context=base_context(),
        config=ProtectionEngineConfig(symbol_rejection_threshold=2),
        now=NOW,
    )

    assert "symbol_rejection_cooldown" in result["protection_reasons"]


def test_max_drawdown_guard_triggers_on_negative_window(tmp_path: Path) -> None:
    write_csv(
        tmp_path / "live_trading" / "trades.csv",
        [
            {
                "symbol": "BTCUSDT",
                "direction": "long",
                "setup_type": "MAIN_SIGNAL",
                "status": "sl_hit",
                "result_r": "-2.5",
                "closed_at": (NOW - timedelta(days=1)).isoformat(),
            },
            {
                "symbol": "ETHUSDT",
                "direction": "long",
                "setup_type": "MAIN_SIGNAL",
                "status": "sl_hit",
                "result_r": "-2.0",
                "closed_at": (NOW - timedelta(days=2)).isoformat(),
            },
        ],
    )

    result = evaluate_protection_engine(
        data_path=tmp_path,
        symbol="SOLUSDT",
        direction="long",
        setup_type="MAIN_SIGNAL",
        setup_context=base_context(),
        config=ProtectionEngineConfig(max_drawdown_guard_r=4.0),
        now=NOW,
    )

    assert "max_drawdown_guard" in result["protection_reasons"]


def test_low_profit_context_lock_triggers_for_bad_context(tmp_path: Path) -> None:
    rows = []
    for idx in range(5):
        rows.append(
            {
                "symbol": "AVAXUSDT",
                "direction": "long",
                "setup_type": "MAIN_SIGNAL",
                "market_regime": "TRENDING",
                "session": "LONDON",
                "entry_context": "BREAKOUT",
                "trade_location": "mid_range",
                "status": "sl_hit",
                "result_r": "-0.5",
                "closed_at": (NOW - timedelta(days=idx)).isoformat(),
            }
        )
    write_csv(tmp_path / "paper_trading" / "trades.csv", rows)

    result = evaluate_protection_engine(
        data_path=tmp_path,
        symbol="AVAXUSDT",
        direction="long",
        setup_type="MAIN_SIGNAL",
        setup_context=base_context(),
        config=ProtectionEngineConfig(low_profit_min_trades=5, low_profit_min_avg_r=-0.2),
        now=NOW,
    )

    assert "low_profit_context_lock" in result["protection_reasons"]


def test_toxic_context_guard_flags_new_york_and_high_volatility_long(tmp_path: Path) -> None:
    result = evaluate_protection_engine(
        data_path=tmp_path,
        symbol="BTCUSDT",
        direction="long",
        setup_type="MAIN_SIGNAL",
        setup_context=base_context(session="NEW_YORK", market_regime="HIGH_VOLATILITY"),
        now=NOW,
    )

    assert "toxic_context_guard" in result["protection_reasons"]
    trigger = next(item for item in result["triggers"] if item["protection_reason"] == "toxic_context_guard")
    assert trigger["toxic_reasons"] == ["session_new_york", "high_volatility_long"]


def test_enforce_paper_mode_marks_enforced_without_changing_callers(tmp_path: Path) -> None:
    result = evaluate_protection_engine(
        data_path=tmp_path,
        symbol="BTCUSDT",
        direction="long",
        setup_type="MAIN_SIGNAL",
        setup_context=base_context(session="NEW_YORK"),
        config=ProtectionEngineConfig(mode="enforce_paper"),
        now=NOW,
    )

    assert result["protection_triggered"] is True
    assert result["protection_enforced"] is True
