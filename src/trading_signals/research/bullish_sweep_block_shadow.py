from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


CSV_FIELDS = (
    "source",
    "symbol",
    "direction",
    "setup_type",
    "score",
    "market_regime",
    "session",
    "entry_context",
    "reasons",
    "warnings",
    "penalties",
    "opened_at",
    "closed_at",
    "outcome",
    "result_r",
)


def generate_bullish_sweep_block_shadow(
    *,
    data_path: Path,
    reports_path: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    result = analyze_bullish_sweep_block_shadow(data_path=data_path, now=now)
    shadow_csv = write_bullish_sweep_block_rows(result["records"], data_path)
    report_path = write_bullish_sweep_block_shadow_report(result, reports_path)
    return {**result, "shadow_csv_path": str(shadow_csv), "report_path": str(report_path)}


def analyze_bullish_sweep_block_shadow(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    canonical_trades = load_canonical_closed_trades(data_path)
    current_metrics = _metrics(canonical_trades)
    bullish_sweep_trades = [row for row in canonical_trades if _liquidity_context(row) == "sweep:bullish_sweep"]
    without_bullish_sweep = [row for row in canonical_trades if _liquidity_context(row) != "sweep:bullish_sweep"]
    records = [
        *[_record_from_trade(row) for row in bullish_sweep_trades],
        *[_record_from_signal(row) for row in _load_signal_candidates(data_path / "bot_activity" / "signals_log.jsonl")],
    ]
    closed_records = [row for row in records if _float(row.get("result_r")) is not None]
    blocked_metrics = _metrics(closed_records)
    without_metrics = _metrics(without_bullish_sweep)
    return {
        "scope": "BULLISH_SWEEP_BLOCK_SHADOW",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "records": records,
        "records_total": len(records),
        "closed_records": len(closed_records),
        "current_global": current_metrics,
        "without_bullish_sweep": without_metrics,
        "blocked_bullish_sweep": blocked_metrics,
        "r_avoided": _round(-float(blocked_metrics.get("total_r", 0.0) or 0.0)),
        "pf_avoided": blocked_metrics.get("profit_factor", 0.0),
        "periods": {
            "last_7d": _period_summary(records, now_dt - timedelta(days=7)),
            "last_30d": _period_summary(records, now_dt - timedelta(days=30)),
            "full": _record_summary(records),
        },
        "comparison": _comparison(current_metrics, without_metrics),
        "classification": classify_block_shadow(current_metrics, without_metrics, blocked_metrics),
        "by_symbol": _group_summary(records, "symbol"),
        "by_session": _group_summary(records, "session"),
        "by_market_regime": _group_summary(records, "market_regime"),
        "by_score_bucket": _group_summary(records, "score_bucket"),
    }


def classify_block_shadow(current: dict[str, Any], without: dict[str, Any], blocked: dict[str, Any]) -> str:
    blocked_trades = int(blocked.get("trades", 0) or 0)
    if blocked_trades < 5:
        return "WATCH"
    total_r_delta = float(without.get("total_r", 0.0) or 0.0) - float(current.get("total_r", 0.0) or 0.0)
    pf_delta = _pf_float(without.get("profit_factor")) - _pf_float(current.get("profit_factor"))
    blocked_total_r = float(blocked.get("total_r", 0.0) or 0.0)
    if total_r_delta > 0 and pf_delta > 0 and blocked_total_r < 0:
        return "SHOULD_BLOCK"
    if total_r_delta < 0 and blocked_total_r > 0:
        return "DO_NOT_BLOCK"
    return "WATCH"


def write_bullish_sweep_block_rows(records: list[dict[str, Any]], data_path: Path) -> Path:
    path = data_path / "shadow_blocks" / "bullish_sweep_block.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in records:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})
    return path


def write_bullish_sweep_block_shadow_report(result: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    content = format_bullish_sweep_block_shadow_markdown(result)
    path = reports_path / "bullish_sweep_block_report.md"
    path.write_text(content, encoding="utf-8")
    legacy_path = reports_path / "bullish_sweep_block_shadow.md"
    legacy_path.write_text(content, encoding="utf-8")
    return path


def format_bullish_sweep_block_shadow_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# BULLISH_SWEEP_BLOCK_SHADOW",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        f"Classification: {result.get('classification')}",
        "",
        "## Summary",
        "",
        f"- Trades/candidates that would have been blocked: {result.get('records_total', 0)}",
        f"- Closed/evaluable blocked records: {result.get('closed_records', 0)}",
        f"- R avoided: {result.get('r_avoided', 0)}",
        f"- PF avoided: {result.get('pf_avoided', 0)}",
        "",
        "## Current vs Without Bullish Sweep",
        "",
        "| Scenario | Trades | Wins | Losses | WR | PF | Total R | Avg R |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        _metrics_row("Current global", result.get("current_global", {})),
        _metrics_row("Without bullish_sweep", result.get("without_bullish_sweep", {})),
        _metrics_row("Blocked bullish_sweep only", result.get("blocked_bullish_sweep", {})),
        "",
        "## Delta",
        "",
        f"- PF delta: {result.get('comparison', {}).get('pf_delta', 0)}",
        f"- Total R delta: {result.get('comparison', {}).get('total_r_delta', 0)}",
        f"- Winrate delta: {result.get('comparison', {}).get('winrate_delta', 0)}",
        "",
        "## Periods",
        "",
        "| Period | Records | Closed | WR | PF | Total R | Avg R | R avoided |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in ("last_7d", "last_30d", "full"):
        lines.append(_period_row(name, result.get("periods", {}).get(name, {})))
    lines.extend(["", "## By Symbol", "", *_group_table(result.get("by_symbol", {}), "Symbol"), ""])
    lines.extend(["## By Session", "", *_group_table(result.get("by_session", {}), "Session"), ""])
    lines.extend(["## By Market Regime", "", *_group_table(result.get("by_market_regime", {}), "Market regime"), ""])
    lines.extend(["## By Score Bucket", "", *_group_table(result.get("by_score_bucket", {}), "Score bucket"), ""])
    return "\n".join(lines).rstrip() + "\n"


def _load_signal_candidates(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and _liquidity_context(item) == "sweep:bullish_sweep":
            rows.append(item)
    return rows


def _record_from_trade(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "canonical_trade",
        "symbol": str(row.get("symbol") or "UNKNOWN").upper(),
        "direction": str(row.get("direction") or "unknown").lower(),
        "setup_type": str(row.get("setup_type") or "UNKNOWN").upper(),
        "score": _value(row.get("score")),
        "market_regime": str(row.get("market_regime") or "UNKNOWN").upper(),
        "session": str(row.get("session") or "UNKNOWN").upper(),
        "entry_context": str(row.get("entry_context") or "UNKNOWN").upper(),
        "reasons": _join(row.get("rejection_reasons")),
        "warnings": _join(row.get("warnings") or row.get("avoidance_warnings")),
        "penalties": _join(row.get("penalties")),
        "opened_at": str(row.get("opened_at") or row.get("created_at") or row.get("timestamp") or ""),
        "closed_at": str(row.get("closed_at") or row.get("timestamp") or ""),
        "outcome": str(row.get("status") or row.get("outcome") or ""),
        "result_r": _value(row.get("result_r")),
    }


def _record_from_signal(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "signals_log",
        "symbol": str(row.get("symbol") or "UNKNOWN").upper(),
        "direction": str(row.get("direction") or "unknown").lower(),
        "setup_type": str(row.get("setup_type") or "UNKNOWN").upper(),
        "score": _value(row.get("score") or row.get("setup_score")),
        "market_regime": str(row.get("market_regime") or "UNKNOWN").upper(),
        "session": str(row.get("session") or "UNKNOWN").upper(),
        "entry_context": str(row.get("entry_context") or "UNKNOWN").upper(),
        "reasons": _join(row.get("rejection_reasons") or row.get("conditions_failed") or row.get("reasons")),
        "warnings": _join(row.get("warnings") or row.get("avoidance_warnings")),
        "penalties": _join(row.get("penalties")),
        "opened_at": str(row.get("opened_at") or row.get("timestamp") or row.get("created_at") or ""),
        "closed_at": str(row.get("closed_at") or ""),
        "outcome": str(row.get("status") or row.get("outcome") or ""),
        "result_r": _value(row.get("result_r") or row.get("r_result")),
    }


def _period_summary(records: list[dict[str, Any]], start: datetime) -> dict[str, Any]:
    return _record_summary([row for row in records if (ts := _timestamp(row)) is not None and ts >= start])


def _record_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [row for row in records if _float(row.get("result_r")) is not None]
    metrics = _metrics(closed)
    return {"records": len(records), "closed": len(closed), "metrics": metrics, "r_avoided": _round(-float(metrics.get("total_r", 0.0) or 0.0))}


def _group_summary(records: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        key = _score_bucket(row.get("score")) if field == "score_bucket" else str(row.get(field) or "UNKNOWN")
        groups[key].append(row)
    return {key: _record_summary(items) for key, items in sorted(groups.items())}


def _comparison(current: dict[str, Any], without: dict[str, Any]) -> dict[str, float]:
    return {
        "pf_delta": _round(_pf_float(without.get("profit_factor")) - _pf_float(current.get("profit_factor"))),
        "total_r_delta": _round(float(without.get("total_r", 0.0) or 0.0) - float(current.get("total_r", 0.0) or 0.0)),
        "winrate_delta": _round(float(without.get("winrate", 0.0) or 0.0) - float(current.get("winrate", 0.0) or 0.0)),
    }


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
        "winrate": _round(len(wins) / len(values) * 100) if values else 0.0,
        "profit_factor": _profit_factor(gross_profit, gross_loss),
        "total_r": _round(sum(values)),
        "avg_r": _round(sum(values) / len(values)) if values else 0.0,
    }


def _liquidity_context(row: dict[str, Any]) -> str:
    explicit = str(row.get("liquidity_context") or "").strip()
    if explicit:
        return explicit
    sweep = str(row.get("liquidity_sweep") or "").strip()
    if sweep:
        return f"sweep:{sweep}"
    return "UNKNOWN"


def _timestamp(row: dict[str, Any]) -> datetime | None:
    value = row.get("closed_at") or row.get("opened_at")
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _profit_factor(gross_profit: float, gross_loss: float) -> float | str:
    if gross_loss > 0:
        return _round(gross_profit / gross_loss)
    if gross_profit > 0:
        return "inf"
    return 0.0


def _pf_float(value: object) -> float:
    if value == "inf":
        return 999.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _value(value: object) -> object:
    parsed = _float(value)
    return parsed if parsed is not None else str(value or "")


def _join(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(item) for item in value if str(item))
    return str(value)


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


def _round(value: float) -> float:
    rounded = round(value, 4)
    return 0.0 if rounded == 0 else rounded


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _metrics_row(label: str, metrics: object) -> str:
    if not isinstance(metrics, dict):
        metrics = {}
    return (
        f"| {label} | {metrics.get('trades', 0)} | {metrics.get('wins', 0)} | {metrics.get('losses', 0)} | "
        f"{metrics.get('winrate', 0)}% | {metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} |"
    )


def _period_row(label: str, payload: object) -> str:
    if not isinstance(payload, dict):
        payload = {}
    metrics = payload.get("metrics", {}) if isinstance(payload.get("metrics"), dict) else {}
    return (
        f"| {label} | {payload.get('records', 0)} | {payload.get('closed', 0)} | {metrics.get('winrate', 0)}% | "
        f"{metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} | {payload.get('r_avoided', 0)} |"
    )


def _group_table(payload: object, label: str) -> list[str]:
    lines = [f"| {label} | Records | Closed | WR | PF | Total R | Avg R | R avoided |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    if not isinstance(payload, dict) or not payload:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 |")
        return lines
    for key, value in payload.items():
        metrics = value.get("metrics", {}) if isinstance(value, dict) else {}
        lines.append(
            f"| {key} | {value.get('records', 0)} | {value.get('closed', 0)} | {metrics.get('winrate', 0)}% | "
            f"{metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} | {value.get('r_avoided', 0)} |"
        )
    return lines
