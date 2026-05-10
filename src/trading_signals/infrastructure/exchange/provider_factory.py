from __future__ import annotations

from trading_signals.infrastructure.exchange.binance_provider import BinanceProvider
from trading_signals.infrastructure.exchange.bybit_provider import BybitProvider


def build_market_data_provider(settings):
    provider = settings.market_data_provider.strip().lower()
    if provider == "binance":
        return BinanceProvider(settings.binance_base_url)
    if provider == "bybit":
        return BybitProvider(settings.bybit_base_url, category=settings.bybit_category)
    raise ValueError(f"Unsupported MARKET_DATA_PROVIDER: {settings.market_data_provider}")
