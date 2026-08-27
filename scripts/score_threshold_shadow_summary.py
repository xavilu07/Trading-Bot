"""Read out what the shadow score floor has observed so far.

The filter went live on 2026-08-27 in shadow mode: it records the candidates it
would have refused and refuses nothing. This is the instrument that turns those
records into the decision it exists to inform - whether to enforce a floor at
all, and at 85, 90 or 95.

The plan called for n>=60 accepted trades above the threshold before choosing,
estimated at 6-8 weeks from the score>=90 population throughput of 1.18
signals/day. That estimate does not survive contact with the record: since the
universe label started in July, score>=90 setups split 19 rejected to 2
accepted, about 2 accepted per month. n>=60 accepted is years away, not weeks,
and the quality gate - not the throughput - is what governs it.

So this prints both universes. The accepted one is what the filter would
actually change and is the one that decides; the rejected one carries the
volume and is where the edge was measured, but it is the counterfactual of a
gate that declined those trades, so it answers "is score>=90 still a real
edge", not "what would this filter do to our signals".

Usage:
    .venv/bin/python scripts/score_threshold_shadow_summary.py
    .venv/bin/python scripts/score_threshold_shadow_summary.py --since 2026-08-27
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter

TRADES = "data/paper_trading/trades.csv"
LOG = "logs/scheduler.log"
SHADOW_MARKER = "setup_score_below_threshold_shadow"
SHADOW_LIVE_SINCE = "2026-08-27"
DEFAULT_COST_R = 0.0388  # commission 0.02 + spread 0.01 + slippage 0.01
TARGET_N = 60


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarise(values: list[float]) -> str:
    if not values:
        return "n=0"
    wins = [v for v in values if v > 0]
    gross_loss = abs(sum(v for v in values if v <= 0))
    pf = (sum(wins) / gross_loss) if gross_loss else float("inf")
    return (
        f"n={len(values):4d}  WR={100 * len(wins) / len(values):5.2f}%  "
        f"PFnet={pf:6.4f}  totR={sum(values):+8.2f}"
    )


def log_readout() -> None:
    reasons: Counter[str] = Counter()
    shadow = blocked = 0
    try:
        stream = open(LOG, errors="replace")
    except OSError:
        print("sin logs/scheduler.log")
        return
    with stream:
        for line in stream:
            if "setup_score_threshold_filter_" not in line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            name = event.get("event", "")
            if name == "setup_score_threshold_filter_evaluated":
                reasons[str(event.get("reason"))] += 1
            elif name == "setup_score_threshold_filter_shadow":
                shadow += 1
            elif name == "setup_score_threshold_filter_blocked":
                blocked += 1
    print("=== scan log ===")
    print(f"  evaluaciones {sum(reasons.values())}")
    for reason, count in reasons.most_common():
        print(f"    {reason:24s} {count}")
    print(f"  would_block en shadow    {shadow}")
    print(f"  bloqueados de verdad     {blocked}  <- debe ser 0 mientras el modo sea shadow")


def _net_r(row) -> float | None:
    net = _num(row.get("net_result_r"))
    if net is not None:
        return net
    gross = _num(row.get("result_r"))
    return None if gross is None else gross - DEFAULT_COST_R


def _population(rows: list[dict], universe: str, since: str) -> list[dict]:
    return [
        row for row in rows
        if row.get("universe") == universe
        and (row.get("created_at") or row.get("opened_at") or "") >= since
        and (row.get("closed_at") or "").strip()
        and row.get("setup_type") != "SECONDARY_SIGNAL"
    ]


def trades_readout(since: str, thresholds: list[float]) -> None:
    try:
        rows = list(csv.DictReader(open(TRADES)))
    except OSError:
        print("sin data/paper_trading/trades.csv")
        return

    marked = [
        row for row in rows
        if SHADOW_MARKER in (row.get("conditions_failed") or "")
        and (row.get("created_at") or row.get("opened_at") or "") >= since
    ]
    print(f"\n=== marcados por el filtro en shadow desde {since}: {len(marked)} ===")

    for universe, note in (
        ("accepted", "lo que el filtro cambiaria de verdad - esto decide"),
        ("rejected", "el volumen, pero son trades que la puerta ya declino - solo confirma el edge"),
    ):
        closed = _population(rows, universe, since)
        print(f"\n=== universo {universe} desde {since} ({len(closed)} cerrados) ===")
        print(f"    {note}")
        for threshold in thresholds:
            above = [row for row in closed if (_num(row.get("score")) or 0.0) >= threshold]
            below = [row for row in closed if (_num(row.get("score")) or 0.0) < threshold]
            above_r = [value for value in map(_net_r, above) if value is not None]
            below_r = [value for value in map(_net_r, below) if value is not None]
            print(f"  umbral {threshold:g}")
            print(f"    por encima (se operaria)   {summarise(above_r)}")
            print(f"    por debajo (se filtraria)  {summarise(below_r)}")
            if universe == "accepted":
                remaining = max(0, TARGET_N - len(above))
                print(
                    f"    {'listo para decidir' if remaining == 0 else f'faltan {remaining} para n={TARGET_N}'}"
                )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default=SHADOW_LIVE_SINCE, help="solo trades creados a partir de esta fecha")
    parser.add_argument(
        "--thresholds",
        default="85,90,95",
        help="umbrales a comparar; el filtro solo aplica el suyo, esto solo los mide",
    )
    args = parser.parse_args()
    thresholds = [float(item) for item in args.thresholds.split(",") if item.strip()]
    log_readout()
    trades_readout(args.since, thresholds)


if __name__ == "__main__":
    main()
