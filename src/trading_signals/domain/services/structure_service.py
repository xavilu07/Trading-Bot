from __future__ import annotations


def detect_structure(highs: list[float], lows: list[float]) -> str:
    recent_highs = highs[-5:-1] if len(highs) >= 5 else highs[-4:]
    recent_lows = lows[-5:-1] if len(lows) >= 5 else lows[-4:]
    if len(recent_highs) < 4 or len(recent_lows) < 4:
        return "range"
    higher_highs = recent_highs[-1] > recent_highs[-3] and recent_highs[-2] > recent_highs[-4]
    higher_lows = recent_lows[-1] > recent_lows[-3] and recent_lows[-2] > recent_lows[-4]
    lower_highs = recent_highs[-1] < recent_highs[-3] and recent_highs[-2] < recent_highs[-4]
    lower_lows = recent_lows[-1] < recent_lows[-3] and recent_lows[-2] < recent_lows[-4]
    if higher_highs and higher_lows:
        return "bullish"
    if lower_highs and lower_lows:
        return "bearish"
    return "range"
