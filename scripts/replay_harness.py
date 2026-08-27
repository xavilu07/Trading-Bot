"""Replay closed paper trades candle-by-candle against stored 1h OHLC.

Built 2026-08-24 after MFE-based reasoning produced a confident but wrong
recommendation (close half at TP1 + break-even, which the replay showed makes
things worse). MFE tells you the best price a trade ever saw; it does not tell
you when, so any policy inferred from it carries lookahead bias. This replays
the actual path instead.

Fidelity check on the record as of 2026-08-24: the replay reproduces the
recorded final status for 1667 of 1707 closed trades (97.7%), with ~99% of
trades having all 24 candles available.

Usage:
    .venv/bin/python scripts/replay_harness.py                  # config comparison
    .venv/bin/python scripts/replay_harness.py --walk-forward   # in vs out of sample
    .venv/bin/python scripts/replay_harness.py --fidelity       # validate the harness
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
from collections import defaultdict
from datetime import datetime

TRADES = "data/paper_trading/trades.csv"
SNAPSHOTS = "data/market_snapshots/*/*.json"
DEFAULT_COST_R = 0.0388  # commission 0.02 + spread 0.01 + slippage 0.01


def _ts(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def _num(row: dict, key: str) -> float | None:
    try:
        return float(row.get(key) or "")
    except ValueError:
        return None


def load_candles(timeframe: str = "1h") -> dict[str, list[tuple]]:
    bars: dict[str, list[tuple]] = defaultdict(list)
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
        bars[snap["symbol"]].append(
            (stamp, float(snap["high"]), float(snap["low"]), float(snap["close"]))
        )
    for symbol in bars:
        bars[symbol].sort()
    return bars


def load_closed_trades() -> list[dict]:
    rows = list(csv.DictReader(open(TRADES)))
    return [
        row for row in rows
        if (row.get("closed_at") or "").strip() and _num(row, "result_r") is not None
    ]


def replay(row: dict, bars: dict, *, use_tp: bool = True, expiry: int | None = None) -> float | None:
    """Return the R this trade would have produced. None if candles are missing.

    The stop is checked before the target within a candle, matching the live
    engine (`evaluate_trade_status`) and keeping the estimate conservative when
    both were touched in the same candle.
    """
    opened = _ts(row.get("opened_at"))
    entry = _num(row, "entry_price")
    stop = _num(row, "stop_loss")
    target = _num(row, "take_profit_2")
    if opened is None or None in (entry, stop, target):
        return None
    risk = abs(entry - stop)
    if risk <= 0:
        return None

    long = row["direction"] == "long"
    limit = expiry or int(float(row.get("expires_after_candles") or 24))
    candles = [bar for bar in bars.get(row["symbol"], []) if bar[0] >= opened][:limit]
    if not candles:
        return None

    def as_r(price: float) -> float:
        return (price - entry) / risk if long else (entry - price) / risk

    for _, high, low, _close in candles:
        if (low <= stop) if long else (high >= stop):
            return -1.0
        if use_tp and ((high >= target) if long else (low <= target)):
            return as_r(target)
    return as_r(candles[-1][3])


def summarise(values: list[float | None], cost: float = DEFAULT_COST_R) -> dict | None:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    net = [v - cost for v in clean]
    wins = [v for v in net if v > 0]
    losses = [v for v in net if v <= 0]
    gross_loss = abs(sum(losses))
    return {
        "n": len(net),
        "wr": 100 * len(wins) / len(net),
        "pf": (sum(wins) / gross_loss) if gross_loss else 0.0,
        "total": sum(net),
        "avg": sum(net) / len(net),
    }


def _line(label: str, stats: dict | None) -> None:
    if not stats:
        print(f"  {label:42s} n=0")
        return
    print(
        f"  {label:42s} n={stats['n']:5d} WR={stats['wr']:5.2f}% "
        f"PFnet={stats['pf']:6.4f} totR={stats['total']:+8.2f} avg={stats['avg']:+7.4f}"
    )


def _score(row: dict) -> float:
    return _num(row, "score") or 0.0


def _no_secondary(row: dict) -> bool:
    return row.get("setup_type") != "SECONDARY_SIGNAL"


CONFIGS = [
    ("A. today (SECONDARY off)", lambda r: _no_secondary(r), True),
    ("B. + score>=90", lambda r: _no_secondary(r) and _score(r) >= 90, True),
    ("C. + no TP cap", lambda r: _no_secondary(r) and _score(r) >= 90, False),
    ("D. C minus BTCUSDT", lambda r: _no_secondary(r) and _score(r) >= 90 and r["symbol"] != "BTCUSDT", False),
    ("E. score>=85, no TP cap", lambda r: _no_secondary(r) and _score(r) >= 85, False),
    ("F. score>=95, no TP cap", lambda r: _no_secondary(r) and _score(r) >= 95, False),
    # The shadow threshold filter keeps the TP cap, so these are the rows that
    # actually decide 85 vs 90 vs 95 - E and F above change two things at once.
    ("G. score>=85 (TP cap kept)", lambda r: _no_secondary(r) and _score(r) >= 85, True),
    ("H. score>=95 (TP cap kept)", lambda r: _no_secondary(r) and _score(r) >= 95, True),
]


def report_configs(trades: list[dict], bars: dict) -> None:
    print("=== configurations (whole record) ===")
    for label, keep, use_tp in CONFIGS:
        pop = [r for r in trades if keep(r)]
        _line(label, summarise([replay(r, bars, use_tp=use_tp) for r in pop]))


def report_walk_forward(trades: list[dict], bars: dict) -> None:
    """Train on May-Jun, test on Jul-Aug. A config that only shines in-sample is curve-fitting."""
    def month(row: dict) -> str:
        stamp = _ts(row["closed_at"])
        return stamp.strftime("%Y-%m") if stamp else ""

    inside = [r for r in trades if month(r) in ("2026-05", "2026-06")]
    outside = [r for r in trades if month(r) in ("2026-07", "2026-08")]
    print(f"=== walk-forward: in-sample n={len(inside)}  out-of-sample n={len(outside)} ===")
    for label, keep, use_tp in CONFIGS:
        a = summarise([replay(r, bars, use_tp=use_tp) for r in inside if keep(r)])
        b = summarise([replay(r, bars, use_tp=use_tp) for r in outside if keep(r)])
        fmt = lambda s: f"{s['pf']:6.4f}(n={s['n']:3d}) {s['total']:+7.2f}" if s else "      n/a      "
        print(f"  {label:42s} IN {fmt(a)}  |  OUT {fmt(b)}")


def report_fidelity(trades: list[dict], bars: dict) -> None:
    """Does the replay reproduce what actually happened? Re-run after any engine change."""
    matched = total = 0
    confusion: dict[tuple[str, str], int] = defaultdict(int)
    for row in trades:
        opened = _ts(row.get("opened_at"))
        entry, stop = _num(row, "entry_price"), _num(row, "stop_loss")
        target = _num(row, "take_profit_2")
        if opened is None or None in (entry, stop, target):
            continue
        long = row["direction"] == "long"
        limit = int(float(row.get("expires_after_candles") or 24))
        candles = [bar for bar in bars.get(row["symbol"], []) if bar[0] >= opened][:limit]
        if not candles:
            continue
        predicted = "expired"
        for _, high, low, _c in candles:
            if (low <= stop) if long else (high >= stop):
                predicted = "sl_hit"
                break
            if (high >= target) if long else (low <= target):
                predicted = "tp2_hit"
                break
        actual = row["status"] if row["status"] in ("sl_hit", "tp2_hit", "expired") else "expired"
        confusion[(actual, predicted)] += 1
        total += 1
        matched += predicted == actual
    print(f"=== fidelity: {matched}/{total} ({100 * matched / total:.1f}%) ===")
    for (actual, predicted), count in sorted(confusion.items(), key=lambda kv: -kv[1]):
        flag = "" if actual == predicted else "   <- mismatch"
        print(f"  recorded {actual:9s} -> replay {predicted:9s}: {count}{flag}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--walk-forward", action="store_true", help="in-sample vs out-of-sample")
    parser.add_argument("--fidelity", action="store_true", help="validate the harness itself")
    args = parser.parse_args()

    bars = load_candles()
    trades = load_closed_trades()
    print(f"{sum(len(v) for v in bars.values())} 1h candles, {len(bars)} symbols, {len(trades)} closed trades\n")

    if args.fidelity:
        report_fidelity(trades, bars)
    elif args.walk_forward:
        report_walk_forward(trades, bars)
    else:
        report_configs(trades, bars)


if __name__ == "__main__":
    main()
