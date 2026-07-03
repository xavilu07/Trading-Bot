from __future__ import annotations

import json
from pathlib import Path

from scripts.analyze_active_signal_cleanup_shadow import analyze, write_reports


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_analyzer_counts_likely_zombie_and_releasable_duplicates(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    logs_path = tmp_path / "logs"
    reports_path = tmp_path / "reports"
    _write_json(
        data_path / "trade_signals" / "2026-01-01" / "sig_active.json",
        {
            "id": "sig_active",
            "symbol": "BTCUSDT",
            "decision": "long",
            "status": "published",
            "published_at": "2026-01-01T00:00:00+00:00",
        },
    )
    (data_path / "bot_activity").mkdir(parents=True)
    (data_path / "bot_activity" / "signals_log.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-01-04T00:00:00+00:00",
                "symbol": "BTCUSDT",
                "direction": "long",
                "score": 100,
                "rejection_reasons": ["duplicate_signal_suppressed"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = analyze(data_path=data_path, logs_path=logs_path, reports_path=reports_path)
    paths = write_reports(result, reports_path)

    assert result["metrics"]["total_active_signals"] == 1
    assert result["metrics"]["likely_zombie_count"] == 1
    assert result["metrics"]["duplicates_blocked_by_likely_zombie"] == 1
    assert result["metrics"]["high_score_duplicates_blocked_by_likely_zombie"] == 1
    assert result["metrics"]["estimated_released_candidates_if_cleanup"] == 1
    assert result["conclusion"]["recommended_action"] == "activar cleanup real"
    assert paths["json"].exists()
    assert paths["markdown"].exists()
    assert "ACTIVE_SIGNAL_CLEANUP_SHADOW_V1" in paths["markdown"].read_text(encoding="utf-8")


def test_analyzer_handles_missing_files_without_crashing(tmp_path: Path) -> None:
    result = analyze(data_path=tmp_path / "missing_data", logs_path=tmp_path / "missing_logs")

    assert result["metrics"]["total_active_signals"] == 0
    assert result["metrics"]["duplicate_signal_suppressed_events"] == 0
    assert result["conclusion"]["recommended_action"] == "datos insuficientes"


def test_analyzer_counts_runtime_shadow_events(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    logs_path = tmp_path / "logs"
    logs_path.mkdir(parents=True)
    (logs_path / "scheduler.log").write_text(
        json.dumps(
            {
                "event": "active_signal_cleanup_shadow_analysis",
                "symbol": "BTCUSDT",
                "direction": "long",
                "cleanup_classification": "LIKELY_ZOMBIE",
            }
        )
        + "\n"
        + json.dumps(
            {
                "event": "active_signal_cleanup_shadow_candidate",
                "symbol": "BTCUSDT",
                "direction": "long",
                "cleanup_classification": "LIKELY_ZOMBIE",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = analyze(data_path=data_path, logs_path=logs_path)

    assert result["metrics"]["runtime_cleanup_analysis_events"] == 1
    assert result["metrics"]["runtime_cleanup_candidate_events"] == 1
