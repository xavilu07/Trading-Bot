from __future__ import annotations


def compute_atr(candles: list[dict[str, float | str]], period: int = 14) -> float:
    if len(candles) < period + 1:
        return 0.0
    true_ranges: list[float] = []
    for previous, current in zip(candles[-(period + 1):-1], candles[-period:]):
        high = float(current["high"])
        low = float(current["low"])
        prev_close = float(previous["close"])
        true_ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return sum(true_ranges) / len(true_ranges)

