from __future__ import annotations

import csv
import inspect
import json
from datetime import UTC, datetime
from pathlib import Path

import trading_signals.application.use_cases.private_runtime_report as private_runtime_report_module
from trading_signals.application.use_cases.private_runtime_report import (
    build_private_runtime_report,
    format_private_runtime_report_for_telegram,
    load_private_runtime_report_state,
    save_private_runtime_report_state,
    should_send_private_runtime_report,
)


PAPER_FIELDS = [
    "trade_id",
    "symbol",
    "direction",
    "setup_type",
    "score",
    "status",
    "result_r",
    "opened_at",
    "updated_at",
    "closed_at",
    "session",
]


def test_private_runtime_report_detects_new_paper_trades(tmp_path: Path) -> None:
    _write_paper_trades(
        tmp_path,
        [
            _trade("t1", "BTCUSDT", "long", "open", "0", score="75", setup_type="MAIN_SIGNAL"),
            _trade("t2", "ETHUSDT", "short", "open", "0", score="90", setup_type="SECONDARY_SIGNAL"),
        ],
    )

    report, next_state = build_private_runtime_report(
        data_path=tmp_path,
        state={},
        cycle_number=5,
        last_cycle_duration_seconds=1.5,
        scheduler_status="ok",
        now=datetime(2026, 6, 10, tzinfo=UTC),
    )

    assert report["new_paper_trades_count"] == 2
    assert report["open_paper_trades_count"] == 2
    assert next_state["last_trade_row_count"] == 2


def test_private_runtime_report_detects_closed_paper_trades_from_state_transition(tmp_path: Path) -> None:
    _write_paper_trades(
        tmp_path,
        [_trade("t1", "BTCUSDT", "long", "tp2_hit", "1.5", closed_at="2026-06-10T10:00:00+00:00")],
    )
    state = {
        "known_paper_trades": {
            "t1": {"status": "open", "result_r": "0", "updated_at": "", "closed_at": ""},
        }
    }

    report, _ = build_private_runtime_report(
        data_path=tmp_path,
        state=state,
        cycle_number=5,
        last_cycle_duration_seconds=1,
        scheduler_status="ok",
    )

    assert report["closed_paper_trades_count"] == 1
    assert report["recent_closed_r_total"] == 1.5
    assert report["recent_wins"] == 1
    assert report["recent_losses"] == 0


def test_private_runtime_report_computes_recent_r_and_losses(tmp_path: Path) -> None:
    _write_paper_trades(
        tmp_path,
        [
            _trade("t1", "BTCUSDT", "long", "sl_hit", "-1.0", closed_at="2026-06-10T10:00:00+00:00"),
            _trade("t2", "ETHUSDT", "short", "tp2_hit", "2.0", closed_at="2026-06-10T10:00:00+00:00"),
        ],
    )

    report, _ = build_private_runtime_report(
        data_path=tmp_path,
        state={},
        cycle_number=5,
        last_cycle_duration_seconds=1,
        scheduler_status="ok",
    )

    assert report["closed_paper_trades_count"] == 2
    assert report["recent_closed_r_total"] == 1.0
    assert report["recent_wins"] == 1
    assert report["recent_losses"] == 1


def test_private_runtime_report_lists_open_trades(tmp_path: Path) -> None:
    _write_paper_trades(
        tmp_path,
        [
            _trade("t1", "BNBUSDT", "long", "open", "0.42", score="75", setup_type="SECONDARY_SIGNAL"),
            _trade("t2", "SOLUSDT", "long", "tp2_hit", "1.5", closed_at="2026-06-10T10:00:00+00:00"),
        ],
    )

    report, _ = build_private_runtime_report(
        data_path=tmp_path,
        state={},
        cycle_number=5,
        last_cycle_duration_seconds=1,
        scheduler_status="ok",
    )
    message = format_private_runtime_report_for_telegram(report)

    assert report["open_paper_trades_count"] == 1
    assert "BNBUSDT long open +0.42R score 75 SECONDARY_SIGNAL LONDON" in message


def test_private_runtime_report_counts_elite_profile_c_and_public_routing(tmp_path: Path) -> None:
    _write_signals(
        tmp_path,
        [
            {
                "symbol": "BTCUSDT",
                "direction": "long",
                "score": 95,
                "setup_type": "SECONDARY_SIGNAL",
                "session": "LONDON",
                "public_published": True,
                "decision_trace": ["elite_profile_c=true"],
            },
            {
                "symbol": "ETHUSDT",
                "direction": "short",
                "score": 80,
                "setup_type": "MAIN_SIGNAL",
                "public_block_reason": "market_regime_ranging",
                "rejection_reasons": ["market_regime_ranging"],
            },
        ],
    )

    report, _ = build_private_runtime_report(
        data_path=tmp_path,
        state={},
        cycle_number=5,
        last_cycle_duration_seconds=1,
        scheduler_status="ok",
    )
    message = format_private_runtime_report_for_telegram(report)

    assert report["public_signals_sent"] == 1
    assert report["blocked_public_signals"] == 1
    assert report["elite_profile_c_matches_count"] == 1
    assert "🔥 ELITE PROFILE C detected" in message
    assert "market_regime_ranging: 1" in message


def test_private_runtime_report_respects_every_n_cycles() -> None:
    assert should_send_private_runtime_report(enabled=True, cycle_number=5, every_cycles=5, state={}) is True
    assert (
        should_send_private_runtime_report(
            enabled=True,
            cycle_number=7,
            every_cycles=5,
            state={"last_cycle_reported": 5},
        )
        is False
    )
    assert (
        should_send_private_runtime_report(
            enabled=True,
            cycle_number=10,
            every_cycles=5,
            state={"last_cycle_reported": 5},
        )
        is True
    )
    assert should_send_private_runtime_report(enabled=False, cycle_number=10, every_cycles=5, state={}) is False


def test_private_runtime_report_handles_missing_files(tmp_path: Path) -> None:
    report, next_state = build_private_runtime_report(
        data_path=tmp_path,
        state={},
        cycle_number=5,
        last_cycle_duration_seconds=None,
        scheduler_status="ok",
    )

    assert report["new_paper_trades_count"] == 0
    assert report["closed_paper_trades_count"] == 0
    assert report["public_signals_sent"] == 0
    assert next_state["last_trade_row_count"] == 0
    assert next_state["last_signal_log_offset"] == 0


def test_private_runtime_report_state_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "runtime" / "private_runtime_report_state.json"
    save_private_runtime_report_state(path, {"last_cycle_reported": 5})

    assert load_private_runtime_report_state(path) == {"last_cycle_reported": 5}


def test_private_runtime_report_does_not_send_public_messages() -> None:
    source = inspect.getsource(private_runtime_report_module)

    assert "send_public_signal" not in source
    assert ".send_public" not in source


def _write_paper_trades(base: Path, rows: list[dict[str, str]]) -> None:
    path = base / "paper_trading" / "trades.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _write_signals(base: Path, rows: list[dict[str, object]]) -> None:
    path = base / "bot_activity" / "signals_log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def _trade(
    trade_id: str,
    symbol: str,
    direction: str,
    status: str,
    result_r: str,
    *,
    score: str = "70",
    setup_type: str = "MAIN_SIGNAL",
    closed_at: str = "",
) -> dict[str, str]:
    return {
        "trade_id": trade_id,
        "symbol": symbol,
        "direction": direction,
        "setup_type": setup_type,
        "score": score,
        "status": status,
        "result_r": result_r,
        "opened_at": "2026-06-10T09:00:00+00:00",
        "updated_at": "2026-06-10T09:00:00+00:00",
        "closed_at": closed_at,
        "session": "LONDON",
    }
