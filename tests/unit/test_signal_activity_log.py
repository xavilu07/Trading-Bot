from __future__ import annotations

import json

from trading_signals.memory import signal_activity_log


def test_append_signal_log_writes_jsonl(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "data/bot_activity/signals_log.jsonl"
    monkeypatch.setattr(signal_activity_log, "SIGNALS_LOG_PATH", log_path)

    appended = signal_activity_log.append_signal_log(
        {
            "timestamp": "2026-05-13T12:34:56+00:00",
            "symbol": "ethusdt",
            "direction": "SHORT",
            "score": 80,
            "status": "rejected",
            "rejection_reasons": ["directional_confluence_failed"],
            "conditions_failed": ["secondary_setup"],
            "rr": 2.1,
            "entry_price": 3000,
            "stop_loss": 3030,
            "take_profit": 2940,
            "trend_entry": "bearish",
            "trend_higher": "bearish",
            "relaxed_public_policy_decision": "allow",
            "relaxed_public_policy_vs_current": "relaxed_allow_current_block",
            "relaxed_public_shadow_sent_dev": True,
            "raw_summary": {"source": "unit_test"},
        }
    )

    assert appended is True
    rows = log_path.read_text().splitlines()
    assert len(rows) == 1
    payload = json.loads(rows[0])
    assert payload["symbol"] == "ETHUSDT"
    assert payload["direction"] == "short"
    assert payload["status"] == "rejected"
    assert payload["rejection_reasons"] == ["directional_confluence_failed"]
    assert payload["relaxed_public_policy_decision"] == "allow"
    assert payload["relaxed_public_policy_vs_current"] == "relaxed_allow_current_block"
    assert payload["relaxed_public_shadow_sent_dev"] is True
    assert payload["dedupe_key"]


def test_append_signal_log_skips_recent_duplicate(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "data/bot_activity/signals_log.jsonl"
    monkeypatch.setattr(signal_activity_log, "SIGNALS_LOG_PATH", log_path)
    entry = {
        "timestamp": "2026-05-13T12:34:56+00:00",
        "symbol": "BTCUSDT",
        "direction": "long",
        "score": 72,
        "status": "paper",
    }

    assert signal_activity_log.append_signal_log(entry) is True
    assert signal_activity_log.append_signal_log({**entry, "timestamp": "2026-05-13T12:34:01+00:00"}) is False
    assert len(log_path.read_text().splitlines()) == 1


def test_append_signal_log_rotates_when_too_large(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "data/bot_activity/signals_log.jsonl"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("x" * 20)
    monkeypatch.setattr(signal_activity_log, "SIGNALS_LOG_PATH", log_path)
    monkeypatch.setattr(signal_activity_log, "MAX_SIGNALS_LOG_BYTES", 10)

    assert signal_activity_log.append_signal_log(
        {
            "timestamp": "2026-05-13T12:35:00+00:00",
            "symbol": "SOLUSDT",
            "direction": "long",
            "score": 65,
            "status": "experimental",
        }
    ) is True

    assert log_path.with_suffix(".jsonl.1").exists()
    assert len(log_path.read_text().splitlines()) == 1
