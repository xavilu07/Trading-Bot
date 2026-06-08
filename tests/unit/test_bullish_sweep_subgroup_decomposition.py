from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.research.bullish_sweep_subgroup_decomposition import (
    analyze_bullish_sweep_subgroup_decomposition,
    write_bullish_sweep_subgroup_decomposition_report,
)


def test_bullish_sweep_subgroup_decomposition_filters_only_bullish_sweep(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            _trade(1, "BTCUSDT", "long", -1.0, liquidity_sweep="bullish_sweep"),
            _trade(2, "ETHUSDT", "short", 1.0, liquidity_context="sweep:bullish_sweep"),
            _trade(3, "SOLUSDT", "long", 1.0, liquidity_sweep="bearish_sweep"),
        ],
    )

    result = analyze_bullish_sweep_subgroup_decomposition(data_path=data_path)

    assert result["metrics"]["trades"] == 2
    assert "BTCUSDT" in result["breakdowns"]["symbol"]
    assert "ETHUSDT" in result["breakdowns"]["symbol"]
    assert "SOLUSDT" not in result["breakdowns"]["symbol"]


def test_bullish_sweep_subgroup_decomposition_finds_toxic_subgroups(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "XRPUSDT", "long", -1.0, session="NEW_YORK", liquidity_sweep="bullish_sweep") for index in range(5)]
    rows.extend(_trade(index + 20, "SOLUSDT", "short", 1.0, session="LONDON", liquidity_sweep="bullish_sweep") for index in range(2))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_bullish_sweep_subgroup_decomposition(data_path=data_path)

    assert result["classification"] == "TOXIC"
    assert result["toxic_subgroups"]
    assert result["toxic_subgroups"][0]["metrics"]["trades"] >= 5


def test_bullish_sweep_subgroup_decomposition_finds_profitable_survivors(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "SOLUSDT", "short", 1.0, session="LONDON", liquidity_sweep="bullish_sweep") for index in range(5)]
    rows.extend(_trade(index + 20, "BTCUSDT", "long", -1.0, session="NEW_YORK", liquidity_sweep="bullish_sweep") for index in range(2))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_bullish_sweep_subgroup_decomposition(data_path=data_path)

    assert result["profitable_survivors"]
    assert result["profitable_survivors"][0]["metrics"]["trades"] >= 5


def test_bullish_sweep_subgroup_decomposition_counterfactual_ranks_impact(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "XRPUSDT", "long", -1.0, session="NEW_YORK", liquidity_sweep="bullish_sweep") for index in range(5)]
    rows.extend(_trade(index + 20, "SOLUSDT", "short", 1.0, session="LONDON", liquidity_sweep="bullish_sweep") for index in range(5))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_bullish_sweep_subgroup_decomposition(data_path=data_path)

    assert result["impact_ranking"]
    assert result["impact_ranking"][0]["r_improvement"] == 5.0
    assert result["impact_ranking"][0]["pf_after"] == "inf"


def test_bullish_sweep_subgroup_decomposition_recommends_partial_block_when_survivors_exist(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [_trade(index, "XRPUSDT", "long", -1.0, session="NEW_YORK", liquidity_sweep="bullish_sweep") for index in range(5)]
    rows.extend(_trade(index + 20, "SOLUSDT", "short", 1.0, session="LONDON", liquidity_sweep="bullish_sweep") for index in range(5))
    _write_csv(data_path / "paper_trading" / "trades.csv", rows)

    result = analyze_bullish_sweep_subgroup_decomposition(data_path=data_path)

    assert result["recommended_action"] == "PARTIAL_BLOCK"


def test_bullish_sweep_subgroup_decomposition_report_is_written(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    _write_csv(data_path / "paper_trading" / "trades.csv", [_trade(1, "BTCUSDT", "long", -1.0, liquidity_sweep="bullish_sweep")])

    result = analyze_bullish_sweep_subgroup_decomposition(data_path=data_path)
    path = write_bullish_sweep_subgroup_decomposition_report(result, tmp_path / "reports")

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "BULLISH_SWEEP_SUBGROUP_DECOMPOSITION" in text
    assert "Counterfactual Removal By Subgroup" in text
    assert "Impact Ranking" in text


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
