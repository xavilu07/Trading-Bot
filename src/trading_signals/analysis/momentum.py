from __future__ import annotations


def compute_rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) <= period:
        return 50.0
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(closes[-period - 1 : -1], closes[-period:]):
        change = current - previous
        gains.append(max(change, 0.0))
        losses.append(abs(min(change, 0.0)))
    average_gain = sum(gains) / period
    average_loss = sum(losses) / period
    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


def volume_profile(volumes: list[float], window: int = 20) -> dict[str, float]:
    volume_window = volumes[-window:] if len(volumes) >= window else volumes
    average_volume = sum(volume_window) / len(volume_window) if volume_window else 0.0
    current_volume = volumes[-1] if volumes else 0.0
    volume_ratio = current_volume / average_volume if average_volume else 0.0
    return {
        "current": current_volume,
        "average": average_volume,
        "ratio": volume_ratio,
    }


def analyze_momentum(entry_snapshot, *, min_body_ratio: float, direction: str = "no_trade") -> dict[str, object]:
    rsi = float(entry_snapshot.metadata.get("rsi", 50.0))
    volume_ratio = float(entry_snapshot.metadata.get("volume_ratio_vs_average_20", 0.0))
    candle_body = abs(entry_snapshot.close - entry_snapshot.open)
    candle_range = entry_snapshot.high - entry_snapshot.low
    body_ok = entry_snapshot.body_ratio >= min_body_ratio
    score = 0.0
    if body_ok:
        score += 40.0
    if volume_ratio >= 1.2:
        score += 35.0
    elif volume_ratio >= 0.8:
        score += 20.0
    if 35 <= rsi <= 65:
        score += 25.0
    elif 30 <= rsi <= 70:
        score += 15.0
    return {
        "ok": body_ok,
        "score": round(min(score, 100.0), 2),
        "reason": "momentum_confirmed" if body_ok else "body_ratio_below_threshold",
        "details": {
            "rsi": rsi,
            "body_ratio": entry_snapshot.body_ratio,
            "MIN_BODY_RATIO": min_body_ratio,
            "candle_body": round(candle_body, 8),
            "candle_range": round(candle_range, 8),
            "volume_current": entry_snapshot.volume,
            "volume_average": entry_snapshot.metadata.get("volume_average_20"),
            "volume_ratio": volume_ratio,
            "direction": direction,
        },
    }
