from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
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
    assert (reports_path / "intelligence" / "daily" / datetime.now(UTC).date().isoformat() / "report.md").exists()
    assert (reports_path / "intelligence_generation_audit.md").exists()
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
    write_csv(
        data_path / "shadow_relaxation" / "skips.csv",
        [
            {
                "symbol": "BTCUSDT",
                "direction": "long",
                "score": "80",
                "block_reasons": json.dumps(["breakout_bad_location", "kill_switch_active"]),
                "safe_filters": json.dumps(["breakout_bad_location"]),
                "unsafe_filters": json.dumps(["kill_switch_active"]),
                "skip_reason": "unsafe_or_empty_filters",
            }
        ],
    )

    result = generate_intelligence_reports(data_path=data_path, reports_path=reports_path, min_trades=1)
    refreshed_payload = json.loads((report_dir / "report.json").read_text(encoding="utf-8"))
    refreshed_json = json.dumps(refreshed_payload)
    refreshed_md = (report_dir / "report.md").read_text(encoding="utf-8")

    assert str(report_dir / "report.json") in result["refreshed_intelligence_reports"]
    assert refreshed_payload["relaxation_shadow_status"]["skips_captured"] == 1
    assert refreshed_payload["relaxation_shadow_status"]["last_skip_reason"] == "unsafe_or_empty_filters"
    assert "reports/outcome_intelligence.csv" not in refreshed_json
    assert "reports/setup_rankings.csv" not in refreshed_json
    assert "reports/edge_breakdown.csv" not in refreshed_json
    assert "reports/controlled_experiments_report.json" in refreshed_json
    assert "reports/outcome_intelligence.csv" not in refreshed_md
    assert "## Relaxation Shadow Status" in refreshed_md
    assert "- skips captured: 1" in refreshed_md


def test_generate_intelligence_reports_uses_current_run_date_for_daily_report(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    old_dir = reports_path / "intelligence" / "daily" / "2026-05-28"
    old_dir.mkdir(parents=True)
    old_report = old_dir / "report.md"
    old_report.write_text("old report\n", encoding="utf-8")
    write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            {
                "status": "tp_hit",
                "result_r": "1",
                "setup_type": "MAIN_SIGNAL",
                "direction": "long",
                "closed_at": "2026-05-28T10:00:00+00:00",
            }
        ],
    )

    result = generate_intelligence_reports(
        data_path=data_path,
        reports_path=reports_path,
        min_trades=1,
        run_datetime=datetime(2026, 6, 1, 9, 0, tzinfo=UTC),
        bot_data_dir=tmp_path,
    )

    daily_dir = reports_path / "intelligence" / "daily" / "2026-06-01"
    assert daily_dir.exists()
    assert (daily_dir / "report.md").exists()
    assert (daily_dir / "report.json").exists()
    assert old_report.read_text(encoding="utf-8") == "old report\n"
    assert result["daily_report"]["date"] == "2026-06-01"
    assert result["generation_audit"]["latest_daily_folder_was_stale_before_generation"] is True
    assert result["generation_audit"]["latest_daily_folder_is_stale_after_generation"] is False


def test_generate_intelligence_reports_writes_daily_json_and_md_to_output_folder(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    write_csv(
        data_path / "paper_trading" / "trades.csv",
        [{"status": "sl_hit", "result_r": "-1", "setup_type": "MAIN_SIGNAL", "direction": "short"}],
    )

    result = generate_intelligence_reports(
        data_path=data_path,
        reports_path=reports_path,
        min_trades=1,
        run_datetime=datetime(2026, 6, 1, 12, 30, tzinfo=UTC),
        bot_data_dir=tmp_path,
    )
    payload = json.loads((reports_path / "intelligence" / "daily" / "2026-06-01" / "report.json").read_text(encoding="utf-8"))
    markdown = (reports_path / "intelligence" / "daily" / "2026-06-01" / "report.md").read_text(encoding="utf-8")

    assert payload["period"] == "2026-06-01"
    assert payload["data_sources"]["latest_trade_timestamp"] == ""
    assert "Intelligence Report DAILY 2026-06-01" in markdown
    assert result["daily_report"]["report_md_written"] is True
