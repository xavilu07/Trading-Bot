from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.application.use_cases.relaxation_shadow_v1 import RelaxationShadowV1Store
from trading_signals.data.canonical_trade_source import compute_trade_metrics


CLASSIFICATIONS = {"SAFE_TO_RELAX", "NEED_MORE_DATA", "TOXIC_TO_RELAX"}


def build_relaxation_shadow_v2_intelligence(
    *,
    data_path: Path = Path("data"),
    min_trades: int = 5,
) -> dict[str, Any]:
    trades = RelaxationShadowV1Store(data_path).list_trades()
    closed = [_normalize_trade(trade) for trade in trades if _is_closed(trade)]
    closed = [trade for trade in closed if trade is not None]
    analyses = {
        "performance_by_relaxed_filter": _analyze_token_group(closed, "relaxed_filters", min_trades=min_trades),
        "filter_combinations": _analyze_filter_combinations(closed, min_trades=min_trades),
        "performance_by_session": _analyze_field_group(closed, "session", min_trades=min_trades),
        "performance_by_market_regime": _analyze_field_group(closed, "market_regime", min_trades=min_trades),
        "performance_by_setup_type": _analyze_field_group(closed, "setup_type", min_trades=min_trades),
        "performance_by_score_bucket": _analyze_score_buckets(closed, min_trades=min_trades),
        "performance_by_direction": _analyze_field_group(closed, "direction", min_trades=min_trades),
        "performance_by_symbol": _analyze_field_group(closed, "symbol", min_trades=min_trades),
    }
    recommendations = _recommendations(analyses)
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset": "data/shadow_relaxation/trades.csv",
        "records_analyzed": len(trades),
        "closed_trades": len(closed),
        "open_trades": len([trade for trade in trades if str(trade.get("status")) in {"open", "tp1_hit"}]),
        "min_trades": min_trades,
        "overall_metrics": compute_trade_metrics(closed),
        "analyses": analyses,
        "recommendations": recommendations,
    }


def write_relaxation_shadow_v2_reports(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "relaxation_shadow_v2_intelligence.json"
    md_path = reports_path / "relaxation_shadow_v2_intelligence.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    md_path.write_text(format_relaxation_shadow_v2_markdown(result), encoding="utf-8")
    return {"json_path": json_path, "markdown_path": md_path}


def format_relaxation_shadow_v2_markdown(result: dict[str, Any]) -> str:
    metrics = result.get("overall_metrics", {})
    lines = [
        "# RELAXATION_SHADOW_V2 Intelligence",
        "",
        f"- Generated at: {result.get('generated_at')}",
        f"- Dataset: `{result.get('dataset')}`",
        f"- Records analyzed: {result.get('records_analyzed', 0)}",
        f"- Closed trades: {result.get('closed_trades', 0)}",
        f"- Open trades: {result.get('open_trades', 0)}",
        f"- Total R: {metrics.get('total_r', 0)}",
        f"- Winrate: {metrics.get('winrate', 0)}%",
        f"- Profit Factor: {metrics.get('profit_factor', 0)}",
        "",
        "## Recommendations",
        "",
    ]
    recommendations = result.get("recommendations", {})
    if isinstance(recommendations, dict):
        for label, items in (
            ("SAFE_TO_RELAX", recommendations.get("safe_to_relax", [])),
            ("NEED_MORE_DATA", recommendations.get("need_more_data", [])),
            ("TOXIC_TO_RELAX", recommendations.get("toxic_to_relax", [])),
        ):
            lines.append(f"### {label}")
            if isinstance(items, list) and items:
                for item in items[:10]:
                    if not isinstance(item, dict):
                        continue
                    lines.append(
                        f"- {item.get('dimension')}={item.get('value')} | "
                        f"n={item.get('closed_trades')} | R={item.get('total_r')} | "
                        f"WR={item.get('winrate')}% | PF={item.get('profit_factor')}"
                    )
            else:
                lines.append("- none")
            lines.append("")

    analyses = result.get("analyses", {})
    if isinstance(analyses, dict):
        for title, key in (
            ("Performance by relaxed filter", "performance_by_relaxed_filter"),
            ("Filter combinations", "filter_combinations"),
            ("Performance by session", "performance_by_session"),
            ("Performance by market regime", "performance_by_market_regime"),
            ("Performance by setup type", "performance_by_setup_type"),
            ("Performance by score bucket", "performance_by_score_bucket"),
            ("Performance by direction", "performance_by_direction"),
            ("Performance by symbol", "performance_by_symbol"),
        ):
            lines.extend([f"## {title}", "", "| Value | Class | n | Total R | WR | AvgR | PF |", "|---|---|---:|---:|---:|---:|---:|"])
            rows = analyses.get(key, [])
            if isinstance(rows, list) and rows:
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    lines.append(
                        f"| {row.get('value')} | {row.get('classification')} | {row.get('closed_trades')} | "
                        f"{row.get('total_r')} | {row.get('winrate')}% | {row.get('avg_r')} | {row.get('profit_factor')} |"
                    )
            else:
                lines.append("| none | NEED_MORE_DATA | 0 | 0 | 0% | 0 | 0 |")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _analyze_field_group(trades: list[dict[str, Any]], field: str, *, min_trades: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        grouped[str(trade.get(field) or "UNKNOWN")].append(trade)
    return _ranked_rows(grouped, dimension=field, min_trades=min_trades)


def _analyze_token_group(trades: list[dict[str, Any]], field: str, *, min_trades: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        for token in _tokens(trade.get(field)):
            grouped[token].append(trade)
    return _ranked_rows(grouped, dimension=field, min_trades=min_trades)


def _analyze_filter_combinations(trades: list[dict[str, Any]], *, min_trades: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        combo = "+".join(sorted(_tokens(trade.get("relaxed_filters")))) or "none"
        grouped[combo].append(trade)
    return _ranked_rows(grouped, dimension="filter_combination", min_trades=min_trades)


def _analyze_score_buckets(trades: list[dict[str, Any]], *, min_trades: int) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        grouped[_score_bucket(trade.get("score"))].append(trade)
    return _ranked_rows(grouped, dimension="score_bucket", min_trades=min_trades)


def _ranked_rows(grouped: dict[str, list[dict[str, Any]]], *, dimension: str, min_trades: int) -> list[dict[str, Any]]:
    rows = []
    for value, items in grouped.items():
        metrics = compute_trade_metrics(items)
        rows.append(
            {
                "dimension": dimension,
                "value": value,
                "classification": _classify(metrics, min_trades=min_trades),
                "closed_trades": metrics["closed_trades"],
                "wins": metrics["wins"],
                "losses": metrics["losses"],
                "winrate": metrics["winrate"],
                "total_r": metrics["total_r"],
                "avg_r": metrics["avg_r"],
                "profit_factor": metrics["profit_factor"],
                "max_drawdown": metrics["max_drawdown"],
                "current_drawdown": metrics["current_drawdown"],
            }
        )
    return sorted(rows, key=lambda row: (_classification_rank(row["classification"]), -float(row["total_r"]), -int(row["closed_trades"])))


def _recommendations(analyses: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    rows = [row for group in analyses.values() for row in group]
    return {
        "safe_to_relax": _top(rows, "SAFE_TO_RELAX"),
        "need_more_data": _top(rows, "NEED_MORE_DATA"),
        "toxic_to_relax": _top(rows, "TOXIC_TO_RELAX"),
    }


def _top(rows: list[dict[str, Any]], classification: str) -> list[dict[str, Any]]:
    matching = [row for row in rows if row.get("classification") == classification]
    if classification == "TOXIC_TO_RELAX":
        return sorted(matching, key=lambda row: (float(row.get("total_r") or 0.0), float(row.get("avg_r") or 0.0)))[:10]
    return sorted(matching, key=lambda row: (-float(row.get("total_r") or 0.0), -float(row.get("profit_factor") or 0.0)))[:10]


def _classify(metrics: dict[str, Any], *, min_trades: int) -> str:
    sample = int(metrics.get("closed_trades") or 0)
    total_r = float(metrics.get("total_r") or 0.0)
    avg_r = float(metrics.get("avg_r") or 0.0)
    winrate = float(metrics.get("winrate") or 0.0)
    profit_factor = float(metrics.get("profit_factor") or 0.0)
    if sample < min_trades:
        return "NEED_MORE_DATA"
    if total_r > 0 and avg_r > 0 and profit_factor >= 1.2 and winrate >= 45:
        return "SAFE_TO_RELAX"
    if total_r < 0 and avg_r < 0 and (profit_factor < 1.0 or winrate < 40):
        return "TOXIC_TO_RELAX"
    return "NEED_MORE_DATA"


def _normalize_trade(trade: dict[str, Any]) -> dict[str, Any] | None:
    try:
        result_r = float(trade.get("result_r") or 0.0)
    except (TypeError, ValueError):
        return None
    return {
        **trade,
        "result_r": result_r,
        "status": str(trade.get("status") or "").lower(),
        "symbol": str(trade.get("symbol") or "UNKNOWN").upper(),
        "direction": str(trade.get("direction") or "unknown").lower(),
        "setup_type": str(trade.get("setup_type") or "UNKNOWN").upper(),
        "session": str(trade.get("session") or "UNKNOWN").upper(),
        "market_regime": str(trade.get("market_regime") or "UNKNOWN").upper(),
        "entry_context": str(trade.get("entry_context") or "UNKNOWN").upper(),
        "score": _float(trade.get("score")),
    }


def _is_closed(trade: dict[str, Any]) -> bool:
    return str(trade.get("status") or "").lower() in {"tp2_hit", "tp_hit", "sl_hit", "expired", "closed", "win", "loss"}


def _tokens(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return _dedupe(str(item).strip() for item in value if str(item).strip())
    text = str(value).strip()
    if not text:
        return []
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        decoded = None
    if isinstance(decoded, list):
        return _dedupe(str(item).strip() for item in decoded if str(item).strip())
    return _dedupe(item.strip() for item in text.replace("|", ",").replace(";", ",").split(",") if item.strip())


def _score_bucket(value: object) -> str:
    score = _float(value)
    if score is None:
        return "UNKNOWN"
    if score < 60:
        return "<60"
    if score < 70:
        return "60-69"
    if score < 80:
        return "70-79"
    if score < 90:
        return "80-89"
    return "90+"


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dedupe(values: object) -> list[str]:
    output: list[str] = []
    for value in values if not isinstance(values, str) else [values]:
        text = str(value).strip()
        if text and text not in output:
            output.append(text)
    return output


def _classification_rank(classification: str) -> int:
    return {"SAFE_TO_RELAX": 0, "NEED_MORE_DATA": 1, "TOXIC_TO_RELAX": 2}.get(classification, 3)
