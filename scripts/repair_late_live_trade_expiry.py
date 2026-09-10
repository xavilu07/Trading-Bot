"""Repair the three live rows that expired late.

`live_trade_expiry_candles` landed on 2026-09-10, so the three signals that had been
open since 2026-08-21/23 were marked to market at the moment the fix first ran - 17 to
20 days after the 24-candle mark they should have expired at. Every row written from
now on expires on time; these three predate the fix and carry the wrong price.

Replays each against the stored 1h OHLC, exactly as scripts/replay_harness.py does: if
SL or TP was touched inside the window the row becomes that, otherwise it expires at
the close of the 24th candle. Backs the file up first and touches nothing else.
"""
from __future__ import annotations

import csv
import glob
import json
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

TRADES = Path("data/live_trading/trades.csv")
SNAPSHOTS = "data/market_snapshots/*/*.json"
EXPIRY_CANDLES = 24


def _ts(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def load_candles(timeframe="1h"):
    bars = {}
    for path in glob.glob(SNAPSHOTS):
        try:
            snap = json.load(open(path))
        except (OSError, json.JSONDecodeError):
            continue
        if snap.get("timeframe") != timeframe:
            continue
        stamp = _ts(snap.get("timestamp"))
        if stamp is None:
            continue
        bars.setdefault(snap["symbol"], []).append(
            (stamp, float(snap["high"]), float(snap["low"]), float(snap["close"]))
        )
    for symbol in bars:
        bars[symbol].sort(key=lambda row: row[0])
    return bars


def replay(trade, candles):
    entry = float(trade["entry"])
    stop = float(trade["stop_loss"])
    target = float(trade["take_profit"])
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    start = _ts(trade["created_at"])
    window = [bar for bar in candles if start < bar[0] <= start + timedelta(hours=EXPIRY_CANDLES)]
    if len(window) < EXPIRY_CANDLES:
        return None
    long = trade["direction"] == "long"
    for _, high, low, _close in window:
        if (low <= stop) if long else (high >= stop):
            return "sl_hit", -1.0
        if (high >= target) if long else (low <= target):
            return "tp_hit", abs(target - entry) / risk
    close = window[-1][3]
    return "expired", (close - entry) / risk if long else (entry - close) / risk


def main() -> int:
    rows = list(csv.DictReader(TRADES.open()))
    fields = list(rows[0].keys())
    candles = load_candles()
    repaired = []
    for trade in rows:
        if trade.get("status") != "expired" or not str(trade.get("closed_at", "")).startswith("2026-09-10"):
            continue
        outcome = replay(trade, candles.get(trade["symbol"], []))
        if outcome is None:
            print(f"  SIN VELAS  {trade['symbol']:9} {trade['created_at'][:16]} - se deja como esta")
            continue
        status, result_r = outcome
        was = (trade["status"], trade["result_r"])
        trade["status"] = status
        trade["result_r"] = f"{result_r:.4f}"
        trade["closed_at"] = (_ts(trade["created_at"]) + timedelta(hours=EXPIRY_CANDLES)).isoformat()
        repaired.append((trade["symbol"], trade["created_at"][:16], was, (status, trade["result_r"])))
    if not repaired:
        print("nada que reparar")
        return 0
    backup = TRADES.with_suffix(".csv.bak_pre_late_expiry_repair_20260910")
    shutil.copy2(TRADES, backup)
    with TRADES.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"backup: {backup}")
    for symbol, created, was, now in repaired:
        print(f"  {symbol:9} {created}  {was[0]}/{was[1]}  ->  {now[0]}/{now[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
