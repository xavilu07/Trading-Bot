from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import scripts.run_kill_switch_monitor as monitor
from trading_signals.risk.trading_pause import is_trading_paused, pause_trading


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # load_settings() reads from process env; make sure no real bot-token/chat-id leaks
    # into these tests so _notify()/_notify_resume() stay no-ops (network-free).
    for key in ("QIC_TELEGRAM_BOT_TOKEN", "QIC_TELEGRAM_CHAT_IDS"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("KILL_SWITCH_ENABLED", "true")
    monkeypatch.setenv("MAX_DAILY_LOSS_R", "10")
    monkeypatch.setenv("MAX_CONSECUTIVE_LOSSES", "2")
    monkeypatch.setenv("MAX_WEEKLY_DRAWDOWN_R", "10")
    monkeypatch.setenv("KILL_SWITCH_COOLDOWN_HOURS", "0")
    monkeypatch.setenv("CONSECUTIVE_LOSS_RESET_HOURS", "12")
    monkeypatch.setenv("DATA_STORAGE_PATH", str(tmp_path / "data"))
    monkeypatch.chdir(tmp_path)


def _write_two_losses(tmp_path: Path, *, closed_at: datetime) -> None:
    trades_csv = tmp_path / "data" / "paper_trading" / "trades.csv"
    trades_csv.parent.mkdir(parents=True, exist_ok=True)
    with trades_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["status", "result_r", "closed_at"])
        writer.writeheader()
        writer.writerow({"status": "sl_hit", "result_r": "-0.5", "closed_at": closed_at.isoformat()})
        writer.writerow({"status": "sl_hit", "result_r": "-0.5", "closed_at": closed_at.isoformat()})


def _run_main(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> tuple[int, dict]:
    captured: dict = {}
    monkeypatch.setattr("builtins.print", lambda payload: captured.update(json.loads(payload)))
    exit_code = monitor.main(argv)
    return exit_code, captured


def test_pauses_when_unhealthy_and_not_yet_paused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_two_losses(tmp_path, closed_at=datetime.now(tz=UTC) - timedelta(hours=1))

    exit_code, result = _run_main(monkeypatch, [])

    assert exit_code == 0
    assert result["status"] == "paused"
    state = is_trading_paused(tmp_path / "data" / "runtime" / "trading_paused.json")
    assert state["paused"] is True
    assert state["reason"] == "consecutive_losses_limit"


def test_auto_resumes_once_consecutive_loss_streak_goes_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_two_losses(tmp_path, closed_at=datetime.now(tz=UTC) - timedelta(hours=13))
    pause_path = tmp_path / "data" / "runtime" / "trading_paused.json"
    pause_trading(reason="consecutive_losses_limit", details={}, path=pause_path)

    exit_code, result = _run_main(monkeypatch, [])

    assert exit_code == 0
    assert result["status"] == "auto_resumed"
    assert is_trading_paused(pause_path)["paused"] is False
    raw_state = json.loads(pause_path.read_text(encoding="utf-8"))
    assert raw_state["resumed_by"] == "qic_kill_switch_monitor"


def test_does_not_auto_resume_a_manual_pause(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_two_losses(tmp_path, closed_at=datetime.now(tz=UTC) - timedelta(hours=13))
    pause_path = tmp_path / "data" / "runtime" / "trading_paused.json"
    pause_trading(reason="manual_telegram", details={"actor": "xavi"}, path=pause_path)

    exit_code, result = _run_main(monkeypatch, [])

    assert exit_code == 0
    assert result["status"] == "already_paused"
    state = is_trading_paused(pause_path)
    assert state["paused"] is True
    assert state["reason"] == "manual_telegram"


def test_does_not_auto_resume_while_streak_still_fresh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_two_losses(tmp_path, closed_at=datetime.now(tz=UTC) - timedelta(hours=1))
    pause_path = tmp_path / "data" / "runtime" / "trading_paused.json"
    pause_trading(reason="consecutive_losses_limit", details={}, path=pause_path)

    exit_code, result = _run_main(monkeypatch, [])

    assert exit_code == 0
    assert result["status"] == "already_paused"
    assert is_trading_paused(pause_path)["paused"] is True


def test_dry_run_does_not_mutate_state_on_auto_resume(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_two_losses(tmp_path, closed_at=datetime.now(tz=UTC) - timedelta(hours=13))
    pause_path = tmp_path / "data" / "runtime" / "trading_paused.json"
    pause_trading(reason="consecutive_losses_limit", details={}, path=pause_path)

    exit_code, result = _run_main(monkeypatch, ["--dry-run"])

    assert exit_code == 0
    assert result["status"] == "would_auto_resume"
    assert is_trading_paused(pause_path)["paused"] is True
