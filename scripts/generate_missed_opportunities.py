from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from trading_signals.app.settings import load_settings
from trading_signals.infrastructure.exchange.provider_factory import build_market_data_provider
from trading_signals.memory.missed_opportunity import analyze_missed_opportunity


OUTPUT_FIELDS = [
    "timestamp",
    "symbol",
    "direction",
    "score",
    "entry_price",
    "atr",
    "status",
    "rejection_reasons",
    "missed_opportunity_type",
    "max_r",
    "min_r",
    "time_to_resolution",
]


def load_rejected_signals(data_path: Path, logs_path: Path, *, min_score: float = 80.0) -> list[dict[str, object]]:
    rows = []
    rows.extend(_read_signal_activity(data_path / "bot_activity" / "signals_log.jsonl", min_score=min_score))
    rows.extend(_read_scheduler_rejections(logs_path / "scheduler.log", min_score=min_score))
    return _dedupe(rows)


def generate_missed_opportunities(data_path: Path, reports_path: Path, logs_path: Path, *, min_score: float = 80.0, timeframe: str = "1h", limit: int = 300) -> dict[str, object]:
    reports_path.mkdir(parents=True, exist_ok=True)
    rejected = load_rejected_signals(data_path, logs_path, min_score=min_score)
    provider = _safe_provider()
    output_rows = []
    for signal in rejected:
        candles = []
        if provider is not None:
            try:
                candles = provider.get_ohlcv(str(signal.get("symbol")), timeframe, limit=limit)
            except Exception:
                candles = []
        result = analyze_missed_opportunity(signal, candles)
        output_rows.append(_output_row(signal, result))
    output_path = reports_path / "missed_opportunities.csv"
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)
    return {"output_path": str(output_path), "rows": output_rows, "summary": _summary(output_rows)}


def format_summary(summary: dict[str, object]) -> str:
    counts = summary.get("counts", {})
    if not isinstance(counts, dict):
        counts = {}
    return (
        "🧠 Missed Opportunities\n"
        f"- MISSED_WIN: {counts.get('MISSED_WIN', 0)}\n"
        f"- MISSED_BIG_WIN: {counts.get('MISSED_BIG_WIN', 0)}\n"
        f"- GOOD_REJECTION: {counts.get('GOOD_REJECTION', 0)}\n"
        f"- NEUTRAL: {counts.get('NEUTRAL', 0)}"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="generate-missed-opportunities")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--reports-path", default="reports")
    parser.add_argument("--logs-path", default="logs")
    parser.add_argument("--min-score", type=float, default=80.0)
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--limit", type=int, default=300)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = generate_missed_opportunities(
        Path(args.data_path),
        Path(args.reports_path),
        Path(args.logs_path),
        min_score=args.min_score,
        timeframe=args.timeframe,
        limit=args.limit,
    )
    print(format_summary(result["summary"]))
    print(f"Report: {result['output_path']}")
    return 0


def _read_signal_activity(path: Path, *, min_score: float) -> list[dict[str, object]]:
    signals = []
    if not path.exists():
        return signals
    for item in _read_jsonl(path):
        status = str(item.get("status") or "").lower()
        score = _float(item.get("score")) or 0.0
        if status in {"no_trade", "rejected"} and score >= min_score:
            signals.append(item)
    return signals


def _read_scheduler_rejections(path: Path, *, min_score: float) -> list[dict[str, object]]:
    signals = []
    if not path.exists():
        return signals
    for item in _read_jsonl(path):
        if item.get("event") not in {"high_score_rejected", "candidate_rejected"}:
            continue
        score = _float(item.get("score") or item.get("setup_score_final")) or 0.0
        if score < min_score:
            continue
        signals.append(
            {
                "timestamp": item.get("timestamp") or item.get("created_at"),
                "symbol": item.get("symbol"),
                "direction": item.get("direction"),
                "score": score,
                "entry_price": item.get("entry") or item.get("entry_price") or item.get("price"),
                "atr": item.get("atr"),
                "status": "rejected",
                "rejection_reasons": item.get("blocking_reasons") or item.get("rejection_reason"),
            }
        )
    return signals


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _dedupe(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    seen = set()
    output = []
    for row in rows:
        key = (row.get("timestamp"), row.get("symbol"), row.get("direction"), row.get("entry_price") or row.get("entry"))
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def _safe_provider():
    try:
        return build_market_data_provider(load_settings())
    except Exception:
        return None


def _output_row(signal: dict[str, object], result: dict[str, object]) -> dict[str, object]:
    return {
        "timestamp": signal.get("timestamp") or signal.get("created_at") or "",
        "symbol": signal.get("symbol", ""),
        "direction": signal.get("direction", ""),
        "score": signal.get("score", ""),
        "entry_price": signal.get("entry_price") or signal.get("entry") or "",
        "atr": signal.get("atr", ""),
        "status": signal.get("status", ""),
        "rejection_reasons": _jsonish(signal.get("rejection_reasons") or signal.get("reasons") or signal.get("conditions_failed")),
        **result,
    }


def _summary(rows: list[dict[str, object]]) -> dict[str, object]:
    return {"counts": dict(Counter(str(row.get("missed_opportunity_type") or "NEUTRAL") for row in rows))}


def _jsonish(value: object) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value or "")


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

