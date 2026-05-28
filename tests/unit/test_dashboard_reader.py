from __future__ import annotations

import csv
import json
from pathlib import Path

from trading_signals.application.use_cases.dashboard_reader import build_dashboard_summary


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_dashboard_summary_handles_missing_files(tmp_path: Path) -> None:
    summary = build_dashboard_summary(
        data_path=tmp_path / "data",
        logs_path=tmp_path / "logs",
        runtime_path=tmp_path / ".runtime",
        reports_path=tmp_path / "reports",
    )

    assert summary["latest_signals"] == []
    assert summary["latest_rejections"] == []
    assert summary["paper_stats"]["trades_total"] == 0
    assert summary["files"]["paper_trades"]["state"] == "missing"
    assert summary["files"]["experimental_signals"]["state"] == "missing"
    assert summary["last_cycle"]["status"] == "missing"
    assert summary["intelligence_layer"]["status"] == "error"


def test_dashboard_summary_reads_signals_rejections_stats_and_logs(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    logs_path = tmp_path / "logs"
    runtime_path = tmp_path / ".runtime"
    write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            {
                "symbol": "BTCUSDT",
                "direction": "long",
                "score": "70",
                "status": "tp2_hit",
                "result_r": "2",
                "closed_at": "2026-01-02T00:00:00+00:00",
                "opened_at": "2026-01-01T00:00:00+00:00",
                "entry_or_rejection_reason": "paper_tradeable",
                "conditions_failed": "[]",
                "avoidance_warnings": "[]",
            },
            {
                "symbol": "ETHUSDT",
                "direction": "short",
                "score": "45",
                "status": "sl_hit",
                "result_r": "-1",
                "closed_at": "2026-01-03T00:00:00+00:00",
                "opened_at": "2026-01-02T00:00:00+00:00",
                "entry_or_rejection_reason": "distance_to_liquidity_penalty|signal_not_ready",
                "conditions_failed": '["quality_score_failed"]',
                "avoidance_warnings": '["low_volume"]',
            },
        ],
    )
    write_csv(
        data_path / "paper_trading" / "experimental_signals.csv",
        [
            {
                "timestamp": "2026-01-04T00:00:00+00:00",
                "symbol": "SOLUSDT",
                "direction": "long",
                "score": "80",
                "experimental_reason": "experimental_accept",
                "real_reason": "directional_confluence_failed|risk_plan_missing",
                "market_regime": "TRENDING",
                "entry_context": "BREAKOUT",
                "outcome": "loss",
                "exit_reason": "adverse_move_reached",
                "evaluated_at": "2026-01-04T01:00:00+00:00",
            }
        ],
    )
    logs_path.mkdir(parents=True)
    (logs_path / "scheduler.log").write_text('cycle started\n{"event": "cycle_finished", "cycle": 7}\n', encoding="utf-8")
    reports_path = tmp_path / "reports"
    reports_path.mkdir()
    (reports_path / "intelligence_layer_manifest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-05-28T10:00:00+00:00",
                "rows": {
                    "closed_trades": 2,
                    "outcome_intelligence": 2,
                    "setup_rankings": 4,
                    "edge_breakdown": 5,
                },
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )

    summary = build_dashboard_summary(data_path=data_path, logs_path=logs_path, runtime_path=runtime_path, reports_path=reports_path)

    assert summary["files"]["paper_trades"]["rows"] == 2
    assert summary["files"]["experimental_signals"]["rows"] == 1
    assert summary["paper_stats"]["closed_trades"] == 2
    assert summary["paper_stats"]["total_r"] == 1.0
    assert summary["latest_signals"][0]["symbol"] == "SOLUSDT"
    assert summary["latest_rejections"][0]["source"] == "experimental_signals"
    assert summary["last_cycle"]["last_event"] == {"event": "cycle_finished", "cycle": 7}
    assert summary["intelligence_layer"]["status"] == "OK"
    assert summary["intelligence_layer"]["edge_breakdown_rows"] == 5
    labels = [item["label"] for item in summary["top_rejection_reasons"]]
    assert "directional_confluence_failed" in labels
    assert "quality_score_failed" in labels
