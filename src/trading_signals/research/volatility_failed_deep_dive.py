from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades
from trading_signals.research.shadow_performance_tracker import build_shadow_performance_tracker, compute_shadow_metrics


def analyze_volatility_failed_deep_dive(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    tracker = build_shadow_performance_tracker(data_path=data_path, now=now)
    records = [row for row in tracker.get("records", []) if "volatility_failed" in _tokens(row.get("rejection_reason"))]
    canonical = load_canonical_closed_trades(data_path)
    accepted = [row for row in canonical if "volatility_failed" not in _tokens(row.get("rejection_reasons"))]
    metrics = compute_shadow_metrics(records)
    baseline_metrics = _canonical_metrics(canonical)
    accepted_metrics = _canonical_metrics(accepted)
    return {
        "scope": "VOLATILITY_FAILED_DEEP_DIVE",
        "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "count": len(records),
        "metrics": metrics,
        "classification": classify_volatility_failed(metrics, len(records)),
        "by_symbol": _group_summary(records, "symbol"),
        "by_session": _group_summary(records, "session"),
        "by_setup": _group_summary(records, "setup"),
        "by_market_regime": _group_summary(records, "market_regime"),
        "by_score_bucket": _group_summary(records, "score_bucket"),
        "accepted_trades": {"count": len(accepted), "metrics": accepted_metrics},
        "canonical_baseline": {"count": len(canonical), "metrics": baseline_metrics},
        "records": records,
    }


def classify_volatility_failed(metrics: dict[str, Any], count: int) -> str:
    closed = int(metrics.get("closed", 0) or 0)
    if count == 0 or closed < 5:
        return "NEUTRAL"
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    pf = _pf_value(metrics.get("profit_factor"))
    wr = float(metrics.get("winrate", 0.0) or 0.0)
    if total_r < 0 and pf < 1.0:
        return "PROTECTIVE"
    if total_r > 0 and pf > 1.2 and wr >= 45:
        return "HARMFUL"
    return "NEUTRAL"


def write_volatility_failed_deep_dive_report(result: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "volatility_failed_deep_dive.md"
    path.write_text(format_volatility_failed_deep_dive_markdown(result), encoding="utf-8")
    return path


def format_volatility_failed_deep_dive_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# VOLATILITY_FAILED_DEEP_DIVE",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Count: {result.get('count', 0)}",
        f"Classification: {result.get('classification')}",
        "",
        "## Volatility Failed Candidates",
        "",
        _metrics_line(result.get("metrics", {})),
        "",
        "## Compare: Accepted Trades",
        "",
        f"- Count: {result.get('accepted_trades', {}).get('count', 0)}",
        _metrics_line(result.get("accepted_trades", {}).get("metrics", {})),
        "",
        "## Compare: Canonical Baseline",
        "",
        f"- Count: {result.get('canonical_baseline', {}).get('count', 0)}",
        _metrics_line(result.get("canonical_baseline", {}).get("metrics", {})),
        "",
        "## By Symbol",
        "",
        *_table_group(result.get("by_symbol", {}), "Symbol"),
        "",
        "## By Session",
        "",
        *_table_group(result.get("by_session", {}), "Session"),
        "",
        "## By Setup",
        "",
        *_table_group(result.get("by_setup", {}), "Setup"),
        "",
        "## By Market Regime",
        "",
        *_table_group(result.get("by_market_regime", {}), "Market regime"),
        "",
        "## By Score Bucket",
        "",
        *_table_group(result.get("by_score_bucket", {}), "Score bucket"),
        "",
        "## Recent Volatility Failed Records",
        "",
        "| Opened | Symbol | Direction | Score | Setup | Regime | Outcome | R |",
        "|---|---|---|---:|---|---|---|---:|",
    ]
    for row in sorted(result.get("records", []), key=lambda item: str(item.get("opened_at") or ""), reverse=True)[:30]:
        lines.append(
            f"| {row.get('opened_at', '')} | {row.get('symbol', '')} | {row.get('direction', '')} | "
            f"{row.get('score', '')} | {row.get('setup', '')} | {row.get('market_regime', '')} | "
            f"{row.get('outcome', '')} | {row.get('result_r', '')} |"
        )
    if not result.get("records"):
        lines.append("| none |  |  |  |  |  |  |  |")
    lines.append("")
    return "\n".join(lines)


def _group_summary(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = _score_bucket(row.get("score")) if field == "score_bucket" else str(row.get(field) or "UNKNOWN")
        groups[value].append(row)
    return {key: {"count": len(items), "metrics": compute_shadow_metrics(items), "classification": classify_volatility_failed(compute_shadow_metrics(items), len(items))} for key, items in sorted(groups.items())}


def _canonical_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(row["result_r"]) for row in rows if row.get("result_r") is not None]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    if gross_loss > 0:
        pf: float | str = round(gross_profit / gross_loss, 4)
    elif gross_profit > 0:
        pf = "inf"
    else:
        pf = 0.0
    return {
        "rows": len(rows),
        "closed": len(values),
        "open_pending": len(rows) - len(values),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": round(len(wins) / len(values) * 100, 2) if values else 0.0,
        "profit_factor": pf,
        "total_r": round(sum(values), 4),
        "avg_r": round(sum(values) / len(values), 4) if values else 0.0,
    }


def _score_bucket(value: object) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
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


def _tokens(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    text = str(value).strip()
    if not text:
        return []
    return [item.strip() for item in text.replace(",", "|").split("|") if item.strip()]


def _pf_value(value: object) -> float:
    if value == "inf":
        return 999.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _metrics_line(metrics: object) -> str:
    if not isinstance(metrics, dict):
        metrics = {}
    return (
        f"- Rows: {metrics.get('rows', 0)} | Closed: {metrics.get('closed', 0)} | Open/Pending: {metrics.get('open_pending', 0)} | "
        f"WR: {metrics.get('winrate', 0)}% | PF: {metrics.get('profit_factor', 0)} | "
        f"Total R: {metrics.get('total_r', 0)} | Avg R: {metrics.get('avg_r', 0)}"
    )


def _table_group(value: object, label: str) -> list[str]:
    lines = [f"| {label} | Count | Closed | WR | PF | Total R | Classification |", "|---|---:|---:|---:|---:|---:|---|"]
    if not isinstance(value, dict) or not value:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | NEUTRAL |")
        return lines
    for key, payload in value.items():
        metrics = payload.get("metrics", {}) if isinstance(payload, dict) else {}
        lines.append(
            f"| {key} | {payload.get('count', 0)} | {metrics.get('closed', 0)} | {metrics.get('winrate', 0)}% | "
            f"{metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {payload.get('classification', 'NEUTRAL')} |"
        )
    return lines
