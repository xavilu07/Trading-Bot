from __future__ import annotations

from datetime import UTC, datetime, timedelta

from trading_signals.domain.entities.trade_signal import TradeSignal
from trading_signals.domain.value_objects.enums import SignalStatus


def apply_active_signal_expiration_v1(
    signal: TradeSignal,
    *,
    enabled: bool = True,
    default_expiration_hours: float = 48.0,
    now: datetime | None = None,
) -> TradeSignal:
    if not enabled:
        return signal
    if signal.status != SignalStatus.PUBLISHED.value:
        return signal

    published_at = signal.published_at or _iso(now or datetime.now(tz=UTC))
    signal.published_at = published_at
    if not signal.lifecycle_status:
        signal.lifecycle_status = "active"
    if not signal.expires_at:
        signal.expires_at = _iso(_parse_datetime(published_at) + timedelta(hours=default_expiration_hours))
    if signal.close_reason is None:
        signal.close_reason = None
    if signal.closed_at is None:
        signal.closed_at = None
    return signal


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()
