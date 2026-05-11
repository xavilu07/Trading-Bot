from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


CLOSED_STATUSES = {"tp2_hit", "tp_hit", "sl_hit", "expired", "breakeven"}
WIN_STATUSES = {"tp2_hit", "tp_hit"}
GROUP_FIELDS = ("direction", "setup_type", "market_regime", "session", "entry_context", "trade_location", "public_published")


def load_dashboard_data(data_path: Path, reports_path: Path) -> dict[str, object]:
    trades = _load_closed_trades(data_path)
    return {
        "trades": trades,
        "setup_rankings": _read_csv(reports_path / "setup_rankings.csv"),
        "setup_combinations_rankings": _read_csv(reports_path / "setup_combinations_rankings.csv"),
        "edge_breakdown": _read_csv(reports_path / "edge_breakdown.csv"),
        "secondary_signal_breakdown": _read_csv(reports_path / "secondary_signal_breakdown.csv"),
        "pattern_memory_records": _read_jsonl(data_path / "pattern_memory" / "patterns.jsonl"),
    }


def build_dashboard_model(data: dict[str, object], *, min_trades: int) -> dict[str, object]:
    trades = _rows(data.get("trades"))
    setup_rankings = _rows(data.get("setup_rankings"))
    setup_combinations = _rows(data.get("setup_combinations_rankings"))
    edge_breakdown = _rows(data.get("edge_breakdown"))
    secondary_breakdown = _rows(data.get("secondary_signal_breakdown"))
    generated_rankings = _build_generated_rankings(trades, min_trades=min_trades)
    ranking_rows = setup_rankings + setup_combinations + edge_breakdown + secondary_breakdown + generated_rankings
    return {
        "summary": _metrics(trades),
        "by_direction": _group_stats(trades, "direction"),
        "by_setup": _group_stats(trades, "setup_type"),
        "by_context": {field: _group_stats(trades, field) for field in ("market_regime", "session", "entry_context", "trade_location")},
        "top_total_r": _rank(ranking_rows, metric="total_r", reverse=True, min_trades=min_trades, limit=10),
        "top_avg_r": _rank(ranking_rows, metric="avg_r", reverse=True, min_trades=min_trades, limit=10),
        "worst_total_r": _rank(ranking_rows, metric="total_r", reverse=False, min_trades=min_trades, limit=10),
        "worst_avg_r": _rank(ranking_rows, metric="avg_r", reverse=False, min_trades=min_trades, limit=10),
        "secondary_analysis": _secondary_analysis(trades, secondary_breakdown, min_trades=min_trades),
        "public_vs_dev": _group_stats(trades, "public_published"),
        "adaptive_pattern_memory": _pattern_memory_summary(_rows(data.get("pattern_memory_records"))),
        "min_trades": min_trades,
    }


def generate_dashboard(data_path: Path, reports_path: Path, *, min_trades: int = 3) -> dict[str, object]:
    reports_path.mkdir(parents=True, exist_ok=True)
    data = load_dashboard_data(data_path, reports_path)
    model = build_dashboard_model(data, min_trades=min_trades)
    output_path = reports_path / "dashboard.html"
    output_path.write_text(render_dashboard_html(model), encoding="utf-8")
    return {"dashboard_path": str(output_path), "model": model}


def render_dashboard_html(model: dict[str, object]) -> str:
    summary = _dict(model.get("summary"))
    winrate_text = f"{summary.get('winrate', 0)}%"
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>Trading Bot Dashboard</title>"
        f"<style>{_css()}</style></head><body>"
        "<main>"
        "<section class='hero'><p class='eyebrow'>Local read-only analytics</p><h1>Trading Bot Dashboard</h1>"
        "<p>Resumen estático de paper/live trading, rankings y Pattern Memory. No ejecuta estrategia ni modifica datos.</p></section>"
        "<section class='grid cards'>"
        f"{_metric_card('Trades cerrados', summary.get('trades', 0))}"
        f"{_metric_card('Winrate', winrate_text)}"
        f"{_metric_card('Total R', summary.get('total_r', 0))}"
        f"{_metric_card('Avg R', summary.get('avg_r', 0))}"
        f"{_metric_card('Profit Factor', _pf(summary.get('profit_factor')))}"
        f"{_metric_card('Max DD aprox', summary.get('max_drawdown', 0))}"
        "</section>"
        f"{_section('Performance por dirección', _table(_rows(model.get('by_direction')), ['group', 'trades', 'winrate', 'total_r', 'avg_r', 'profit_factor']))}"
        f"{_section('Performance por setup', _table(_rows(model.get('by_setup')), ['group', 'trades', 'winrate', 'total_r', 'avg_r', 'profit_factor']))}"
        f"{_context_sections(_dict(model.get('by_context')))}"
        f"{_section('Mejores setups/contextos por Total R', _table(_rows(model.get('top_total_r')), ['ranking_type', 'group', 'trades', 'winrate', 'total_r', 'avg_r', 'profit_factor']))}"
        f"{_section('Mejores setups/contextos por AvgR', _table(_rows(model.get('top_avg_r')), ['ranking_type', 'group', 'trades', 'winrate', 'total_r', 'avg_r', 'profit_factor']))}"
        f"{_section('Peores fugas por Total R', _table(_rows(model.get('worst_total_r')), ['ranking_type', 'group', 'trades', 'winrate', 'total_r', 'avg_r', 'profit_factor']))}"
        f"{_section('Peores fugas por AvgR', _table(_rows(model.get('worst_avg_r')), ['ranking_type', 'group', 'trades', 'winrate', 'total_r', 'avg_r', 'profit_factor']))}"
        f"{_section('Secondary Signal Analysis', _table(_rows(model.get('secondary_analysis')), ['ranking_type', 'group', 'trades', 'winrate', 'total_r', 'avg_r', 'profit_factor']))}"
        f"{_section('Public vs DEV/Paper', _table(_rows(model.get('public_vs_dev')), ['group', 'trades', 'winrate', 'total_r', 'avg_r', 'profit_factor']))}"
        f"{_section('Adaptive / Pattern Memory', _pattern_memory_html(_dict(model.get('adaptive_pattern_memory'))))}"
        "</main></body></html>"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="generate-dashboard")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--reports-path", default="reports")
    parser.add_argument("--min-trades", type=int, default=3)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = generate_dashboard(Path(args.data_path), Path(args.reports_path), min_trades=max(1, args.min_trades))
    print(f"Dashboard: {result['dashboard_path']}")
    return 0


def _load_closed_trades(data_path: Path) -> list[dict[str, object]]:
    trades = []
    csv_paths = []
    paper_path = data_path / "paper_trading"
    if paper_path.exists():
        csv_paths.extend(path for path in paper_path.glob("*.csv") if path.is_file())
    live_path = data_path / "live_trading" / "trades.csv"
    if live_path.exists():
        csv_paths.append(live_path)
    for path in sorted(csv_paths):
        for row in _read_csv(path):
            status = str(row.get("status", row.get("outcome", ""))).strip().lower()
            result_r = _to_float(row.get("result_r") or row.get("r_result"))
            if status not in CLOSED_STATUSES or result_r is None:
                continue
            item = dict(row)
            item["status"] = status
            item["result_r"] = result_r
            item["source_csv"] = str(path)
            trades.append(item)
    return trades


def _read_csv(path: Path) -> list[dict[str, object]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except csv.Error:
        return []


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            records.append(item)
    return records


def _metrics(trades: list[dict[str, object]]) -> dict[str, object]:
    r_values = [_to_float(trade.get("result_r")) or 0.0 for trade in trades]
    wins = [trade for trade in trades if _is_win(trade)]
    gross_profit = sum(max(0.0, value) for value in r_values)
    gross_loss = abs(sum(min(0.0, value) for value in r_values))
    return {
        "trades": len(trades),
        "winrate": round(len(wins) / len(trades) * 100, 2) if trades else 0.0,
        "total_r": round(sum(r_values), 4),
        "avg_r": round(sum(r_values) / len(r_values), 4) if r_values else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else (round(gross_profit, 4) if gross_profit else 0.0),
        "max_drawdown": round(_max_drawdown(r_values), 4),
    }


def _group_stats(trades: list[dict[str, object]], field: str) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for trade in trades:
        groups[_group_value(trade, field)].append(trade)
    return sorted(({"ranking_type": field, "group": group, **_metrics(items)} for group, items in groups.items()), key=lambda row: float(row["total_r"]), reverse=True)


def _build_generated_rankings(trades: list[dict[str, object]], *, min_trades: int) -> list[dict[str, object]]:
    rows = []
    for field in GROUP_FIELDS:
        rows.extend(row for row in _group_stats(trades, field) if int(row.get("trades", 0)) >= min_trades)
    return rows


def _secondary_analysis(trades: list[dict[str, object]], report_rows: list[dict[str, object]], *, min_trades: int) -> list[dict[str, object]]:
    rows = [dict(row, ranking_type=row.get("group_type", row.get("ranking_type", "secondary"))) for row in report_rows]
    secondary = [trade for trade in trades if str(trade.get("setup_type", "")).upper() == "SECONDARY_SIGNAL"]
    for field in ("liquidity_sweep", "direction", "market_regime", "session", "entry_context", "trade_location"):
        for row in _group_stats(secondary, field):
            if int(row.get("trades", 0)) >= min_trades:
                row["ranking_type"] = f"SECONDARY_SIGNAL+{field}"
                rows.append(row)
    return rows


def _pattern_memory_summary(records: list[dict[str, object]]) -> dict[str, object]:
    if not records:
        return {"status": "datos insuficientes", "records": 0}
    outcomes = Counter(str(record.get("outcome") or "unknown") for record in records)
    r_values = [_to_float(record.get("r_result")) for record in records if _to_float(record.get("r_result")) is not None]
    return {
        "status": "ok" if len(records) >= 5 else "datos insuficientes",
        "records": len(records),
        "wins": outcomes.get("win", 0),
        "losses": outcomes.get("loss", 0),
        "avg_r": round(sum(r_values) / len(r_values), 4) if r_values else 0.0,
    }


def _rank(rows: list[dict[str, object]], *, metric: str, reverse: bool, min_trades: int, limit: int) -> list[dict[str, object]]:
    valid = [row for row in rows if int(_to_float(row.get("trades")) or 0) >= min_trades and _to_float(row.get(metric)) is not None]
    return sorted(valid, key=lambda row: float(row.get(metric, 0.0)), reverse=reverse)[:limit]


def _is_win(trade: dict[str, object]) -> bool:
    return str(trade.get("status", "")).lower() in WIN_STATUSES or (_to_float(trade.get("result_r")) or 0.0) > 0


def _max_drawdown(values: list[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    drawdown = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        drawdown = min(drawdown, cumulative - peak)
    return drawdown


def _group_value(trade: dict[str, object], field: str) -> str:
    if field == "public_published":
        raw = str(trade.get(field, "") or "").strip().lower()
        return "true" if raw == "true" else "false" if raw == "false" else "unknown"
    value = str(trade.get(field, "") or "").strip()
    return value if value else "UNKNOWN"


def _section(title: str, content: str) -> str:
    return f"<section class='panel'><h2>{html.escape(title)}</h2>{content}</section>"


def _context_sections(context: dict[str, object]) -> str:
    parts = []
    for title, key in (
        ("Contexto: market_regime", "market_regime"),
        ("Contexto: session", "session"),
        ("Contexto: entry_context", "entry_context"),
        ("Contexto: trade_location", "trade_location"),
    ):
        parts.append(_section(title, _table(_rows(context.get(key)), ["group", "trades", "winrate", "total_r", "avg_r", "profit_factor"])))
    return "".join(parts)


def _table(rows: list[dict[str, object]], columns: list[str]) -> str:
    if not rows:
        return "<p class='muted'>Datos insuficientes.</p>"
    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{html.escape(str(_display(row.get(column))))}</td>" for column in columns) + "</tr>")
    return f"<div class='table-wrap'><table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"


def _metric_card(label: str, value: object) -> str:
    return f"<article class='card'><span>{html.escape(label)}</span><strong>{html.escape(str(value))}</strong></article>"


def _pattern_memory_html(summary: dict[str, object]) -> str:
    if summary.get("status") != "ok":
        return "<p class='muted'>datos insuficientes</p>"
    return _table([summary], ["records", "wins", "losses", "avg_r"])


def _css() -> str:
    return """
    :root{--bg:#f4efe6;--ink:#1d211c;--muted:#687064;--panel:#fffaf0;--line:#ded4c2;--accent:#bd5a33;--good:#1e6b4f;--bad:#9c2f2f}
    body{margin:0;background:linear-gradient(135deg,#f8f1df,#e8efe4);color:var(--ink);font-family:Georgia,'Times New Roman',serif}
    main{max-width:1180px;margin:0 auto;padding:36px 18px 64px}
    .hero{padding:34px;border:1px solid var(--line);background:rgba(255,250,240,.78);border-radius:24px;margin-bottom:18px}
    .hero h1{font-size:44px;line-height:1;margin:6px 0 12px}.eyebrow{color:var(--accent);text-transform:uppercase;letter-spacing:.14em;font-size:12px}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}.cards{margin-bottom:18px}
    .card,.panel{background:var(--panel);border:1px solid var(--line);border-radius:18px;box-shadow:0 12px 30px rgba(60,42,20,.08)}
    .card{padding:18px}.card span{display:block;color:var(--muted);font-size:13px}.card strong{font-size:28px}
    .panel{padding:20px;margin:16px 0}.panel h2{margin:0 0 14px;font-size:24px}
    .table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}th{color:var(--accent);font-size:12px;text-transform:uppercase;letter-spacing:.08em}
    .muted{color:var(--muted)}
    """


def _display(value: object) -> object:
    return "inf" if value is None else value


def _pf(value: object) -> object:
    return "inf" if value is None else value


def _to_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _rows(value: object) -> list[dict[str, object]]:
    if isinstance(value, dict):
        return [dict(row, group=group) for group, row in value.items() if isinstance(row, dict)]
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
