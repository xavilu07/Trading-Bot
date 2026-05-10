from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

from trading_signals.infrastructure.exchange.base import ExchangeProviderBase


TIMEFRAME_TO_BYBIT_INTERVAL = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "1h": "60",
    "4h": "240",
    "1d": "D",
}

TIMEFRAME_TO_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


class BybitProvider(ExchangeProviderBase):
    provider_name = "bybit"

    def __init__(
        self,
        base_url: str = "https://api.bybit.com",
        timeout_seconds: int = 15,
        max_retries: int = 3,
        category: str = "spot",
    ) -> None:
        self.base_url = (base_url or "https://api.bybit.com").rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.category = category

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 300) -> list[dict[str, float | str]]:
        interval = self._to_bybit_interval(timeframe)
        params = urllib.parse.urlencode(
            {
                "category": self.category,
                "symbol": self.normalize_symbol(symbol),
                "interval": interval,
                "limit": min(limit, 1000),
            }
        )
        payload = self._request_json(f"{self.base_url}/v5/market/kline?{params}")
        rows = self._result_list(payload, endpoint="kline")
        candles = [self._parse_kline_row(row, timeframe) for row in rows]
        candles.sort(key=lambda item: str(item["open_time"]))
        return self._closed_candles_only(candles, timeframe)

    def get_current_price(self, symbol: str) -> float:
        params = urllib.parse.urlencode(
            {
                "category": self.category,
                "symbol": self.normalize_symbol(symbol),
            }
        )
        payload = self._request_json(f"{self.base_url}/v5/market/tickers?{params}")
        rows = self._result_list(payload, endpoint="tickers")
        if not rows:
            raise ValueError(f"Bybit ticker not found for {symbol}")
        return float(rows[0]["lastPrice"])

    def get_symbols(self) -> list[str]:
        params = urllib.parse.urlencode({"category": self.category, "limit": 1000})
        payload = self._request_json(f"{self.base_url}/v5/market/instruments-info?{params}")
        rows = self._result_list(payload, endpoint="instruments-info")
        return sorted(str(row["symbol"]) for row in rows if row.get("symbol") and row.get("status", "Trading") == "Trading")

    def normalize_symbol(self, symbol: str) -> str:
        return symbol.strip().upper().replace("/", "").replace("-", "")

    def validate_symbol(self, symbol: str) -> bool:
        normalized = self.normalize_symbol(symbol)
        try:
            symbols = self.get_symbols()
        except Exception:
            return bool(normalized)
        return normalized in set(symbols)

    def _request_json(self, url: str) -> dict[str, object]:
        last_error: Exception | None = None
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        for attempt in range(1, self.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError(f"Unexpected Bybit response: {payload}")
                if str(payload.get("retCode")) != "0":
                    raise ValueError(f"Bybit error response: {payload}")
                return payload
            except (ConnectionResetError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(0.35 * attempt)
        raise last_error or RuntimeError("bybit_request_failed")

    @staticmethod
    def _result_list(payload: dict[str, object], *, endpoint: str) -> list[dict[str, object] | list[object]]:
        result = payload.get("result")
        if not isinstance(result, dict):
            raise ValueError(f"Unexpected Bybit {endpoint} result: {payload}")
        rows = result.get("list", [])
        if not isinstance(rows, list):
            raise ValueError(f"Unexpected Bybit {endpoint} list: {payload}")
        return rows

    @staticmethod
    def _to_bybit_interval(timeframe: str) -> str:
        if timeframe not in TIMEFRAME_TO_BYBIT_INTERVAL:
            raise ValueError(f"Unsupported Bybit timeframe: {timeframe}")
        return TIMEFRAME_TO_BYBIT_INTERVAL[timeframe]

    @staticmethod
    def _to_iso(ms: int | str) -> str:
        return datetime.fromtimestamp(int(ms) / 1000, tz=UTC).isoformat()

    @classmethod
    def _parse_kline_row(cls, row: dict[str, object] | list[object], timeframe: str) -> dict[str, float | str]:
        if isinstance(row, dict):
            open_ms = int(row["start"])
            open_price = row["open"]
            high = row["high"]
            low = row["low"]
            close = row["close"]
            volume = row["volume"]
        else:
            open_ms = int(row[0])
            open_price = row[1]
            high = row[2]
            low = row[3]
            close = row[4]
            volume = row[5]
        close_ms = open_ms + TIMEFRAME_TO_SECONDS.get(timeframe, 3600) * 1000
        return {
            "open_time": cls._to_iso(open_ms),
            "open": float(open_price),
            "high": float(high),
            "low": float(low),
            "close": float(close),
            "volume": float(volume),
            "close_time": cls._to_iso(close_ms),
        }

    @staticmethod
    def _closed_candles_only(candles: list[dict[str, float | str]], timeframe: str) -> list[dict[str, float | str]]:
        if not candles:
            return candles
        now = datetime.now(tz=UTC)
        interval = timedelta(seconds=TIMEFRAME_TO_SECONDS.get(timeframe, 3600))
        closed = []
        for candle in candles:
            open_ts = datetime.fromisoformat(str(candle["open_time"]))
            if open_ts + interval <= now:
                closed.append(candle)
        if len(closed) >= 3:
            return closed
        return candles[:-1] if len(candles) > 1 else candles
