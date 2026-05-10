from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SignalDelivery:
    id: str
    signal_id: str
    channel: str
    status: str
    recipient: str
    provider_message_id: str | None
    payload: dict[str, object]
    error_message: str | None
    attempted_at: str
    schema_version: str = "1.0"

