from __future__ import annotations

import pytest

from trading_signals.app.settings import Settings
from trading_signals.infrastructure.exchange.binance_provider import BinanceProvider
from trading_signals.infrastructure.exchange.bybit_provider import BybitProvider
from trading_signals.infrastructure.exchange.provider_factory import build_market_data_provider


def test_market_data_provider_defaults_to_binance(monkeypatch) -> None:
    monkeypatch.delenv("MARKET_DATA_PROVIDER", raising=False)

    provider = build_market_data_provider(Settings())

    assert isinstance(provider, BinanceProvider)
    assert provider.provider_name == "binance"
    assert provider.normalize_symbol(" btcusdt ") == "BTCUSDT"


def test_market_data_provider_can_build_bybit_stub() -> None:
    provider = build_market_data_provider(Settings(market_data_provider="bybit", bybit_base_url="https://example.test"))

    assert isinstance(provider, BybitProvider)
    assert provider.provider_name == "bybit"
    assert provider.base_url == "https://example.test"


def test_market_data_provider_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported MARKET_DATA_PROVIDER"):
        build_market_data_provider(Settings(market_data_provider="unknown"))
