from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.winner_dna_2_super_survivor_analysis import (
    analyze_winner_dna_2_super_survivor,
    classify_survivor_set,
    write_winner_dna_2_super_survivor_reports,
)


def test_excludes_existing_production_blocks_from_baseline(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "BTCUSDT", "long", -1.0, liquidity_sweep="bullish_sweep") for index in range(5)]
    rows.extend(_trade(index + 10, "ETHUSDT", "long", -1.0, warnings="against_htf", entry_context="BREAKOUT") for index in range(5))
    rows.extend(_trade(index + 20, "SOLUSDT", "short", 1.0, setup="SECONDARY_SIGNAL", session="LONDON") for index in range(10))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_winner_dna_2_super_survivor(data_path=data_path, min_trades=5)

    assert result["baseline_after_production_blocks"]["trades"] == 10
    assert result["excluded_metrics"]["trades"] == 10
    assert "bullish_sweep" not in result["breakdowns"]["liquidity_sweep"]


def test_finds_super_survivors_and_classifies_elite(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "SOLUSDT", "short", 2.0, setup="SECONDARY_SIGNAL", session="LONDON", location="near_resistance") for index in range(10)]
    rows.extend(_trade(index + 20, "BTCUSDT", "long", -1.0, setup="MAIN_SIGNAL", session="ASIA") for index in range(4))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_winner_dna_2_super_survivor(data_path=data_path, min_trades=10)

    assert result["super_survivors"]
    assert any(row["dimension"] == "session" and row["value"] == "LONDON" for row in result["super_survivors"])
    assert result["super_survivors"][0]["survivor_classification"] == "ELITE"
    assert result["answers"]["near_resistance_edge"].startswith("YES")


def test_finds_multi_factor_dna_candidates(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(index, "SOLUSDT", "short", 1.0, setup="SECONDARY_SIGNAL", session="LONDON", regime="TRENDING", location="near_resistance", score=95)
        for index in range(12)
    ]
    rows.extend(_trade(index + 20, "XRPUSDT", "long", -1.0, setup="MAIN_SIGNAL", session="ASIA", regime="RANGING", score=65) for index in range(6))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_winner_dna_2_super_survivor(data_path=data_path, min_trades=10)

    assert result["multi_factor_dna_top_20"]
    assert any("setup_type=SECONDARY_SIGNAL" in row["combination"] for row in result["multi_factor_dna_top_20"])
    assert result["answers"]["secondary_signal_superior"].startswith("YES")
    assert result["answers"]["score_90_plus_confirmed_edge"].startswith("YES")


def test_what_if_analysis_calculates_elite_and_top_contexts(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "SOLUSDT", "short", 1.5, setup="SECONDARY_SIGNAL", session="LONDON", location="near_resistance") for index in range(10)]
    rows.extend(_trade(index + 20, "ETHUSDT", "short", 0.7, setup="MAIN_SIGNAL", session="OVERLAP", location="mid_range") for index in range(10))
    rows.extend(_trade(index + 40, "BTCUSDT", "long", -1.0, setup="MAIN_SIGNAL", session="ASIA") for index in range(5))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_winner_dna_2_super_survivor(data_path=data_path, min_trades=10)
    what_if = result["what_if_analysis"]

    assert what_if["only_elite"]["trades"] >= 10
    assert float(what_if["only_elite"]["profit_factor"]) > 1.8
    assert what_if["only_elite_and_strong"]["trades"] >= what_if["only_elite"]["trades"]
    assert what_if["only_top_20_percent_contexts"]["trades"] > 0


def test_classification_helper() -> None:
    assert classify_survivor_set({"trades": 4, "total_r": 10, "profit_factor": 3}) == "NO_EDGE"
    assert classify_survivor_set({"trades": 10, "total_r": -1, "profit_factor": 2}) == "NO_EDGE"
    assert classify_survivor_set({"trades": 10, "total_r": 2, "profit_factor": 1.21}) == "PROMISING"
    assert classify_survivor_set({"trades": 10, "total_r": 2, "profit_factor": 1.41}) == "STRONG"
    assert classify_survivor_set({"trades": 10, "total_r": 2, "profit_factor": 1.81}) == "ELITE"


def test_report_markdown_and_json_are_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade(1, "SOLUSDT", "short", 1.0, setup="SECONDARY_SIGNAL")])

    result = analyze_winner_dna_2_super_survivor(data_path=data_path, min_trades=1)
    paths = write_winner_dna_2_super_survivor_reports(result, tmp_path / "reports")

    assert paths["markdown"].exists()
    assert paths["json"].exists()
    markdown = paths["markdown"].read_text(encoding="utf-8")
    json_text = paths["json"].read_text(encoding="utf-8")
    assert "WINNER_DNA_2_0_SUPER_SURVIVOR_ANALYSIS" in markdown
    assert "Super Survivors" in markdown
    assert "WINNER_DNA_2_0_SUPER_SURVIVOR_ANALYSIS" in json_text


def _trade(
    index: int,
    symbol: str,
    direction: str,
    result_r: float,
    *,
    session: str = "LONDON",
    regime: str = "TRENDING",
    setup: str = "MAIN_SIGNAL",
    score: float = 90,
    entry_context: str = "PULLBACK",
    location: str = "mid_range",
    liquidity_sweep: str = "",
    warnings: str = "",
    penalties: str = "",
    trend_entry: str = "",
    trend_higher: str = "",
) -> dict[str, object]:
    return {
        "trade_id": f"trade-{index}",
        "symbol": symbol,
        "direction": direction,
        "setup_type": setup,
        "market_regime": regime,
        "session": session,
        "entry_context": entry_context,
        "trade_location": location,
        "score": score,
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "opened_at": "2026-06-01T12:00:00+00:00",
        "closed_at": "2026-06-01T13:00:00+00:00",
        "liquidity_sweep": liquidity_sweep,
        "warnings": warnings,
        "penalties": penalties,
        "trend_entry": trend_entry,
        "trend_higher": trend_higher,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
