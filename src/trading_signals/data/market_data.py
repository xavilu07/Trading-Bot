from __future__ import annotations


def market_data_status(symbol: str, entry_snapshot, higher_snapshot) -> dict[str, object]:
    ok = bool(entry_snapshot and higher_snapshot)
    return {
        "ok": ok,
        "score": 100.0 if ok else 0.0,
        "reason": "market_data_available" if ok else "market_data_missing",
        "details": {
            "symbol": symbol,
            "entry_timeframe": getattr(entry_snapshot, "timeframe", None),
            "higher_timeframe": getattr(higher_snapshot, "timeframe", None),
            "entry_timestamp": getattr(entry_snapshot, "timestamp", None),
            "higher_timestamp": getattr(higher_snapshot, "timestamp", None),
            "entry_close": getattr(entry_snapshot, "close", None),
            "higher_close": getattr(higher_snapshot, "close", None),
        },
    }

