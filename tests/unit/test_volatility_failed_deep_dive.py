from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from trading_signals.research.volatility_failed_deep_dive import (
    analyze_volatility_failed_deep_dive,
    write_volatility_failed_deep_dive_report,
)


def test_volatility_failed_deep_dive_filters_tracked_candidates_and_groups(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_jsonl(
        data_path / "bot_activity" / "signals_log.jsonl",
        [
            _signal("BTCUSDT", "short", "no_trade", "2026-06-01T10:00:00+00:00", "vol-a", score=92),
            _signal("ETHUSDT", "short", "no_trade", "2026-06-01T10:15:00+00:00", "vol-b", score=90),
            _signal("SOLUSDT", "short", "no_trade", "2026-06-01T10:30:00+00:00", "other", reason="against_htf"),
        ],
    )
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade("vol-a", "BTCUSDT", "short", 1.5),
            _trade("vol-b", "ETHUSDT", "short", -1.0),
        ],
    )

    result = analyze_volatility_failed_deep_dive(
        data_path=data_path,
        now=datetime(2026, 6, 1, 12, tzinfo=timezone.utc),
    )

    assert result["count"] == 2
    assert result["metrics"]["closed"] == 2
    assert result["metrics"]["total_r"] == 0.5
    assert result["by_symbol"]["BTCUSDT"]["count"] == 1
    assert result["by_session"]["LONDON"]["count"] == 2
    assert result["by_setup"]["MAIN_SIGNAL"]["count"] == 2
    assert result["by_market_regime"]["LOW_VOLATILITY"]["count"] == 2
    assert result["by_score_bucket"]["90+"]["count"] == 2


def test_volatility_failed_deep_dive_classifies_protective_when_rejected_trades_lose(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_jsonl(
        data_path / "bot_activity" / "signals_log.jsonl",
        [
            _signal(f"SYM{index}", "short", "no_trade", f"2026-06-01T1{index}:00:00+00:00", f"loss-{index}")
            for index in range(5)
        ],
    )
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [_trade(f"loss-{index}", f"SYM{index}", "short", -1.0) for index in range(5)],
    )

    result = analyze_volatility_failed_deep_dive(data_path=data_path)

    assert result["classification"] == "PROTECTIVE"


def test_volatility_failed_deep_dive_classifies_harmful_when_rejected_trades_win(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_jsonl(
        data_path / "bot_activity" / "signals_log.jsonl",
        [
            _signal(f"SYM{index}", "short", "no_trade", f"2026-06-01T1{index}:00:00+00:00", f"win-{index}")
            for index in range(5)
        ],
    )
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [_trade(f"win-{index}", f"SYM{index}", "short", 1.5) for index in range(5)],
    )

    result = analyze_volatility_failed_deep_dive(data_path=data_path)

    assert result["classification"] == "HARMFUL"


def test_volatility_failed_deep_dive_report_is_written(tmp_path: Path) -> None:
    result = analyze_volatility_failed_deep_dive(data_path=tmp_path / "data")
    path = write_volatility_failed_deep_dive_report(result, tmp_path / "reports")

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "VOLATILITY_FAILED_DEEP_DIVE" in text
    assert "Canonical Baseline" in text


def _signal(
    symbol: str,
    direction: str,
    status: str,
    timestamp: str,
    dedupe_key: str,
    *,
    reason: str = "volatility_failed",
    score: float = 90,
) -> dict[str, object]:
    return {
        "timestamp": timestamp,
        "symbol": symbol,
        "direction": direction,
        "status": status,
        "score": score,
        "setup_type": "MAIN_SIGNAL",
        "session": "LONDON",
        "market_regime": "LOW_VOLATILITY",
        "rejection_reasons": [reason],
        "dedupe_key": dedupe_key,
    }


def _trade(dedupe_key: str, symbol: str, direction: str, result_r: float) -> dict[str, object]:
    return {
        "dedupe_key": dedupe_key,
        "trade_id": dedupe_key,
        "symbol": symbol,
        "direction": direction,
        "setup_type": "MAIN_SIGNAL",
        "session": "LONDON",
        "market_regime": "LOW_VOLATILITY",
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "closed_at": "2026-06-01T12:00:00+00:00",
        "opened_at": "2026-06-01T10:00:00+00:00",
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
