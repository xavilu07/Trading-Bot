from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


CLOSED_STATUSES = {"tp2_hit", "tp_hit", "sl_hit", "expired", "breakeven", "closed", "win", "loss"}
RANGE_PENALTY_TOKEN = "market_structure_range_penalty"

SUMMARY_FIELDS = [
    "generated_at",
    "context",
    "context_value",
    "range_penalty_trades",
    "no_range_penalty_trades",
    "range_penalty_winrate",
    "no_range_penalty_winrate",
    "range_penalty_total_r",
    "no_range_penalty_total_r",
    "range_penalty_avg_r",
    "no_range_penalty_avg_r",
    "range_penalty_profit_factor",
    "no_range_penalty_profit_factor",
    "delta_avg_r_penalty_vs_no_penalty",
    "delta_total_r_penalty_vs_no_penalty",
    "sample_confidence",
    "shadow_interpretation",
    "recommended_action",
]


FOCUSED_CONTEXTS = {
    "ALL": lambda row: True,
    "SHORT": lambda row: _norm_lower(row.get("direction")) == "short",
    "HIGH_VOLATILITY": lambda row: _norm_upper(row.get("market_regime")) == "HIGH_VOLATILITY",
    "CHOPPY_RANGE": lambda row: _norm_upper(row.get("entry_context")) == "CHOPPY_RANGE",
    "SHORT+HIGH_VOLATILITY": lambda row: _norm_lower(row.get("direction")) == "short"
    and _norm_upper(row.get("market_regime")) == "HIGH_VOLATILITY",
    "SHORT+CHOPPY_RANGE": lambda row: _norm_lower(row.get("direction")) == "short"
    and _norm_upper(row.get("entry_context")) == "CHOPPY_RANGE",
    "SHORT+HIGH_VOLATILITY+CHOPPY_RANGE": lambda row: _norm_lower(row.get("direction")) == "short"
    and _norm_upper(row.get("market_regime")) == "HIGH_VOLATILITY"
    and _norm_upper(row.get("entry_context")) == "CHOPPY_RANGE",
}


def load_research_rows(data_path: Path, reports_path: Path | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(_load_trade_csvs(data_path))
    if reports_path is not None:
        rows.extend(_load_meta_dataset(reports_path / "meta_dataset.csv"))
    return rows


def analyze_range_penalty_shadow(rows: list[dict[str, Any]], *, min_trades: int = 5) -> dict[str, Any]:
    normalized = [_normalize_row(row) for row in rows]
    normalized = [row for row in normalized if row is not None]
    summary_rows = _build_summary_rows(normalized, min_trades=min_trades)
    range_rows = [row for row in normalized if row["has_range_penalty"]]
    no_range_rows = [row for row in normalized if not row["has_range_penalty"]]
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "rows_analyzed": len(normalized),
        "range_penalty_rows": len(range_rows),
        "no_range_penalty_rows": len(no_range_rows),
        "range_penalty_metrics": _metrics(range_rows),
        "no_range_penalty_metrics": _metrics(no_range_rows),
        "summary_rows": summary_rows,
        "top_edge_destroyed_candidates": [
            row for row in summary_rows if row["shadow_interpretation"] == "RANGE_PENALTY_MAY_DESTROY_EDGE"
        ][:10],
        "top_protective_candidates": [
            row for row in summary_rows if row["shadow_interpretation"] == "RANGE_PENALTY_LOOKS_PROTECTIVE"
        ][:10],
    }


def write_range_penalty_reports(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    csv_path = reports_path / "range_penalty_shadow.csv"
    json_path = reports_path / "range_penalty_shadow.json"
    _write_csv(csv_path, result.get("summary_rows", []), result.get("generated_at"))
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return {"csv_path": csv_path, "json_path": json_path}


def format_range_penalty_shadow(result: dict[str, Any]) -> str:
    destroyed = result.get("top_edge_destroyed_candidates", [])
    protective = result.get("top_protective_candidates", [])
    range_metrics = result.get("range_penalty_metrics", {})
    no_range_metrics = result.get("no_range_penalty_metrics", {})
    return (
        "🧪 Range Penalty Shadow Research\n"
        f"- Rows analyzed: {result.get('rows_analyzed', 0)}\n"
        f"- With range penalty: {result.get('range_penalty_rows', 0)} | "
        f"WR {range_metrics.get('winrate', 0)}% | Total R {range_metrics.get('total_r', 0)} | "
        f"AvgR {range_metrics.get('avg_r', 0)} | PF {_pf(range_metrics.get('profit_factor'))}\n"
        f"- Without range penalty: {result.get('no_range_penalty_rows', 0)} | "
        f"WR {no_range_metrics.get('winrate', 0)}% | Total R {no_range_metrics.get('total_r', 0)} | "
        f"AvgR {no_range_metrics.get('avg_r', 0)} | PF {_pf(no_range_metrics.get('profit_factor'))}\n\n"
        "🔥 Possible edge destroyed\n"
        f"{_format_rows(destroyed)}\n\n"
        "🛡️ Penalty looks protective\n"
        f"{_format_rows(protective)}"
    )


def _build_summary_rows(rows: list[dict[str, Any]], *, min_trades: int) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for context_name, predicate in FOCUSED_CONTEXTS.items():
        items = [row for row in rows if predicate(row)]
        if not items:
            continue
        output.append(_comparison_row(context_name, context_name, items, min_trades=min_trades))

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    dimensions = (
        "direction",
        "market_regime",
        "entry_context",
        "setup_type",
        "session",
        "trade_location",
        ("direction", "market_regime"),
        ("direction", "entry_context"),
        ("direction", "market_regime", "entry_context"),
        ("setup_type", "direction"),
    )
    for row in rows:
        for definition in dimensions:
            context = _context_name(definition)
            value = _context_value(row, definition)
            grouped[(context, value)].append(row)

    for (context, value), items in grouped.items():
        output.append(_comparison_row(context, value, items, min_trades=min_trades))
    return sorted(
        output,
        key=lambda row: (
            row["shadow_interpretation"] == "RANGE_PENALTY_MAY_DESTROY_EDGE",
            float(row["delta_avg_r_penalty_vs_no_penalty"]),
            int(row["range_penalty_trades"]),
        ),
        reverse=True,
    )


def _comparison_row(context: str, value: str, rows: list[dict[str, Any]], *, min_trades: int) -> dict[str, Any]:
    range_rows = [row for row in rows if row["has_range_penalty"]]
    no_range_rows = [row for row in rows if not row["has_range_penalty"]]
    range_metrics = _metrics(range_rows)
    no_range_metrics = _metrics(no_range_rows)
    delta_avg = round(float(range_metrics["avg_r"]) - float(no_range_metrics["avg_r"]), 4)
    delta_total = round(float(range_metrics["total_r"]) - float(no_range_metrics["total_r"]), 4)
    interpretation = _interpretation(range_metrics, no_range_metrics, min_trades=min_trades)
    return {
        "context": context,
        "context_value": value,
        "range_penalty_trades": range_metrics["trades"],
        "no_range_penalty_trades": no_range_metrics["trades"],
        "range_penalty_winrate": range_metrics["winrate"],
        "no_range_penalty_winrate": no_range_metrics["winrate"],
        "range_penalty_total_r": range_metrics["total_r"],
        "no_range_penalty_total_r": no_range_metrics["total_r"],
        "range_penalty_avg_r": range_metrics["avg_r"],
        "no_range_penalty_avg_r": no_range_metrics["avg_r"],
        "range_penalty_profit_factor": range_metrics["profit_factor"],
        "no_range_penalty_profit_factor": no_range_metrics["profit_factor"],
        "delta_avg_r_penalty_vs_no_penalty": delta_avg,
        "delta_total_r_penalty_vs_no_penalty": delta_total,
        "sample_confidence": _confidence(min(int(range_metrics["trades"]), int(no_range_metrics["trades"]))),
        "shadow_interpretation": interpretation,
        "recommended_action": _recommended_action(interpretation),
    }


def _interpretation(range_metrics: dict[str, Any], no_range_metrics: dict[str, Any], *, min_trades: int) -> str:
    range_trades = int(range_metrics["trades"])
    if range_trades < min_trades:
        return "INSUFFICIENT_RANGE_PENALTY_SAMPLE"
    pf = range_metrics["profit_factor"]
    avg_r = float(range_metrics["avg_r"])
    winrate = float(range_metrics["winrate"])
    if avg_r > 0 and (pf is None or float(pf) > 1.0) and winrate >= 50:
        return "RANGE_PENALTY_MAY_DESTROY_EDGE"
    if avg_r < 0 or (pf is not None and float(pf) < 1.0):
        return "RANGE_PENALTY_LOOKS_PROTECTIVE"
    if int(no_range_metrics["trades"]) < min_trades:
        return "INSUFFICIENT_CONTROL_SAMPLE"
    return "NEUTRAL_OR_MIXED"


def _recommended_action(interpretation: str) -> str:
    if interpretation == "RANGE_PENALTY_MAY_DESTROY_EDGE":
        return "keep_shadow_tracking_consider_relaxed_canary"
    if interpretation == "RANGE_PENALTY_LOOKS_PROTECTIVE":
        return "keep_current_penalty"
    if interpretation.startswith("INSUFFICIENT"):
        return "collect_more_samples"
    return "no_change"


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(row["result_r"]) for row in rows]
    wins = [value for value in values if value > 0]
    gross_profit = sum(max(0.0, value) for value in values)
    gross_loss = abs(sum(min(0.0, value) for value in values))
    return {
        "trades": len(values),
        "winrate": round(len(wins) / len(values) * 100, 2) if values else 0.0,
        "total_r": round(sum(values), 4),
        "avg_r": round(sum(values) / len(values), 4) if values else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else (None if gross_profit > 0 else 0.0),
    }


def _load_trade_csvs(data_path: Path) -> list[dict[str, Any]]:
    paths = []
    paper_path = data_path / "paper_trading"
    if paper_path.exists():
        paths.extend(path for path in paper_path.glob("*.csv") if path.is_file())
    live_path = data_path / "live_trading" / "trades.csv"
    if live_path.exists():
        paths.append(live_path)

    rows = []
    for path in sorted(paths):
        for row in _read_csv(path):
            status = str(row.get("status") or row.get("outcome") or "").strip().lower()
            result_r = _to_float(row.get("result_r") or row.get("r_result") or row.get("realized_r"))
            if result_r is None:
                continue
            if status and status not in CLOSED_STATUSES and not row.get("closed_at"):
                continue
            rows.append({**row, "result_r": result_r, "source": f"trade_csv:{path.name}"})
    return rows


def _load_meta_dataset(path: Path) -> list[dict[str, Any]]:
    rows = []
    for row in _read_csv(path):
        result_r = _to_float(row.get("result_r"))
        if result_r is None:
            continue
        label = str(row.get("label") or "").strip().lower()
        if label not in {"0", "1", "tp_hit", "sl_hit"}:
            continue
        rows.append({**row, "result_r": result_r, "source": "meta_dataset"})
    return rows


def _normalize_row(row: dict[str, Any]) -> dict[str, Any] | None:
    result_r = _to_float(row.get("result_r"))
    if result_r is None:
        return None
    penalties = _tokens(row.get("penalties"))
    warnings = _tokens(row.get("warnings") or row.get("avoidance_warnings"))
    failed = _tokens(row.get("conditions_failed") or row.get("failed_conditions") or row.get("blocking_reasons"))
    has_flag = _truthy(row.get("has_market_structure_range_penalty"))
    return {
        **row,
        "result_r": result_r,
        "direction": _norm_lower(row.get("direction") or "unknown"),
        "setup_type": _norm_upper(row.get("setup_type") or "UNKNOWN"),
        "market_regime": _norm_upper(row.get("market_regime") or "UNKNOWN"),
        "session": _norm_upper(row.get("session") or "UNKNOWN"),
        "entry_context": _norm_upper(row.get("entry_context") or "UNKNOWN"),
        "trade_location": str(row.get("trade_location") or "UNKNOWN").strip() or "UNKNOWN",
        "has_range_penalty": has_flag or RANGE_PENALTY_TOKEN in penalties | warnings | failed,
    }


def _context_name(definition: str | tuple[str, ...]) -> str:
    return definition if isinstance(definition, str) else "+".join(definition)


def _context_value(row: dict[str, Any], definition: str | tuple[str, ...]) -> str:
    if isinstance(definition, str):
        return str(row.get(definition) or "UNKNOWN")
    return "|".join(str(row.get(field) or "UNKNOWN") for field in definition)


def _write_csv(path: Path, rows: list[dict[str, Any]], generated_at: str | None) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in SUMMARY_FIELDS} | {"generated_at": generated_at or ""})


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except csv.Error:
        return []


def _tokens(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, list):
        return {str(item).strip().lower() for item in value if str(item).strip()}
    text = str(value).strip()
    if not text:
        return set()
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        decoded = None
    if isinstance(decoded, list):
        return {str(item).strip().lower() for item in decoded if str(item).strip()}
    return {item.strip().lower() for item in text.replace("|", ",").replace(";", ",").split(",") if item.strip()}


def _format_rows(rows: object) -> str:
    if not isinstance(rows, list) or not rows:
        return "- sin datos"
    return "\n".join(
        f"- {row.get('context')}={row.get('context_value')} | range n={row.get('range_penalty_trades')} | "
        f"WR {row.get('range_penalty_winrate')}% | TotalR {row.get('range_penalty_total_r')} | "
        f"AvgR {row.get('range_penalty_avg_r')} | PF {_pf(row.get('range_penalty_profit_factor'))}"
        for row in rows[:5]
        if isinstance(row, dict)
    )


def _confidence(sample_size: int) -> str:
    if sample_size >= 30:
        return "HIGH"
    if sample_size >= 10:
        return "MEDIUM"
    return "LOW"


def _pf(value: object) -> object:
    return "inf" if value is None else value


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _to_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _norm_upper(value: object) -> str:
    return str(value or "UNKNOWN").strip().upper()


def _norm_lower(value: object) -> str:
    return str(value or "unknown").strip().lower()
