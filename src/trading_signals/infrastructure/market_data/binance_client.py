from __future__ import annotations

from trading_signals.infrastructure.exchange.binance_provider import BinanceProvider, INTERVAL_TO_SECONDS


class BinanceClient(BinanceProvider):
    """Compatibility wrapper for legacy imports.

    New code should depend on infrastructure.exchange providers through the
    provider factory. This class preserves the previous fetch_ohlcv contract.
    """

