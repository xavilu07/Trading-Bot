from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.score_80_89_regime_decomposition import (
    analyze_score_80_89_regime_decomposition,
    classify_loss_component,
    write_score_80_89_regime_decomposition_report,
)


def test_regime_decomposition_separates_trending_and_ranging_after_filters(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "long", -1.0, score=85, regime="TRENDING"),
            _trade(2, "ETHUSDT", "short", 1.0, score=85, regime="RANGING"),
            _trade(3, "SOLUSDT", "long", -1.0, score=79, regime="TRENDING"),
            _trade(4, "ADAUSDT", "long", -1.0, score=85, regime="TRENDING", liquidity_sweep="bullish_sweep"),
        ],
    )

    result = analyze_score_80_89_regime_decomposition(data_path=data_path)

    assert result["metrics"]["trending"]["trades"] == 1
    assert result["metrics"]["ranging"]["trades"] == 1
    assert "BTCUSDT" in result["breakdowns"]["trending"]["symbol"]
    assert "ETHUSDT" in result["breakdowns"]["ranging"]["symbol"]
    assert "ADAUSDT" not in result["breakdowns"]["trending"]["symbol"]


def test_regime_decomposition_finds_toxic_trending_subgroups(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "XRPUSDT", "long", -1.0, score=85, regime="TRENDING", session="NEW_YORK") for index in range(12)]
    rows.extend(_trade(index + 20, "SOLUSDT", "short", 1.0, score=85, regime="RANGING", session="LONDON") for index in range(12))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_score_80_89_regime_decomposition(data_path=data_path)

    assert result["classification"]["trending"] == "IMPORTANT"
    assert result["toxic_trending_subgroups"]
    assert result["toxic_trending_subgroups"][0]["metrics"]["trades"] >= 10
    assert result["answers"]["future_shadow_filter_evidence"] == "YES"


def test_regime_decomposition_finds_safe_ranging_survivors(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "SOLUSDT", "short", 1.0, score=85, regime="RANGING", session="LONDON") for index in range(10)]
    rows.extend(_trade(index + 20, "BTCUSDT", "long", -1.0, score=85, regime="TRENDING", session="NEW_YORK") for index in range(3))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_score_80_89_regime_decomposition(data_path=data_path)

    assert result["safe_ranging_survivors"]
    assert result["safe_ranging_survivors"][0]["metrics"]["trades"] >= 10
    assert "RANGING" in result["answers"]["why_ranging_survives"] or "SOLUSDT" in result["answers"]["why_ranging_survives"]


def test_regime_difference_includes_winners_losers_and_largest_gap(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "XRPUSDT", "long", -1.0, score=85, regime="TRENDING", session="NEW_YORK") for index in range(10)]
    rows.extend(_trade(index + 20, "XRPUSDT", "long", 1.0, score=85, regime="RANGING", session="LONDON") for index in range(10))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_score_80_89_regime_decomposition(data_path=data_path)
    symbol_diff = result["regime_difference_analysis"]["symbol"]

    assert symbol_diff["biggest_loser_trending"]["value"] == "XRPUSDT"
    assert symbol_diff["biggest_winner_ranging"]["value"] == "XRPUSDT"
    assert symbol_diff["largest_total_r_gap"]["value"] == "XRPUSDT"
    assert symbol_diff["largest_total_r_gap"]["gap"] == 20.0


def test_regime_decomposition_counterfactual_removes_worst_trending_group(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "XRPUSDT", "long", -1.0, score=85, regime="TRENDING", session="NEW_YORK") for index in range(12)]
    rows.extend(_trade(index + 20, "SOLUSDT", "short", 1.0, score=85, regime="RANGING", session="LONDON") for index in range(12))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_score_80_89_regime_decomposition(data_path=data_path)
    counterfactual = result["top_trending_subgroup_counterfactual"]

    assert counterfactual["removed_group"] != "none"
    assert counterfactual["remaining_metrics"]["profit_factor"] == "inf"
    assert "Deep dive" in result["next_recommended_investigation"]


def test_regime_decomposition_classifies_loss_components() -> None:
    assert classify_loss_component({"trades": 1, "total_r": -1.0, "profit_factor": 0.0}) == "NOISE"
    assert classify_loss_component({"trades": 4, "total_r": -1.0, "profit_factor": 0.5}) == "WATCH"
    assert classify_loss_component({"trades": 10, "total_r": -2.0, "profit_factor": 0.8}) == "IMPORTANT"
    assert classify_loss_component({"trades": 20, "total_r": -5.0, "profit_factor": 0.8}) == "CRITICAL"


def test_regime_decomposition_report_is_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "long", -1.0, score=85, regime="TRENDING"),
            _trade(2, "ETHUSDT", "short", 1.0, score=85, regime="RANGING"),
        ],
    )

    result = analyze_score_80_89_regime_decomposition(data_path=data_path)
    path = write_score_80_89_regime_decomposition_report(result, tmp_path / "reports")

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "SCORE_80_89_REGIME_DECOMPOSITION" in text
    assert "Regime Difference Analysis" in text
    assert "Next Recommended Investigation" in text


def _trade(
    index: int,
    symbol: str,
    direction: str,
    result_r: float,
    *,
    session: str = "LONDON",
    regime: str = "TRENDING",
    setup: str = "MAIN_SIGNAL",
    score: float = 85,
    entry_context: str = "PULLBACK",
    liquidity_sweep: str = "",
    liquidity_context: str = "",
    reasons: str = "",
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
        "trade_location": "mid_range",
        "score": score,
        "status": "tp2_hit" if result_r > 0 else "sl_hit",
        "result_r": result_r,
        "opened_at": "2026-06-01T12:00:00+00:00",
        "closed_at": "2026-06-01T13:00:00+00:00",
        "liquidity_sweep": liquidity_sweep,
        "liquidity_context": liquidity_context,
        "rejection_reasons": reasons,
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
