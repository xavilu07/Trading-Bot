from __future__ import annotations

import csv
from pathlib import Path

from scripts.generate_intelligence_reports import generate_intelligence_reports


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_generate_intelligence_reports_creates_required_outputs(tmp_path: Path) -> None:
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
                "status": "tp_hit",
                "result_r": "1.5",
            },
            {
                "symbol": "ETHUSDT",
                "direction": "short",
                "setup_type": "SECONDARY_SIGNAL",
                "market_regime": "RANGING",
                "session": "NEW_YORK",
                "entry_context": "CHOPPY_RANGE",
                "trade_location": "near_resistance",
                "status": "sl_hit",
                "result_r": "-1",
            },
        ],
    )

    result = generate_intelligence_reports(data_path=data_path, reports_path=reports_path, min_trades=1)

    assert (reports_path / "edge_breakdown.csv").exists()
    assert (reports_path / "setup_rankings.csv").exists()
    assert (reports_path / "outcome_intelligence.csv").exists()
    assert (reports_path / "dashboard.html").exists()
    assert (reports_path / "intelligence_layer_manifest.json").exists()
    assert result["warnings"] == []


def test_generate_intelligence_reports_refreshes_stale_intelligence_warnings(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    report_dir = reports_path / "intelligence" / "daily" / "2026-01-01"
    report_dir.mkdir(parents=True)
    (report_dir / "report.json").write_text(
        """
        {
          "data_sources": {
            "outcome_rows": 0,
            "setup_rankings_rows": 0,
            "edge_breakdown_rows": 0,
            "warnings": [
              "Missing optional file: reports/outcome_intelligence.csv",
              "Missing optional file: reports/setup_rankings.csv",
              "Missing optional file: reports/edge_breakdown.csv",
              "Missing optional file: reports/controlled_experiments_report.json"
            ]
          },
          "warnings": [
            "Missing optional file: reports/outcome_intelligence.csv",
            "Missing optional file: reports/controlled_experiments_report.json"
          ]
        }
        """,
        encoding="utf-8",
    )
    (report_dir / "report.md").write_text(
        "- Missing optional file: reports/outcome_intelligence.csv\n"
        "- Missing optional file: reports/controlled_experiments_report.json\n",
        encoding="utf-8",
    )
    write_csv(
        data_path / "paper_trading" / "trades.csv",
        [{"status": "tp_hit", "result_r": "1", "setup_type": "MAIN_SIGNAL", "direction": "long"}],
    )

    result = generate_intelligence_reports(data_path=data_path, reports_path=reports_path, min_trades=1)
    refreshed_json = (report_dir / "report.json").read_text(encoding="utf-8")
    refreshed_md = (report_dir / "report.md").read_text(encoding="utf-8")

    assert result["refreshed_intelligence_reports"] == [str(report_dir / "report.json")]
    assert "reports/outcome_intelligence.csv" not in refreshed_json
    assert "reports/setup_rankings.csv" not in refreshed_json
    assert "reports/edge_breakdown.csv" not in refreshed_json
    assert "reports/controlled_experiments_report.json" in refreshed_json
    assert "reports/outcome_intelligence.csv" not in refreshed_md
