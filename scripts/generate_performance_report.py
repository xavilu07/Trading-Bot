from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path


CLOSED_STATUSES = {"tp2_hit", "tp_hit", "sl_hit", "expired"}
WIN_STATUSES = {"tp2_hit", "tp_hit"}
EDGE_GROUP_FIELDS = (
    "direction",
    "setup_type",
    "score_bucket",
    "market_regime",
    "session",
    "entry_context",
    "trade_location",
    "warnings",
    "penalties",
    "blocking_reasons",
    "high_score_rejected",
)
SECONDARY_GROUP_FIELDS = (
    "setup_type",
    "liquidity_sweep",
    "setup_type_liquidity_sweep",
    "setup_type_market_structure",
    "setup_type_warnings",
    "setup_type_penalties",
)


def discover_paper_csvs(data_path: Path) -> list[Path]:
    paper_path = data_path / "paper_trading"
    if not paper_path.exists():
        return []
    return sorted(path for path in paper_path.glob("*.csv") if path.is_file())


def load_closed_trades(data_path: Path) -> list[dict[str, object]]:
    trades: list[dict[str, object]] = []
    for csv_path in discover_paper_csvs(data_path):
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                status = str(row.get("status", row.get("outcome", ""))).strip().lower()
                result_r = _to_float(row.get("result_r"))
                if status not in CLOSED_STATUSES or result_r is None:
                    continue
                item: dict[str, object] = dict(row)
                item["source_csv"] = str(csv_path)
                item["status"] = status
                item["result_r"] = result_r
                trades.append(item)
    return trades


def build_performance_metrics(trades: list[dict[str, object]]) -> dict[str, object]:
    r_values = [float(trade["result_r"]) for trade in trades]
    wins = [trade for trade in trades if str(trade.get("status")) in WIN_STATUSES or float(trade["result_r"]) > 0]
    losses = [trade for trade in trades if float(trade["result_r"]) < 0]
    gross_profit = sum(max(0.0, value) for value in r_values)
    gross_loss = abs(sum(min(0.0, value) for value in r_values))
    return {
        "total_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": round(len(wins) / len(trades) * 100, 2) if trades else 0.0,
        "total_r": round(sum(r_values), 4),
        "avg_r": round(sum(r_values) / len(r_values), 4) if r_values else 0.0,
        "max_drawdown": round(_max_drawdown(r_values), 4),
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else None,
        "best_setups": _rank_by_total_r(trades, "setup_type", reverse=True),
        "worst_warnings": _rank_tokens(trades, "avoidance_warnings", reverse=False),
        "worst_penalties": _rank_tokens(trades, "penalties", reverse=False),
        "edge_breakdown": build_edge_breakdown(trades),
        "secondary_signal_breakdown": build_secondary_signal_breakdown(trades),
    }


def build_edge_breakdown(trades: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for trade in trades:
        for field in EDGE_GROUP_FIELDS:
            for value in _edge_values(trade, field):
                groups[(field, value)].append(trade)
    rows = []
    for (field, value), items in groups.items():
        rows.append({"group_type": field, "group": value, **_group_metrics(items)})
    return sorted(rows, key=lambda item: float(item["total_r"]))


def build_secondary_signal_breakdown(trades: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for trade in trades:
        for field in SECONDARY_GROUP_FIELDS:
            for value in _secondary_values(trade, field):
                groups[(field, value)].append(trade)
    rows = []
    for (field, value), items in groups.items():
        rows.append({"group_type": field, "group": value, **_group_metrics(items)})
    return sorted(rows, key=lambda item: (str(item["group_type"]), str(item["group"])))


def generate_performance_report(data_path: Path, reports_path: Path) -> dict[str, object]:
    reports_path.mkdir(parents=True, exist_ok=True)
    output_path = reports_path / "performance_report.html"
    trades = load_closed_trades(data_path)
    metrics = build_performance_metrics(trades)
    edge_csv_path = reports_path / "edge_breakdown.csv"
    secondary_csv_path = reports_path / "secondary_signal_breakdown.csv"
    write_edge_breakdown_csv(edge_csv_path, metrics.get("edge_breakdown", []))
    write_edge_breakdown_csv(secondary_csv_path, metrics.get("secondary_signal_breakdown", []))
    if len(trades) < 2:
        output_path.write_text(_simple_html("Datos insuficientes", metrics), encoding="utf-8")
        return {
            "ok": False,
            "reason": "insufficient_closed_trades",
            "report_path": str(output_path),
            "edge_breakdown_path": str(edge_csv_path),
            "secondary_signal_breakdown_path": str(secondary_csv_path),
            "metrics": metrics,
        }
    returns = _returns_by_date(trades)
    quantstats_ok = _write_quantstats_report(returns, output_path)
    if not quantstats_ok:
        output_path.write_text(_simple_html("Performance report", metrics), encoding="utf-8")
    return {
        "ok": True,
        "reason": "quantstats_report_generated" if quantstats_ok else "fallback_report_generated",
        "report_path": str(output_path),
        "edge_breakdown_path": str(edge_csv_path),
        "secondary_signal_breakdown_path": str(secondary_csv_path),
        "metrics": metrics,
    }


def format_metrics(metrics: dict[str, object]) -> str:
    profit_factor = metrics.get("profit_factor")
    return (
        "📊 Paper Trading Performance\n"
        f"- Total trades: {metrics.get('total_trades', 0)}\n"
        f"- Winrate: {metrics.get('winrate', 0.0)}%\n"
        f"- Total R: {metrics.get('total_r', 0.0)}R\n"
        f"- Avg R: {metrics.get('avg_r', 0.0)}R\n"
        f"- Max drawdown aprox: {metrics.get('max_drawdown', 0.0)}R\n"
        f"- Profit factor: {profit_factor if profit_factor is not None else 'inf'}\n"
        f"- Mejores setups: {_format_rank(metrics.get('best_setups', []))}\n"
        f"- Peores warnings: {_format_rank(metrics.get('worst_warnings', []))}\n"
        f"- Peores penalties: {_format_rank(metrics.get('worst_penalties', []))}\n\n"
        f"{format_secondary_signal_analysis(metrics.get('secondary_signal_breakdown', []))}\n\n"
        f"{format_edge_breakdown(metrics.get('edge_breakdown', []))}"
    )


def format_secondary_signal_analysis(rows: object) -> str:
    if not isinstance(rows, list):
        rows = []
    valid_rows = [row for row in rows if isinstance(row, dict)]
    secondary_no_sweep = _find_breakdown(valid_rows, "setup_type_liquidity_sweep", "SECONDARY_SIGNAL|no")
    secondary_with_sweep = _find_breakdown(valid_rows, "setup_type_liquidity_sweep", "SECONDARY_SIGNAL|yes")
    main = _find_breakdown(valid_rows, "setup_type", "MAIN_SIGNAL")
    return (
        "🧪 Secondary Signal Analysis\n"
        f"- SECONDARY sin sweep: {_format_secondary_metric_line(secondary_no_sweep)}\n"
        f"- SECONDARY con sweep: {_format_secondary_metric_line(secondary_with_sweep)}\n"
        f"- MAIN: {_format_secondary_metric_line(main)}"
    )


def format_edge_breakdown(edge_rows: object) -> str:
    if not isinstance(edge_rows, list) or not edge_rows:
        return "🔎 Edge Breakdown\n- Sin datos suficientes"
    valid_rows = [row for row in edge_rows if isinstance(row, dict)]
    best = sorted(valid_rows, key=lambda item: float(item.get("total_r", 0.0)), reverse=True)[:5]
    worst = sorted(valid_rows, key=lambda item: float(item.get("total_r", 0.0)))[:5]
    leaks = [row for row in worst if float(row.get("total_r", 0.0)) < 0][:5]
    return (
        "🔎 Edge Breakdown\n"
        "✅ Mejores grupos\n"
        f"{_format_edge_rows(best)}\n\n"
        "⚠️ Peores grupos\n"
        f"{_format_edge_rows(worst)}\n\n"
        "🧨 Principales fugas de R\n"
        f"{_format_edge_rows(leaks)}"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="generate-performance-report")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--reports-path", default="reports")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = generate_performance_report(Path(args.data_path), Path(args.reports_path))
    print(format_metrics(result["metrics"]))
    print(f"Report: {result['report_path']}")
    print(f"Edge breakdown: {result['edge_breakdown_path']}")
    print(f"Secondary signal breakdown: {result['secondary_signal_breakdown_path']}")
    if not result["ok"]:
        print(f"Info: {result['reason']}")
    return 0


def _write_quantstats_report(returns: list[tuple[datetime, float]], output_path: Path) -> bool:
    try:
        import pandas as pd
        import quantstats as qs
    except Exception:
        return False
    series = pd.Series(
        [value for _, value in returns],
        index=pd.DatetimeIndex([date for date, _ in returns]),
        name="paper_r_returns",
    )
    if series.empty:
        return False
    try:
        qs.reports.html(series, output=str(output_path), title="Paper Trading Performance")
        return True
    except Exception:
        return False


def _returns_by_date(trades: list[dict[str, object]]) -> list[tuple[datetime, float]]:
    returns = []
    fallback_date = datetime(2026, 1, 1)
    for index, trade in enumerate(trades):
        raw_date = str(trade.get("closed_at") or trade.get("updated_at") or trade.get("opened_at") or "")
        try:
            date = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            date = fallback_date + timedelta(days=index)
        returns.append((date, float(trade["result_r"]) / 100.0))
    return sorted(returns, key=lambda item: item[0])


def _simple_html(title: str, metrics: dict[str, object]) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title></head><body>"
        f"<h1>{html.escape(title)}</h1>"
        "<pre>"
        f"{html.escape(format_metrics(metrics))}"
        "</pre></body></html>"
    )


def _max_drawdown(values: list[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        max_dd = min(max_dd, cumulative - peak)
    return max_dd


def write_edge_breakdown_csv(path: Path, rows: object) -> Path:
    fieldnames = ["group_type", "group", "trades", "winrate", "total_r", "avg_r", "profit_factor"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    writer.writerow({field: row.get(field, "") for field in fieldnames})
    return path


def _group_metrics(trades: list[dict[str, object]]) -> dict[str, object]:
    r_values = [float(trade["result_r"]) for trade in trades]
    wins = [trade for trade in trades if str(trade.get("status")) in WIN_STATUSES or float(trade["result_r"]) > 0]
    gross_profit = sum(max(0.0, value) for value in r_values)
    gross_loss = abs(sum(min(0.0, value) for value in r_values))
    return {
        "trades": len(trades),
        "winrate": round(len(wins) / len(trades) * 100, 2) if trades else 0.0,
        "total_r": round(sum(r_values), 4),
        "avg_r": round(sum(r_values) / len(r_values), 4) if r_values else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else None,
    }


def _edge_values(trade: dict[str, object], field: str) -> list[str]:
    if field == "score_bucket":
        return [_score_bucket(_to_float(trade.get("score")))]
    if field == "warnings":
        return _tokens(trade.get("avoidance_warnings") or trade.get("warnings"))
    if field == "high_score_rejected":
        value = trade.get("high_score_rejected")
        if str(value).strip().lower() in {"1", "true", "yes", "high_score_rejected"}:
            return ["high_score_rejected"]
        if str(trade.get("final_status", "")).strip().lower() == "high_score_rejected":
            return ["high_score_rejected"]
        return []
    if field in {"penalties", "blocking_reasons"}:
        return _tokens(trade.get(field))
    value = str(trade.get(field, "") or "").strip()
    return [value] if value else []


def _secondary_values(trade: dict[str, object], field: str) -> list[str]:
    setup_type = str(trade.get("setup_type", "") or "UNKNOWN").strip() or "UNKNOWN"
    sweep = _liquidity_sweep_state(trade)
    if field == "setup_type":
        return [setup_type]
    if field == "liquidity_sweep":
        return [sweep]
    if field == "setup_type_liquidity_sweep":
        return [f"{setup_type}|{sweep}"]
    if field == "setup_type_market_structure":
        market_structure = str(trade.get("market_structure", "") or "UNKNOWN").strip() or "UNKNOWN"
        return [f"{setup_type}|{market_structure}"]
    if field == "setup_type_warnings":
        return [f"{setup_type}|{warning}" for warning in _tokens(trade.get("avoidance_warnings") or trade.get("warnings"))]
    if field == "setup_type_penalties":
        return [f"{setup_type}|{penalty}" for penalty in _tokens(trade.get("penalties"))]
    return []


def _liquidity_sweep_state(trade: dict[str, object]) -> str:
    raw = str(trade.get("liquidity_sweep", "") or "").strip().lower()
    if not raw or raw in {"none", "no", "false", "0"}:
        return "no" if raw else "none"
    return "yes"


def _score_bucket(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score < 60:
        return "<60"
    if score < 70:
        return "60-70"
    if score < 80:
        return "70-80"
    if score < 90:
        return "80-90"
    return "90+"


def _find_breakdown(rows: list[dict[str, object]], group_type: str, group: str) -> dict[str, object] | None:
    for row in rows:
        if row.get("group_type") == group_type and row.get("group") == group:
            return row
    return None


def _format_secondary_metric_line(row: dict[str, object] | None) -> str:
    if row is None:
        return "trades 0 | WR 0.0% | Total R 0.0 | AvgR 0.0 | PF -"
    profit_factor = row.get("profit_factor")
    return (
        f"trades {row.get('trades', 0)} | "
        f"WR {row.get('winrate', 0.0)}% | "
        f"Total R {row.get('total_r', 0.0)} | "
        f"AvgR {row.get('avg_r', 0.0)} | "
        f"PF {profit_factor if profit_factor is not None else 'inf'}"
    )


def _rank_by_total_r(trades: list[dict[str, object]], field: str, *, reverse: bool) -> list[dict[str, object]]:
    totals: dict[str, float] = defaultdict(float)
    counts: Counter[str] = Counter()
    for trade in trades:
        label = str(trade.get(field, "") or "UNKNOWN")
        totals[label] += float(trade["result_r"])
        counts[label] += 1
    rows = [{"label": label, "total_r": round(total, 4), "count": counts[label]} for label, total in totals.items()]
    return sorted(rows, key=lambda item: float(item["total_r"]), reverse=reverse)[:5]


def _rank_tokens(trades: list[dict[str, object]], field: str, *, reverse: bool) -> list[dict[str, object]]:
    totals: dict[str, float] = defaultdict(float)
    counts: Counter[str] = Counter()
    for trade in trades:
        for token in _tokens(trade.get(field)):
            totals[token] += float(trade["result_r"])
            counts[token] += 1
    rows = [{"label": label, "total_r": round(total, 4), "count": counts[label]} for label, total in totals.items()]
    return sorted(rows, key=lambda item: float(item["total_r"]), reverse=reverse)[:5]


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


def _format_rank(items: object) -> str:
    if not isinstance(items, list) or not items:
        return "sin datos"
    return ", ".join(f"{item.get('label')} ({item.get('total_r')}R)" for item in items[:3] if isinstance(item, dict))


def _format_edge_rows(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "- sin datos"
    lines = []
    for row in rows[:5]:
        profit_factor = row.get("profit_factor")
        pf_text = profit_factor if profit_factor is not None else "inf"
        lines.append(
            f"- {row.get('group_type')}:{row.get('group')} | "
            f"trades {row.get('trades')} | winrate {row.get('winrate')}% | "
            f"totalR {row.get('total_r')} | avgR {row.get('avg_r')} | PF {pf_text}"
        )
    return "\n".join(lines)


def _to_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
