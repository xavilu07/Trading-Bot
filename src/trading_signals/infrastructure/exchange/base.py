from __future__ import annotations


class ExchangeProviderBase:
    provider_name = "unknown"

    def fetch_ohlcv(self, symbol: str, interval: str, limit: int = 300) -> list[dict[str, float | str]]:
        return self.get_ohlcv(symbol, interval, limit=limit)

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 300) -> list[dict[str, float | str]]:
        raise NotImplementedError

    def get_current_price(self, symbol: str) -> float:
        candles = self.get_ohlcv(symbol, "1m", limit=2)
        if not candles:
            raise ValueError(f"No candles available for {symbol}")
        return float(candles[-1]["close"])

    def get_symbols(self) -> list[str]:
        return []

    def normalize_symbol(self, symbol: str) -> str:
        return symbol.strip().upper()

    def validate_symbol(self, symbol: str) -> bool:
        normalized = self.normalize_symbol(symbol)
        symbols = self.get_symbols()
        return bool(normalized) if not symbols else normalized in set(symbols)
