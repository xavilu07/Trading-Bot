from __future__ import annotations

import csv
import json
from pathlib import Path

from trading_signals.intelligence.historical_intelligence.engine import generate_historical_intelligence, load_historical_trades
from trading_signals.intelligence.historical_intelligence.metrics import compute_metrics


REQUIRED_REPORTS = {
    "overview",
    "symbol_analysis",
    "session_analysis",
    "score_analysis",
    "setup_analysis",
    "market_regime_analysis",
    "trade_location_analysis",
    "edge_matrix",
    "negative_edges",
    "positive_edges",
    "recommendations",
    "dna_profiles",
}


def test_compute_metrics_calculates_core_stats() -> None:
    rows = [
        {"status": "tp2_hit", "result_r": 2.0},
        {"status": "sl_hit", "result_r": -1.0},
        {"status": "expired", "result_r": 0.5},
        {"status": "open", "result_r": None},
    ]

    metrics = compute_metrics(rows)

    assert metrics["trades"] == 4
    assert metrics["closed"] == 3
    assert metrics["open"] == 1
    assert metrics["wins"] == 2
    assert metrics["losses"] == 1
    assert metrics["winrate"] == 66.6667
    assert metrics["profit_factor"] == 2.5
    assert metrics["total_r"] == 1.5


def test_load_historical_trades_keeps_open_rows(tmp_path: Path) -> None:
    _write_fixture(tmp_path, closed_positive=1, closed_negative=1, open_rows=2)

    rows = load_historical_trades(tmp_path / "data")

    assert len(rows) == 4
    assert sum(1 for row in rows if row["result_r"] is None) == 2
    assert {row["score_bucket"] for row in rows} >= {"90-100", "60-69"}


def test_generate_historical_intelligence_writes_required_reports(tmp_path: Path) -> None:
    _write_fixture(tmp_path, closed_positive=25, closed_negative=25, open_rows=3)
    reports_path = tmp_path / "reports" / "historical_intelligence"

    result = generate_historical_intelligence(
        data_path=tmp_path / "data",
        reports_path=reports_path,
    )

    assert result["overview"]["trades"] == 53
    assert result["overview"]["closed"] == 50
    assert result["overview"]["open"] == 3
    for name in REQUIRED_REPORTS:
        json_path = reports_path / f"{name}.json"
        md_path = reports_path / f"{name}.md"
        assert json_path.exists(), name
        assert md_path.exists(), name
        json.loads(json_path.read_text(encoding="utf-8"))


def test_engine_discovers_positive_negative_edges_and_recommendations(tmp_path: Path) -> None:
    _write_fixture(tmp_path, closed_positive=25, closed_negative=25, open_rows=0)
    reports_path = tmp_path / "reports" / "historical_intelligence"

    generate_historical_intelligence(data_path=tmp_path / "data", reports_path=reports_path)

    positive = json.loads((reports_path / "positive_edges.json").read_text(encoding="utf-8"))
    negative = json.loads((reports_path / "negative_edges.json").read_text(encoding="utf-8"))
    recommendations = json.loads((reports_path / "recommendations.json").read_text(encoding="utf-8"))

    assert any(edge["context"].get("session") == "LONDON" for edge in positive["edges"])
    assert any(edge["context"].get("symbol") == "BTCUSDT" for edge in negative["edges"])
    assert recommendations["recommendations"]


def test_edge_matrix_uses_multi_factor_minimum_sample(tmp_path: Path) -> None:
    _write_fixture(tmp_path, closed_positive=22, closed_negative=5, open_rows=0)
    reports_path = tmp_path / "reports" / "historical_intelligence"

    generate_historical_intelligence(data_path=tmp_path / "data", reports_path=reports_path)

    matrix = json.loads((reports_path / "edge_matrix.json").read_text(encoding="utf-8"))

    assert any(
        group["context"].get("symbol") == "ETHUSDT"
        and group["context"].get("direction") == "long"
        and group["closed"] >= 20
        for group in matrix["groups"]
    )


def _write_fixture(tmp_path: Path, *, closed_positive: int, closed_negative: int, open_rows: int) -> None:
    path = tmp_path / "data" / "paper_trading" / "trades.csv"
    path.parent.mkdir(parents=True)
    fieldnames = [
        "trade_id",
        "symbol",
        "direction",
        "setup_type",
        "score",
        "opened_at",
        "closed_at",
        "status",
        "result_r",
        "candles_held",
        "risk_reward_tp2",
        "market_regime",
        "session",
        "entry_context",
        "trade_location",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for idx in range(closed_positive):
            writer.writerow(
                {
                    "trade_id": f"pos-{idx}",
                    "symbol": "ETHUSDT",
                    "direction": "long",
                    "setup_type": "SECONDARY_SIGNAL",
                    "score": "95",
                    "opened_at": "2026-06-01T10:00:00Z",
                    "closed_at": "2026-06-01T12:00:00Z",
                    "status": "tp2_hit" if idx % 4 else "expired",
                    "result_r": "1.2" if idx % 4 else "0.4",
                    "candles_held": "6",
                    "risk_reward_tp2": "2.4",
                    "market_regime": "TRENDING",
                    "session": "LONDON",
                    "entry_context": "PULLBACK",
                    "trade_location": "near_resistance",
                }
            )
        for idx in range(closed_negative):
            writer.writerow(
                {
                    "trade_id": f"neg-{idx}",
                    "symbol": "BTCUSDT",
                    "direction": "long",
                    "setup_type": "MAIN_SIGNAL",
                    "score": "65",
                    "opened_at": "2026-06-02T15:00:00Z",
                    "closed_at": "2026-06-02T16:00:00Z",
                    "status": "sl_hit" if idx % 5 else "expired",
                    "result_r": "-1.0" if idx % 5 else "-0.2",
                    "candles_held": "3",
                    "risk_reward_tp2": "1.4",
                    "market_regime": "RANGING",
                    "session": "NEW_YORK",
                    "entry_context": "BREAKOUT",
                    "trade_location": "near_support",
                }
            )
        for idx in range(open_rows):
            writer.writerow(
                {
                    "trade_id": f"open-{idx}",
                    "symbol": "SOLUSDT",
                    "direction": "short",
                    "setup_type": "MAIN_SIGNAL",
                    "score": "82",
                    "opened_at": "2026-06-03T09:00:00Z",
                    "closed_at": "",
                    "status": "open",
                    "result_r": "",
                    "candles_held": "",
                    "risk_reward_tp2": "2.1",
                    "market_regime": "HIGH_VOLATILITY",
                    "session": "OVERLAP",
                    "entry_context": "EXHAUSTION",
                    "trade_location": "premium_zone",
                }
            )
