from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from trading_signals.infrastructure.exchange import binance_provider
from trading_signals.infrastructure.market_data.binance_client import BinanceClient


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _binance_row(idx: int) -> list[object]:
    open_time = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=idx)
    close_time = open_time + timedelta(hours=1)
    return [
        int(open_time.timestamp() * 1000),
        "100.0",
        "101.0",
        "99.0",
        "100.5",
        "1000.0",
        int(close_time.timestamp() * 1000),
    ]


def test_binance_client_retries_transient_connection_reset(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_urlopen(req, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise ConnectionResetError("connection reset by peer")
        return FakeResponse([_binance_row(1), _binance_row(2), _binance_row(3)])

    monkeypatch.setattr(binance_provider.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(binance_provider.time, "sleep", lambda seconds: None)

    client = BinanceClient("https://example.test/klines", max_retries=3)
    candles = client.fetch_ohlcv("BTCUSDT", "1h", limit=3)

    assert calls["count"] == 2
    assert len(candles) == 3
    assert candles[0]["close"] == 100.5
