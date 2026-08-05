from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from trading_signals.risk.kill_switch import evaluate_kill_switch


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_daily_loss_activates_kill_switch(tmp_path: Path) -> None:
    write_csv(
        tmp_path / "paper_trading" / "trades.csv",
        [{"status": "sl_hit", "result_r": "-2.1", "closed_at": "2026-05-24T09:00:00+00:00"}],
    )

    result = evaluate_kill_switch(
        tmp_path,
        enabled=True,
        max_daily_loss_r=2.0,
        max_consecutive_losses=10,
        now=datetime(2026, 5, 24, 12, tzinfo=timezone.utc),
    )

    assert result["kill_switch_active"] is True
    assert result["kill_switch_reason"] == "daily_loss_limit"
    assert result["daily_realized_r"] == -2.1


def test_consecutive_losses_activate_kill_switch(tmp_path: Path) -> None:
    write_csv(
        tmp_path / "paper_trading" / "trades.csv",
        [
            {"status": "tp2_hit", "result_r": "1", "closed_at": "2026-05-23T08:00:00+00:00"},
            {"status": "sl_hit", "result_r": "-0.5", "closed_at": "2026-05-24T09:00:00+00:00"},
            {"status": "sl_hit", "result_r": "-0.5", "closed_at": "2026-05-24T10:00:00+00:00"},
        ],
    )

    result = evaluate_kill_switch(
        tmp_path,
        enabled=True,
        max_daily_loss_r=10.0,
        max_consecutive_losses=2,
        max_weekly_drawdown_r=10.0,
        cooldown_hours=0,
        now=datetime(2026, 5, 24, 12, tzinfo=timezone.utc),
    )

    assert result["kill_switch_active"] is True
    assert result["kill_switch_reason"] == "consecutive_losses_limit"
    assert result["consecutive_losses"] == 2


def test_weekly_drawdown_activates_kill_switch(tmp_path: Path) -> None:
    write_csv(
        tmp_path / "live_trading" / "trades.csv",
        [
            {"status": "sl_hit", "result_r": "-1.5", "closed_at": "2026-05-20T09:00:00+00:00"},
            {"status": "sl_hit", "result_r": "-1.5", "closed_at": "2026-05-21T09:00:00+00:00"},
            {"status": "sl_hit", "result_r": "-1.2", "closed_at": "2026-05-22T09:00:00+00:00"},
        ],
    )

    result = evaluate_kill_switch(
        tmp_path,
        enabled=True,
        max_daily_loss_r=10.0,
        max_consecutive_losses=10,
        max_weekly_drawdown_r=4.0,
        cooldown_hours=0,
        now=datetime(2026, 5, 24, 12, tzinfo=timezone.utc),
    )

    assert result["kill_switch_active"] is True
    assert result["kill_switch_reason"] == "weekly_drawdown_limit"
    assert result["weekly_realized_r"] == -4.2


def test_cooldown_active_blocks_after_recent_loss(tmp_path: Path) -> None:
    write_csv(
        tmp_path / "paper_trading" / "trades.csv",
        [{"status": "sl_hit", "result_r": "-0.2", "closed_at": "2026-05-24T09:00:00+00:00"}],
    )

    result = evaluate_kill_switch(
        tmp_path,
        enabled=True,
        max_daily_loss_r=10.0,
        max_consecutive_losses=10,
        max_weekly_drawdown_r=10.0,
        cooldown_hours=12,
        now=datetime(2026, 5, 24, 12, tzinfo=timezone.utc),
    )

    assert result["kill_switch_active"] is True
    assert result["kill_switch_reason"] == "cooldown_active"
    assert result["cooldown_until"] == "2026-05-24T21:00:00+00:00"


def test_stale_consecutive_losses_stop_blocking_when_weekly_is_fine(tmp_path: Path) -> None:
    # Same 2-loss streak as test_consecutive_losses_activate_kill_switch, but "now" is
    # 13h after the last loss (past the 12h default reset window) instead of 2h after —
    # and nothing else is bad, so the kill switch should have cleared on its own.
    write_csv(
        tmp_path / "paper_trading" / "trades.csv",
        [
            {"status": "tp2_hit", "result_r": "1", "closed_at": "2026-05-23T08:00:00+00:00"},
            {"status": "sl_hit", "result_r": "-0.5", "closed_at": "2026-05-24T09:00:00+00:00"},
            {"status": "sl_hit", "result_r": "-0.5", "closed_at": "2026-05-24T10:00:00+00:00"},
        ],
    )

    result = evaluate_kill_switch(
        tmp_path,
        enabled=True,
        max_daily_loss_r=10.0,
        max_consecutive_losses=2,
        max_weekly_drawdown_r=10.0,
        cooldown_hours=0,
        now=datetime(2026, 5, 24, 23, tzinfo=timezone.utc),
    )

    assert result["kill_switch_active"] is False
    assert result["kill_switch_reason"] == ""
    assert result["consecutive_losses"] == 2
    assert result["consecutive_losses_stale"] is True


def test_stale_consecutive_losses_fall_through_to_weekly_drawdown(tmp_path: Path) -> None:
    # Same stale-streak timing as above, but the week is still deep in the red — the
    # consecutive-loss lock should lift, but the weekly cap must keep blocking until the
    # old trades actually age out of the 7-day window.
    write_csv(
        tmp_path / "paper_trading" / "trades.csv",
        [
            {"status": "sl_hit", "result_r": "-3.0", "closed_at": "2026-05-20T09:00:00+00:00"},
            {"status": "sl_hit", "result_r": "-0.5", "closed_at": "2026-05-24T09:00:00+00:00"},
            {"status": "sl_hit", "result_r": "-0.5", "closed_at": "2026-05-24T10:00:00+00:00"},
        ],
    )

    result = evaluate_kill_switch(
        tmp_path,
        enabled=True,
        max_daily_loss_r=10.0,
        max_consecutive_losses=2,
        max_weekly_drawdown_r=2.0,
        cooldown_hours=0,
        now=datetime(2026, 5, 24, 23, tzinfo=timezone.utc),
    )

    assert result["kill_switch_active"] is True
    assert result["kill_switch_reason"] == "weekly_drawdown_limit"
    assert result["consecutive_losses_stale"] is True


def test_consecutive_loss_reset_hours_zero_disables_the_stale_check(tmp_path: Path) -> None:
    write_csv(
        tmp_path / "paper_trading" / "trades.csv",
        [
            {"status": "sl_hit", "result_r": "-0.5", "closed_at": "2026-05-24T09:00:00+00:00"},
            {"status": "sl_hit", "result_r": "-0.5", "closed_at": "2026-05-24T10:00:00+00:00"},
        ],
    )

    result = evaluate_kill_switch(
        tmp_path,
        enabled=True,
        max_daily_loss_r=10.0,
        max_consecutive_losses=2,
        max_weekly_drawdown_r=10.0,
        cooldown_hours=0,
        consecutive_loss_reset_hours=0,
        now=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )

    assert result["kill_switch_active"] is True
    assert result["kill_switch_reason"] == "consecutive_losses_limit"
    assert result["consecutive_losses_stale"] is False


def test_flag_false_calculates_metrics_but_does_not_activate(tmp_path: Path) -> None:
    write_csv(
        tmp_path / "paper_trading" / "trades.csv",
        [{"status": "sl_hit", "result_r": "-5", "closed_at": "2026-05-24T09:00:00+00:00"}],
    )

    result = evaluate_kill_switch(
        tmp_path,
        enabled=False,
        max_daily_loss_r=2.0,
        now=datetime(2026, 5, 24, 12, tzinfo=timezone.utc),
    )

    assert result["daily_realized_r"] == -5.0
    assert result["kill_switch_active"] is False
    assert result["kill_switch_reason"] == ""
