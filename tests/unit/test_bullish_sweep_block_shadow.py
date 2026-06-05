from __future__ import annotations

import csv
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path

from trading_signals.research import bullish_sweep_block_shadow
from trading_signals.research.bullish_sweep_block_shadow import (
    analyze_bullish_sweep_block_shadow,
    generate_bullish_sweep_block_shadow,
)


def test_bullish_sweep_block_shadow_detects_bullish_sweep_trades_and_candidates(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", -1.0, liquidity_sweep="bullish_sweep"),
            _trade(2, "ETHUSDT", 1.5, liquidity_sweep="bearish_sweep"),
        ],
    )
    _write_jsonl(
        data_path / "bot_activity" / "signals_log.jsonl",
        [
            {
                "timestamp": "2026-06-01T12:00:00+00:00",
                "symbol": "SOLUSDT",
                "direction": "long",
                "liquidity_context": "sweep:bullish_sweep",
                "score": 80,
                "status": "no_trade",
            }
        ],
    )

    result = analyze_bullish_sweep_block_shadow(data_path=data_path, now=datetime(2026, 6, 5, tzinfo=timezone.utc))

    assert result["records_total"] == 2
    assert result["closed_records"] == 1
    assert result["by_symbol"]["BTCUSDT"]["closed"] == 1
    assert result["by_symbol"]["SOLUSDT"]["closed"] == 0


def test_bullish_sweep_block_shadow_writes_csv_and_report(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade(1, "BTCUSDT", -1.0, liquidity_sweep="bullish_sweep")])

    result = generate_bullish_sweep_block_shadow(data_path=data_path, reports_path=reports_path, now=datetime(2026, 6, 5, tzinfo=timezone.utc))

    csv_path = Path(result["shadow_csv_path"])
    report_path = Path(result["report_path"])
    assert csv_path.exists()
    assert report_path.exists()
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8", newline="")))
    assert rows[0]["symbol"] == "BTCUSDT"
    assert "BULLISH_SWEEP_BLOCK_SHADOW" in report_path.read_text(encoding="utf-8")


def test_bullish_sweep_block_shadow_computes_avoided_r_and_should_block(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", 1.5),
            _trade(2, "ETHUSDT", -1.0),
            *[_trade(index + 10, f"BAD{index}", -1.0, liquidity_sweep="bullish_sweep") for index in range(5)],
        ],
    )

    result = analyze_bullish_sweep_block_shadow(data_path=data_path, now=datetime(2026, 6, 5, tzinfo=timezone.utc))

    assert result["blocked_bullish_sweep"]["total_r"] == -5.0
    assert result["r_avoided"] == 5.0
    assert result["comparison"]["total_r_delta"] == 5.0
    assert result["classification"] == "SHOULD_BLOCK"


def test_bullish_sweep_block_shadow_does_not_touch_public_sending() -> None:
    source = inspect.getsource(bullish_sweep_block_shadow)

    assert "publish_signal" not in source
    assert "telegram" not in source.lower()
    assert "public_published" not in source


def _trade(index: int, symbol: str, result_r: float, *, liquidity_sweep: str = "", liquidity_context: str = "") -> dict[str, object]:
    return {
        "trade_id": f"trade-{index}",
        "symbol": symbol,
        "direction": "long",
        "setup_type": "MAIN_SIGNAL",
        "score": 80,
        "market_regime": "TRENDING",
        "session": "LONDON",
        "entry_context": "PULLBACK",
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "opened_at": "2026-06-01T12:00:00+00:00",
        "closed_at": "2026-06-01T13:00:00+00:00",
        "liquidity_sweep": liquidity_sweep,
        "liquidity_context": liquidity_context,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
