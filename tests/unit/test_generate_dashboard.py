from __future__ import annotations

import csv
from pathlib import Path

from scripts.generate_dashboard import build_dashboard_model, generate_dashboard, load_dashboard_data


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_dashboard_without_data_does_not_break(tmp_path: Path) -> None:
    result = generate_dashboard(tmp_path / "data", tmp_path / "reports", min_trades=3)
    dashboard = tmp_path / "reports" / "dashboard.html"

    assert result["model"]["summary"]["trades"] == 0
    assert dashboard.exists()
    assert "Trading Bot Dashboard" in dashboard.read_text(encoding="utf-8")
    assert "Datos insuficientes" in dashboard.read_text(encoding="utf-8")


def test_dashboard_with_trades_generates_html_and_metrics(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            {
                "symbol": "BTCUSDT",
                "direction": "long",
                "setup_type": "MAIN_SIGNAL",
                "market_regime": "TRENDING",
                "session": "LONDON",
                "entry_context": "BREAKOUT",
                "trade_location": "near_support",
                "liquidity_sweep": "yes",
                "public_published": "true",
                "status": "tp2_hit",
                "result_r": "2",
            },
            {
                "symbol": "ETHUSDT",
                "direction": "short",
                "setup_type": "SECONDARY_SIGNAL",
                "market_regime": "RANGING",
                "session": "NEW_YORK",
                "entry_context": "CHOPPY_RANGE",
                "trade_location": "near_resistance",
                "liquidity_sweep": "no",
                "public_published": "false",
                "status": "sl_hit",
                "result_r": "-1",
            },
        ],
    )
    write_csv(
        reports_path / "setup_rankings.csv",
        [{"ranking_type": "setup_type", "group": "MAIN_SIGNAL", "trades": "1", "winrate": "100", "total_r": "2", "avg_r": "2", "profit_factor": ""}],
    )

    result = generate_dashboard(data_path, reports_path, min_trades=1)
    html = (reports_path / "dashboard.html").read_text(encoding="utf-8")

    assert result["model"]["summary"]["trades"] == 2
    assert result["model"]["summary"]["winrate"] == 50.0
    assert result["model"]["summary"]["total_r"] == 1.0
    assert "Performance por dirección" in html
    assert "MAIN_SIGNAL" in html
    assert "SECONDARY_SIGNAL" in html
    assert "Public vs DEV/Paper" in html


def test_dashboard_tolerates_missing_columns(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_csv(
        data_path / "paper_trading" / "old.csv",
        [
            {"status": "tp_hit", "result_r": "1.5"},
            {"status": "sl_hit", "result_r": "-1"},
        ],
    )

    data = load_dashboard_data(data_path, tmp_path / "reports")
    model = build_dashboard_model(data, min_trades=1)

    assert model["summary"]["trades"] == 2
    assert any(row["group"] == "UNKNOWN" for row in model["by_setup"])
    assert any(row["group"] == "unknown" for row in model["public_vs_dev"])

