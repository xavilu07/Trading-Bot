from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.long_main_signal_decomposition import (
    analyze_long_main_signal_decomposition,
    write_long_main_signal_decomposition_report,
)


def test_long_main_signal_decomposition_filters_only_long_main_signal(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "long", "MAIN_SIGNAL", 1.5),
            _trade(2, "ETHUSDT", "long", "SECONDARY_SIGNAL", 1.5),
            _trade(3, "SOLUSDT", "short", "MAIN_SIGNAL", 1.5),
        ],
    )

    result = analyze_long_main_signal_decomposition(data_path=data_path)

    assert result["metrics"]["trades"] == 1
    assert result["metrics"]["total_r"] == 1.5
    assert result["breakdowns"]["symbol"]["BTCUSDT"]["metrics"]["trades"] == 1
    assert "ETHUSDT" not in result["breakdowns"]["symbol"]


def test_long_main_signal_decomposition_classifies_toxic_and_ranks_worst(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "long", "MAIN_SIGNAL", -1.0, session="NEW_YORK", regime="HIGH_VOLATILITY", score=95),
            _trade(2, "BTCUSDT", "long", "MAIN_SIGNAL", -1.0, session="NEW_YORK", regime="HIGH_VOLATILITY", score=92),
            _trade(3, "ETHUSDT", "long", "MAIN_SIGNAL", 0.5, session="LONDON", regime="TRENDING", score=65),
        ],
    )

    result = analyze_long_main_signal_decomposition(data_path=data_path)

    assert result["classification"] == "TOXIC"
    assert result["worst_groups"][0]["metrics"]["total_r"] < 0
    assert any(row["dimension"] == "market_regime" and row["value"] == "HIGH_VOLATILITY" for row in result["worst_groups"])
    assert result["recommended_action"] == "candidate for future filter"


def test_long_main_signal_decomposition_finds_candidate_survivor_with_minimum_sample(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "BTCUSDT", "long", "MAIN_SIGNAL", 1.0, session="LONDON", regime="TRENDING", score=72) for index in range(20)]
    rows.extend(_trade(index + 30, "ETHUSDT", "long", "MAIN_SIGNAL", -1.0, session="NEW_YORK", regime="RANGING", score=95) for index in range(5))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_long_main_signal_decomposition(data_path=data_path)

    assert result["candidate_long_survivors"]
    assert result["candidate_long_survivors"][0]["metrics"]["trades"] >= 20
    assert result["answers"]["recommended_action"] == "candidate for shadow promotion"


def test_long_main_signal_decomposition_breaks_down_reasons_liquidity_and_trend(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(
                1,
                "BTCUSDT",
                "long",
                "MAIN_SIGNAL",
                -1.0,
                reasons="against_htf",
                warnings="low_volume",
                penalties="market_structure_range_penalty",
                trade_location="near_resistance",
                trend_entry="bullish",
                trend_higher="bearish",
            ),
            _trade(
                2,
                "ETHUSDT",
                "long",
                "MAIN_SIGNAL",
                1.5,
                liquidity_sweep="bullish_sweep",
                trend_entry="bullish",
                trend_higher="bullish",
            ),
        ],
    )

    result = analyze_long_main_signal_decomposition(data_path=data_path)

    assert "against_htf" in result["breakdowns"]["reason"]
    assert "low_volume" in result["breakdowns"]["reason"]
    assert "market_structure_range_penalty" in result["breakdowns"]["reason"]
    assert "location:near_resistance" in result["breakdowns"]["liquidity_context"]
    assert "sweep:bullish_sweep" in result["breakdowns"]["liquidity_context"]
    assert "against_htf_bearish" in result["breakdowns"]["trend_alignment"]
    assert "aligned_bullish" in result["breakdowns"]["trend_alignment"]


def test_long_main_signal_decomposition_report_is_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade(1, "BTCUSDT", "long", "MAIN_SIGNAL", 1.5)])

    result = analyze_long_main_signal_decomposition(data_path=data_path)
    path = write_long_main_signal_decomposition_report(result, tmp_path / "reports")

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "LONG_MAIN_SIGNAL_DECOMPOSITION" in text
    assert "Candidate LONG Survivors" in text


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
