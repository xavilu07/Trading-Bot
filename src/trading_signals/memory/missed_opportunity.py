from __future__ import annotations

from datetime import datetime


def analyze_missed_opportunity(
    signal: dict[str, object],
    candles: list[dict[str, object]],
    *,
    default_rr: float = 2.0,
) -> dict[str, object]:
    direction = str(signal.get("direction") or "").lower()
    entry = _float(signal.get("entry_price") or signal.get("entry") or signal.get("close"))
    if direction not in {"long", "short"} or entry is None or entry <= 0:
        return _empty("NEUTRAL")
    stop_loss, take_profit = _levels(signal, entry=entry, direction=direction, default_rr=default_rr)
    risk = abs(entry - stop_loss)
    if risk <= 0:
        return _empty("NEUTRAL")
    start = _parse_time(signal.get("timestamp") or signal.get("created_at") or signal.get("opened_at"))
    future = _future_candles(candles, start)
    max_r = 0.0
    min_r = 0.0
    resolved_type = "NEUTRAL"
    time_to_resolution = len(future)
    for index, candle in enumerate(future, start=1):
        high = _float(candle.get("high"))
        low = _float(candle.get("low"))
        if high is None or low is None:
            continue
        if direction == "long":
            favorable_r = (high - entry) / risk
            adverse_r = (low - entry) / risk
            tp_hit = high >= take_profit
            sl_hit = low <= stop_loss
        else:
            favorable_r = (entry - low) / risk
            adverse_r = (entry - high) / risk
            tp_hit = low <= take_profit
            sl_hit = high >= stop_loss
        max_r = max(max_r, favorable_r)
        min_r = min(min_r, adverse_r)
        if tp_hit:
            resolved_type = "MISSED_BIG_WIN" if max_r >= 3.0 else "MISSED_WIN"
            time_to_resolution = index
            break
        if sl_hit:
            resolved_type = "GOOD_REJECTION"
            time_to_resolution = index
            break
    if resolved_type == "NEUTRAL":
        if max_r >= 3.0:
            resolved_type = "MISSED_BIG_WIN"
        elif max_r >= default_rr:
            resolved_type = "MISSED_WIN"
        elif min_r <= -1.0:
            resolved_type = "GOOD_REJECTION"
    return {
        "missed_opportunity_type": resolved_type,
        "max_r": round(max_r, 4),
        "min_r": round(min_r, 4),
        "time_to_resolution": time_to_resolution,
    }


def _levels(signal: dict[str, object], *, entry: float, direction: str, default_rr: float) -> tuple[float, float]:
    stop_loss = _float(signal.get("stop_loss"))
    take_profit = _float(signal.get("take_profit") or signal.get("take_profit_1"))
    atr = _float(signal.get("atr"))
    if stop_loss is None:
        risk = atr if atr is not None and atr > 0 else entry * 0.01
        stop_loss = entry - risk if direction == "long" else entry + risk
    risk = abs(entry - stop_loss)
    if take_profit is None:
        take_profit = entry + risk * default_rr if direction == "long" else entry - risk * default_rr
    return stop_loss, take_profit


def _future_candles(candles: list[dict[str, object]], start: datetime | None) -> list[dict[str, object]]:
    if start is None:
        return candles
    future = []
    for candle in candles:
        candle_time = _parse_time(candle.get("open_time") or candle.get("timestamp") or candle.get("close_time"))
        if candle_time is None or candle_time >= start:
            future.append(candle)
    return future


def _empty(kind: str) -> dict[str, object]:
    return {"missed_opportunity_type": kind, "max_r": 0.0, "min_r": 0.0, "time_to_resolution": 0}


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_time(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

