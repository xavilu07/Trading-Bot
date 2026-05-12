from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from trading_signals.memory.outcome_intelligence import analyze_trade_outcome


CLOSED_STATUSES = {"tp2_hit", "tp_hit", "sl_hit", "expired", "breakeven"}
OUTPUT_FIELDS = [
    "source_csv",
    "symbol",
    "direction",
    "setup_type",
    "market_regime",
    "session",
    "entry_context",
    "trade_location",
    "status",
    "result_r",
    "mfe_r",
    "mae_r",
    "bars_held",
    "outcome_quality_score",
    "outcome_grade",
    "outcome_type",
    "post_entry_behavior",
    "mfe_efficiency",
    "mae_pressure",
    "time_to_resolution",
    "outcome_reasons",
    "outcome_risks",
]


def load_closed_trades(data_path: Path) -> list[dict[str, object]]:
    trades = []
    paths = []
    paper_path = data_path / "paper_trading"
    if paper_path.exists():
        paths.extend(path for path in paper_path.glob("*.csv") if path.is_file())
    live_path = data_path / "live_trading" / "trades.csv"
    if live_path.exists():
        paths.append(live_path)
    for path in sorted(paths):
        for row in _read_csv(path):
            status = str(row.get("status", row.get("outcome", ""))).strip().lower()
            if status not in CLOSED_STATUSES and not str(row.get("closed_at", "")).strip():
                continue
            row["source_csv"] = str(path)
            trades.append(row)
    return trades


def build_outcome_rows(trades: list[dict[str, object]]) -> list[dict[str, object]]:
    rows = []
    for trade in trades:
        outcome = analyze_trade_outcome(trade)
        row = {field: trade.get(field, "") for field in OUTPUT_FIELDS}
        row.update(
            {
                "mfe_r": trade.get("mfe_r") or trade.get("max_favorable_move_r") or trade.get("max_favorable_move") or "",
                "mae_r": trade.get("mae_r") or trade.get("max_adverse_move_r") or trade.get("max_adverse_move") or "",
                "bars_held": trade.get("bars_held") or trade.get("candles_held") or trade.get("candles_elapsed") or "",
                "outcome_quality_score": outcome["outcome_quality_score"],
                "outcome_grade": outcome["outcome_grade"],
                "outcome_type": outcome["outcome_type"],
                "post_entry_behavior": outcome["post_entry_behavior"],
                "mfe_efficiency": outcome["mfe_efficiency"],
                "mae_pressure": outcome["mae_pressure"],
                "time_to_resolution": outcome["time_to_resolution"],
                "outcome_reasons": json.dumps(outcome["outcome_reasons"], ensure_ascii=False),
                "outcome_risks": json.dumps(outcome["outcome_risks"], ensure_ascii=False),
            }
        )
        rows.append(row)
    return rows


def generate_outcome_intelligence(data_path: Path, reports_path: Path) -> dict[str, object]:
    reports_path.mkdir(parents=True, exist_ok=True)
    trades = load_closed_trades(data_path)
    rows = build_outcome_rows(trades)
    output_path = reports_path / "outcome_intelligence.csv"
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in OUTPUT_FIELDS} for row in rows)
    return {
        "output_path": str(output_path),
        "rows": rows,
        "summary": build_summary(rows),
    }


def build_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    counter = Counter(str(row.get("outcome_type") or "UNKNOWN") for row in rows)
    return {
        "counts": dict(counter),
        "best_contexts": _rank_contexts(rows, reverse=True),
        "worst_contexts": _rank_contexts(rows, reverse=False),
    }


def format_summary(summary: dict[str, object]) -> str:
    counts = summary.get("counts", {})
    if not isinstance(counts, dict):
        counts = {}
    return (
        "🧠 Outcome Intelligence\n"
        f"- CLEAN_WIN: {counts.get('CLEAN_WIN', 0)}\n"
        f"- DIRTY_WIN: {counts.get('DIRTY_WIN', 0)}\n"
        f"- CLEAN_LOSS: {counts.get('CLEAN_LOSS', 0)}\n"
        f"- BAD_LOSS: {counts.get('BAD_LOSS', 0)}\n"
        f"- TIMEOUT: {counts.get('TIMEOUT', 0)}\n\n"
        "🔥 Best outcome contexts\n"
        f"{_format_contexts(summary.get('best_contexts', []))}\n\n"
        "⚠️ Worst outcome contexts\n"
        f"{_format_contexts(summary.get('worst_contexts', []))}"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="generate-outcome-intelligence")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--reports-path", default="reports")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = generate_outcome_intelligence(Path(args.data_path), Path(args.reports_path))
    print(format_summary(result["summary"]))
    print(f"Report: {result['output_path']}")
    return 0


def _read_csv(path: Path) -> list[dict[str, object]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except csv.Error:
        return []


def _rank_contexts(rows: list[dict[str, object]], *, reverse: bool) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        for key in ("setup_type", "direction", "market_regime", "session", "entry_context", "trade_location"):
            label = str(row.get(key) or "UNKNOWN")
            groups[f"{key}:{label}"].append(row)
    ranked = []
    for label, items in groups.items():
        avg_score = sum(float(item.get("outcome_quality_score") or 0.0) for item in items) / len(items)
        ranked.append({"label": label, "trades": len(items), "avg_outcome_score": round(avg_score, 2)})
    return sorted(ranked, key=lambda item: float(item["avg_outcome_score"]), reverse=reverse)[:10]


def _format_contexts(items: object) -> str:
    if not isinstance(items, list) or not items:
        return "- sin datos"
    return "\n".join(f"- {item.get('label')} | trades {item.get('trades')} | avg score {item.get('avg_outcome_score')}" for item in items if isinstance(item, dict))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

