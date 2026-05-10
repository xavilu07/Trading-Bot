from __future__ import annotations

import json

from scripts.bot_status import build_bot_status, format_bot_status


class DummySettings:
    telegram_bot_token = "token"
    telegram_public_chat_id = "public"
    telegram_dev_chat_id = "dev"
    scan_interval_seconds = 900


def _pattern(direction: str = "long", outcome: str = "win", r_result: float = 1.0) -> dict[str, object]:
    return {
        "direction": direction,
        "setup_type": "MAIN_SIGNAL",
        "market_regime": "TRENDING",
        "session": "LONDON",
        "entry_context": "BREAKOUT",
        "trade_location": "near_support",
        "htf_trend": "bullish",
        "ltf_trend": "bullish",
        "warnings": ["low_volume"],
        "penalties": ["distance_to_liquidity_penalty"],
        "blocking_reasons": [],
        "outcome": outcome,
        "r_result": r_result,
    }


def test_bot_status_reads_pattern_memory_and_logs(tmp_path) -> None:
    patterns_path = tmp_path / "data" / "pattern_memory" / "patterns.jsonl"
    patterns_path.parent.mkdir(parents=True)
    patterns = [_pattern(outcome="win", r_result=1.2) for _ in range(5)]
    patterns_path.write_text("\n".join(json.dumps(item) for item in patterns), encoding="utf-8")
    log_path = tmp_path / "logs" / "scheduler.log"
    log_path.parent.mkdir()
    log_path.write_text("scheduler ok\n", encoding="utf-8")

    status = build_bot_status(base_path=tmp_path, settings=DummySettings())

    assert status["telegram"]["bot_token_configured"] is True
    assert status["telegram"]["public_chat_configured"] is True
    assert status["telegram"]["dev_chat_configured"] is True
    assert status["pattern_memory"]["records"] == 5
    assert status["pattern_memory"]["insights_ready"] is True
    assert status["logs"]["scheduler_log_exists"] is True
    assert status["runtime"]["scheduler_expected_interval_seconds"] == 900


def test_format_bot_status_contains_expected_sections(tmp_path) -> None:
    status = {
        "telegram": {
            "bot_token_configured": True,
            "public_chat_configured": True,
            "dev_chat_configured": True,
        },
        "pattern_memory": {
            "records": 5,
            "size_bytes": 2048,
            "insights_ready": True,
        },
        "logs": {
            "scheduler_log_exists": True,
            "scheduler_log_size_bytes": 1024 * 1024,
            "scheduler_log_updated_at": "2026-01-01T00:00:00",
        },
        "runtime": {
            "environment_loaded": True,
            "scheduler_expected_interval_seconds": 900,
        },
    }

    message = format_bot_status(status)

    assert "✅ Bot status" in message
    assert "✅ Telegram configured" in message
    assert "🧠 Pattern Memory" in message
    assert "- Patterns stored: 5" in message
    assert "- Insights ready: YES" in message
    assert "📄 Logs" in message
    assert "- Scheduler log: OK" in message
    assert "⚙️ Runtime" in message
    assert "- Scheduler expected interval: 900 sec" in message
