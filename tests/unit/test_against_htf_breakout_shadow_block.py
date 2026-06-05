from __future__ import annotations

import csv
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path

from trading_signals.research import against_htf_breakout_shadow_block
from trading_signals.research.against_htf_breakout_shadow_block import (
    analyze_against_htf_breakout_shadow_block,
    generate_against_htf_breakout_shadow_block,
)


def test_against_htf_breakout_shadow_detects_against_htf_breakout(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", -1.0, warnings="against_htf", entry_context="BREAKOUT"),
            _trade(2, "ETHUSDT", -1.0, warnings="against_htf", entry_context="PULLBACK"),
            _trade(3, "SOLUSDT", -1.0, entry_context="BREAKOUT"),
            _trade(4, "ADAUSDT", -1.0, entry_context="BREAKOUT", direction="long", trend_higher="bearish"),
        ],
    )

    result = analyze_against_htf_breakout_shadow_block(data_path=data_path, now=datetime(2026, 6, 5, tzinfo=timezone.utc))

    assert result["records_total"] == 2
    assert result["closed_records"] == 2
    assert result["by_symbol"]["BTCUSDT"]["closed"] == 1
    assert result["by_symbol"]["ADAUSDT"]["closed"] == 1
    assert "ETHUSDT" not in result["by_symbol"]
    assert "SOLUSDT" not in result["by_symbol"]


def test_against_htf_breakout_shadow_detects_signal_candidates(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_jsonl(
        data_path / "bot_activity" / "signals_log.jsonl",
        [
            {
                "timestamp": "2026-06-01T12:00:00+00:00",
                "symbol": "BTCUSDT",
                "direction": "long",
                "entry_context": "BREAKOUT",
                "warnings": ["against_htf"],
                "score": 85,
            },
            {
                "timestamp": "2026-06-01T12:00:00+00:00",
                "symbol": "ETHUSDT",
                "direction": "long",
                "entry_context": "PULLBACK",
                "warnings": ["against_htf"],
                "score": 85,
            },
        ],
    )

    result = analyze_against_htf_breakout_shadow_block(data_path=data_path, now=datetime(2026, 6, 5, tzinfo=timezone.utc))

    assert result["records_total"] == 1
    assert result["records"][0]["source"] == "signals_log"
    assert result["records"][0]["symbol"] == "BTCUSDT"


def test_against_htf_breakout_shadow_writes_csv_and_report(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade(1, "BTCUSDT", -1.0, warnings="against_htf", entry_context="BREAKOUT")])

    result = generate_against_htf_breakout_shadow_block(data_path=data_path, reports_path=reports_path, now=datetime(2026, 6, 5, tzinfo=timezone.utc))

    csv_path = Path(result["shadow_csv_path"])
    report_path = Path(result["report_path"])
    assert csv_path.exists()
    assert report_path.exists()
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8", newline="")))
    assert rows[0]["symbol"] == "BTCUSDT"
    assert "AGAINST_HTF_BREAKOUT_SHADOW_BLOCK" in report_path.read_text(encoding="utf-8")


def test_against_htf_breakout_shadow_computes_r_avoided_and_recommendation(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, f"BAD{index}", -1.0, warnings="against_htf", entry_context="BREAKOUT") for index in range(5)]
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_against_htf_breakout_shadow_block(data_path=data_path, now=datetime(2026, 6, 5, tzinfo=timezone.utc))

    assert result["blocked_group_metrics"]["total_r"] == -5.0
    assert result["hypothetical_r_avoided"] == 5.0
    assert result["recommendation"] == "CONTINUE_SHADOW"


def test_against_htf_breakout_shadow_does_not_touch_public_sending() -> None:
    source = inspect.getsource(against_htf_breakout_shadow_block)

    assert "publish_signal" not in source
    assert "telegram" not in source.lower()
    assert "public_published" not in source


def _trade(
    index: int,
    symbol: str,
    result_r: float,
    *,
    direction: str = "long",
    warnings: str = "",
    reasons: str = "",
    penalties: str = "",
    entry_context: str = "BREAKOUT",
    trend_higher: str = "",
) -> dict[str, object]:
    return {
        "trade_id": f"trade-{index}",
        "symbol": symbol,
        "direction": direction,
        "setup_type": "MAIN_SIGNAL",
        "score": 85,
        "market_regime": "TRENDING",
        "session": "LONDON",
        "entry_context": entry_context,
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "opened_at": "2026-06-01T12:00:00+00:00",
        "closed_at": "2026-06-01T13:00:00+00:00",
        "warnings": warnings,
        "rejection_reasons": reasons,
        "penalties": penalties,
        "trend_higher": trend_higher,
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
