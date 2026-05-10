from __future__ import annotations

from datetime import UTC, datetime, timedelta


def generate_trend_dataset(rows: int = 260, direction: str = "up") -> list[dict[str, float | str]]:
    candles: list[dict[str, float | str]] = []
    base = 100.0
    current = base
    step = 0.7 if direction == "up" else -0.7
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for idx in range(rows):
        current += step
        high = current + 0.6
        low = current - 0.6
        open_price = current - 0.2
        close_price = current + 0.2 if direction == "up" else current - 0.2
        if idx == rows - 1:
            if direction == "up":
                previous_low = min(float(item["low"]) for item in candles[-20:]) if len(candles) >= 20 else low
                low = previous_low - 0.5
                open_price = previous_low - 0.1
                close_price = previous_low + 0.55
                high = close_price + 0.2
            else:
                previous_high = max(float(item["high"]) for item in candles[-20:]) if len(candles) >= 20 else high
                high = previous_high + 0.5
                open_price = previous_high + 0.1
                close_price = previous_high - 0.55
                low = close_price - 0.2
        open_time = start + timedelta(hours=idx)
        close_time = open_time + timedelta(hours=1)
        candles.append(
            {
                "open_time": open_time.isoformat(),
                "open": round(open_price, 6),
                "high": round(high, 6),
                "low": round(low, 6),
                "close": round(close_price, 6),
                "volume": 1000.0 + idx,
                "close_time": close_time.isoformat(),
            }
        )
    return candles


class FakeMarketDataClient:
    def __init__(self, datasets: dict[tuple[str, str], list[dict[str, float | str]]]) -> None:
        self.datasets = datasets

    def fetch_ohlcv(self, symbol: str, interval: str, limit: int = 300) -> list[dict[str, float | str]]:
        key = (symbol, interval)
        if key not in self.datasets:
            raise ValueError(f"Dataset missing for {key}")
        return self.datasets[key][-limit:]


def generate_backtest_dataset(rows: int = 320) -> list[dict[str, float | str]]:
    candles = generate_trend_dataset(rows=rows, direction="up")
    for idx in range(230, rows - 6, 12):
        reference_low = min(float(item["low"]) for item in candles[idx - 20:idx])
        candles[idx]["low"] = round(reference_low - 0.4, 6)
        candles[idx]["open"] = round(reference_low - 0.05, 6)
        candles[idx]["close"] = round(reference_low + 0.7, 6)
        candles[idx]["high"] = round(reference_low + 0.9, 6)
        for future_idx in range(idx + 1, min(idx + 4, rows)):
            candles[future_idx]["high"] = round(float(candles[future_idx]["high"]) + 2.5, 6)
            candles[future_idx]["close"] = round(float(candles[future_idx]["close"]) + 1.8, 6)
    return candles
