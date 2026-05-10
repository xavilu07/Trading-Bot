from __future__ import annotations


def get_liquidity_levels(highs: list[float], lows: list[float], lookback: int = 20) -> tuple[float, float]:
    recent_highs = highs[-lookback:]
    recent_lows = lows[-lookback:]
    return max(recent_highs), min(recent_lows)


def detect_liquidity_sweep(candles: list[dict[str, float | str]], lookback: int = 20) -> str:
    if len(candles) < lookback + 1:
        return "none"
    previous = candles[-(lookback + 1):-1]
    last = candles[-1]
    previous_high = max(float(item["high"]) for item in previous)
    previous_low = min(float(item["low"]) for item in previous)
    last_high = float(last["high"])
    last_low = float(last["low"])
    last_close = float(last["close"])
    if last_low < previous_low and last_close > previous_low:
        return "bullish_sweep"
    if last_high > previous_high and last_close < previous_high:
        return "bearish_sweep"
    return "none"


def liquidity_context(
    *,
    close_price: float,
    trend: str,
    liquidity_high: float,
    liquidity_low: float,
    atr: float,
) -> dict[str, float | str]:
    target_liquidity = liquidity_low if trend == "bullish" else liquidity_high
    target_liquidity_side = "below" if target_liquidity < close_price else "above"
    nearest_liquidity = liquidity_low if abs(close_price - liquidity_low) <= abs(close_price - liquidity_high) else liquidity_high
    nearest_liquidity_side = "below" if nearest_liquidity < close_price else "above"
    distance_to_liquidity_atr = abs(close_price - target_liquidity) / atr if atr > 0 else 999.0
    nearest_distance_to_liquidity_atr = abs(close_price - nearest_liquidity) / atr if atr > 0 else 999.0
    return {
        "directional_liquidity_level": target_liquidity,
        "directional_liquidity_side": target_liquidity_side,
        "nearest_liquidity_level": nearest_liquidity,
        "nearest_liquidity_side": nearest_liquidity_side,
        "distance_to_liquidity_atr": distance_to_liquidity_atr,
        "nearest_distance_to_liquidity_atr": nearest_distance_to_liquidity_atr,
    }


def analyze_liquidity(entry_snapshot, *, max_distance_to_liquidity_atr: float) -> dict[str, object]:
    nearest_distance = float(entry_snapshot.metadata.get("nearest_distance_to_liquidity_atr", entry_snapshot.distance_to_liquidity_atr))
    directional_ok = entry_snapshot.distance_to_liquidity_atr <= max_distance_to_liquidity_atr
    nearest_ok = nearest_distance <= max_distance_to_liquidity_atr
    has_sweep = entry_snapshot.liquidity_sweep in {"bullish_sweep", "bearish_sweep"}
    ok = directional_ok or nearest_ok or has_sweep
    if has_sweep and directional_ok:
        score = 100.0
    elif has_sweep or directional_ok:
        score = 80.0
    elif nearest_ok:
        score = 60.0
    else:
        score = 20.0
    return {
        "ok": ok,
        "score": score,
        "reason": "liquidity_sweep_confirmed" if has_sweep else "liquidity_distance_ok" if directional_ok else "nearest_liquidity_ok" if nearest_ok else "liquidity_too_far",
        "details": {
            "liquidity_sweep": entry_snapshot.liquidity_sweep,
            "directional_liquidity_level": entry_snapshot.metadata.get("directional_liquidity_level"),
            "directional_liquidity_side": entry_snapshot.metadata.get("directional_liquidity_side"),
            "nearest_liquidity_level": entry_snapshot.metadata.get("nearest_liquidity_level"),
            "nearest_liquidity_side": entry_snapshot.metadata.get("nearest_liquidity_side"),
            "distance_to_liquidity_atr": entry_snapshot.distance_to_liquidity_atr,
            "nearest_distance_to_liquidity_atr": nearest_distance,
            "max_distance_to_liquidity_atr": max_distance_to_liquidity_atr,
        },
    }
