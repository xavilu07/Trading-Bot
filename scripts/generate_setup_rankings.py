from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


CLOSED_STATUSES = {"tp2_hit", "tp_hit", "sl_hit", "expired", "breakeven"}
WIN_STATUSES = {"tp2_hit", "tp_hit"}
RANKING_FIELDS = (
    "setup_type",
    "direction",
    "market_regime",
    "session",
    "entry_context",
    "trade_location",
    "liquidity_sweep",
    "warnings",
    "penalties",
)
COMBINATION_FIELDS = (
    ("setup_type", "direction"),
    ("direction", "market_regime"),
    ("setup_type", "session"),
    ("setup_type", "entry_context"),
    ("setup_type", "liquidity_sweep"),
    ("session", "market_regime"),
    ("warnings",),
    ("penalties",),
)
CSV_FIELDS = [
    "ranking_type",
    "group",
    "trades",
    "winrate",
    "total_r",
    "avg_r",
    "profit_factor",
    "expectancy",
    "long_trades",
    "short_trades",
    "main_signal_trades",
    "secondary_signal_trades",
]


def discover_trade_csvs(data_path: Path) -> list[Path]:
    paths = []
    paper_path = data_path / "paper_trading"
    if paper_path.exists():
        paths.extend(path for path in paper_path.glob("*.csv") if path.is_file())
    live_path = data_path / "live_trading" / "trades.csv"
    if live_path.exists():
        paths.append(live_path)
    return sorted(paths)


def load_closed_trades(data_path: Path) -> list[dict[str, object]]:
    trades: list[dict[str, object]] = []
    for path in discover_trade_csvs(data_path):
        if path.stat().st_size == 0:
            continue
        try:
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    status = str(row.get("status", row.get("outcome", ""))).strip().lower()
                    result_r = _to_float(row.get("result_r") or row.get("r_result"))
                    if status not in CLOSED_STATUSES or result_r is None:
                        continue
                    item: dict[str, object] = dict(row)
                    item["status"] = status
                    item["result_r"] = result_r
                    item["source_csv"] = str(path)
                    trades.append(item)
        except csv.Error:
            continue
    return trades


def build_setup_rankings(trades: list[dict[str, object]], *, min_trades: int = 1) -> dict[str, list[dict[str, object]]]:
    return {
        "single": _build_rows(trades, RANKING_FIELDS, min_trades=min_trades),
        "combinations": _build_rows(trades, COMBINATION_FIELDS, min_trades=min_trades),
    }


def generate_setup_rankings(data_path: Path, reports_path: Path, *, min_trades: int = 1, dry_run: bool = False) -> dict[str, object]:
    trades = load_closed_trades(data_path)
    rankings = build_setup_rankings(trades, min_trades=min_trades)
    single_path = reports_path / "setup_rankings.csv"
    combinations_path = reports_path / "setup_combinations_rankings.csv"
    if not dry_run:
        reports_path.mkdir(parents=True, exist_ok=True)
        _write_rows(single_path, rankings["single"])
        _write_rows(combinations_path, rankings["combinations"])
    return {
        "trades": len(trades),
        "min_trades": min_trades,
        "setup_rankings_path": str(single_path),
        "setup_combinations_rankings_path": str(combinations_path),
        **rankings,
    }


def format_setup_rankings(result: dict[str, object]) -> str:
    single = _rows(result.get("single"))
    combinations = _rows(result.get("combinations"))
    all_rows = single + combinations
    top = sorted(all_rows, key=lambda row: (float(row.get("avg_r", 0.0)), float(row.get("total_r", 0.0))), reverse=True)[:5]
    worst = sorted(all_rows, key=lambda row: (float(row.get("avg_r", 0.0)), float(row.get("total_r", 0.0))))[:5]
    frequent = sorted(all_rows, key=lambda row: int(row.get("trades", 0)), reverse=True)[:5]
    return (
        "🔥 TOP PERFORMERS\n"
        f"{_format_rows(top)}\n\n"
        "⚠️ WORST PERFORMERS\n"
        f"{_format_rows(worst)}\n\n"
        "🧪 MOST FREQUENT CONTEXTS\n"
        f"{_format_rows(frequent)}\n\n"
        f"Closed trades analyzed: {result.get('trades', 0)}\n"
        f"Min trades: {result.get('min_trades', 1)}\n"
        f"Setup rankings: {result.get('setup_rankings_path')}\n"
        f"Combination rankings: {result.get('setup_combinations_rankings_path')}"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="generate-setup-rankings")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--reports-path", default="reports")
    parser.add_argument("--min-trades", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = generate_setup_rankings(
        Path(args.data_path),
        Path(args.reports_path),
        min_trades=max(1, args.min_trades),
        dry_run=args.dry_run,
    )
    print(format_setup_rankings(result))
    if args.dry_run:
        print("Dry-run: CSV files were not written.")
    return 0


def _build_rows(
    trades: list[dict[str, object]],
    definitions: tuple[str | tuple[str, ...], ...],
    *,
    min_trades: int,
) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for trade in trades:
        for definition in definitions:
            ranking_type = _ranking_type(definition)
            for group in _group_values(trade, definition):
                groups[(ranking_type, group)].append(trade)
    rows = []
    for (ranking_type, group), items in groups.items():
        if len(items) < min_trades:
            continue
        rows.append({"ranking_type": ranking_type, "group": group, **_metrics(items)})
    return sorted(rows, key=lambda row: (str(row["ranking_type"]), -float(row["total_r"]), -float(row["avg_r"])))


def _group_values(trade: dict[str, object], definition: str | tuple[str, ...]) -> list[str]:
    if isinstance(definition, str):
        if definition in {"warnings", "penalties"}:
            return _tokens(_field_value(trade, definition))
        value = _normalize_scalar(_field_value(trade, definition))
        return [value] if value else []
    parts = []
    for field in definition:
        values = _tokens(_field_value(trade, field)) if field in {"warnings", "penalties"} else [_normalize_scalar(_field_value(trade, field))]
        values = [value for value in values if value]
        if not values:
            values = ["UNKNOWN"]
        parts.append(values)
    return _cartesian_join(parts)


def _field_value(trade: dict[str, object], field: str) -> object:
    if field == "warnings":
        return trade.get("avoidance_warnings") or trade.get("warnings")
    if field == "liquidity_sweep":
        return _liquidity_sweep_state(trade)
    return trade.get(field)


def _metrics(trades: list[dict[str, object]]) -> dict[str, object]:
    r_values = [float(trade["result_r"]) for trade in trades]
    wins = [trade for trade in trades if _is_win(trade)]
    gross_profit = sum(max(0.0, value) for value in r_values)
    gross_loss = abs(sum(min(0.0, value) for value in r_values))
    total_r = sum(r_values)
    return {
        "trades": len(trades),
        "winrate": round(len(wins) / len(trades) * 100, 2) if trades else 0.0,
        "total_r": round(total_r, 4),
        "avg_r": round(total_r / len(trades), 4) if trades else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else None,
        "expectancy": round(total_r / len(trades), 4) if trades else 0.0,
        "long_trades": _count_value(trades, "direction", "long"),
        "short_trades": _count_value(trades, "direction", "short"),
        "main_signal_trades": _count_value(trades, "setup_type", "MAIN_SIGNAL"),
        "secondary_signal_trades": _count_value(trades, "setup_type", "SECONDARY_SIGNAL"),
    }


def _write_rows(path: Path, rows: list[dict[str, object]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})
    return path


def _ranking_type(definition: str | tuple[str, ...]) -> str:
    if isinstance(definition, str):
        return definition
    return "+".join(definition)


def _cartesian_join(parts: list[list[str]]) -> list[str]:
    values = [""]
    for part in parts:
        values = [f"{prefix}|{item}" if prefix else item for prefix in values for item in part]
    return values


def _normalize_scalar(value: object) -> str:
    text = str(value or "").strip()
    return text if text else "UNKNOWN"


def _liquidity_sweep_state(trade: dict[str, object]) -> str:
    raw = str(trade.get("liquidity_sweep", "") or "").strip().lower()
    if not raw:
        return "none"
    if raw in {"no", "none", "false", "0"}:
        return "no"
    return "yes"


def _tokens(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        decoded = None
    if isinstance(decoded, list):
        return [str(item).strip() for item in decoded if str(item).strip()]
    return [item.strip() for item in text.replace("|", ",").split(",") if item.strip()]


def _is_win(trade: dict[str, object]) -> bool:
    return str(trade.get("status", "")).lower() in WIN_STATUSES or float(trade.get("result_r", 0.0)) > 0


def _count_value(trades: list[dict[str, object]], key: str, expected: str) -> int:
    expected_norm = expected.lower()
    return len([trade for trade in trades if str(trade.get(key, "")).strip().lower() == expected_norm])


def _rows(value: object) -> list[dict[str, object]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _format_rows(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "- sin datos"
    lines = []
    for row in rows:
        pf = row.get("profit_factor")
        lines.append(
            f"- {row.get('ranking_type')}:{row.get('group')} | trades {row.get('trades')} | "
            f"WR {row.get('winrate')}% | Total R {row.get('total_r')} | "
            f"Avg R {row.get('avg_r')} | PF {pf if pf is not None else 'inf'}"
        )
    return "\n".join(lines)


def _to_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

