from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.triple_barrier import UNKNOWN, label_triple_barrier


OUTPUT_FIELDS = [
    "signal_id",
    "timestamp",
    "symbol",
    "direction",
    "entry",
    "stop_loss",
    "take_profit",
    "time_barrier_bars",
    "label",
    "label_reason",
    "result_r",
    "max_r",
    "min_r",
    "bars_to_label",
    "market_regime",
    "session",
    "entry_context",
    "trade_location",
    "setup_type",
    "warnings",
    "penalties",
]


def generate_triple_barrier_labels(
    *,
    data_path: Path,
    logs_path: Path,
    reports_path: Path,
    time_barrier_bars: int = 24,
    source: str = "all",
    limit: int | None = None,
) -> dict[str, Any]:
    signals = load_label_candidates(data_path=data_path, logs_path=logs_path, source=source)
    if limit is not None:
        signals = sorted(signals, key=lambda item: str(item.get("timestamp") or ""), reverse=True)[:limit]
        signals = sorted(signals, key=lambda item: str(item.get("timestamp") or ""))

    rows = []
    for signal in signals:
        label = label_triple_barrier(signal, time_barrier_bars=time_barrier_bars)
        rows.append(_output_row(signal, label, time_barrier_bars=time_barrier_bars))

    reports_path.mkdir(parents=True, exist_ok=True)
    output_path = reports_path / "triple_barrier_labels.csv"
    _write_csv(output_path, rows)
    return {
        "output_path": output_path,
        "rows": rows,
        "summary": _summary(rows),
    }


def load_label_candidates(*, data_path: Path, logs_path: Path, source: str = "all") -> list[dict[str, Any]]:
    selected = source.strip().lower()
    rows: list[dict[str, Any]] = []
    if selected in {"all", "live"}:
        rows.extend(_read_trade_csv(data_path / "live_trading" / "trades.csv", source="live"))
    if selected in {"all", "paper"}:
        paper_path = data_path / "paper_trading"
        if paper_path.exists():
            for path in sorted(paper_path.glob("*.csv")):
                rows.extend(_read_trade_csv(path, source=f"paper:{path.name}"))
    if selected in {"all", "signals"}:
        rows.extend(_read_signal_activity(data_path / "bot_activity" / "signals_log.jsonl"))
        rows.extend(_read_scheduler_events(logs_path / "scheduler.log"))
    return _dedupe(rows)


def format_summary(summary: dict[str, Any]) -> str:
    counts = summary.get("counts", {})
    if not isinstance(counts, dict):
        counts = {}
    return (
        "🏷️ Triple Barrier Labels\n"
        f"- TP_HIT: {counts.get('TP_HIT', 0)}\n"
        f"- SL_HIT: {counts.get('SL_HIT', 0)}\n"
        f"- TIMEOUT: {counts.get('TIMEOUT', 0)}\n"
        f"- UNKNOWN: {counts.get('UNKNOWN', 0)}\n"
        f"- Avg result R: {summary.get('avg_result_r', 0.0)}\n"
        f"- Best contexts: {_format_contexts(summary.get('best_contexts'))}\n"
        f"- Worst contexts: {_format_contexts(summary.get('worst_contexts'))}"
    )


def _read_trade_csv(path: Path, *, source: str) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    rows = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                normalized = _normalize_row(dict(row), source=source)
                if normalized is not None:
                    rows.append(normalized)
    except csv.Error:
        return []
    return rows


def _read_signal_activity(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for item in _read_jsonl(path):
        normalized = _normalize_row(item, source="signals_log")
        if normalized is not None:
            rows.append(normalized)
    return rows


def _read_scheduler_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for item in _read_jsonl(path):
        if not item.get("symbol") or not (item.get("entry") or item.get("entry_price")):
            continue
        normalized = _normalize_row(item, source="scheduler_log")
        if normalized is not None:
            rows.append(normalized)
    return rows


def _normalize_row(row: dict[str, Any], *, source: str) -> dict[str, Any] | None:
    timestamp = (
        row.get("timestamp")
        or row.get("created_at")
        or row.get("opened_at")
        or row.get("closed_at")
        or row.get("evaluated_at")
    )
    symbol = row.get("symbol")
    direction = row.get("direction")
    if not timestamp or not symbol or not direction:
        return None

    raw_summary = _dict(row.get("raw_summary"))
    entry = row.get("entry") or row.get("entry_price")
    take_profit = row.get("take_profit") or row.get("take_profit_1") or row.get("tp1") or row.get("tp")
    normalized = {
        "signal_id": row.get("signal_id") or raw_summary.get("signal_id") or row.get("trade_id") or "",
        "timestamp": _iso_timestamp(timestamp),
        "symbol": symbol,
        "direction": direction,
        "entry": entry,
        "entry_price": entry,
        "stop_loss": row.get("stop_loss") or row.get("sl"),
        "take_profit": take_profit,
        "status": row.get("status") or row.get("outcome") or row.get("exit_reason") or "",
        "result_r": row.get("result_r") or row.get("r_result") or row.get("realized_r") or "",
        "mfe_r": row.get("mfe_r") or row.get("max_r") or "",
        "mae_r": row.get("mae_r") or row.get("min_r") or "",
        "candles_held": row.get("candles_held") or row.get("bars_held") or row.get("candles_elapsed") or "",
        "market_regime": row.get("market_regime") or "",
        "session": row.get("session") or "",
        "entry_context": row.get("entry_context") or "",
        "trade_location": row.get("trade_location") or "",
        "setup_type": row.get("setup_type") or raw_summary.get("setup_detected") or "",
        "warnings": row.get("warnings") or row.get("avoidance_warnings") or "",
        "penalties": row.get("penalties") or "",
        "source": source,
    }
    for key in ("bars", "candles", "price_bars", "ohlcv"):
        if key in row:
            normalized[key] = row[key]
    return normalized


def _output_row(signal: dict[str, Any], label: dict[str, Any], *, time_barrier_bars: int) -> dict[str, Any]:
    return {
        "signal_id": signal.get("signal_id", ""),
        "timestamp": signal.get("timestamp", ""),
        "symbol": signal.get("symbol", ""),
        "direction": signal.get("direction", ""),
        "entry": signal.get("entry") or signal.get("entry_price") or "",
        "stop_loss": signal.get("stop_loss", ""),
        "take_profit": signal.get("take_profit", ""),
        "time_barrier_bars": time_barrier_bars,
        "label": label.get("label", UNKNOWN),
        "label_reason": label.get("label_reason", ""),
        "result_r": label.get("result_r", ""),
        "max_r": label.get("max_r", ""),
        "min_r": label.get("min_r", ""),
        "bars_to_label": label.get("bars_to_label", ""),
        "market_regime": signal.get("market_regime", ""),
        "session": signal.get("session", ""),
        "entry_context": signal.get("entry_context", ""),
        "trade_location": signal.get("trade_location", ""),
        "setup_type": signal.get("setup_type", ""),
        "warnings": _jsonish(signal.get("warnings")),
        "penalties": _jsonish(signal.get("penalties")),
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result_values = [_float(row.get("result_r")) for row in rows if _float(row.get("result_r")) is not None]
    return {
        "counts": dict(Counter(str(row.get("label") or UNKNOWN) for row in rows)),
        "avg_result_r": round(sum(result_values) / len(result_values), 4) if result_values else 0.0,
        "best_contexts": _context_rank(rows, reverse=True),
        "worst_contexts": _context_rank(rows, reverse=False),
    }


def _context_rank(rows: list[dict[str, Any]], *, reverse: bool) -> list[dict[str, Any]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        result_r = _float(row.get("result_r"))
        if result_r is None:
            continue
        for key in ("direction", "setup_type", "market_regime", "session", "entry_context", "trade_location"):
            value = str(row.get(key) or "").strip()
            if value:
                grouped[f"{key}:{value}"].append(result_r)
    ranked = [
        {"context": context, "trades": len(values), "total_r": round(sum(values), 4)}
        for context, values in grouped.items()
    ]
    return sorted(ranked, key=lambda item: float(item["total_r"]), reverse=reverse)[:5]


def _format_contexts(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "none"
    return "; ".join(f"{item.get('context')} R={item.get('total_r')}" for item in value if isinstance(item, dict))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in OUTPUT_FIELDS})


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output = []
    for row in rows:
        key = str(row.get("signal_id") or "")
        if not key:
            key = "|".join(
                [
                    str(row.get("timestamp") or ""),
                    str(row.get("symbol") or ""),
                    str(row.get("direction") or ""),
                    str(row.get("entry") or ""),
                ]
            )
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return sorted(output, key=lambda item: str(item.get("timestamp") or ""))


def _iso_timestamp(value: Any) -> str:
    parsed = _parse_datetime(str(value or ""))
    return parsed.isoformat() if parsed is not None else str(value or "")


def _parse_datetime(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _jsonish(value: Any) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value or "")


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="generate-triple-barrier-labels")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--logs-path", default="logs")
    parser.add_argument("--reports-path", default="reports")
    parser.add_argument("--time-barrier-bars", type=int, default=24)
    parser.add_argument("--source", choices=("all", "paper", "live", "signals"), default="all")
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = generate_triple_barrier_labels(
        data_path=Path(args.data_path),
        logs_path=Path(args.logs_path),
        reports_path=Path(args.reports_path),
        time_barrier_bars=max(1, args.time_barrier_bars),
        source=args.source,
        limit=args.limit,
    )
    print(format_summary(result["summary"]))
    print(f"Report: {result['output_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
