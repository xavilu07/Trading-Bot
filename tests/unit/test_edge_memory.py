from __future__ import annotations

import csv
from pathlib import Path

from trading_signals.memory.edge_memory import build_edge_memory, evaluate_edge_for_context


def test_edge_memory_reads_trades_csv_and_ignores_open_trades(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(1, "BTCUSDT", "short", "LONDON", "RANGING", "PULLBACK", "mid_range", "tp2_hit", 1.0),
        _trade(2, "BTCUSDT", "short", "LONDON", "RANGING", "PULLBACK", "mid_range", "open", 5.0),
        _trade(3, "BTCUSDT", "short", "LONDON", "RANGING", "PULLBACK", "mid_range", "sl_hit", -1.0),
    ]
    _write_trades(data_path, rows)

    memory = build_edge_memory(data_path, min_sample_size=1)

    assert memory["closed_trades"] == 2
    direction_edge = memory["groups"]["direction|direction=short"]
    assert direction_edge["sample_size"] == 2
    assert direction_edge["winrate"] == 50.0
    assert direction_edge["avg_r"] == 0.0
    assert direction_edge["total_r"] == 0.0
    assert direction_edge["profit_factor"] == 1.0


def test_short_london_detects_positive_edge_when_fixture_contains_it(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(index, "ETHUSDT", "short", "LONDON", "RANGING", "PULLBACK", "mid_range", "tp2_hit", 1.0)
        for index in range(12)
    ]
    rows.extend(
        _trade(index + 20, "BTCUSDT", "short", "LONDON", "RANGING", "PULLBACK", "mid_range", "sl_hit", -1.0)
        for index in range(3)
    )
    _write_trades(data_path, rows)

    result = evaluate_edge_for_context(
        data_path,
        {"direction": "short", "session": "LONDON", "market_regime": "RANGING", "entry_context": "PULLBACK"},
    )

    assert result["available"] is True
    assert result["matched_patterns_count"] == 15
    assert result["historical_edge_score"] > 50
    assert result["historical_confidence"] == "MEDIUM"
    assert result["best_edge"]["group"] in {"direction+session", "direction+market_regime+entry_context"}
    assert result["best_edge"]["edge_grade"] in {"GOOD", "STRONG"}


def test_long_high_volatility_breakout_detects_weak_edge_when_fixture_contains_it(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(index, "SOLUSDT", "long", "OVERLAP", "HIGH_VOLATILITY", "BREAKOUT", "near_resistance", "sl_hit", -1.0)
        for index in range(12)
    ]
    rows.extend(
        _trade(index + 20, "AVAXUSDT", "long", "OVERLAP", "HIGH_VOLATILITY", "BREAKOUT", "near_resistance", "tp2_hit", 1.0)
        for index in range(3)
    )
    _write_trades(data_path, rows)

    result = evaluate_edge_for_context(
        data_path,
        {"direction": "long", "market_regime": "HIGH_VOLATILITY", "entry_context": "BREAKOUT"},
    )

    assert result["matched_patterns_count"] == 15
    assert result["historical_edge_score"] < 50
    assert result["worst_edge"]["edge_grade"] in {"BAD", "WEAK"}
    assert result["worst_edge"]["profit_factor"] < 1


def test_no_match_returns_neutral_score(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(index, "ETHUSDT", "short", "LONDON", "RANGING", "PULLBACK", "mid_range", "tp2_hit", 1.0)
        for index in range(15)
    ]
    _write_trades(data_path, rows)

    result = evaluate_edge_for_context(
        data_path,
        {"direction": "long", "session": "ASIA", "market_regime": "LOW_VOLATILITY", "entry_context": "EXHAUSTION"},
    )

    assert result["available"] is True
    assert result["matched_patterns_count"] == 0
    assert result["historical_edge_score"] == 50
    assert result["historical_confidence"] == "LOW"
    assert result["matched_edges"] == []
    assert result["best_edge"] is None
    assert result["worst_edge"] is None


def test_build_edge_memory_exposes_all_required_group_types(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    rows = [
        _trade(index, "ETHUSDT", "short", "LONDON", "RANGING", "PULLBACK", "mid_range", "tp2_hit", 1.0)
        for index in range(15)
    ]
    _write_trades(data_path, rows)

    memory = build_edge_memory(data_path)

    expected_groups = {
        "direction|direction=short",
        "symbol|symbol=ethusdt",
        "market_regime|market_regime=ranging",
        "session|session=london",
        "entry_context|entry_context=pullback",
        "trade_location|trade_location=mid_range",
        "direction+session|direction=short|session=london",
        "direction+entry_context|direction=short|entry_context=pullback",
        "direction+market_regime|direction=short|market_regime=ranging",
        "market_regime+entry_context|market_regime=ranging|entry_context=pullback",
        "direction+market_regime+entry_context|direction=short|market_regime=ranging|entry_context=pullback",
        "symbol+direction|symbol=ethusdt|direction=short",
        "symbol+direction+market_regime|symbol=ethusdt|direction=short|market_regime=ranging",
        "direction+session+entry_context|direction=short|session=london|entry_context=pullback",
    }
    assert expected_groups.issubset(set(memory["groups"]))


def _trade(
    index: int,
    symbol: str,
    direction: str,
    session: str,
    market_regime: str,
    entry_context: str,
    trade_location: str,
    status: str,
    result_r: float,
) -> dict[str, object]:
    return {
        "trade_id": f"trade-{index}",
        "symbol": symbol,
        "direction": direction,
        "session": session,
        "market_regime": market_regime,
        "entry_context": entry_context,
        "trade_location": trade_location,
        "status": status,
        "result_r": result_r,
        "opened_at": "2026-06-01T10:00:00+00:00",
        "closed_at": "2026-06-01T11:00:00+00:00" if status != "open" else "",
    }


def _write_trades(data_path: Path, rows: list[dict[str, object]]) -> None:
    path = data_path / "paper_trading" / "trades.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
