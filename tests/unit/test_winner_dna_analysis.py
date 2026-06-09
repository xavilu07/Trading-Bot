from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.winner_dna_analysis import analyze_winner_dna, write_winner_dna_report


def test_winner_dna_builds_winner_and_loser_profiles(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "short", 1.0, session="LONDON", setup="MAIN_SIGNAL"),
            _trade(2, "ETHUSDT", "short", 1.0, session="LONDON", setup="MAIN_SIGNAL"),
            _trade(3, "SOLUSDT", "long", -1.0, session="ASIA", setup="SECONDARY_SIGNAL", warnings="low_volume"),
            _trade(4, "XRPUSDT", "long", -1.0, session="ASIA", setup="SECONDARY_SIGNAL", warnings="low_volume"),
        ],
    )

    result = analyze_winner_dna(data_path=data_path, min_trades=1)

    winner_values = {(row["dimension"], row["value"]) for rows in result["winner_profile"].values() for row in rows}
    loser_values = {(row["dimension"], row["value"]) for rows in result["loser_profile"].values() for row in rows}
    assert ("session", "LONDON") in winner_values
    assert ("session", "ASIA") in loser_values


def test_winner_dna_finds_positive_and_negative_predictors(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "BTCUSDT", "short", 1.0, session="LONDON", setup="MAIN_SIGNAL") for index in range(5)]
    rows.extend(_trade(index + 10, "ETHUSDT", "long", -1.0, session="ASIA", setup="SECONDARY_SIGNAL", warnings="low_volume") for index in range(5))
    rows.extend(_trade(index + 20, "SOLUSDT", "long", 1.0, session="NEW_YORK", setup="MAIN_SIGNAL") for index in range(2))
    rows.extend(_trade(index + 30, "ADAUSDT", "short", -1.0, session="NEW_YORK", setup="MAIN_SIGNAL") for index in range(2))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_winner_dna(data_path=data_path, min_trades=5)

    assert any(row["dimension"] == "session" and row["value"] == "LONDON" for row in result["top_positive_predictors"])
    assert any(row["dimension"] == "session" and row["value"] == "ASIA" for row in result["top_negative_predictors"])
    assert any(row["dimension"] == "warning" and row["value"] == "low_volume" for row in result["top_negative_predictors"])


def test_winner_dna_counterfactual_uplift_ranks_bad_context_removal(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "BTCUSDT", "short", 1.0, session="LONDON") for index in range(5)]
    rows.extend(_trade(index + 10, "ETHUSDT", "long", -1.0, session="ASIA", warnings="low_volume") for index in range(5))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_winner_dna(data_path=data_path, min_trades=5)

    assert result["counterfactual_uplift"]
    top = result["counterfactual_uplift"][0]
    assert top["total_r_uplift"] > 0
    assert top["value"] in {"ASIA", "low_volume", "long", "ETHUSDT"}


def test_winner_dna_variable_impact_ranking_is_generated(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "BTCUSDT", "short", 1.0, session="LONDON", setup="MAIN_SIGNAL") for index in range(5)]
    rows.extend(_trade(index + 10, "ETHUSDT", "long", -1.0, session="ASIA", setup="SECONDARY_SIGNAL") for index in range(5))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_winner_dna(data_path=data_path, min_trades=1)

    assert result["variable_impact_ranking"]
    assert result["variable_impact_ranking"][0]["avg_abs_winrate_impact"] >= 0


def test_winner_dna_report_is_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "short", 1.0, session="LONDON"),
            _trade(2, "ETHUSDT", "long", -1.0, session="ASIA"),
        ],
    )

    result = analyze_winner_dna(data_path=data_path, min_trades=1)
    path = write_winner_dna_report(result, tmp_path / "reports")

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "WINNER_DNA_ANALYSIS" in text
    assert "Winner Profile" in text
    assert "Top Positive Predictors" in text
    assert "Final Recommendation" in text


def _trade(
    index: int,
    symbol: str,
    direction: str,
    result_r: float,
    *,
    session: str = "LONDON",
    setup: str = "MAIN_SIGNAL",
    regime: str = "TRENDING",
    entry_context: str = "PULLBACK",
    score: float = 90,
    warnings: str = "",
    penalties: str = "",
    reasons: str = "",
) -> dict[str, object]:
    return {
        "trade_id": f"trade-{index}",
        "symbol": symbol,
        "direction": direction,
        "setup_type": setup,
        "market_regime": regime,
        "session": session,
        "entry_context": entry_context,
        "trade_location": "mid_range",
        "score": score,
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "opened_at": "2026-06-01T12:00:00+00:00",
        "closed_at": "2026-06-01T13:00:00+00:00",
        "warnings": warnings,
        "penalties": penalties,
        "rejection_reasons": reasons,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
