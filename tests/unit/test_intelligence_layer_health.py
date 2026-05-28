from __future__ import annotations

import json
from pathlib import Path

from trading_signals.application.use_cases.intelligence_layer_health import (
    build_intelligence_layer_health,
    format_intelligence_layer_health_for_telegram,
)


def test_intelligence_layer_health_missing_manifest_is_error(tmp_path: Path) -> None:
    health = build_intelligence_layer_health(tmp_path / "reports")

    assert health["status"] == "error"
    assert health["missing_required_reports"] == ["missing_manifest"]


def test_intelligence_layer_health_reads_manifest_counts(tmp_path: Path) -> None:
    reports_path = tmp_path / "reports"
    reports_path.mkdir()
    (reports_path / "intelligence_layer_manifest.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-05-28T10:00:00+00:00",
                "rows": {
                    "closed_trades": 45,
                    "outcome_intelligence": 45,
                    "setup_rankings": 25,
                    "edge_breakdown": 32,
                },
                "warnings": [],
            }
        ),
        encoding="utf-8",
    )

    health = build_intelligence_layer_health(reports_path)
    message = format_intelligence_layer_health_for_telegram(health)

    assert health["status"] == "OK"
    assert health["closed_trades_analyzed"] == 45
    assert health["outcome_rows"] == 45
    assert health["setup_ranking_rows"] == 25
    assert health["edge_breakdown_rows"] == 32
    assert "🧠 Intelligence Layer" in message
    assert "- Missing required: 0" in message


def test_intelligence_layer_health_manifest_warnings_are_warning(tmp_path: Path) -> None:
    reports_path = tmp_path / "reports"
    reports_path.mkdir()
    (reports_path / "intelligence_layer_manifest.json").write_text(
        json.dumps({"generated_at": "2026-05-28T10:00:00+00:00", "rows": {}, "warnings": ["missing edge"]}),
        encoding="utf-8",
    )

    health = build_intelligence_layer_health(reports_path)

    assert health["status"] == "warning"
    assert health["missing_required_reports"] == ["missing edge"]
