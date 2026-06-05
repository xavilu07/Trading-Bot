from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.bullish_sweep_failure_deep_dive import (
    analyze_bullish_sweep_failure_deep_dive,
    write_bullish_sweep_failure_deep_dive_report,
)


def test_bullish_sweep_filters_only_bullish_sweep_rows(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "long", 1.5, liquidity_sweep="bullish_sweep"),
            _trade(2, "ETHUSDT", "long", 1.5, liquidity_sweep="bearish_sweep"),
            _trade(3, "SOLUSDT", "short", 1.5, liquidity_context="sweep:bullish_sweep"),
        ],
    )

    result = analyze_bullish_sweep_failure_deep_dive(data_path=data_path)

    assert result["metrics"]["trades"] == 2
    assert result["breakdowns"]["symbol"]["BTCUSDT"]["metrics"]["trades"] == 1
    assert result["breakdowns"]["symbol"]["SOLUSDT"]["metrics"]["trades"] == 1
    assert "ETHUSDT" not in result["breakdowns"]["symbol"]


def test_bullish_sweep_classifies_toxic_and_ranks_worst_groups(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "long", -1.0, session="NEW_YORK", regime="HIGH_VOLATILITY", liquidity_sweep="bullish_sweep"),
            _trade(2, "BTCUSDT", "long", -1.0, session="NEW_YORK", regime="HIGH_VOLATILITY", liquidity_sweep="bullish_sweep"),
            _trade(3, "ETHUSDT", "long", 0.5, session="LONDON", regime="TRENDING", liquidity_sweep="bullish_sweep"),
        ],
    )

    result = analyze_bullish_sweep_failure_deep_dive(data_path=data_path)

    assert result["classification"] == "TOXIC"
    assert result["worst_groups"]
    assert any(row["dimension"] == "market_regime" and row["value"] == "HIGH_VOLATILITY" for row in result["worst_groups"])
    assert result["recommended_action"] == "candidate for future filter"


def test_bullish_sweep_finds_survivor_with_minimum_sample(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "BTCUSDT", "long", 1.0, session="LONDON", regime="TRENDING", liquidity_sweep="bullish_sweep") for index in range(20)]
    rows.extend(_trade(index + 30, "ETHUSDT", "long", -1.0, session="NEW_YORK", regime="RANGING", liquidity_sweep="bullish_sweep") for index in range(5))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_bullish_sweep_failure_deep_dive(data_path=data_path)

    assert result["bullish_sweep_survivors"]
    assert result["bullish_sweep_survivors"][0]["metrics"]["trades"] >= 20
    assert result["answers"]["recommended_action"] == "candidate for shadow promotion"


def test_bullish_sweep_breaks_down_reason_direction_and_htf_alignment(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(
                1,
                "BTCUSDT",
                "long",
                -1.0,
                liquidity_sweep="bullish_sweep",
                reasons="against_htf",
                warnings="low_volume",
                penalties="market_structure_range_penalty",
                trend_entry="bullish",
                trend_higher="bearish",
            ),
            _trade(
                2,
                "ETHUSDT",
                "long",
                1.5,
                liquidity_sweep="bullish_sweep",
                trend_entry="bullish",
                trend_higher="bullish",
            ),
        ],
    )

    result = analyze_bullish_sweep_failure_deep_dive(data_path=data_path)

    assert "against_htf" in result["breakdowns"]["reason"]
    assert "low_volume" in result["breakdowns"]["reason"]
    assert "market_structure_range_penalty" in result["breakdowns"]["reason"]
    assert "long" in result["breakdowns"]["direction"]
    assert "against_htf" in result["breakdowns"]["htf_alignment"]
    assert "aligned_with_htf" in result["breakdowns"]["htf_alignment"]


def test_bullish_sweep_report_is_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade(1, "BTCUSDT", "long", 1.5, liquidity_sweep="bullish_sweep")])

    result = analyze_bullish_sweep_failure_deep_dive(data_path=data_path)
    path = write_bullish_sweep_failure_deep_dive_report(result, tmp_path / "reports")

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "BULLISH_SWEEP_FAILURE_DEEP_DIVE" in text
    assert "Bullish Sweep Survivors" in text


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
