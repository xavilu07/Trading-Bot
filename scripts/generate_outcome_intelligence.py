from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from trading_signals.memory.outcome_intelligence import analyze_trade_outcome


CLOSED_STATUSES = {"tp2_hit", "tp_hit", "sl_hit", "expired", "breakeven"}
OUTPUT_FIELDS = [
    "generated_at",
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
    "sample_size",
    "confidence",
    "winrate",
    "avg_r",
    "profit_factor",
    "PF",
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
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    for trade in trades:
        outcome = analyze_trade_outcome(trade)
        row = {field: trade.get(field, "") for field in OUTPUT_FIELDS}
        row.update(
            {
                "generated_at": generated_at,
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
    _attach_context_metrics(rows)
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


def _attach_context_metrics(rows: list[dict[str, object]]) -> None:
    groups: dict[tuple[str, str, str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[_context_key(row)].append(row)
    metrics_by_key = {key: _result_metrics(items) for key, items in groups.items()}
    for row in rows:
        metrics = metrics_by_key.get(_context_key(row), {})
        row.update(metrics)


def _context_key(row: dict[str, object]) -> tuple[str, str, str, str, str]:
    return (
        _value(row.get("setup_type")),
        _value(row.get("direction")),
        _value(row.get("session")),
        _value(row.get("entry_context")),
        _value(row.get("market_regime")),
    )


def _result_metrics(rows: list[dict[str, object]]) -> dict[str, object]:
    r_values = [_to_float(row.get("result_r")) for row in rows]
    r_values = [value for value in r_values if value is not None]
    wins = [value for value in r_values if value > 0]
    gross_profit = sum(max(0.0, value) for value in r_values)
    gross_loss = abs(sum(min(0.0, value) for value in r_values))
    profit_factor = round(gross_profit / gross_loss, 4) if gross_loss > 0 else None
    sample_size = len(r_values)
    return {
        "sample_size": sample_size,
        "confidence": _confidence(sample_size),
        "winrate": round(len(wins) / sample_size * 100, 2) if sample_size else 0.0,
        "avg_r": round(sum(r_values) / sample_size, 4) if sample_size else 0.0,
        "profit_factor": profit_factor,
        "PF": profit_factor,
    }


def _value(value: object) -> str:
    text = str(value or "").strip()
    return text if text else "UNKNOWN"


def _confidence(sample_size: int) -> str:
    if sample_size >= 30:
        return "HIGH"
    if sample_size >= 10:
        return "MEDIUM"
    return "LOW"


def _to_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_contexts(items: object) -> str:
    if not isinstance(items, list) or not items:
        return "- sin datos"
    return "\n".join(f"- {item.get('label')} | trades {item.get('trades')} | avg score {item.get('avg_outcome_score')}" for item in items if isinstance(item, dict))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
