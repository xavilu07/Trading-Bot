from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


CLOSED_STATUSES = {"tp2_hit", "tp_hit", "sl_hit", "expired", "breakeven", "closed", "win", "loss"}
WIN_STATUSES = {"tp2_hit", "tp_hit", "win"}
LOSS_STATUSES = {"sl_hit", "loss"}
GROUP_FIELDS = (
    "direction",
    "setup_type",
    "market_regime",
    "session",
    "entry_context",
    "trade_location",
)

WINDOW_FIELDS = [
    "window_id",
    "group_type",
    "group",
    "train_start",
    "train_end",
    "test_start",
    "test_end",
    "train_trades",
    "test_trades",
    "train_winrate",
    "test_winrate",
    "train_total_r",
    "test_total_r",
    "train_avg_r",
    "test_avg_r",
    "train_profit_factor",
    "test_profit_factor",
    "max_drawdown_r",
    "stability_score",
    "overfit_warning",
]

SUMMARY_FIELDS = [
    "group_type",
    "group",
    "windows",
    "positive_test_windows",
    "negative_test_windows",
    "insufficient_windows",
    "avg_test_r",
    "total_test_r",
    "avg_stability_score",
    "overfit_warnings",
]


def run_walk_forward_backtest(
    *,
    data_path: Path,
    reports_path: Path,
    train_days: int = 30,
    test_days: int = 7,
    step_days: int = 7,
    min_trades: int = 5,
) -> dict[str, object]:
    trades = load_trade_history(data_path=data_path, reports_path=reports_path)
    rows = build_walk_forward_rows(
        trades,
        train_days=train_days,
        test_days=test_days,
        step_days=step_days,
        min_trades=min_trades,
    )
    summary_rows = build_walk_forward_summary(rows)

    reports_path.mkdir(parents=True, exist_ok=True)
    detail_path = reports_path / "walk_forward_backtest.csv"
    summary_path = reports_path / "walk_forward_summary.csv"
    _write_csv(detail_path, rows, WINDOW_FIELDS)
    _write_csv(summary_path, summary_rows, SUMMARY_FIELDS)

    return {
        "trades": trades,
        "rows": rows,
        "summary": summary_rows,
        "detail_csv_path": detail_path,
        "summary_csv_path": summary_path,
        "min_trades": min_trades,
    }


def format_walk_forward(result: dict[str, object]) -> str:
    rows = [row for row in result.get("rows", []) if isinstance(row, dict)]
    overall = [row for row in rows if row.get("group_type") == "OVERALL"]
    positive = [row for row in overall if float(row.get("test_total_r") or 0.0) > 0]
    negative = [row for row in overall if float(row.get("test_total_r") or 0.0) < 0]
    avg_test_r = _avg([float(row.get("test_total_r") or 0.0) for row in overall])
    avg_stability = _avg([float(row.get("stability_score") or 0.0) for row in overall])
    summary = [row for row in result.get("summary", []) if isinstance(row, dict)]
    best = _best_stable_contexts(summary)
    worst = _worst_unstable_contexts(summary)
    return (
        "🧪 Walk-Forward Backtest\n"
        f"- Total windows: {len(overall)}\n"
        f"- Positive test windows: {len(positive)}\n"
        f"- Negative test windows: {len(negative)}\n"
        f"- Avg test R: {round(avg_test_r, 4)}\n"
        f"- Stability score: {round(avg_stability, 2)}\n"
        f"- Best stable contexts: {_format_contexts(best)}\n"
        f"- Worst unstable contexts: {_format_contexts(worst)}\n"
        f"- Detail CSV: {result.get('detail_csv_path')}\n"
        f"- Summary CSV: {result.get('summary_csv_path')}"
    )


def load_trade_history(*, data_path: Path, reports_path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    rows.extend(_load_closed_trades(data_path / "live_trading" / "trades.csv", source="live"))
    paper_path = data_path / "paper_trading"
    if paper_path.exists():
        for path in sorted(paper_path.glob("*.csv")):
            rows.extend(_load_closed_trades(path, source=f"paper:{path.name}"))
    rows.extend(_load_report_rows(reports_path / "recent_public_signals_audit.csv", source="recent_public_signals_audit"))
    rows.extend(_load_public_filter_backtest_rows(reports_path / "public_signal_filter_backtest.csv"))
    return _dedupe_trades(rows)


def build_walk_forward_rows(
    trades: list[dict[str, object]],
    *,
    train_days: int,
    test_days: int,
    step_days: int,
    min_trades: int,
) -> list[dict[str, object]]:
    dated = sorted([trade for trade in trades if isinstance(trade.get("timestamp"), datetime)], key=lambda row: row["timestamp"])
    if not dated:
        return []

    start = _floor_day(dated[0]["timestamp"])
    end = dated[-1]["timestamp"]
    rows: list[dict[str, object]] = []
    window_id = 1
    cursor = start
    while cursor + timedelta(days=train_days) <= end:
        train_start = cursor
        train_end = cursor + timedelta(days=train_days)
        test_start = train_end
        test_end = test_start + timedelta(days=test_days)
        if test_start > end:
            break
        train = [trade for trade in dated if train_start <= trade["timestamp"] < train_end]
        test = [trade for trade in dated if test_start <= trade["timestamp"] < test_end]
        rows.extend(_window_group_rows(window_id, train_start, train_end, test_start, test_end, train, test, min_trades))
        window_id += 1
        cursor += timedelta(days=step_days)
    return rows


def build_walk_forward_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("group_type", "")), str(row.get("group", "")))].append(row)

    summary_rows = []
    for (group_type, group), items in grouped.items():
        test_r = [float(item.get("test_total_r") or 0.0) for item in items if item.get("overfit_warning") != "insufficient_data"]
        stability = [float(item.get("stability_score") or 0.0) for item in items if item.get("overfit_warning") != "insufficient_data"]
        warnings = sorted({str(item.get("overfit_warning")) for item in items if item.get("overfit_warning")})
        summary_rows.append(
            {
                "group_type": group_type,
                "group": group,
                "windows": len(items),
                "positive_test_windows": sum(1 for value in test_r if value > 0),
                "negative_test_windows": sum(1 for value in test_r if value < 0),
                "insufficient_windows": sum(1 for item in items if item.get("overfit_warning") == "insufficient_data"),
                "avg_test_r": round(_avg(test_r), 4),
                "total_test_r": round(sum(test_r), 4),
                "avg_stability_score": round(_avg(stability), 2),
                "overfit_warnings": "|".join(warnings),
            }
        )
    return sorted(summary_rows, key=lambda row: (str(row["group_type"]), -float(row["avg_stability_score"]), -float(row["total_test_r"])))


def _window_group_rows(
    window_id: int,
    train_start: datetime,
    train_end: datetime,
    test_start: datetime,
    test_end: datetime,
    train: list[dict[str, object]],
    test: list[dict[str, object]],
    min_trades: int,
) -> list[dict[str, object]]:
    rows = [
        _build_window_row(
            window_id,
            "OVERALL",
            "ALL",
            train_start,
            train_end,
            test_start,
            test_end,
            train,
            test,
            min_trades,
        )
    ]
    for field in GROUP_FIELDS:
        for value in sorted(_group_values(train + test, field)):
            rows.append(
                _build_window_row(
                    window_id,
                    field,
                    value,
                    train_start,
                    train_end,
                    test_start,
                    test_end,
                    [trade for trade in train if _normalize_group(trade.get(field)) == value],
                    [trade for trade in test if _normalize_group(trade.get(field)) == value],
                    min_trades,
                )
            )
    return rows


def _build_window_row(
    window_id: int,
    group_type: str,
    group: str,
    train_start: datetime,
    train_end: datetime,
    test_start: datetime,
    test_end: datetime,
    train: list[dict[str, object]],
    test: list[dict[str, object]],
    min_trades: int,
) -> dict[str, object]:
    train_metrics = _metrics(train)
    test_metrics = _metrics(test)
    insufficient = len(train) < min_trades or len(test) < min_trades
    stability_score = 0.0 if insufficient else _stability_score(train_metrics, test_metrics)
    return {
        "window_id": window_id,
        "group_type": group_type,
        "group": group,
        "train_start": train_start.isoformat(),
        "train_end": train_end.isoformat(),
        "test_start": test_start.isoformat(),
        "test_end": test_end.isoformat(),
        "train_trades": len(train),
        "test_trades": len(test),
        "train_winrate": train_metrics["winrate"],
        "test_winrate": test_metrics["winrate"],
        "train_total_r": train_metrics["total_r"],
        "test_total_r": test_metrics["total_r"],
        "train_avg_r": train_metrics["avg_r"],
        "test_avg_r": test_metrics["avg_r"],
        "train_profit_factor": train_metrics["profit_factor"],
        "test_profit_factor": test_metrics["profit_factor"],
        "max_drawdown_r": test_metrics["max_drawdown_r"],
        "stability_score": round(stability_score, 2),
        "overfit_warning": "insufficient_data" if insufficient else _overfit_warning(train_metrics, test_metrics),
    }


def _metrics(trades: list[dict[str, object]]) -> dict[str, object]:
    r_values = [float(trade["result_r"]) for trade in trades if _to_float(trade.get("result_r")) is not None]
    wins = [value for value in r_values if value > 0]
    losses = [value for value in r_values if value < 0]
    gross_profit = sum(max(0.0, value) for value in r_values)
    gross_loss = abs(sum(min(0.0, value) for value in r_values))
    total_r = sum(r_values)
    return {
        "trades": len(r_values),
        "winrate": round(len(wins) / len(r_values) * 100, 2) if r_values else 0.0,
        "total_r": round(total_r, 4),
        "avg_r": round(total_r / len(r_values), 4) if r_values else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else (round(gross_profit, 4) if gross_profit else 0.0),
        "max_drawdown_r": round(_max_drawdown(r_values), 4),
        "wins": len(wins),
        "losses": len(losses),
    }


def _stability_score(train: dict[str, object], test: dict[str, object]) -> float:
    train_avg = float(train.get("avg_r") or 0.0)
    test_avg = float(test.get("avg_r") or 0.0)
    train_total = float(train.get("total_r") or 0.0)
    test_total = float(test.get("total_r") or 0.0)
    score = 50.0
    if train_avg > 0 and test_avg > 0:
        score += 30.0
    elif train_avg < 0 and test_avg < 0:
        score -= 10.0
    elif train_avg * test_avg < 0:
        score -= 25.0
    if test_total > 0:
        score += 10.0
    elif test_total < 0:
        score -= 10.0
    score -= min(25.0, abs(train_avg - test_avg) * 20.0)
    return max(0.0, min(100.0, score))


def _overfit_warning(train: dict[str, object], test: dict[str, object]) -> str:
    train_total = float(train.get("total_r") or 0.0)
    test_total = float(test.get("total_r") or 0.0)
    train_avg = float(train.get("avg_r") or 0.0)
    test_avg = float(test.get("avg_r") or 0.0)
    if train_total > 0 and test_total < 0:
        return "train_positive_test_negative"
    if train_avg > 0 and test_avg <= 0:
        return "unstable_edge"
    if train_total > 0 and test_total > 0:
        return "stable_positive"
    if train_total < 0 and test_total < 0:
        return "stable_negative"
    return "mixed"


def _load_closed_trades(path: Path, *, source: str) -> list[dict[str, object]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    rows: list[dict[str, object]] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                item = _normalize_trade_row(row, source=source)
                if item is not None:
                    rows.append(item)
    except csv.Error:
        return []
    return rows


def _load_report_rows(path: Path, *, source: str) -> list[dict[str, object]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    rows: list[dict[str, object]] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                item = _normalize_report_row(row, source=source)
                if item is not None:
                    rows.append(item)
    except csv.Error:
        return []
    return rows


def _load_public_filter_backtest_rows(path: Path) -> list[dict[str, object]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    rows: list[dict[str, object]] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if str(row.get("scenario", "")).upper() != "BASELINE":
                    continue
                item = _normalize_report_row(row, source="public_signal_filter_backtest")
                if item is not None:
                    rows.append(item)
    except csv.Error:
        return []
    return rows


def _normalize_trade_row(row: dict[str, str], *, source: str) -> dict[str, object] | None:
    status = str(row.get("status") or row.get("outcome") or "").strip().lower()
    result_r = _to_float(row.get("result_r") or row.get("r_result") or row.get("realized_r"))
    timestamp = _first_datetime(row, ("closed_at", "exit_time", "evaluated_at", "updated_at", "created_at", "opened_at", "timestamp"))
    if result_r is None or timestamp is None:
        return None
    if status and status not in CLOSED_STATUSES and not (result_r > 0 or result_r < 0):
        return None
    return _base_trade(row, result_r=result_r, timestamp=timestamp, source=source)


def _normalize_report_row(row: dict[str, str], *, source: str) -> dict[str, object] | None:
    result_r = _to_float(row.get("result_r"))
    timestamp = _first_datetime(row, ("timestamp", "closed_at", "exit_time", "evaluated_at"))
    if result_r is None or timestamp is None:
        return None
    return _base_trade(row, result_r=result_r, timestamp=timestamp, source=source)


def _base_trade(row: dict[str, str], *, result_r: float, timestamp: datetime, source: str) -> dict[str, object]:
    return {
        "signal_id": row.get("signal_id") or row.get("trade_id") or "",
        "timestamp": timestamp,
        "result_r": result_r,
        "direction": _normalize_group(row.get("direction")),
        "setup_type": _normalize_group(row.get("setup_type")),
        "market_regime": _normalize_group(row.get("market_regime")),
        "session": _normalize_group(row.get("session")),
        "entry_context": _normalize_group(row.get("entry_context")),
        "trade_location": _normalize_group(row.get("trade_location")),
        "source": source,
    }


def _dedupe_trades(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[str] = set()
    deduped: list[dict[str, object]] = []
    for row in sorted(rows, key=lambda item: (str(item.get("signal_id") or ""), item.get("timestamp"))):
        key = str(row.get("signal_id") or "")
        if not key:
            timestamp = row.get("timestamp")
            key = "|".join(
                [
                    str(timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp),
                    str(row.get("direction") or ""),
                    str(row.get("setup_type") or ""),
                    str(row.get("result_r") or ""),
                ]
            )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return sorted(deduped, key=lambda item: item["timestamp"])


def _group_values(trades: list[dict[str, object]], field: str) -> set[str]:
    return {value for value in (_normalize_group(trade.get(field)) for trade in trades) if value != "UNKNOWN"}


def _normalize_group(value: object) -> str:
    text = str(value or "").strip()
    return text if text else "UNKNOWN"


def _first_datetime(row: dict[str, str], keys: tuple[str, ...]) -> datetime | None:
    for key in keys:
        parsed = _parse_datetime(str(row.get(key) or ""))
        if parsed is not None:
            return parsed
    return None


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


def _floor_day(value: datetime) -> datetime:
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


def _to_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _max_drawdown(values: list[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    drawdown = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        drawdown = min(drawdown, cumulative - peak)
    return drawdown


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _best_stable_contexts(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    candidates = [row for row in rows if row.get("group_type") != "OVERALL" and float(row.get("avg_test_r") or 0.0) > 0]
    return sorted(candidates, key=lambda row: (float(row.get("avg_stability_score") or 0.0), float(row.get("total_test_r") or 0.0)), reverse=True)[:5]


def _worst_unstable_contexts(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    candidates = [row for row in rows if row.get("group_type") != "OVERALL" and float(row.get("total_test_r") or 0.0) < 0]
    return sorted(candidates, key=lambda row: (float(row.get("avg_stability_score") or 0.0), float(row.get("total_test_r") or 0.0)))[:5]


def _format_contexts(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "none"
    return "; ".join(
        f"{row.get('group_type')}={row.get('group')} R={row.get('total_test_r')} stability={row.get('avg_stability_score')}"
        for row in rows[:5]
    )


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="run-walk-forward-backtest")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--reports-path", default="reports")
    parser.add_argument("--train-days", type=int, default=30)
    parser.add_argument("--test-days", type=int, default=7)
    parser.add_argument("--step-days", type=int, default=7)
    parser.add_argument("--min-trades", type=int, default=5)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_walk_forward_backtest(
        data_path=Path(args.data_path),
        reports_path=Path(args.reports_path),
        train_days=max(1, args.train_days),
        test_days=max(1, args.test_days),
        step_days=max(1, args.step_days),
        min_trades=max(1, args.min_trades),
    )
    print(format_walk_forward(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
