from __future__ import annotations

import csv
from pathlib import Path

from scripts.generate_performance_report import (
    build_edge_breakdown,
    build_performance_metrics,
    format_edge_breakdown,
    generate_performance_report,
    load_closed_trades,
)


def write_trades(path: Path, rows: list[dict[str, object]]) -> None:
    trades_dir = path / "paper_trading"
    trades_dir.mkdir(parents=True)
    fields = sorted({key for row in rows for key in row})
    with (trades_dir / "trades.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_performance_report_handles_missing_csv(tmp_path: Path) -> None:
    result = generate_performance_report(tmp_path / "data", tmp_path / "reports")

    assert result["ok"] is False
    assert result["reason"] == "insufficient_closed_trades"
    assert result["metrics"]["total_trades"] == 0
    assert (tmp_path / "reports" / "performance_report.html").exists()


def test_performance_report_builds_metrics_from_closed_trades(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_trades(
        data_path,
        [
            {
                "symbol": "BTCUSDT",
                "direction": "long",
                "setup_type": "MAIN_SIGNAL",
                "score": "92",
                "market_regime": "TRENDING",
                "session": "LONDON",
                "entry_context": "BREAKOUT",
                "trade_location": "near_support",
                "status": "tp2_hit",
                "result_r": "2",
                "closed_at": "2026-01-01T00:00:00+00:00",
                "avoidance_warnings": '["low_volume"]',
                "penalties": '["distance_to_liquidity_penalty"]',
            },
            {
                "symbol": "ETHUSDT",
                "direction": "short",
                "setup_type": "SECONDARY_SIGNAL",
                "score": "55",
                "market_regime": "RANGING",
                "session": "NEW_YORK",
                "entry_context": "CHOPPY_RANGE",
                "trade_location": "near_resistance",
                "status": "sl_hit",
                "result_r": "-1",
                "closed_at": "2026-01-02T00:00:00+00:00",
                "avoidance_warnings": '["dirty_sideways_market"]',
                "penalties": '["timeframe_alignment_penalty"]',
                "blocking_reasons": '["directional_confluence_failed"]',
                "final_status": "high_score_rejected",
            },
            {
                "symbol": "SOLUSDT",
                "status": "open",
                "result_r": "1",
            },
        ],
    )

    trades = load_closed_trades(data_path)
    metrics = build_performance_metrics(trades)

    assert len(trades) == 2
    assert metrics["total_trades"] == 2
    assert metrics["winrate"] == 50.0
    assert metrics["total_r"] == 1.0
    assert metrics["avg_r"] == 0.5
    assert metrics["max_drawdown"] == -1.0
    assert metrics["profit_factor"] == 2.0
    assert metrics["best_setups"][0]["label"] == "MAIN_SIGNAL"
    assert metrics["worst_warnings"][0]["label"] == "dirty_sideways_market"
    assert metrics["worst_penalties"][0]["label"] == "timeframe_alignment_penalty"
    edge = metrics["edge_breakdown"]
    assert any(row["group_type"] == "direction" and row["group"] == "long" for row in edge)
    assert any(row["group_type"] == "score_bucket" and row["group"] == "90+" for row in edge)
    assert any(row["group_type"] == "score_bucket" and row["group"] == "<60" for row in edge)
    assert any(row["group_type"] == "blocking_reasons" and row["group"] == "directional_confluence_failed" for row in edge)
    assert any(row["group_type"] == "high_score_rejected" and row["group"] == "high_score_rejected" for row in edge)


def test_performance_report_creates_reports_directory(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    write_trades(
        data_path,
        [
            {"status": "tp2_hit", "result_r": "2", "closed_at": "2026-01-01"},
            {"status": "sl_hit", "result_r": "-1", "closed_at": "2026-01-02"},
        ],
    )

    result = generate_performance_report(data_path, reports_path)

    assert result["ok"] is True
    assert reports_path.exists()
    assert (reports_path / "performance_report.html").exists()
    assert (reports_path / "edge_breakdown.csv").exists()


def test_edge_breakdown_metrics_and_console_format() -> None:
    trades = [
        {"direction": "long", "setup_type": "MAIN_SIGNAL", "score": "95", "result_r": 2.0, "status": "tp2_hit"},
        {"direction": "long", "setup_type": "MAIN_SIGNAL", "score": "82", "result_r": -1.0, "status": "sl_hit"},
        {"direction": "short", "setup_type": "SECONDARY_SIGNAL", "score": "65", "result_r": -1.0, "status": "sl_hit"},
    ]

    rows = build_edge_breakdown(trades)
    text = format_edge_breakdown(rows)
    long_row = next(row for row in rows if row["group_type"] == "direction" and row["group"] == "long")

    assert long_row["trades"] == 2
    assert long_row["winrate"] == 50.0
    assert long_row["total_r"] == 1.0
    assert "🔎 Edge Breakdown" in text
    assert "✅ Mejores grupos" in text
    assert "⚠️ Peores grupos" in text
    assert "🧨 Principales fugas de R" in text
