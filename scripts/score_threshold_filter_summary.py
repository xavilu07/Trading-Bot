"""Read out what the setup-score floor is doing, in shadow or enforcing.

History: shipped 2026-08-27 in shadow, flipped to hard_block the same day once
the tradeable-population measurement settled the threshold. On setups the
strategy would actually signal (those that pass directional confluence), the
record gives PF 1.8457 above a floor of 90 against 0.9051 with no floor, and the
85-90 band loses money. Rows I-M of scripts/replay_harness.py carry the numbers.

What a week of enforcement can and cannot say: almost nothing, on its own. 15
trades were accepted in the seven days before the flip, but 14 were
SECONDARY_SIGNAL opened under sha c5323ba, before 9c1b205 switched that branch
off. Discounting them, August produced 2 accepted MAIN_SIGNAL trades in the
whole month - both scoring 100, both of which this floor would have passed. So
a week of hard_block will likely block nothing and trade once, and the traded
and blocked columns below will stay too thin to read for a long time.

The third section below tracks the candidates the quality gate declines, which
are written with a full lifecycle as universe=rejected and arrive at about 6 a
day. That was the hope for a faster-accumulating comparison, and it is not one
either: across the whole labelled era only 6 of them are confluent and score
>=90, against 103 below. Watch it for a large drift, do not decide from it.

Nothing in the live stream accumulates the 90-versus-below comparison at a
useful rate. The evidence for 90 is the historical record - rows I-M of
scripts/replay_harness.py, n=67 above the floor - and a week of enforcement
will confirm the filter behaves, not whether it pays. Say so rather than
reading a verdict into four trades.

Usage:
    .venv/bin/python scripts/score_threshold_filter_summary.py
    .venv/bin/python scripts/score_threshold_filter_summary.py --since 2026-07-01
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter

TRADES = "data/paper_trading/trades.csv"
LOG = "logs/scheduler.log"
SHADOW_MARKER = "setup_score_below_threshold_shadow"
BLOCK_MARKER = "setup_score_below_threshold"
ENFORCING_SINCE = "2026-08-27"
DEFAULT_COST_R = 0.0388  # commission 0.02 + spread 0.01 + slippage 0.01


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _net_r(row) -> float | None:
    net = _num(row.get("net_result_r"))
    if net is not None:
        return net
    gross = _num(row.get("result_r"))
    return None if gross is None else gross - DEFAULT_COST_R


def _markers(row) -> list[str]:
    raw = row.get("conditions_failed") or ""
    try:
        parsed = json.loads(raw or "[]")
    except ValueError:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _confluent(row) -> bool:
    """Did the strategy actually signal this? `directional_confluence_failed`
    means it declined - sweep one way, trend and structure the other - and those
    setups are written to the record anyway. Splitting scores without excluding
    them measures a population the bot cannot trade, which is the mistake rows
    A-H of the replay harness made: 1.3284 over the mixed population against
    1.8457 over the tradeable one.
    """
    return "directional_confluence_failed" not in _markers(row)


def _blocked_by_floor(row) -> bool:
    """Refused by this filter - not merely marked while it was only watching."""
    if BLOCK_MARKER in _markers(row):
        return True
    return BLOCK_MARKER in (row.get("entry_or_rejection_reason") or "") and SHADOW_MARKER not in _markers(row)


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
        print(f"    {reason:26s} {count}")
    print(f"  marcados en shadow          {shadow}")
    print(f"  bloqueados de verdad        {blocked}")


def trades_readout(since: str) -> None:
    try:
        rows = list(csv.DictReader(open(TRADES)))
    except OSError:
        print("sin data/paper_trading/trades.csv")
        return

    def window(row) -> bool:
        return (row.get("created_at") or row.get("opened_at") or "") >= since

    live = [row for row in rows if window(row) and row.get("setup_type") != "SECONDARY_SIGNAL"]
    traded = [row for row in live if row.get("universe") == "accepted"]
    blocked = [row for row in live if _blocked_by_floor(row)]

    print(f"\n=== desde {since} ===")
    print(f"  operados (universe=accepted)   {len(traded):4d}   cerrados {len([r for r in traded if (r.get('closed_at') or '').strip()])}")
    print(f"  bloqueados por el suelo        {len(blocked):4d}   cerrados {len([r for r in blocked if (r.get('closed_at') or '').strip()])}")

    print("\n  lo que hizo cada lado (solo cerrados):")
    for label, population in (
        ("operados            ", [r for r in traded if (r.get("closed_at") or "").strip()]),
        ("bloqueados por suelo", [r for r in blocked if (r.get("closed_at") or "").strip()]),
    ):
        values = [value for value in map(_net_r, population) if value is not None]
        print(f"    {label}  {summarise(values)}")

    print("\n  el suelo esta ganandose el sueldo si los bloqueados van peor que los operados.")
    print("  con menos de ~30 cerrados por lado, no leas nada de la comparacion.")

    tracked = [
        row for row in live
        if row.get("universe") == "rejected" and (row.get("closed_at") or "").strip() and _confluent(row)
    ]
    declined = len([
        row for row in live
        if row.get("universe") == "rejected" and (row.get("closed_at") or "").strip() and not _confluent(row)
    ])
    print(f"\n  candidatos rastreados, cerrados y operables (universe=rejected): {len(tracked)}")
    print(f"    ({declined} mas excluidos por directional_confluence_failed: la estrategia no los habria emitido)")
    print("    crece ~6/dia, pero casi toda por debajo de 90: en toda la era etiquetada")
    print("    solo hay 6 por encima. Sirve para vigilar una deriva grande, no para decidir.")
    for label, population in (
        ("score >= 90", [r for r in tracked if (_num(r.get("score")) or 0) >= 90]),
        ("score <  90", [r for r in tracked if (_num(r.get("score")) or 0) < 90]),
    ):
        values = [value for value in map(_net_r, population) if value is not None]
        print(f"    {label}  {summarise(values)}")

    if traded:
        scores = Counter(int(_num(r.get("score")) or 0) for r in traded)
        print(f"\n  scores de los operados: {sorted(scores.items(), reverse=True)}")
        below = [r for r in traded if (_num(r.get("score")) or 0) < 90]
        if below:
            print(f"  AVISO: {len(below)} operados por debajo de 90 - el suelo no los detuvo, revisa por que")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default=ENFORCING_SINCE, help="fecha desde la que contar (por defecto, el dia del flip)")
    args = parser.parse_args()
    log_readout()
    trades_readout(args.since)


if __name__ == "__main__":
    main()
