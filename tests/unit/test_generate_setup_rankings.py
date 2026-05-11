from __future__ import annotations

import csv
from pathlib import Path

from scripts.generate_setup_rankings import (
    build_setup_rankings,
    format_setup_rankings,
    generate_setup_rankings,
    load_closed_trades,
)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_setup_rankings_empty_csv_does_not_break(tmp_path: Path) -> None:
    result = generate_setup_rankings(tmp_path / "data", tmp_path / "reports", min_trades=1)

    assert result["trades"] == 0
    assert result["single"] == []
    assert result["combinations"] == []
    assert (tmp_path / "reports" / "setup_rankings.csv").exists()
    assert (tmp_path / "reports" / "setup_combinations_rankings.csv").exists()
    assert "sin datos" in format_setup_rankings(result)


def test_setup_rankings_builds_simple_rankings_from_paper_and_live(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            {
                "symbol": "BTCUSDT",
                "direction": "long",
                "setup_type": "MAIN_SIGNAL",
                "market_regime": "TRENDING",
                "session": "LONDON",
                "entry_context": "BREAKOUT",
                "trade_location": "near_support",
                "liquidity_sweep": "yes",
                "warnings": '["low_volume"]',
                "penalties": '["distance_to_liquidity_penalty"]',
                "status": "tp2_hit",
                "result_r": "2",
            },
            {
                "symbol": "ETHUSDT",
                "direction": "short",
                "setup_type": "SECONDARY_SIGNAL",
                "market_regime": "RANGING",
                "session": "NEW_YORK",
                "entry_context": "PULLBACK",
                "trade_location": "near_resistance",
                "liquidity_sweep": "no",
                "warnings": '["dirty_sideways_market"]',
                "penalties": '["timeframe_alignment_penalty"]',
                "status": "sl_hit",
                "result_r": "-1",
            },
        ],
    )
    write_csv(
        data_path / "live_trading" / "trades.csv",
        [
            {
                "symbol": "SOLUSDT",
                "direction": "long",
                "setup_type": "MAIN_SIGNAL",
                "market_regime": "TRENDING",
                "session": "LONDON",
                "entry_context": "BREAKOUT",
                "trade_location": "near_support",
                "liquidity_sweep": "yes",
                "warnings": "[]",
                "penalties": "[]",
                "status": "tp_hit",
                "result_r": "1.5",
            }
        ],
    )

    trades = load_closed_trades(data_path)
    rankings = build_setup_rankings(trades, min_trades=1)
    setup_rows = [row for row in rankings["single"] if row["ranking_type"] == "setup_type"]
    main = next(row for row in setup_rows if row["group"] == "MAIN_SIGNAL")

    assert len(trades) == 3
    assert main["trades"] == 2
    assert main["winrate"] == 100.0
    assert main["total_r"] == 3.5
    assert main["long_trades"] == 2
    assert main["main_signal_trades"] == 2


def test_setup_rankings_builds_combinations_and_token_groups(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            {
                "direction": "long",
                "setup_type": "SECONDARY_SIGNAL",
                "market_regime": "TRENDING",
                "session": "LONDON",
                "entry_context": "BREAKOUT",
                "liquidity_sweep": "no",
                "warnings": '["low_volume", "spread_high"]',
                "penalties": "distance_to_liquidity_penalty|market_structure_range_penalty",
                "status": "tp2_hit",
                "result_r": "2",
            }
        ],
    )

    result = generate_setup_rankings(data_path, tmp_path / "reports", min_trades=1)
    combo = result["combinations"]

    assert any(row["ranking_type"] == "setup_type+direction" and row["group"] == "SECONDARY_SIGNAL|long" for row in combo)
    assert any(row["ranking_type"] == "setup_type+liquidity_sweep" and row["group"] == "SECONDARY_SIGNAL|no" for row in combo)
    assert any(row["ranking_type"] == "warnings" and row["group"] == "low_volume" for row in combo)
    assert any(row["ranking_type"] == "penalties" and row["group"] == "distance_to_liquidity_penalty" for row in combo)


def test_setup_rankings_tolerates_missing_columns(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_csv(
        data_path / "paper_trading" / "old.csv",
        [
            {"direction": "long", "status": "tp_hit", "result_r": "1.5"},
            {"status": "sl_hit", "result_r": "-1"},
        ],
    )

    result = generate_setup_rankings(data_path, tmp_path / "reports", min_trades=1)

    assert result["trades"] == 2
    assert any(row["ranking_type"] == "direction" and row["group"] == "long" for row in result["single"])
    assert any(row["ranking_type"] == "setup_type" and row["group"] == "UNKNOWN" for row in result["single"])


def test_setup_rankings_dry_run_does_not_write_reports(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_csv(data_path / "paper_trading" / "trades.csv", [{"status": "tp_hit", "result_r": "1"}])

    result = generate_setup_rankings(data_path, tmp_path / "reports", dry_run=True)

    assert result["trades"] == 1
    assert not (tmp_path / "reports" / "setup_rankings.csv").exists()

