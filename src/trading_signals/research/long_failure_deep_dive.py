from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


MIN_GROUP_TRADES = 1


def analyze_long_failure_deep_dive(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    trades = load_canonical_closed_trades(data_path)
    long_trades = [row for row in trades if str(row.get("direction") or "").lower() == "long"]
    short_trades = [row for row in trades if str(row.get("direction") or "").lower() == "short"]
    long_metrics = _metrics(long_trades)
    return {
        "scope": "LONG_FAILURE_DEEP_DIVE",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "classification": classify_long_performance(long_metrics),
        "long_metrics": long_metrics,
        "short_metrics": _metrics(short_trades),
        "long_vs_short": {
            "long": long_metrics,
            "short": _metrics(short_trades),
        },
        "main_vs_secondary": {
            "all_trades": _group_summary(trades, "setup_type"),
            "long_only": _group_summary(long_trades, "setup_type"),
        },
        "breakdowns": {
            "symbol": _group_summary(long_trades, "symbol"),
            "session": _group_summary(long_trades, "session"),
            "market_regime": _group_summary(long_trades, "market_regime"),
            "setup_type": _group_summary(long_trades, "setup_type"),
            "score_bucket": _group_summary(long_trades, "score_bucket"),
            "related_rejection_reasons": _reason_summary(long_trades),
        },
        "longs_destroying_money": _rank_groups(long_trades, toxic=True),
        "longs_working": _rank_groups(long_trades, toxic=False),
        "interpretation": _interpret(long_metrics, short_trades, long_trades),
    }


def classify_long_performance(metrics: dict[str, Any]) -> str:
    trades = int(metrics.get("trades", 0) or 0)
    if trades < 2:
        return "NEUTRAL"
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    pf = _pf_float(metrics.get("profit_factor"))
    winrate = float(metrics.get("winrate", 0.0) or 0.0)
    if total_r < 0 and pf < 1.0:
        return "TOXIC"
    if total_r > 0 and pf > 1.2 and winrate >= 45:
        return "PROMISING"
    return "NEUTRAL"


def write_long_failure_deep_dive_report(result: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "long_failure_deep_dive.md"
    path.write_text(format_long_failure_deep_dive_markdown(result), encoding="utf-8")
    return path


def format_long_failure_deep_dive_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# LONG_FAILURE_DEEP_DIVE",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        f"Classification: {result.get('classification')}",
        "",
        "## Executive Summary",
        "",
        f"- LONG: {_metrics_inline(result.get('long_metrics', {}))}",
        f"- SHORT: {_metrics_inline(result.get('short_metrics', {}))}",
        f"- Diagnosis: {result.get('interpretation', {}).get('diagnosis', '')}",
        f"- Recommended action: {result.get('interpretation', {}).get('recommended_action', '')}",
        "",
        "## LONG vs SHORT",
        "",
        "| Direction | Trades | Wins | Losses | WR | PF | Total R | Avg R |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        _metrics_row("LONG", result.get("long_vs_short", {}).get("long", {})),
        _metrics_row("SHORT", result.get("long_vs_short", {}).get("short", {})),
        "",
        "## MAIN_SIGNAL vs SECONDARY_SIGNAL",
        "",
        "### All trades",
        "",
        *_group_table(result.get("main_vs_secondary", {}).get("all_trades", {}), "Setup"),
        "",
        "### LONG only",
        "",
        *_group_table(result.get("main_vs_secondary", {}).get("long_only", {}), "Setup"),
        "",
        "## LONG Breakdowns",
        "",
    ]
    for title, key in (
        ("By Symbol", "symbol"),
        ("By Session", "session"),
        ("By Market Regime", "market_regime"),
        ("By Setup", "setup_type"),
        ("By Score Bucket", "score_bucket"),
        ("Related Rejection / Warning / Penalty Reasons", "related_rejection_reasons"),
    ):
        lines.extend([f"### {title}", "", *_group_table(result.get("breakdowns", {}).get(key, {}), title), ""])
    lines.extend(
        [
            "## LONG Types Destroying Money",
            "",
            *_rank_table(result.get("longs_destroying_money", [])),
            "",
            "## LONG Subsets That Work",
            "",
            *_rank_table(result.get("longs_working", [])),
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _interpret(metrics: dict[str, Any], short_trades: list[dict[str, Any]], long_trades: list[dict[str, Any]]) -> dict[str, str]:
    classification = classify_long_performance(metrics)
    short_metrics = _metrics(short_trades)
    toxic = _rank_groups(long_trades, toxic=True)
    working = _rank_groups(long_trades, toxic=False)
    if classification == "TOXIC":
        diagnosis = "LONG is currently losing money on the canonical dataset."
        action = "Keep LONG constrained; inspect toxic groups before relaxing public routing."
    elif classification == "PROMISING":
        diagnosis = "LONG is profitable on the canonical dataset; failures are concentrated in specific subsets."
        action = "Do not globally disable LONG; isolate losing subsets and continue monitoring."
    else:
        diagnosis = "LONG does not show a strong global edge or toxicity with the available sample."
        action = "Continue monitoring and use subset-level filters only after more sample."
    if toxic:
        diagnosis += f" Worst subset: {toxic[0]['dimension']}={toxic[0]['value']} TotalR={toxic[0]['metrics']['total_r']}."
    if working:
        diagnosis += f" Best subset: {working[0]['dimension']}={working[0]['value']} TotalR={working[0]['metrics']['total_r']}."
    if short_metrics.get("trades", 0):
        diagnosis += f" SHORT comparison TotalR={short_metrics['total_r']} PF={short_metrics['profit_factor']}."
    return {"diagnosis": diagnosis, "recommended_action": action}


def _rank_groups(rows: list[dict[str, Any]], *, toxic: bool) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for field in ("symbol", "session", "market_regime", "setup_type", "score_bucket"):
        for value, items in _raw_groups(rows, field).items():
            metrics = _metrics(items)
            if metrics["trades"] < MIN_GROUP_TRADES:
                continue
            pf = _pf_float(metrics["profit_factor"])
            if toxic and metrics["total_r"] < 0 and pf < 1:
                ranked.append({"dimension": field, "value": value, "metrics": metrics})
            if not toxic and metrics["total_r"] > 0 and pf > 1:
                ranked.append({"dimension": field, "value": value, "metrics": metrics})
    if toxic:
        return sorted(ranked, key=lambda row: (row["metrics"]["total_r"], row["metrics"]["avg_r"]))[:15]
    return sorted(ranked, key=lambda row: (row["metrics"]["total_r"], row["metrics"]["avg_r"]), reverse=True)[:15]


def _reason_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        reasons = sorted(set(_tokens(row.get("rejection_reasons")) | _tokens(row.get("warnings")) | _tokens(row.get("avoidance_warnings")) | _tokens(row.get("penalties"))))
        if not reasons:
            groups["none"].append(row)
            continue
        for reason in reasons:
            groups[reason].append(row)
    return {key: {"metrics": _metrics(items), "classification": classify_long_performance(_metrics(items))} for key, items in sorted(groups.items())}


def _group_summary(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    return {key: {"metrics": _metrics(items), "classification": classify_long_performance(_metrics(items))} for key, items in sorted(_raw_groups(rows, field).items())}


def _raw_groups(rows: list[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = _score_bucket(row.get("score")) if field == "score_bucket" else str(row.get(field) or "UNKNOWN")
        groups[value].append(row)
    return groups


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [_float(row.get("result_r")) for row in rows]
    values = [value for value in values if value is not None]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "trades": len(values),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": round(len(wins) / len(values) * 100, 2) if values else 0.0,
        "profit_factor": _profit_factor(gross_profit, gross_loss),
        "total_r": round(sum(values), 4),
        "avg_r": round(sum(values) / len(values), 4) if values else 0.0,
    }


def _profit_factor(gross_profit: float, gross_loss: float) -> float | str:
    if gross_loss > 0:
        return round(gross_profit / gross_loss, 4)
    if gross_profit > 0:
        return "inf"
    return 0.0


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


def _tokens(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, set, tuple)):
        return {str(item).strip() for item in value if str(item).strip()}
    text = str(value).strip()
    if not text:
        return set()
    return {item.strip() for item in text.replace("|", ",").replace(";", ",").split(",") if item.strip()}


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pf_float(value: object) -> float:
    if value == "inf":
        return 999.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _metrics_inline(metrics: object) -> str:
    if not isinstance(metrics, dict):
        metrics = {}
    return (
        f"trades={metrics.get('trades', 0)}, WR={metrics.get('winrate', 0)}%, "
        f"PF={metrics.get('profit_factor', 0)}, TotalR={metrics.get('total_r', 0)}, AvgR={metrics.get('avg_r', 0)}"
    )


def _metrics_row(label: str, metrics: object) -> str:
    if not isinstance(metrics, dict):
        metrics = {}
    return (
        f"| {label} | {metrics.get('trades', 0)} | {metrics.get('wins', 0)} | {metrics.get('losses', 0)} | "
        f"{metrics.get('winrate', 0)}% | {metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} |"
    )


def _group_table(payload: object, label: str) -> list[str]:
    lines = [f"| {label} | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |", "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    if not isinstance(payload, dict) or not payload:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NEUTRAL |")
        return lines
    for key, value in payload.items():
        metrics = value.get("metrics", {}) if isinstance(value, dict) else {}
        lines.append(
            f"| {key} | {metrics.get('trades', 0)} | {metrics.get('wins', 0)} | {metrics.get('losses', 0)} | "
            f"{metrics.get('winrate', 0)}% | {metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | "
            f"{metrics.get('avg_r', 0)} | {value.get('classification', 'NEUTRAL') if isinstance(value, dict) else 'NEUTRAL'} |"
        )
    return lines


def _rank_table(rows: object) -> list[str]:
    lines = ["| Dimension | Value | Trades | WR | PF | Total R | Avg R |", "|---|---|---:|---:|---:|---:|---:|"]
    if not isinstance(rows, list) or not rows:
        lines.append("| none | none | 0 | 0 | 0 | 0 | 0 |")
        return lines
    for row in rows[:15]:
        metrics = row.get("metrics", {}) if isinstance(row, dict) else {}
        lines.append(
            f"| {row.get('dimension', '')} | {row.get('value', '')} | {metrics.get('trades', 0)} | "
            f"{metrics.get('winrate', 0)}% | {metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} |"
        )
    return lines
