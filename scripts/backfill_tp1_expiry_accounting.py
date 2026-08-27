"""Replace the fabricated +1R that expired-at-TP1 trades recorded.

`evaluate_trade_status` used to return the TP1 distance as a trade's R for as
long as it sat at `tp1_hit`, and the status is sticky. Nothing is ever sold at
TP1 in this engine - there is no partial close - so a trade that touched TP1 and
then drifted out its remaining candles closed as `expired` booking a profit it
never took. 299 of 1738 closed paper trades carry that number, and 40 of them
actually finished negative.

The code is fixed forward (marks to market). This repairs the rows already
written, using the engine's own formula - (close - entry) / risk at the expiry
candle, direction-adjusted - applied to the 1h candle the scan stored at the
time. It is not the replay harness and does not use its path logic: the aim is
the number the engine would have written, not a better one.

A row is repaired only when its recorded R equals the TP1 distance to within
1e-9 and its status is `expired`. That signature is what the bug produced;
anything else is left alone. A blank `net_result_r` stays blank: most of these
rows predate the cost columns, and writing a net computed from zero costs would
trade one false number for another.

Usage:
    .venv/bin/python scripts/backfill_tp1_expiry_accounting.py            # dry run
    .venv/bin/python scripts/backfill_tp1_expiry_accounting.py --apply    # writes, after a backup
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import shutil
from collections import defaultdict
from datetime import datetime

STORES = (
    "data/paper_trading/trades.csv",
    "data/live_trading/trades.csv",
    "data/shadow_relaxation/trades.csv",
)
SNAPSHOTS = "data/market_snapshots/*/*.json"


def _ts(value):
    try:
        return datetime.fromisoformat((value or "").replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def _num(row, key):
    try:
        return float(row.get(key) or "")
    except (TypeError, ValueError):
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
        bars[snap["symbol"]].append((stamp, float(snap["close"])))
    for symbol in bars:
        bars[symbol].sort()
    return bars


def fabricated_tp1_r(row) -> float | None:
    """The R this row would carry if the bug wrote it; None if it cannot have."""
    if row.get("status") != "expired":
        return None
    entry, stop, tp1 = _num(row, "entry_price"), _num(row, "stop_loss"), _num(row, "take_profit_1")
    recorded = _num(row, "result_r")
    if None in (entry, stop, tp1, recorded):
        return None
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    tp1_r = abs(tp1 - entry) / risk
    return tp1_r if abs(recorded - tp1_r) < 1e-9 else None


def expiry_r(row, bars) -> float | None:
    """The engine's own mark-to-market at the candle the trade expired on."""
    opened = _ts(row.get("opened_at"))
    entry, stop = _num(row, "entry_price"), _num(row, "stop_loss")
    if opened is None or None in (entry, stop):
        return None
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    limit = int(float(row.get("expires_after_candles") or 24))
    candles = [bar for bar in bars.get(row["symbol"], []) if bar[0] >= opened][:limit]
    if len(candles) < limit:
        return None
    close = candles[-1][1]
    return (close - entry) / risk if row.get("direction") == "long" else (entry - close) / risk


def repair(path: str, bars, apply: bool) -> None:
    try:
        with open(path) as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames or []
            rows = list(reader)
    except OSError:
        print(f"\n{path}: no existe, se omite")
        return

    candidates = [row for row in rows if fabricated_tp1_r(row) is not None]
    repaired = skipped = 0
    became_losses = 0
    delta = 0.0
    for row in candidates:
        corrected = expiry_r(row, bars)
        if corrected is None:
            skipped += 1
            continue
        before = _num(row, "result_r") or 0.0
        delta += corrected - before
        if corrected < 0:
            became_losses += 1
        repaired += 1
        if not apply:
            continue
        row["result_r"] = f"{corrected:.4f}"
        if "gross_result_r" in fields:
            row["gross_result_r"] = f"{corrected:.4f}"
        # Only rewrite a net that already existed. 254 of these rows predate the
        # cost columns and carry a blank net; filling it in from zero costs would
        # publish a "net" that is net of nothing, and every reader that currently
        # substitutes a default cost for a blank would silently stop doing so.
        if "net_result_r" in fields and (row.get("net_result_r") or "").strip():
            total_cost = sum(_num(row, field) or 0.0 for field in ("commission", "spread", "slippage", "funding"))
            row["net_result_r"] = f"{corrected - total_cost:.4f}"

    print(f"\n{path}")
    print(f"  filas totales                {len(rows)}")
    print(f"  con la firma del bug         {len(candidates)}")
    print(f"  reparables (hay velas)       {repaired}")
    print(f"  sin velas suficientes        {skipped}  <- se dejan como estan")
    print(f"  pasan a ser perdidas         {became_losses}")
    print(f"  cambio total en R            {delta:+.2f}")

    if not apply or not repaired:
        return
    backup = f"{path}.bak_pre_tp1_backfill_{datetime.now():%Y%m%d}"
    shutil.copy2(path, backup)
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  escrito. copia de seguridad: {backup}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="escribe los cambios (por defecto solo los cuenta)")
    args = parser.parse_args()
    if not args.apply:
        print("DRY RUN - nada se escribe. Usa --apply para escribir.")
    bars = load_candles()
    print(f"{sum(len(v) for v in bars.values())} velas 1h, {len(bars)} simbolos")
    for path in STORES:
        repair(path, bars, args.apply)


if __name__ == "__main__":
    main()
