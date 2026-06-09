from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.main_signal_long_dna import (
    analyze_main_signal_long_dna,
    classify_main_signal_long,
    classify_partial_block,
    write_main_signal_long_dna_report,
)


def test_main_signal_long_dna_filters_main_signal_long_only(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "long", "MAIN_SIGNAL", 1.5),
            _trade(2, "ETHUSDT", "long", "SECONDARY_SIGNAL", 1.5),
            _trade(3, "SOLUSDT", "short", "MAIN_SIGNAL", 1.5),
        ],
    )

    result = analyze_main_signal_long_dna(data_path=data_path)

    assert result["main_signal_long_metrics"]["trades"] == 1
    assert result["main_signal_short_metrics"]["trades"] == 1
    assert "BTCUSDT" in result["breakdowns"]["symbol"]
    assert "ETHUSDT" not in result["breakdowns"]["symbol"]
    assert "SOLUSDT" not in result["breakdowns"]["symbol"]


def test_main_signal_long_dna_detects_toxic_clusters_and_short_outperformance(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "XRPUSDT", "long", "MAIN_SIGNAL", -1.0, session="NEW_YORK", regime="RANGING") for index in range(30)]
    rows.extend(_trade(index + 40, "SOLUSDT", "short", "MAIN_SIGNAL", 1.0, session="LONDON", regime="TRENDING") for index in range(30))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_main_signal_long_dna(data_path=data_path)

    assert result["classification"] == "CRITICAL"
    assert result["toxic_long_clusters"]
    assert result["answers"]["worse_than_main_short"] == "YES"
    assert result["recommended_action"] in {"FULL_BLOCK", "SHADOW_BLOCK", "PARTIAL_BLOCK", "REDEFINE_MAIN_SIGNAL_LONG"}


def test_main_signal_long_dna_finds_profitable_long_survivor(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "SOLUSDT", "long", "MAIN_SIGNAL", 1.0, session="LONDON", regime="TRENDING") for index in range(10)]
    rows.extend(_trade(index + 20, "BTCUSDT", "long", "MAIN_SIGNAL", -1.0, session="NEW_YORK", regime="RANGING") for index in range(3))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_main_signal_long_dna(data_path=data_path)

    assert result["profitable_long_survivors"]
    assert result["profitable_long_survivors"][0]["metrics"]["trades"] >= 10
    assert result["answers"]["salvageable"] == "YES"


def test_main_signal_long_counterfactual_removal_tracks_improvement(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "XRPUSDT", "long", "MAIN_SIGNAL", -1.0) for index in range(10)]
    rows.extend(_trade(index + 20, "SOLUSDT", "short", "MAIN_SIGNAL", 1.0) for index in range(10))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_main_signal_long_dna(data_path=data_path)
    counterfactual = result["counterfactual_removal"]

    assert counterfactual["trades_removed"] == 10
    assert counterfactual["current_metrics"]["profit_factor"] == 1.0
    assert counterfactual["without_main_long_metrics"]["profit_factor"] == "inf"
    assert counterfactual["winrate_delta"] == 50.0


def test_main_signal_long_partial_blocks_include_requested_rules(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(index, "BTCUSDT", "long", "MAIN_SIGNAL", -1.0, liquidity_sweep="bullish_sweep", warnings="against_htf")
        for index in range(12)
    ]
    rows.extend(_trade(index + 20, "SOLUSDT", "short", "MAIN_SIGNAL", 1.0) for index in range(12))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_main_signal_long_dna(data_path=data_path)
    rules = {row["name"]: row for row in result["counterfactual_partial_blocks"]}

    assert "MAIN_SIGNAL LONG + bullish_sweep" in rules
    assert "MAIN_SIGNAL LONG + against_htf" in rules
    assert rules["MAIN_SIGNAL LONG + bullish_sweep"]["removed_trades"] == 12
    assert rules["MAIN_SIGNAL LONG + bullish_sweep"]["r_improvement"] > 0


def test_main_signal_long_classification_helpers() -> None:
    assert classify_main_signal_long({"trades": 1, "total_r": -1.0, "profit_factor": 0.0}) == "NOISE"
    assert classify_main_signal_long({"trades": 4, "total_r": -1.0, "profit_factor": 0.5}) == "WATCH"
    assert classify_main_signal_long({"trades": 10, "total_r": -2.0, "profit_factor": 0.8}) == "IMPORTANT"
    assert classify_main_signal_long({"trades": 30, "total_r": -10.0, "profit_factor": 0.8}) == "CRITICAL"
    assert classify_partial_block({"removed_trades": 5, "r_improvement": 0, "pf_improvement": 0, "profitable_trades_lost": 0, "losing_trades_removed": 0}) == "WATCH"


def test_main_signal_long_report_is_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade(1, "BTCUSDT", "long", "MAIN_SIGNAL", 1.5)])

    result = analyze_main_signal_long_dna(data_path=data_path)
    path = write_main_signal_long_dna_report(result, tmp_path / "reports")

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "MAIN_SIGNAL_LONG_DNA" in text
    assert "LONG vs SHORT DNA Comparison" in text
    assert "Counterfactual Partial Blocks" in text
    assert "Recommended Action" in text


def _trade(
    index: int,
    symbol: str,
    direction: str,
    setup: str,
    result_r: float,
    *,
    session: str = "LONDON",
    regime: str = "TRENDING",
    score: float = 90,
    entry_context: str = "PULLBACK",
    trade_location: str = "mid_range",
    reasons: str = "",
    warnings: str = "",
    penalties: str = "",
    conditions_failed: str = "",
    liquidity_sweep: str = "",
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
        "trade_location": trade_location,
        "score": score,
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "opened_at": "2026-06-01T12:00:00+00:00",
        "closed_at": "2026-06-01T13:00:00+00:00",
        "rejection_reasons": reasons,
        "warnings": warnings,
        "penalties": penalties,
        "conditions_failed": conditions_failed,
        "liquidity_sweep": liquidity_sweep,
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
