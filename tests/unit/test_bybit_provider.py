from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from trading_signals.infrastructure.exchange import bybit_provider
from trading_signals.infrastructure.exchange.bybit_provider import BybitProvider


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def bybit_kline_row(idx: int) -> list[str]:
    open_time = datetime.now(tz=UTC) - timedelta(hours=10 - idx)
    return [
        str(int(open_time.timestamp() * 1000)),
        "100.0",
        "101.0",
        "99.0",
        "100.5",
        "1000.0",
        "100500.0",
    ]


def test_bybit_get_ohlcv_parses_v5_kline_response(monkeypatch) -> None:
    requested_urls: list[str] = []

    def fake_urlopen(req, timeout):
        requested_urls.append(req.full_url)
        return FakeResponse({
            "retCode": 0,
            "retMsg": "OK",
            "result": {"category": "spot", "symbol": "BTCUSDT", "list": [bybit_kline_row(2), bybit_kline_row(1), bybit_kline_row(3)]},
        })

    monkeypatch.setattr(bybit_provider.urllib.request, "urlopen", fake_urlopen)

    provider = BybitProvider("https://api-test.bybit.com", category="spot")
    candles = provider.get_ohlcv("btc/usdt", "1h", limit=3)

    assert "category=spot" in requested_urls[0]
    assert "symbol=BTCUSDT" in requested_urls[0]
    assert "interval=60" in requested_urls[0]
    assert len(candles) == 3
    assert candles[0]["close"] == 100.5
    assert candles[0]["open_time"] < candles[-1]["open_time"]


def test_bybit_get_current_price_uses_tickers(monkeypatch) -> None:
    def fake_urlopen(req, timeout):
        return FakeResponse({
            "retCode": 0,
            "retMsg": "OK",
            "result": {"category": "spot", "list": [{"symbol": "ETHUSDT", "lastPrice": "2345.67"}]},
        })

    monkeypatch.setattr(bybit_provider.urllib.request, "urlopen", fake_urlopen)

    provider = BybitProvider("https://api-test.bybit.com")

    assert provider.get_current_price("eth-usdt") == 2345.67


def test_bybit_get_symbols_and_validate_symbol(monkeypatch) -> None:
    def fake_urlopen(req, timeout):
        return FakeResponse({
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "category": "spot",
                "list": [
                    {"symbol": "BTCUSDT", "status": "Trading"},
                    {"symbol": "OLDUSDT", "status": "Closed"},
                ],
            },
        })

    monkeypatch.setattr(bybit_provider.urllib.request, "urlopen", fake_urlopen)

    provider = BybitProvider("https://api-test.bybit.com")

    assert provider.get_symbols() == ["BTCUSDT"]
    assert provider.validate_symbol("btc/usdt") is True
    assert provider.validate_symbol("oldusdt") is False


def test_bybit_rejects_unsupported_timeframe() -> None:
    provider = BybitProvider("https://api-test.bybit.com")

    try:
        provider.get_ohlcv("BTCUSDT", "2h")
    except ValueError as exc:
        assert "Unsupported Bybit timeframe" in str(exc)
    else:
        raise AssertionError("expected unsupported timeframe error")
