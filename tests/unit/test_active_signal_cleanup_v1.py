from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from trading_signals.application.use_cases.active_signal_cleanup_v1 import (
    CLEANUP_VERSION,
    CLOSE_REASON,
    LIFECYCLE_STATUS,
    ActiveSignalCleanupConfig,
    run_active_signal_cleanup_v1,
    write_active_signal_cleanup_v1_design_report,
)


def _now() -> datetime:
    return datetime(2026, 1, 4, 12, 0, tzinfo=UTC)


def _write_signal(path: Path, **overrides: object) -> Path:
    payload = {
        "id": path.stem,
        "symbol": "BTCUSDT",
        "decision": "long",
        "status": "published",
        "created_at": "2026-01-01T00:00:00+00:00",
        "published_at": "2026-01-01T00:00:00+00:00",
    }
    payload.update(overrides)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_flag_false_does_not_modify_candidate(tmp_path: Path) -> None:
    signal_path = _write_signal(tmp_path / "data" / "trade_signals" / "2026-01-01" / "sig.json")

    result = run_active_signal_cleanup_v1(
        data_path=tmp_path / "data",
        config=ActiveSignalCleanupConfig(enabled=False, dry_run=False, zombie_hours=48),
        now=_now(),
    )

    assert len(result.candidates) == 1
    assert len(result.closed) == 0
    assert _read(signal_path)["status"] == "published"
    assert result.skipped[0]["reason"] == "cleanup_disabled"


def test_dry_run_does_not_modify_candidate(tmp_path: Path) -> None:
    signal_path = _write_signal(tmp_path / "data" / "trade_signals" / "2026-01-01" / "sig.json")

    result = run_active_signal_cleanup_v1(
        data_path=tmp_path / "data",
        config=ActiveSignalCleanupConfig(enabled=True, dry_run=True, zombie_hours=48),
        now=_now(),
    )

    assert len(result.candidates) == 1
    assert len(result.closed) == 0
    assert _read(signal_path)["status"] == "published"
    assert result.skipped[0]["reason"] == "dry_run"


def test_apply_closes_zombie_and_creates_backup(tmp_path: Path) -> None:
    signal_path = _write_signal(tmp_path / "data" / "trade_signals" / "2026-01-01" / "sig.json")

    result = run_active_signal_cleanup_v1(
        data_path=tmp_path / "data",
        config=ActiveSignalCleanupConfig(enabled=True, dry_run=False, zombie_hours=48),
        now=_now(),
    )

    updated = _read(signal_path)
    assert len(result.closed) == 1
    assert updated["status"] == "closed"
    assert updated["lifecycle_status"] == LIFECYCLE_STATUS
    assert updated["close_reason"] == CLOSE_REASON
    assert updated["cleanup_version"] == CLEANUP_VERSION
    assert result.backup_dir is not None
    backup_files = list(result.backup_dir.glob("*.json"))
    assert len(backup_files) == 1
    assert json.loads(backup_files[0].read_text(encoding="utf-8"))["status"] == "published"


def test_does_not_close_recent_signal(tmp_path: Path) -> None:
    signal_path = _write_signal(
        tmp_path / "data" / "trade_signals" / "2026-01-04" / "sig.json",
        published_at="2026-01-04T00:00:00+00:00",
    )

    result = run_active_signal_cleanup_v1(
        data_path=tmp_path / "data",
        config=ActiveSignalCleanupConfig(enabled=True, dry_run=False, zombie_hours=48),
        now=_now(),
    )

    assert len(result.candidates) == 0
    assert _read(signal_path)["status"] == "published"


def test_does_not_close_signal_with_future_expires_at(tmp_path: Path) -> None:
    signal_path = _write_signal(
        tmp_path / "data" / "trade_signals" / "2026-01-01" / "sig.json",
        expires_at="2026-01-05T00:00:00+00:00",
    )

    result = run_active_signal_cleanup_v1(
        data_path=tmp_path / "data",
        config=ActiveSignalCleanupConfig(enabled=True, dry_run=False, zombie_hours=48),
        now=_now(),
    )

    assert len(result.candidates) == 0
    assert _read(signal_path)["status"] == "published"


def test_does_not_close_already_closed_signal(tmp_path: Path) -> None:
    signal_path = _write_signal(
        tmp_path / "data" / "trade_signals" / "2026-01-01" / "sig.json",
        status="closed",
        close_reason="manual",
    )

    result = run_active_signal_cleanup_v1(
        data_path=tmp_path / "data",
        config=ActiveSignalCleanupConfig(enabled=True, dry_run=False, zombie_hours=48),
        now=_now(),
    )

    assert len(result.candidates) == 0
    assert _read(signal_path)["close_reason"] == "manual"


def test_idempotency_second_run_does_not_touch_closed_signal(tmp_path: Path) -> None:
    signal_path = _write_signal(tmp_path / "data" / "trade_signals" / "2026-01-01" / "sig.json")
    first = run_active_signal_cleanup_v1(
        data_path=tmp_path / "data",
        config=ActiveSignalCleanupConfig(enabled=True, dry_run=False, zombie_hours=48),
        now=_now(),
    )

    second = run_active_signal_cleanup_v1(
        data_path=tmp_path / "data",
        config=ActiveSignalCleanupConfig(enabled=True, dry_run=False, zombie_hours=48),
        now=_now(),
    )

    assert len(first.closed) == 1
    assert len(second.candidates) == 0
    assert _read(signal_path)["status"] == "closed"


def test_writes_design_report(tmp_path: Path) -> None:
    path = write_active_signal_cleanup_v1_design_report(tmp_path)

    assert path.exists()
    assert "ACTIVE_SIGNAL_CLEANUP_V1" in path.read_text(encoding="utf-8")
