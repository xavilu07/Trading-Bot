from __future__ import annotations

import json
from pathlib import Path

from trading_signals.application.use_cases.bot_health_report import (
    build_bot_health_report,
    format_bot_health_report_for_telegram,
)


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def test_bot_health_report_falls_back_to_signals_log(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    reports_path = tmp_path / "reports"
    write_jsonl(
        data_path / "bot_activity" / "signals_log.jsonl",
        [
            {
                "status": "sent",
                "symbol": "BTCUSDT",
                "direction": "long",
                "score": 82,
                "rejection_reasons": [],
            },
            {
                "status": "rejected",
                "symbol": "ETHUSDT",
                "direction": "long",
                "score": 92,
                "rejection_reasons": ["directional_confluence_failed"],
            },
            {
                "status": "no_trade",
                "symbol": "SOLUSDT",
                "direction": "short",
                "score": 64,
                "conditions_failed": ["volatility_failed"],
                "raw_summary": {"shadow_score": 78},
            },
        ],
    )

    report = build_bot_health_report(data_path=data_path, reports_path=reports_path, min_score=70)

    assert report["signals_emitted"] == 1
    assert report["signals_rejected"] == 2
    assert report["high_score_rejects"] == 1
    assert report["shadow_score_blocked"] == 1
    assert report["top_rejection_reasons"][0] == {"reason": "directional_confluence_failed", "count": 1}


def test_bot_health_report_prefers_existing_json(tmp_path: Path) -> None:
    reports_path = tmp_path / "reports"
    reports_path.mkdir(parents=True)
    (reports_path / "bot_health_report.json").write_text(
        json.dumps(
            {
                "signals_emitted": 2,
                "signals_rejected": 5,
                "top_rejection_reasons": [{"reason": "quality_score_failed", "count": 3}],
                "high_score_rejects": 4,
                "shadow_score_blocked": 1,
                "diagnosis": "json report ok",
            }
        ),
        encoding="utf-8",
    )

    report = build_bot_health_report(data_path=tmp_path / "data", reports_path=reports_path, min_score=70)

    assert report["source"] == "bot_health_report_json"
    assert report["signals_emitted"] == 2
    assert report["diagnosis"] == "json report ok"


def test_bot_health_telegram_message_is_short_and_contains_core_fields() -> None:
    message = format_bot_health_report_for_telegram(
        {
            "signals_emitted": 1,
            "signals_rejected": 10,
            "min_score": 70,
            "high_score_rejects": 3,
            "shadow_score_blocked": 2,
            "top_rejection_reasons": [
                {"reason": "distance_to_liquidity_extreme", "count": 5},
                {"reason": "quality_score_failed", "count": 3},
                {"reason": "against_htf", "count": 2},
                {"reason": "extra", "count": 1},
            ],
            "diagnosis": "hay candidatos fuertes bloqueados",
        }
    )

    assert len(message) <= 1200
    assert "🩺 Bot Health Report" in message
    assert "Señales emitidas: 1" in message
    assert "High score rejects >= 70: 3" in message
    assert "4." not in message
