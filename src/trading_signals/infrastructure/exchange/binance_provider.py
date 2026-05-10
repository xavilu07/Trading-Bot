from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime

from trading_signals.infrastructure.exchange.base import ExchangeProviderBase


INTERVAL_TO_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


class BinanceProvider(ExchangeProviderBase):
    provider_name = "binance"

    def __init__(self, base_url: str, timeout_seconds: int = 15, max_retries: int = 3) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 300) -> list[dict[str, float | str]]:
        params = urllib.parse.urlencode({"symbol": self.normalize_symbol(symbol), "interval": timeframe, "limit": limit})
        req = urllib.request.Request(f"{self._klines_url()}?{params}", headers={"User-Agent": "Mozilla/5.0"})
        payload = self._request_json(req)
        candles = []
        for row in payload:
            candles.append(
                {
                    "open_time": self._to_iso(row[0]),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                    "close_time": self._to_iso(row[6]),
                }
            )
        return self._closed_candles_only(candles, timeframe)

    def _klines_url(self) -> str:
        if self.base_url.endswith("/klines"):
            return self.base_url
        return f"{self.base_url}/klines"

    def _request_json(self, req: urllib.request.Request) -> list[list[object]]:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, list):
                    raise ValueError(f"Unexpected Binance response: {payload}")
                return payload
            except (ConnectionResetError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(0.35 * attempt)
        raise last_error or RuntimeError("binance_request_failed")

    @staticmethod
    def _to_iso(ms: int) -> str:
        return datetime.fromtimestamp(ms / 1000, tz=UTC).isoformat()

    @staticmethod
    def _closed_candles_only(candles: list[dict[str, float | str]], interval: str) -> list[dict[str, float | str]]:
        if not candles:
            return candles
        now = datetime.now(tz=UTC).timestamp()
        closed: list[dict[str, float | str]] = []
        for candle in candles:
            close_ts = datetime.fromisoformat(str(candle["close_time"])).timestamp()
            if close_ts + 1 <= now and now - close_ts >= 0:
                closed.append(candle)
        if len(closed) >= 3:
            return closed
        return candles[:-1] if len(candles) > 1 else candles
