from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path

from trading_signals.application.use_cases.daily_dev_report import (
    build_daily_dev_report,
    format_daily_dev_report,
    send_daily_dev_report,
)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_daily_dev_report_handles_missing_csvs(tmp_path: Path) -> None:
    report = build_daily_dev_report(
        tmp_path / "data",
        logs_path=tmp_path / "logs",
        report_date=date(2026, 5, 11),
        now=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
    )
    message = format_daily_dev_report(report)

    assert report["performance_today"]["trades"] == 0
    assert report["status"]["open_live_trades"] == 0
    assert "📊 Daily Bot Report" in message
    assert "Datos insuficientes todavía." in message


def test_daily_dev_report_builds_today_metrics_and_breakdowns(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    logs_path = tmp_path / "logs"
    logs_path.mkdir()
    scheduler_log = logs_path / "scheduler.log"
    scheduler_log.write_text("cycle ok\n", encoding="utf-8")
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    timestamp = now.timestamp()
    scheduler_log.touch()

    write_csv(
        data_path / "paper_trading" / "trades.csv",
        [
            {
                "symbol": "BTCUSDT",
                "direction": "long",
                "setup_type": "SECONDARY_SIGNAL",
                "status": "tp2_hit",
                "result_r": "2",
                "closed_at": "2026-05-11T09:00:00+00:00",
                "session": "LONDON",
            },
            {
                "symbol": "ETHUSDT",
                "direction": "short",
                "setup_type": "MAIN_SIGNAL",
                "status": "sl_hit",
                "result_r": "-1",
                "closed_at": "2026-05-11T10:00:00+00:00",
                "session": "NEW_YORK",
            },
            {
                "symbol": "SOLUSDT",
                "direction": "long",
                "setup_type": "MAIN_SIGNAL",
                "status": "tp2_hit",
                "result_r": "2",
                "closed_at": "2026-05-10T10:00:00+00:00",
            },
        ],
    )
    write_csv(data_path / "live_trading" / "trades.csv", [{"symbol": "BTCUSDT", "status": "open"}])
    patterns_path = data_path / "pattern_memory" / "patterns.jsonl"
    patterns_path.parent.mkdir(parents=True)
    records = [
        {
            "direction": "long",
            "setup_type": "MAIN_SIGNAL",
            "market_regime": "TRENDING",
            "session": "LONDON",
            "entry_context": "BREAKOUT",
            "trade_location": "near_support",
            "htf_trend": "bullish",
            "ltf_trend": "bullish",
            "warnings": [],
            "penalties": [],
            "blocking_reasons": [],
            "outcome": "win",
            "r_result": 1.0,
        }
        for _ in range(5)
    ]
    patterns_path.write_text("\n".join(json.dumps(item) for item in records), encoding="utf-8")
    scheduler_log.touch()
    # Keep the log mtime close to the injected `now` on platforms that support it.
    import os

    os.utime(scheduler_log, (timestamp, timestamp))

    report = build_daily_dev_report(
        data_path,
        logs_path=logs_path,
        report_date=date(2026, 5, 11),
        now=now,
        scheduler_expected_interval_seconds=900,
    )

    assert report["status"]["scheduler_ok"] is True
    assert report["status"]["pattern_memory_records"] == 5
    assert report["status"]["open_live_trades"] == 1
    assert report["performance_today"]["trades"] == 2
    assert report["performance_today"]["winrate"] == 50.0
    assert report["performance_today"]["total_r"] == 1.0
    assert report["performance_today"]["profit_factor"] == 2.0
    assert report["breakdown"]["direction"]["long"]["total_r"] == 2.0
    assert report["breakdown"]["setup_type"]["MAIN_SIGNAL"]["total_r"] == -1.0
    assert report["pattern_memory"]["insights_ready"] is True


def test_daily_dev_report_message_contains_main_sections(tmp_path: Path) -> None:
    report = build_daily_dev_report(
        tmp_path / "data",
        logs_path=tmp_path / "logs",
        report_date=date(2026, 5, 11),
        now=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
    )

    message = format_daily_dev_report(report)

    assert "📊 Daily Bot Report" in message
    assert "Fecha: 2026-05-11" in message
    assert "⚙️ Estado" in message
    assert "📈 Performance hoy" in message
    assert "🧪 Breakdown rápido" in message
    assert "⚠️ Fugas principales" in message
    assert "🧠 Pattern Memory" in message


def test_send_daily_dev_report_dry_run_prints_without_notifier_send(tmp_path: Path, capsys) -> None:
    class FakeNotifier:
        def send_dev_message(self, message: str, dry_run: bool = False):
            raise AssertionError("dry-run must not send Telegram messages")

    results = send_daily_dev_report(FakeNotifier(), tmp_path / "data", logs_path=tmp_path / "logs", dry_run=True)
    captured = capsys.readouterr()

    assert results == [{"recipient": "dry_run", "status": "printed", "provider_message_id": "dry_run"}]
    assert "📊 Daily Bot Report" in captured.out

