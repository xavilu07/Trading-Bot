from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.backtest_public_signal_filters import backtest_public_signal_filters, format_backtest


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


def base_signal(signal_id: str, timestamp: str, symbol: str = "BTCUSDT", meta: object | None = None) -> dict[str, object]:
    row: dict[str, object] = {
        "timestamp": timestamp,
        "symbol": symbol,
        "direction": "long",
        "status": "sent",
        "setup_type": "MAIN_SIGNAL",
        "raw_summary": {"signal_id": signal_id},
    }
    if meta is not None:
        row["meta_decision"] = meta
    return row


def trade(signal_id: str, timestamp: str, closed_at: str, result_r: float, symbol: str = "BTCUSDT") -> dict[str, object]:
    return {
        "signal_id": signal_id,
        "public_published": "true",
        "symbol": symbol,
        "direction": "long",
        "status": "tp_hit" if result_r > 0 else "sl_hit",
        "result_r": str(result_r),
        "created_at": timestamp,
        "closed_at": closed_at,
    }


def summary_by_scenario(result: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        str(row["scenario"]): row
        for row in result["summary"]
        if isinstance(row, dict)
    }


def test_baseline_counts_all_public_signals(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_jsonl(
        data_path / "bot_activity" / "signals_log.jsonl",
        [
            base_signal("sig_1", "2026-05-24T08:00:00+00:00", "BTCUSDT", {"meta_decision": "SEND"}),
            base_signal("sig_2", "2026-05-24T09:00:00+00:00", "ETHUSDT", {"meta_decision": "SEND"}),
        ],
    )
    write_csv(
        data_path / "live_trading" / "trades.csv",
        [
            trade("sig_1", "2026-05-24T08:00:00+00:00", "2026-05-24T08:30:00+00:00", -1, "BTCUSDT"),
            trade("sig_2", "2026-05-24T09:00:00+00:00", "2026-05-24T09:30:00+00:00", 2, "ETHUSDT"),
        ],
    )

    result = backtest_public_signal_filters(
        data_path=data_path,
        logs_path=tmp_path / "logs",
        reports_path=tmp_path / "reports",
        now=datetime(2026, 5, 24, 12, tzinfo=timezone.utc),
    )

    baseline = summary_by_scenario(result)["BASELINE"]
    assert baseline["total_signals"] == 2
    assert baseline["wins"] == 1
    assert baseline["losses"] == 1
    assert baseline["total_r"] == 1.0


def test_kill_switch_blocks_after_prior_loss(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_jsonl(
        data_path / "bot_activity" / "signals_log.jsonl",
        [
            base_signal("sig_loss", "2026-05-24T08:00:00+00:00", "BTCUSDT", {"meta_decision": "SEND"}),
            base_signal("sig_next", "2026-05-24T10:00:00+00:00", "ETHUSDT", {"meta_decision": "SEND"}),
        ],
    )
    write_csv(
        data_path / "live_trading" / "trades.csv",
        [
            trade("sig_loss", "2026-05-24T08:00:00+00:00", "2026-05-24T08:30:00+00:00", -1, "BTCUSDT"),
            trade("sig_next", "2026-05-24T10:00:00+00:00", "2026-05-24T10:30:00+00:00", -1, "ETHUSDT"),
        ],
    )

    result = backtest_public_signal_filters(
        data_path=data_path,
        logs_path=tmp_path / "logs",
        reports_path=tmp_path / "reports",
        now=datetime(2026, 5, 24, 12, tzinfo=timezone.utc),
    )

    kill = summary_by_scenario(result)["KILL_SWITCH"]
    assert kill["total_signals"] == 1
    assert kill["blocked_signals"] == 1
    assert kill["avoided_losses"] == 1


def test_meta_unknown_does_not_invent_block(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_jsonl(
        data_path / "bot_activity" / "signals_log.jsonl",
        [base_signal("sig_unknown", "2026-05-24T08:00:00+00:00", "BTCUSDT")],
    )
    write_csv(
        data_path / "live_trading" / "trades.csv",
        [trade("sig_unknown", "2026-05-24T08:00:00+00:00", "2026-05-24T08:30:00+00:00", -1)],
    )

    result = backtest_public_signal_filters(
        data_path=data_path,
        logs_path=tmp_path / "logs",
        reports_path=tmp_path / "reports",
        now=datetime(2026, 5, 24, 12, tzinfo=timezone.utc),
    )

    meta = summary_by_scenario(result)["META_FILTER"]
    assert meta["total_signals"] == 1
    assert meta["blocked_signals"] == 0
    assert meta["meta_filter_evaluable"] == "false"
    assert meta["meta_unknown_signals"] == 1


def test_combined_applies_meta_and_kill_switch(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_jsonl(
        data_path / "bot_activity" / "signals_log.jsonl",
        [
            base_signal("sig_loss", "2026-05-24T08:00:00+00:00", "BTCUSDT", {"meta_decision": "SEND"}),
            base_signal("sig_reject", "2026-05-24T10:00:00+00:00", "ETHUSDT", {"meta_decision": "REJECT"}),
        ],
    )
    write_csv(
        data_path / "live_trading" / "trades.csv",
        [
            trade("sig_loss", "2026-05-24T08:00:00+00:00", "2026-05-24T08:30:00+00:00", -1, "BTCUSDT"),
            trade("sig_reject", "2026-05-24T10:00:00+00:00", "2026-05-24T10:30:00+00:00", -1, "ETHUSDT"),
        ],
    )

    result = backtest_public_signal_filters(
        data_path=data_path,
        logs_path=tmp_path / "logs",
        reports_path=tmp_path / "reports",
        now=datetime(2026, 5, 24, 12, tzinfo=timezone.utc),
    )

    combined = summary_by_scenario(result)["META_FILTER_PLUS_KILL_SWITCH"]
    details = [
        row
        for row in result["details"]
        if isinstance(row, dict) and row.get("scenario") == "META_FILTER_PLUS_KILL_SWITCH"
    ]
    assert combined["total_signals"] == 1
    assert combined["blocked_signals"] == 1
    assert combined["avoided_losses"] == 1
    assert details[-1]["block_reason"] == "meta_filter|kill_switch"


def test_backtest_writes_csv_outputs(tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    write_jsonl(
        data_path / "bot_activity" / "signals_log.jsonl",
        [base_signal("sig_1", "2026-05-24T08:00:00+00:00", "BTCUSDT", {"meta_decision": "SEND"})],
    )
    write_csv(
        data_path / "live_trading" / "trades.csv",
        [trade("sig_1", "2026-05-24T08:00:00+00:00", "2026-05-24T08:30:00+00:00", 1)],
    )

    result = backtest_public_signal_filters(
        data_path=data_path,
        logs_path=tmp_path / "logs",
        reports_path=tmp_path / "reports",
        now=datetime(2026, 5, 24, 12, tzinfo=timezone.utc),
    )

    assert Path(result["detail_csv_path"]).exists()
    assert Path(result["summary_csv_path"]).exists()
    assert "Public Signal Filter Backtest" in format_backtest(result)
