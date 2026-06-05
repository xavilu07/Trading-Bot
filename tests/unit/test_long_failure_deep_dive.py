from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.long_failure_deep_dive import (
    analyze_long_failure_deep_dive,
    write_long_failure_deep_dive_report,
)


def test_long_failure_deep_dive_classifies_toxic_long_performance(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "long", -1.0, session="LONDON", setup="MAIN_SIGNAL"),
            _trade(2, "ETHUSDT", "long", -1.0, session="NEW_YORK", setup="SECONDARY_SIGNAL"),
            _trade(3, "SOLUSDT", "long", 0.5, session="LONDON", setup="MAIN_SIGNAL"),
            _trade(4, "BNBUSDT", "short", 1.5, session="LONDON", setup="MAIN_SIGNAL"),
        ],
    )

    result = analyze_long_failure_deep_dive(data_path=data_path)

    assert result["classification"] == "TOXIC"
    assert result["long_metrics"]["total_r"] == -1.5
    assert result["short_metrics"]["total_r"] == 1.5
    assert result["breakdowns"]["session"]["NEW_YORK"]["classification"] == "NEUTRAL"
    assert result["longs_destroying_money"]


def test_long_failure_deep_dive_finds_profitable_long_subset(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "long", 1.5, session="LONDON", setup="MAIN_SIGNAL", score=92),
            _trade(2, "BTCUSDT", "long", 1.0, session="LONDON", setup="MAIN_SIGNAL", score=91),
            _trade(3, "ETHUSDT", "long", -1.0, session="NEW_YORK", setup="SECONDARY_SIGNAL", score=65),
            _trade(4, "SOLUSDT", "long", 1.5, session="LONDON", setup="MAIN_SIGNAL", score=88),
        ],
    )

    result = analyze_long_failure_deep_dive(data_path=data_path)

    assert result["classification"] == "PROMISING"
    assert result["breakdowns"]["symbol"]["BTCUSDT"]["classification"] == "PROMISING"
    assert any(row["value"] == "BTCUSDT" for row in result["longs_working"])


def test_long_failure_deep_dive_breaks_down_reasons_and_main_vs_secondary(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "long", -1.0, setup="MAIN_SIGNAL", reasons="against_htf", penalties="market_structure_range_penalty"),
            _trade(2, "ETHUSDT", "long", 1.5, setup="SECONDARY_SIGNAL", warnings="low_volume"),
            _trade(3, "SOLUSDT", "short", -1.0, setup="SECONDARY_SIGNAL"),
        ],
    )

    result = analyze_long_failure_deep_dive(data_path=data_path)

    reasons = result["breakdowns"]["related_rejection_reasons"]
    assert "against_htf" in reasons
    assert "market_structure_range_penalty" in reasons
    assert "low_volume" in reasons
    assert result["main_vs_secondary"]["all_trades"]["SECONDARY_SIGNAL"]["metrics"]["trades"] == 2
    assert result["main_vs_secondary"]["long_only"]["MAIN_SIGNAL"]["metrics"]["trades"] == 1


def test_long_failure_deep_dive_report_is_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade(1, "BTCUSDT", "long", 1.5)])

    result = analyze_long_failure_deep_dive(data_path=data_path)
    path = write_long_failure_deep_dive_report(result, tmp_path / "reports")

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "LONG_FAILURE_DEEP_DIVE" in text
    assert "LONG vs SHORT" in text


def _trade(
    index: int,
    symbol: str,
    direction: str,
    result_r: float,
    *,
    session: str = "LONDON",
    setup: str = "MAIN_SIGNAL",
    regime: str = "TRENDING",
    score: float = 90,
    reasons: str = "",
    warnings: str = "",
    penalties: str = "",
) -> dict[str, object]:
    return {
        "trade_id": f"trade-{index}",
        "symbol": symbol,
        "direction": direction,
        "setup_type": setup,
        "market_regime": regime,
        "session": session,
        "entry_context": "PULLBACK",
        "trade_location": "mid_range",
        "score": score,
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "opened_at": "2026-06-01T12:00:00+00:00",
        "closed_at": "2026-06-01T13:00:00+00:00",
        "rejection_reasons": reasons,
        "warnings": warnings,
        "penalties": penalties,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
