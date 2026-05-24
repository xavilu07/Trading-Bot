from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.analyze_recent_public_signals import analyze_recent_public_signals, format_audit


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_recent_public_signals_audit_handles_no_data(tmp_path: Path) -> None:
    result = analyze_recent_public_signals(
        data_path=tmp_path / "data",
        logs_path=tmp_path / "logs",
        reports_path=tmp_path / "reports",
        now=datetime(2026, 5, 24, 12, tzinfo=timezone.utc),
    )

    assert result["summary"]["total_public_signals"] == 0
    assert (tmp_path / "reports" / "recent_public_signals_audit.csv").exists()
    assert "Total public signals: 0" in format_audit(result)


def test_recent_public_signals_detects_public_signal_and_result(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_jsonl(
        data_path / "bot_activity" / "signals_log.jsonl",
        [
            {
                "timestamp": "2026-05-24T10:00:00+00:00",
                "symbol": "BTCUSDT",
                "direction": "long",
                "status": "sent",
                "setup_type": "MAIN_SIGNAL",
                "entry_price": 100,
                "stop_loss": 95,
                "take_profit": 110,
                "market_regime": "TRENDING",
                "session": "LONDON",
                "entry_context": "BREAKOUT",
                "raw_summary": {"signal_id": "sig_1"},
            }
        ],
    )
    write_csv(
        data_path / "live_trading" / "trades.csv",
        [
            {
                "signal_id": "sig_1",
                "public_published": "true",
                "symbol": "BTCUSDT",
                "direction": "long",
                "status": "tp_hit",
                "result_r": "2",
                "created_at": "2026-05-24T10:00:00+00:00",
                "closed_at": "2026-05-24T11:00:00+00:00",
            }
        ],
    )

    result = analyze_recent_public_signals(
        data_path=data_path,
        logs_path=tmp_path / "logs",
        reports_path=tmp_path / "reports",
        now=datetime(2026, 5, 24, 12, tzinfo=timezone.utc),
    )

    assert result["summary"]["total_public_signals"] == 1
    assert result["summary"]["wins"] == 1
    assert result["summary"]["total_r"] == 2.0
    assert result["rows"][0]["public_published"] is True


def test_loss_with_meta_reject_marks_would_meta_filter_block(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_jsonl(
        data_path / "bot_activity" / "signals_log.jsonl",
        [
            {
                "timestamp": "2026-05-24T10:00:00+00:00",
                "symbol": "ETHUSDT",
                "direction": "long",
                "status": "sent",
                "setup_type": "MAIN_SIGNAL",
                "raw_summary": {"signal_id": "sig_loss"},
                "meta_decision": {"meta_decision": "REJECT", "capital_preservation_mode": False},
                "trade_quality": {"trade_quality_grade": "B"},
                "edge_confirmation": {"edge_confirmation_level": "LOW"},
                "adaptive_thresholds": {"adaptive_threshold": 70},
            }
        ],
    )
    write_csv(
        data_path / "live_trading" / "trades.csv",
        [
            {
                "signal_id": "sig_loss",
                "public_published": "true",
                "symbol": "ETHUSDT",
                "direction": "long",
                "status": "sl_hit",
                "result_r": "-1",
                "created_at": "2026-05-24T10:00:00+00:00",
                "closed_at": "2026-05-24T11:00:00+00:00",
            }
        ],
    )

    result = analyze_recent_public_signals(
        data_path=data_path,
        logs_path=tmp_path / "logs",
        reports_path=tmp_path / "reports",
        now=datetime(2026, 5, 24, 12, tzinfo=timezone.utc),
    )

    row = result["rows"][0]
    assert row["result_r"] == -1.0
    assert row["meta_decision"] == "REJECT"
    assert row["would_meta_filter_block"] is True
    assert row["audit_recommendation"] == "loss_avoidable_by_meta_filter:meta_decision_reject"


def test_recent_public_signals_audit_generates_csv(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_jsonl(
        data_path / "bot_activity" / "signals_log.jsonl",
        [{"timestamp": "2026-05-24T10:00:00+00:00", "symbol": "BTCUSDT", "direction": "long", "status": "sent"}],
    )

    result = analyze_recent_public_signals(
        data_path=data_path,
        logs_path=tmp_path / "logs",
        reports_path=tmp_path / "reports",
        now=datetime(2026, 5, 24, 12, tzinfo=timezone.utc),
    )

    csv_path = result["csv_path"]
    rows = list(csv.DictReader(Path(csv_path).open("r", encoding="utf-8")))
    assert rows
    assert "would_meta_filter_block" in rows[0]
