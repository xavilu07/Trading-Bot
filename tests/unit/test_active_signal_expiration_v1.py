from __future__ import annotations

from datetime import UTC, datetime

from trading_signals.application.use_cases.active_signal_expiration_v1 import apply_active_signal_expiration_v1
from trading_signals.domain.entities.trade_signal import TradeSignal


def _signal(*, status: str = "published", published_at: str | None = "2026-01-01T10:00:00+00:00") -> TradeSignal:
    return TradeSignal(
        id="sig",
        scan_run_id="run",
        evaluation_id="eval",
        risk_plan_id="risk",
        strategy_id="liquidity_sweep_mtf",
        strategy_version="v1",
        symbol="BTCUSDT",
        decision="long",
        status=status,
        dedupe_key="dedupe",
        entry_timeframe="1h",
        higher_timeframe="4h",
        entry_snapshot_id="entry",
        higher_snapshot_id="higher",
        created_at="2026-01-01T09:00:00+00:00",
        published_at=published_at,
    )


def test_published_signal_receives_expires_at_and_lifecycle_fields() -> None:
    signal = _signal()

    apply_active_signal_expiration_v1(signal, default_expiration_hours=48)

    assert signal.lifecycle_status == "active"
    assert signal.expires_at == "2026-01-03T10:00:00+00:00"
    assert signal.close_reason is None
    assert signal.closed_at is None


def test_rejected_signal_does_not_receive_expiration() -> None:
    signal = _signal(status="rejected")

    apply_active_signal_expiration_v1(signal)

    assert signal.expires_at is None
    assert signal.lifecycle_status is None


def test_valid_unpublished_signal_does_not_receive_expiration() -> None:
    signal = _signal(status="valid", published_at=None)

    apply_active_signal_expiration_v1(signal)

    assert signal.expires_at is None
    assert signal.published_at is None


def test_existing_expires_at_is_not_overwritten() -> None:
    signal = _signal()
    signal.expires_at = "2026-01-10T00:00:00+00:00"

    apply_active_signal_expiration_v1(signal, default_expiration_hours=48)

    assert signal.expires_at == "2026-01-10T00:00:00+00:00"


def test_expiration_uses_published_at_as_base() -> None:
    signal = _signal(published_at="2026-01-02T12:30:00+00:00")

    apply_active_signal_expiration_v1(signal, default_expiration_hours=24)

    assert signal.expires_at == "2026-01-03T12:30:00+00:00"


def test_missing_published_at_is_filled_for_published_signal() -> None:
    signal = _signal(published_at=None)

    apply_active_signal_expiration_v1(
        signal,
        default_expiration_hours=1,
        now=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )

    assert signal.published_at == "2026-01-01T12:00:00+00:00"
    assert signal.expires_at == "2026-01-01T13:00:00+00:00"


def test_disabled_flag_does_not_mutate_signal() -> None:
    signal = _signal()

    apply_active_signal_expiration_v1(signal, enabled=False)

    assert signal.expires_at is None
    assert signal.lifecycle_status is None
