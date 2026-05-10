from __future__ import annotations


def body_ratio(candle: dict[str, float | str]) -> float:
    high = float(candle["high"])
    low = float(candle["low"])
    open_price = float(candle["open"])
    close_price = float(candle["close"])
    candle_range = high - low
    if candle_range <= 0:
        return 0.0
    return abs(close_price - open_price) / candle_range

