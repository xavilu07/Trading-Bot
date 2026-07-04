from __future__ import annotations

import csv
import json
from pathlib import Path

from trading_signals.research.dataset import load_research_dataset
from trading_signals.research.engine import run_quant_research
from trading_signals.research.statistics import compute_metrics


REPORTS = {
    "overview",
    "feature_importance",
    "feature_correlations",
    "edge_discovery",
    "clusters",
    "outliers",
    "strategy_v2_candidates",
    "recommendations",
}


def test_dataset_normalizes_available_columns_without_assuming_all_columns(tmp_path: Path) -> None:
    _write_fixture(tmp_path, positive=2, negative=1, open_rows=1, minimal=True)

    dataset = load_research_dataset(tmp_path / "data")
    row = dataset["rows"][0]

    assert len(dataset["rows"]) == 4
    assert row["symbol"] == "ETHUSDT"
    assert row["score_bucket"] == "90-100"
    assert "htf_alignment" in row


def test_compute_metrics_for_quant_dataset() -> None:
    rows = [
        {"result_r": 2.0},
        {"result_r": -1.0},
        {"result_r": 0.5},
        {"result_r": None},
    ]

    metrics = compute_metrics(rows)

    assert metrics["trades"] == 4
    assert metrics["closed"] == 3
    assert metrics["open"] == 1
    assert metrics["profit_factor"] == 2.5
    assert metrics["total_r"] == 1.5


def test_run_quant_research_generates_all_reports(tmp_path: Path) -> None:
    _write_fixture(tmp_path, positive=25, negative=25, open_rows=2)
    reports_path = tmp_path / "reports" / "quant_research"

    result = run_quant_research(
        data_path=tmp_path / "data",
        reports_path=reports_path,
        min_evidence=5,
        edge_min_evidence=10,
    )

    assert result["overview"]["metrics"]["trades"] == 52
    assert result["overview"]["metrics"]["closed"] == 50
    for report in REPORTS:
        json_path = reports_path / f"{report}.json"
        md_path = reports_path / f"{report}.md"
        assert json_path.exists(), report
        assert md_path.exists(), report
        json.loads(json_path.read_text(encoding="utf-8"))


def test_edge_discovery_and_strategy_candidates_are_populated(tmp_path: Path) -> None:
    _write_fixture(tmp_path, positive=25, negative=25, open_rows=0)
    reports_path = tmp_path / "reports" / "quant_research"

    run_quant_research(
        data_path=tmp_path / "data",
        reports_path=reports_path,
        min_evidence=5,
        edge_min_evidence=10,
    )

    edges = json.loads((reports_path / "edge_discovery.json").read_text(encoding="utf-8"))
    candidates = json.loads((reports_path / "strategy_v2_candidates.json").read_text(encoding="utf-8"))

    assert edges["top_by_pf"]
    assert edges["worst_by_total_r"]
    assert candidates["candidates"]
    assert any(candidate["action"] in {"Eliminar simbolo", "Eliminar contexto"} for candidate in candidates["candidates"])


def test_correlations_rank_positive_and_negative_features(tmp_path: Path) -> None:
    _write_fixture(tmp_path, positive=15, negative=15, open_rows=0)
    reports_path = tmp_path / "reports" / "quant_research"

    run_quant_research(
        data_path=tmp_path / "data",
        reports_path=reports_path,
        min_evidence=5,
        edge_min_evidence=5,
    )

    correlations = json.loads((reports_path / "feature_correlations.json").read_text(encoding="utf-8"))

    assert correlations["ranked"]
    assert correlations["positive"] or correlations["negative"]


def _write_fixture(tmp_path: Path, *, positive: int, negative: int, open_rows: int, minimal: bool = False) -> None:
    path = tmp_path / "data" / "paper_trading" / "trades.csv"
    path.parent.mkdir(parents=True)
    fieldnames = [
        "trade_id",
        "symbol",
        "direction",
        "setup_type",
        "score",
        "risk_reward_tp2",
        "opened_at",
        "closed_at",
        "candles_held",
        "status",
        "result_r",
    ]
    if not minimal:
        fieldnames.extend(
            [
                "volume_ratio",
                "rsi",
                "trend_1h",
                "trend_4h",
                "break_of_structure",
                "liquidity_sweep",
                "directional_distance_to_liquidity_atr",
                "market_regime",
                "session",
                "entry_context",
                "trade_location",
            ]
        )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for idx in range(positive):
            row = {
                "trade_id": f"pos-{idx}",
                "symbol": "ETHUSDT",
                "direction": "short",
                "setup_type": "SECONDARY_SIGNAL",
                "score": "92",
                "risk_reward_tp2": "2.5",
                "opened_at": "2026-06-01T10:00:00Z",
                "closed_at": "2026-06-01T12:00:00Z",
                "candles_held": "5",
                "status": "tp2_hit",
                "result_r": "1.4",
            }
            if not minimal:
                row.update(
                    {
                        "volume_ratio": "1.5",
                        "rsi": "48",
                        "trend_1h": "bearish",
                        "trend_4h": "bearish",
                        "break_of_structure": "bearish_bos",
                        "liquidity_sweep": "bearish_sweep",
                        "directional_distance_to_liquidity_atr": "1.2",
                        "market_regime": "HIGH_VOLATILITY",
                        "session": "LONDON",
                        "entry_context": "PULLBACK",
                        "trade_location": "premium_zone",
                    }
                )
            writer.writerow(row)
        for idx in range(negative):
            row = {
                "trade_id": f"neg-{idx}",
                "symbol": "BTCUSDT",
                "direction": "long",
                "setup_type": "MAIN_SIGNAL",
                "score": "58",
                "risk_reward_tp2": "1.2",
                "opened_at": "2026-06-02T14:00:00Z",
                "closed_at": "2026-06-02T15:00:00Z",
                "candles_held": "3",
                "status": "sl_hit",
                "result_r": "-1.0",
            }
            if not minimal:
                row.update(
                    {
                        "volume_ratio": "0.7",
                        "rsi": "62",
                        "trend_1h": "bearish",
                        "trend_4h": "bearish",
                        "break_of_structure": "bullish_bos",
                        "liquidity_sweep": "bullish_sweep",
                        "directional_distance_to_liquidity_atr": "4.5",
                        "market_regime": "RANGING",
                        "session": "NEW_YORK",
                        "entry_context": "BREAKOUT",
                        "trade_location": "near_support",
                    }
                )
            writer.writerow(row)
        for idx in range(open_rows):
            row = {
                "trade_id": f"open-{idx}",
                "symbol": "SOLUSDT",
                "direction": "long",
                "setup_type": "MAIN_SIGNAL",
                "score": "75",
                "risk_reward_tp2": "2.0",
                "opened_at": "2026-06-03T09:00:00Z",
                "closed_at": "",
                "candles_held": "",
                "status": "open",
                "result_r": "",
            }
            if not minimal:
                row.update(
                    {
                        "volume_ratio": "1.0",
                        "rsi": "50",
                        "trend_1h": "bullish",
                        "trend_4h": "bullish",
                        "break_of_structure": "bullish_bos",
                        "liquidity_sweep": "",
                        "directional_distance_to_liquidity_atr": "2.5",
                        "market_regime": "TRENDING",
                        "session": "OVERLAP",
                        "entry_context": "EXHAUSTION",
                        "trade_location": "mid_range",
                    }
                )
            writer.writerow(row)
