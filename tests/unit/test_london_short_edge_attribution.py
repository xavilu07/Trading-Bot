from __future__ import annotations

import csv
import json
from pathlib import Path

from trading_signals.research.london_short_edge_attribution import (
    analyze_london_short_edge_attribution,
    load_london_short_research_rows,
    write_london_short_edge_reports,
)


def test_london_short_edge_detects_positive_and_negative_drivers() -> None:
    rows = []
    for index in range(5):
        rows.append(_row(result_r=1.0, setup_type="MAIN_SIGNAL", entry_context="PULLBACK", score=85))
    for index in range(5):
        rows.append(_row(result_r=-1.0, setup_type="SECONDARY_SIGNAL", entry_context="BREAKOUT", score=72))

    result = analyze_london_short_edge_attribution(rows, min_trades=5)

    assert result["closed_trades"] == 10
    assert any(row["feature"] == "setup_type" and row["value"] == "MAIN_SIGNAL" for row in result["top_positive_drivers"])
    assert any(row["feature"] == "setup_type" and row["value"] == "SECONDARY_SIGNAL" for row in result["top_negative_drivers"])
    assert result["recommended_rules"]
    assert "do_not_enable_all_shorts_globally" in result["what_not_to_change"]


def test_london_short_edge_filters_to_london_short_only() -> None:
    rows = [
        _row(result_r=1.0, direction="short", session="LONDON"),
        _row(result_r=1.0, direction="long", session="LONDON"),
        _row(result_r=1.0, direction="short", session="NEW_YORK"),
    ]

    result = analyze_london_short_edge_attribution(rows, min_trades=1)

    assert result["rows_analyzed"] == 1
    assert result["closed_trades"] == 1


def test_london_short_edge_loads_only_canonical_trades(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [_row(result_r=1.0, direction="short", session="LONDON", setup_type="MAIN_SIGNAL")],
    )
    signal_log = data_path / "bot_activity" / "signals_log.jsonl"
    signal_log.parent.mkdir(parents=True, exist_ok=True)
    signal_log.write_text(json.dumps({"symbol": "BTCUSDT", "direction": "short", "session": "LONDON"}) + "\n", encoding="utf-8")
    _write_csv(
        reports_path / "meta_dataset.csv",
        [_row(result_r=-1.0, direction="short", session="LONDON", setup_type="SECONDARY_SIGNAL", label="0")],
    )

    rows = load_london_short_research_rows(data_path, reports_path)

    assert len(rows) == 1
    assert rows[0]["source"].endswith("paper_trading/trades.csv")


def test_london_short_edge_writes_reports(tmp_path: Path) -> None:
    result = analyze_london_short_edge_attribution([_row(result_r=1.0)], min_trades=1)
    paths = write_london_short_edge_reports(result, tmp_path / "reports")

    assert paths["json_path"].exists()
    assert paths["csv_path"].exists()
    assert paths["summary_path"].exists()


def _row(
    *,
    result_r: float | None,
    direction: str = "short",
    session: str = "LONDON",
    setup_type: str = "MAIN_SIGNAL",
    entry_context: str = "PULLBACK",
    market_regime: str = "TRENDING",
    trade_location: str = "mid_range",
    score: float = 80,
    label: str | None = None,
) -> dict[str, object]:
    row = {
        "symbol": "TESTUSDT",
        "direction": direction,
        "session": session,
        "setup_type": setup_type,
        "entry_context": entry_context,
        "market_regime": market_regime,
        "trade_location": trade_location,
        "score": score,
        "status": "tp_hit" if result_r and result_r > 0 else "sl_hit",
        "result_r": result_r,
        "volume_ratio": 1.3,
        "body_ratio": 0.55,
        "risk_reward": 2.0,
        "trend_entry": "bearish",
        "trend_higher": "bearish",
        "penalties": ["market_structure_range_penalty"] if setup_type == "SECONDARY_SIGNAL" else [],
    }
    if label is not None:
        row["label"] = label
    return row


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
