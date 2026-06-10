from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.elite_profile_c_dna_expansion import (
    analyze_elite_profile_c_dna_expansion,
    classify_combo,
    matches_elite_profile_c,
    write_elite_profile_c_dna_expansion_reports,
)


def test_matches_elite_profile_c_requires_secondary_score_90_and_aligned_htf() -> None:
    assert matches_elite_profile_c(_trade(1, "BTCUSDT", "long", 1.0, setup="SECONDARY_SIGNAL", score=90, trend_higher="bullish"))
    assert not matches_elite_profile_c(_trade(2, "BTCUSDT", "long", 1.0, setup="MAIN_SIGNAL", score=90, trend_higher="bullish"))
    assert not matches_elite_profile_c(_trade(3, "BTCUSDT", "long", 1.0, setup="SECONDARY_SIGNAL", score=89.9, trend_higher="bullish"))
    assert not matches_elite_profile_c(_trade(4, "BTCUSDT", "long", 1.0, setup="SECONDARY_SIGNAL", score=90, trend_higher="bearish"))


def test_dna_expansion_filters_profile_c_and_builds_factor_breakdowns(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "BTCUSDT", "long", 1.0, session="OVERLAP", regime="HIGH_VOLATILITY", location="near_resistance", entry_context="BREAKOUT", liquidity_sweep="none", trend_higher="bullish") for index in range(6)]
    rows.extend(_trade(index + 10, "ETHUSDT", "short", -1.0, session="LONDON", regime="TRENDING", location="premium_zone", entry_context="PULLBACK", liquidity_sweep="bearish_sweep", trend_higher="bearish") for index in range(4))
    rows.extend(_trade(index + 20, "SOLUSDT", "short", 1.0, setup="MAIN_SIGNAL", score=95, trend_higher="bearish") for index in range(3))
    rows.extend(_trade(index + 30, "BNBUSDT", "short", 1.0, setup="SECONDARY_SIGNAL", score=85, trend_higher="bearish") for index in range(3))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_elite_profile_c_dna_expansion(data_path=data_path)

    assert result["baseline"]["trades"] == 10
    assert result["baseline"]["winrate"] == 60.0
    assert result["factor_breakdowns"]["direction"][0]["value"] == "long"
    assert result["factor_breakdowns"]["direction"][0]["metrics"]["total_r"] == 6.0
    assert result["factor_breakdowns"]["session"][0]["value"] == "OVERLAP"
    assert result["factor_breakdowns"]["market_regime"][0]["value"] == "HIGH_VOLATILITY"
    assert result["factor_breakdowns"]["trade_location"][0]["value"] == "near_resistance"
    assert result["factor_breakdowns"]["entry_context"][0]["value"] == "BREAKOUT"
    assert result["factor_breakdowns"]["liquidity_sweep"][0]["value"] == "none"


def test_multi_factor_combinations_and_rankings_use_minimum_sample(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "BTCUSDT", "long", 2.0, session="OVERLAP", regime="HIGH_VOLATILITY", location="near_resistance", entry_context="BREAKOUT", trend_higher="bullish") for index in range(5)]
    rows.extend(_trade(index + 10, "ETHUSDT", "short", -1.0, session="LONDON", regime="TRENDING", location="premium_zone", entry_context="PULLBACK", liquidity_sweep="bearish_sweep", trend_higher="bearish") for index in range(5))
    rows.extend(_trade(index + 20, "AAVEUSDT", "long", 3.0, session="ASIA", regime="RANGING", location="discount_zone", entry_context="EXHAUSTION", trend_higher="bullish") for index in range(4))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_elite_profile_c_dna_expansion(data_path=data_path)
    combinations = result["multi_factor_combinations"]

    assert all(row["metrics"]["trades"] >= 5 for row in combinations)
    assert any(row["factors"] == ["direction=long", "market_regime=HIGH_VOLATILITY"] for row in combinations)
    assert not any("session=ASIA" in row["factors"] for row in combinations)
    assert result["rankings"]["BEST_PF_COMBINATIONS"][0]["classification"] == "ELITE"
    assert "direction=long" in result["final_answer"]["highest_total_r_elite_dna"]


def test_classification_rules() -> None:
    assert classify_combo({"trades": 4, "total_r": 10, "profit_factor": 10, "winrate": 100}) == "NOISE"
    assert classify_combo({"trades": 5, "total_r": 5, "profit_factor": 2.1, "winrate": 60}) == "ELITE"
    assert classify_combo({"trades": 5, "total_r": 5, "profit_factor": 1.5, "winrate": 50}) == "STRONG"
    assert classify_combo({"trades": 5, "total_r": 0, "profit_factor": 1.0, "winrate": 50}) == "NEUTRAL"
    assert classify_combo({"trades": 5, "total_r": -1, "profit_factor": 0.8, "winrate": 40}) == "NOISE"


def test_reports_are_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    rows = [_trade(index, "BTCUSDT", "long", 1.0, trend_higher="bullish") for index in range(5)]
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_elite_profile_c_dna_expansion(data_path=data_path)
    paths = write_elite_profile_c_dna_expansion_reports(result, reports_path)

    assert paths["markdown"].exists()
    assert paths["json"].exists()
    markdown = paths["markdown"].read_text(encoding="utf-8")
    json_text = paths["json"].read_text(encoding="utf-8")
    assert "ELITE_PROFILE_C_DNA_EXPANSION" in markdown
    assert "Multi-factor Analysis" in markdown
    assert "ELITE_PROFILE_C_DNA_EXPANSION" in json_text


def _trade(
    index: int,
    symbol: str,
    direction: str,
    result_r: float,
    *,
    setup: str = "SECONDARY_SIGNAL",
    score: float = 95,
    session: str = "LONDON",
    regime: str = "TRENDING",
    location: str = "premium_zone",
    entry_context: str = "PULLBACK",
    liquidity_sweep: str = "none",
    trend_higher: str = "bearish",
) -> dict[str, object]:
    return {
        "trade_id": f"trade-{index}",
        "symbol": symbol,
        "direction": direction,
        "setup_type": setup,
        "score": score,
        "session": session,
        "market_regime": regime,
        "trade_location": location,
        "entry_context": entry_context,
        "liquidity_sweep": liquidity_sweep,
        "trend_higher": trend_higher,
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "opened_at": "2026-06-01T12:00:00+00:00",
        "closed_at": "2026-06-01T13:00:00+00:00",
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
