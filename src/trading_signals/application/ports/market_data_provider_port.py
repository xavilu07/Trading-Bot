from __future__ import annotations

from typing import Protocol


class MarketDataProviderPort(Protocol):
    provider_name: str

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 300) -> list[dict[str, float | str]]:
        ...

    def fetch_ohlcv(self, symbol: str, interval: str, limit: int = 300) -> list[dict[str, float | str]]:
        ...

    def get_current_price(self, symbol: str) -> float:
        ...

    def get_symbols(self) -> list[str]:
        ...

    def normalize_symbol(self, symbol: str) -> str:
        ...

    def validate_symbol(self, symbol: str) -> bool:
        ...
