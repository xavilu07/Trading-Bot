from __future__ import annotations


def ema(values: list[float], period: int) -> float:
    multiplier = 2 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = (value - result) * multiplier + result
    return result


def detect_trend(closes: list[float]) -> tuple[str, dict[str, float]]:
    ema20 = ema(closes[-50:], 20)
    ema50 = ema(closes[-100:], 50)
    ema200 = ema(closes[-200:], 200)
    trend = "bullish" if ema20 > ema50 else "bearish"
    return trend, {"ema20": round(ema20, 6), "ema50": round(ema50, 6), "ema200": round(ema200, 6)}


def detect_break_of_structure(candles: list[dict[str, float | str]], lookback: int = 20) -> str:
    if len(candles) <= lookback:
        return "none"
    previous = candles[-lookback - 1 : -1]
    recent = candles[-9:-1]
    last_close = float(candles[-1]["close"])
    last_open = float(candles[-1]["open"])
    last_high = float(candles[-1]["high"])
    last_low = float(candles[-1]["low"])
    previous_high = max(float(item["high"]) for item in previous)
    previous_low = min(float(item["low"]) for item in previous)
    recent_high = max(float(item["high"]) for item in recent)
    recent_low = min(float(item["low"]) for item in recent)
    recent_close_high = max(float(item["close"]) for item in recent)
    recent_close_low = min(float(item["close"]) for item in recent)
    if last_close > previous_high:
        return "bullish_bos"
    if last_close < previous_low:
        return "bearish_bos"
    if last_high > recent_high and last_close > recent_close_high and last_close > last_open:
        return "bullish_bos"
    if last_low < recent_low and last_close < recent_close_low and last_close < last_open:
        return "bearish_bos"
    return "none"


def analyze_trend(entry_snapshot, higher_snapshot) -> dict[str, object]:
    aligned = entry_snapshot.trend == higher_snapshot.trend
    ok = entry_snapshot.trend in {"bullish", "bearish"} and higher_snapshot.trend in {"bullish", "bearish"}
    return {
        "ok": ok,
        "score": 100.0 if aligned else 50.0 if ok else 0.0,
        "reason": "trend_aligned" if aligned else "trend_timeframe_mismatch" if ok else "trend_unknown",
        "details": {
            "trend_entry": entry_snapshot.trend,
            "trend_higher": higher_snapshot.trend,
            "aligned": aligned,
        },
    }
