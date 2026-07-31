from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import TradeUniverse, canonical_trades_path, load_trade_universe
from trading_signals.intelligence.historical_intelligence.discovery import discover_negative_edges, discover_positive_edges
from trading_signals.intelligence.historical_intelligence.dna import build_dna_profiles
from trading_signals.intelligence.historical_intelligence.metrics import compute_metrics, group_by_dimensions, group_metrics, summarize_statuses
from trading_signals.intelligence.historical_intelligence.recommendations import build_recommendations


REPORT_NAMES = {
    "overview": "overview",
    "symbol": "symbol_analysis",
    "session": "session_analysis",
    "score": "score_analysis",
    "setup": "setup_analysis",
    "market_regime": "market_regime_analysis",
    "trade_location": "trade_location_analysis",
    "edge_matrix": "edge_matrix",
    "negative_edges": "negative_edges",
    "positive_edges": "positive_edges",
    "recommendations": "recommendations",
    "dna_profiles": "dna_profiles",
}

DIMENSION_REPORTS = {
    "symbol": "symbol",
    "session": "session",
    "score": "score_bucket",
    "setup": "setup_type",
    "market_regime": "market_regime",
    "trade_location": "trade_location",
}

ANALYSIS_DIMENSIONS = {
    "symbol": "symbol",
    "direction": "direction",
    "setup": "setup_type",
    "strategy": "strategy",
    "session": "session",
    "hour_utc": "opened_hour_utc",
    "market_regime": "market_regime",
    "trade_location": "trade_location",
    "entry_zone": "entry_zone",
    "score": "score_bucket",
    "rr": "rr_bucket",
    "holding_time": "holding_time_bucket",
    "exit_reason": "exit_reason",
    "status": "status",
}

EDGE_MATRIX_DIMENSIONS = ("symbol", "direction", "session", "setup_type", "market_regime", "trade_location", "score_bucket")


def generate_historical_intelligence(
    *,
    data_path: Path = Path("data"),
    reports_path: Path = Path("reports") / "historical_intelligence",
) -> dict[str, Any]:
    rows = load_historical_trades(data_path)
    closed_rows = [row for row in rows if row.get("result_r") is not None]
    reports_path.mkdir(parents=True, exist_ok=True)
    overview = {
        "source": str(canonical_trades_path(data_path)),
        **compute_metrics(rows),
        "status_distribution": summarize_statuses(rows),
    }
    all_group_rows = []
    analyses: dict[str, Any] = {}
    for label, dimension in ANALYSIS_DIMENSIONS.items():
        analysis = {
            "dimension": dimension,
            "groups": group_metrics(closed_rows, dimension),
        }
        analyses[label] = analysis
        all_group_rows.extend(analysis["groups"])
    overview["dimension_summaries"] = {
        label: analysis["groups"][:20]
        for label, analysis in analyses.items()
    }

    edge_matrix_rows = group_by_dimensions(closed_rows, EDGE_MATRIX_DIMENSIONS, min_trades=20)
    positive_edges = discover_positive_edges([*all_group_rows, *edge_matrix_rows], min_trades=20)
    negative_edges = discover_negative_edges([*all_group_rows, *edge_matrix_rows], min_trades=20)
    dna_profiles = build_dna_profiles(closed_rows, min_trades=10)
    recommendations = build_recommendations(
        positive_edges=positive_edges,
        negative_edges=negative_edges,
        overview=overview,
    )

    reports: dict[str, Any] = {
        "overview": overview,
        "edge_matrix": {"dimensions": list(EDGE_MATRIX_DIMENSIONS), "groups": edge_matrix_rows},
        "positive_edges": {"edges": positive_edges},
        "negative_edges": {"edges": negative_edges},
        "recommendations": recommendations,
        "dna_profiles": dna_profiles,
    }
    for report_key, dimension_key in DIMENSION_REPORTS.items():
        reports[report_key] = analyses[report_key]

    paths = {}
    for key, report in reports.items():
        name = REPORT_NAMES[key]
        paths[name] = _write_report(reports_path, name, report)

    return {
        "reports_path": str(reports_path),
        "source": str(canonical_trades_path(data_path)),
        "overview": overview,
        "paths": {key: {kind: str(path) for kind, path in value.items()} for key, value in paths.items()},
    }


def load_historical_trades(data_path: Path) -> list[dict[str, Any]]:
    return [_enrich_row(row) for row in load_trade_universe(data_path, TradeUniverse.ACCEPTED, closed_only=False)]


def _normalize_open_or_unknown(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **row,
        "symbol": str(row.get("symbol") or "UNKNOWN").upper(),
        "direction": str(row.get("direction") or "unknown").lower(),
        "setup_type": str(row.get("setup_type") or "UNKNOWN").upper(),
        "market_regime": str(row.get("market_regime") or "UNKNOWN").upper(),
        "session": str(row.get("session") or "UNKNOWN").upper(),
        "entry_context": str(row.get("entry_context") or "UNKNOWN").upper(),
        "trade_location": str(row.get("trade_location") or "UNKNOWN"),
        "status": str(row.get("status") or "UNKNOWN").lower(),
        "result_r": _float(row.get("result_r")),
        "score": _float(row.get("score")),
        "risk_reward": _float(row.get("risk_reward_tp2") or row.get("risk_reward") or row.get("rr")),
        "opened_hour_utc": str(row.get("opened_hour_utc") or "UNKNOWN"),
        "timestamp": str(row.get("closed_at") or row.get("updated_at") or row.get("opened_at") or ""),
    }


def _enrich_row(row: dict[str, Any]) -> dict[str, Any]:
    score = _float(row.get("score"))
    rr = _float(row.get("risk_reward") or row.get("risk_reward_tp2") or row.get("rr"))
    candles_held = _float(row.get("candles_held") or row.get("bars_held"))
    row["score_bucket"] = score_bucket(score)
    row["rr_bucket"] = rr_bucket(rr)
    row["holding_time_bucket"] = holding_time_bucket(candles_held)
    row["entry_zone"] = str(row.get("entry_zone") or row.get("entry_context") or "UNKNOWN")
    row["exit_reason"] = str(row.get("exit_reason") or row.get("status") or "UNKNOWN")
    row["strategy"] = str(row.get("strategy") or row.get("strategy_id") or "liquidity_sweep_mtf_v1")
    return row


def score_bucket(score: float | None) -> str:
    if score is None:
        return "UNKNOWN"
    if score < 50:
        return "0-49"
    if score < 60:
        return "50-59"
    if score < 70:
        return "60-69"
    if score < 80:
        return "70-79"
    if score < 90:
        return "80-89"
    return "90-100"


def rr_bucket(rr: float | None) -> str:
    if rr is None:
        return "UNKNOWN"
    if rr < 1:
        return "<1"
    if rr < 1.5:
        return "1-1.49"
    if rr < 2:
        return "1.5-1.99"
    if rr < 3:
        return "2-2.99"
    return "3+"


def holding_time_bucket(value: float | None) -> str:
    if value is None:
        return "UNKNOWN"
    if value <= 3:
        return "0-3"
    if value <= 8:
        return "4-8"
    if value <= 16:
        return "9-16"
    return "17+"


def _write_report(reports_path: Path, name: str, payload: dict[str, Any]) -> dict[str, Path]:
    json_path = reports_path / f"{name}.json"
    md_path = reports_path / f"{name}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(format_markdown(name, payload), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def format_markdown(name: str, payload: dict[str, Any]) -> str:
    title = name.replace("_", " ").title()
    lines = [f"# {title}", ""]
    if "groups" in payload:
        lines.extend(_table(payload["groups"]))
    elif "edges" in payload:
        lines.extend(_table(payload["edges"]))
    elif "profiles" in payload:
        lines.extend(_table(payload["profiles"]))
    elif "recommendations" in payload:
        lines.extend(_table(payload["recommendations"]))
    else:
        for key, value in payload.items():
            lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"


def _table(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["No data."]
    columns = _columns(rows)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows[:100]:
        lines.append("| " + " | ".join(_md(row.get(column, "")) for column in columns) + " |")
    return lines


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    preferred = [
        "label",
        "dimension",
        "value",
        "closed",
        "trades",
        "winrate",
        "profit_factor",
        "total_r",
        "avg_r",
        "expectancy",
        "confidence",
        "evidence_count",
        "action",
        "expected_impact",
        "classification",
    ]
    available = {key for row in rows for key in row}
    return [key for key in preferred if key in available][:10]


def _md(value: Any) -> str:
    if isinstance(value, dict):
        value = json.dumps(value, sort_keys=True)
    return str(value).replace("|", "\\|")


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
