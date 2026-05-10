from __future__ import annotations

from typing import Protocol

from trading_signals.domain.entities.signal_delivery import SignalDelivery
from trading_signals.domain.entities.trade_signal import TradeSignal


class SignalRepositoryPort(Protocol):
    def save_signal(self, signal: TradeSignal) -> None:
        ...

    def save_delivery(self, delivery: SignalDelivery) -> None:
        ...

    def list_latest_signals(self, limit: int = 20) -> list[dict[str, object]]:
        ...

    def get_signal(self, signal_id: str) -> dict[str, object] | None:
        ...

    def has_published_dedupe_key(self, dedupe_key: str) -> bool:
        ...
