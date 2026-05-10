from __future__ import annotations

from datetime import datetime


def detect_market_regime(snapshot, *, atr_min_threshold: float) -> str:
    atr_ratio = snapshot.atr / snapshot.close if snapshot.close else 0.0
    if atr_ratio < atr_min_threshold:
        return "LOW_VOLATILITY"
    if atr_ratio >= atr_min_threshold * 4:
        return "HIGH_VOLATILITY"
    if snapshot.market_structure == "range":
        return "RANGING"
    return "TRENDING"


def detect_session(timestamp: str) -> str:
    hour = datetime.fromisoformat(timestamp).hour
    if 13 <= hour < 17:
        return "OVERLAP"
    if 7 <= hour < 13:
        return "LONDON"
    if 17 <= hour < 22:
        return "NEW_YORK"
    return "ASIA"


def detect_entry_context(snapshot) -> str:
    bos = str(snapshot.metadata.get("break_of_structure", "none"))
    volume_ratio = float(snapshot.metadata.get("volume_ratio_vs_average_20", 0.0))
    rsi = float(snapshot.metadata.get("rsi", 50.0))
    if snapshot.market_structure == "range" and volume_ratio < 1.0:
        return "CHOPPY_RANGE"
    if bos in {"bullish_bos", "bearish_bos"}:
        return "BREAKOUT"
    if snapshot.body_ratio >= 0.65 and volume_ratio >= 1.2:
        return "IMPULSE"
    if rsi >= 70 or rsi <= 30:
        return "EXHAUSTION"
    if snapshot.distance_to_liquidity_atr <= 2.5:
        return "PULLBACK"
    return "CHOPPY_RANGE" if snapshot.market_structure == "range" else "PULLBACK"


def detect_trade_location(snapshot) -> str:
    price_range = snapshot.liquidity_high - snapshot.liquidity_low
    if price_range <= 0:
        return "mid_range"
    nearest_distance = float(snapshot.metadata.get("nearest_distance_to_liquidity_atr", snapshot.distance_to_liquidity_atr))
    if nearest_distance <= 1.0:
        nearest_side = str(snapshot.metadata.get("nearest_liquidity_side", ""))
        if nearest_side == "below":
            return "near_support"
        if nearest_side == "above":
            return "near_resistance"
    position = (snapshot.close - snapshot.liquidity_low) / price_range
    if position >= 0.66:
        return "premium_zone"
    if position <= 0.34:
        return "discount_zone"
    return "mid_range"


def analyze_market_regime(entry_snapshot, *, atr_min_threshold: float) -> dict[str, object]:
    regime = detect_market_regime(entry_snapshot, atr_min_threshold=atr_min_threshold)
    ok = regime != "LOW_VOLATILITY"
    score = 80.0
    if regime == "TRENDING":
        score = 100.0
    elif regime == "HIGH_VOLATILITY":
        score = 70.0
    elif regime == "RANGING":
        score = 50.0
    elif regime == "LOW_VOLATILITY":
        score = 20.0
    return {
        "ok": ok,
        "score": score,
        "reason": f"market_regime_{regime.lower()}",
        "details": {
            "market_regime": regime,
            "session": detect_session(entry_snapshot.timestamp),
            "entry_context": detect_entry_context(entry_snapshot),
            "trade_location": detect_trade_location(entry_snapshot),
            "atr_ratio": entry_snapshot.atr / entry_snapshot.close if entry_snapshot.close else 0.0,
            "atr_min_threshold": atr_min_threshold,
        },
    }
