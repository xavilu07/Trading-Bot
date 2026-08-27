import csv
from collections import defaultdict

FILE = "data/paper_trading/trades.csv"

CLOSED_STATUSES = {"expired", "sl_hit", "tp1_hit", "tp2_hit"}

GROUPS = [
    ("direction",),
    ("symbol",),
    ("market_regime",),
    ("session",),
    ("entry_context",),
    ("trade_location",),
    ("direction","market_regime"),
    ("direction","session"),
    ("direction","entry_context"),
    ("market_regime","entry_context"),
    ("direction","market_regime","entry_context"),
    ("symbol","direction"),
    ("symbol","direction","market_regime"),
    ("direction","session","entry_context"),
]

def clean(x, default="UNKNOWN"):
    return str(x or default).strip() or default

def num(x):
    try:
        return float(x)
    except:
        return None

rows = []
with open(FILE, newline="") as fh:
    for r in csv.DictReader(fh):
        status = clean(r.get("status")).lower()
        if status not in CLOSED_STATUSES:
            continue

        rr = num(r.get("result_r"))
        if rr is None:
            continue

        rows.append({**r, "_r": rr})

print("\nEDGE DISCOVERY REPORT")
print(f"Trades analyzed: {len(rows)}")
print()

def summarize(group_cols):
    buckets = defaultdict(list)

    for r in rows:
        key = " | ".join(clean(r.get(c)) for c in group_cols)
        buckets[key].append(r["_r"])

    out = []

    for key, vals in buckets.items():
        if len(vals) < 15:
            continue

        wins = [v for v in vals if v > 0]
        losses = [v for v in vals if v < 0]

        total = sum(vals)
        winrate = len(wins) / len(vals) * 100
        pf = sum(wins) / abs(sum(losses)) if losses else 999
        avg = total / len(vals)

        out.append((pf, total, winrate, avg, len(vals), key))

    return sorted(out, key=lambda x: x[1], reverse=True)

for group in GROUPS:
    print("\n" + "="*90)
    print("GROUP BY:", " + ".join(group))

    data = summarize(group)

    print("\nBEST EDGES BY TOTAL R")
    for pf,total,wr,avg,n,key in data[:10]:
        print(f"{key} | n={n} | WR={wr:.2f}% | PF={pf:.2f} | avgR={avg:.4f} | totalR={total:.4f}")

    print("\nWORST EDGES BY TOTAL R")
    for pf,total,wr,avg,n,key in data[-10:]:
        print(f"{key} | n={n} | WR={wr:.2f}% | PF={pf:.2f} | avgR={avg:.4f} | totalR={total:.4f}")
