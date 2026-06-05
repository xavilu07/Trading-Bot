from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


CSV_FIELDS = (
    "timestamp",
    "source",
    "candidate_id",
    "dedupe_key",
    "symbol",
    "direction",
    "score",
    "setup_type",
    "market_regime",
    "session",
    "entry_context",
    "liquidity_context",
    "warnings",
    "reasons",
    "penalties",
    "outcome",
    "result_r",
)


def generate_against_htf_breakout_shadow_block(
    *,
    data_path: Path,
    reports_path: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    result = analyze_against_htf_breakout_shadow_block(data_path=data_path, now=now)
    csv_path = write_against_htf_breakout_shadow_rows(result["records"], data_path)
    report_path = write_against_htf_breakout_shadow_report(result, reports_path)
    return {**result, "shadow_csv_path": str(csv_path), "report_path": str(report_path)}


def analyze_against_htf_breakout_shadow_block(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    canonical_trades = load_canonical_closed_trades(data_path)
    trade_records = [_record_from_trade(row) for row in canonical_trades if _is_against_htf_breakout(row)]
    signal_records = [_record_from_signal(row) for row in _load_signal_candidates(data_path / "bot_activity" / "signals_log.jsonl")]
    records = _dedupe_records([*trade_records, *signal_records])
    closed_records = [row for row in records if _float(row.get("result_r")) is not None]
    blocked_metrics = _metrics(closed_records)
    return {
        "scope": "AGAINST_HTF_BREAKOUT_SHADOW_BLOCK",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "records": records,
        "records_total": len(records),
        "closed_records": len(closed_records),
        "blocked_group_metrics": blocked_metrics,
        "hypothetical_r_avoided": _round(-float(blocked_metrics.get("total_r", 0.0) or 0.0)),
        "periods": {
            "last_7d": _period_summary(records, now_dt - timedelta(days=7)),
            "last_30d": _period_summary(records, now_dt - timedelta(days=30)),
            "full": _record_summary(records),
        },
        "by_symbol": _group_summary(records, "symbol"),
        "by_session": _group_summary(records, "session"),
        "by_direction": _group_summary(records, "direction"),
        "by_score_bucket": _group_summary(records, "score_bucket"),
        "recommendation": recommend_shadow_block(blocked_metrics),
    }


def recommend_shadow_block(metrics: dict[str, Any]) -> str:
    trades = int(metrics.get("trades", 0) or 0)
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    pf = _pf_float(metrics.get("profit_factor"))
    if trades >= 20 and total_r < 0 and pf < 0.9:
        return "PROMOTE_TO_BLOCK"
    if trades >= 5 and total_r < 0 and pf < 1.0:
        return "CONTINUE_SHADOW"
    if trades >= 5 and total_r > 0 and pf >= 1.0:
        return "DO_NOT_BLOCK"
    return "CONTINUE_SHADOW"


def write_against_htf_breakout_shadow_rows(records: list[dict[str, Any]], data_path: Path) -> Path:
    path = data_path / "shadow_blocks" / "against_htf_breakout_block.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in records:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})
    return path


def write_against_htf_breakout_shadow_report(result: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "against_htf_breakout_shadow_block.md"
    path.write_text(format_against_htf_breakout_shadow_markdown(result), encoding="utf-8")
    return path


def format_against_htf_breakout_shadow_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# AGAINST_HTF_BREAKOUT_SHADOW_BLOCK",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        f"Recommendation: {result.get('recommendation')}",
        "",
        "## Summary",
        "",
        f"- Total tracked: {result.get('records_total', 0)}",
        f"- Closed/evaluable: {result.get('closed_records', 0)}",
        f"- Hypothetical R avoided: {result.get('hypothetical_r_avoided', 0)}",
        f"- PF of blocked group: {result.get('blocked_group_metrics', {}).get('profit_factor', 0)}",
        "",
        "## Blocked Group Metrics",
        "",
        "| Trades | Wins | Losses | WR | PF | Total R | Avg R |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        _metrics_row(result.get("blocked_group_metrics", {})),
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
    lines.extend(["## By Direction", "", *_group_table(result.get("by_direction", {}), "Direction"), ""])
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
        if isinstance(item, dict) and _is_against_htf_breakout(item):
            rows.append(item)
    return rows


def _record_from_trade(row: dict[str, Any]) -> dict[str, Any]:
    timestamp = str(row.get("opened_at") or row.get("created_at") or row.get("timestamp") or "")
    symbol = str(row.get("symbol") or "UNKNOWN").upper()
    direction = str(row.get("direction") or "unknown").lower()
    return {
        "timestamp": timestamp,
        "source": "canonical_trade",
        "candidate_id": str(row.get("trade_id") or row.get("signal_id") or ""),
        "dedupe_key": _dedupe_key(timestamp, symbol, direction, row),
        "symbol": symbol,
        "direction": direction,
        "score": _value(row.get("score")),
        "setup_type": str(row.get("setup_type") or "UNKNOWN").upper(),
        "market_regime": str(row.get("market_regime") or "UNKNOWN").upper(),
        "session": str(row.get("session") or "UNKNOWN").upper(),
        "entry_context": str(row.get("entry_context") or "UNKNOWN").upper(),
        "liquidity_context": _liquidity_context(row),
        "warnings": _join(row.get("warnings") or row.get("avoidance_warnings")),
        "reasons": _join(row.get("rejection_reasons") or row.get("conditions_failed")),
        "penalties": _join(row.get("penalties")),
        "outcome": str(row.get("status") or row.get("outcome") or ""),
        "result_r": _value(row.get("result_r")),
    }


def _record_from_signal(row: dict[str, Any]) -> dict[str, Any]:
    timestamp = str(row.get("timestamp") or row.get("opened_at") or row.get("created_at") or "")
    symbol = str(row.get("symbol") or "UNKNOWN").upper()
    direction = str(row.get("direction") or "unknown").lower()
    return {
        "timestamp": timestamp,
        "source": "signals_log",
        "candidate_id": str(row.get("candidate_id") or row.get("signal_id") or row.get("trade_id") or ""),
        "dedupe_key": _dedupe_key(timestamp, symbol, direction, row),
        "symbol": symbol,
        "direction": direction,
        "score": _value(row.get("score") or row.get("setup_score")),
        "setup_type": str(row.get("setup_type") or "UNKNOWN").upper(),
        "market_regime": str(row.get("market_regime") or "UNKNOWN").upper(),
        "session": str(row.get("session") or "UNKNOWN").upper(),
        "entry_context": str(row.get("entry_context") or "UNKNOWN").upper(),
        "liquidity_context": _liquidity_context(row),
        "warnings": _join(row.get("warnings") or row.get("avoidance_warnings")),
        "reasons": _join(row.get("rejection_reasons") or row.get("conditions_failed") or row.get("reasons")),
        "penalties": _join(row.get("penalties")),
        "outcome": str(row.get("status") or row.get("outcome") or ""),
        "result_r": _value(row.get("result_r") or row.get("r_result")),
    }


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result = []
    for row in records:
        key = str(row.get("dedupe_key") or "")
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def _dedupe_key(timestamp: str, symbol: str, direction: str, row: dict[str, Any]) -> str:
    candidate_id = str(row.get("candidate_id") or row.get("signal_id") or row.get("trade_id") or "").strip()
    if candidate_id:
        return candidate_id
    return "|".join(
        [
            timestamp[:16],
            symbol,
            direction,
            str(row.get("setup_type") or "UNKNOWN").upper(),
            str(row.get("entry_context") or "UNKNOWN").upper(),
        ]
    )


def _is_against_htf_breakout(row: dict[str, Any]) -> bool:
    return _entry_context(row) == "BREAKOUT" and _is_against_htf(row)


def _is_against_htf(row: dict[str, Any]) -> bool:
    return "against_htf" in _all_tokens(row) or _htf_alignment(row) == "against_htf"


def _all_tokens(row: dict[str, Any]) -> set[str]:
    return (
        _tokens(row.get("warnings"))
        | _tokens(row.get("avoidance_warnings"))
        | _tokens(row.get("rejection_reasons"))
        | _tokens(row.get("conditions_failed"))
        | _tokens(row.get("penalties"))
        | _tokens(row.get("reasons"))
    )


def _entry_context(row: dict[str, Any]) -> str:
    return str(row.get("entry_context") or "UNKNOWN").upper()


def _htf_alignment(row: dict[str, Any]) -> str:
    explicit = str(row.get("htf_alignment") or "").strip().lower()
    if explicit:
        return explicit
    direction = str(row.get("direction") or "").strip().lower()
    higher = str(row.get("trend_higher") or row.get("trend_4h") or row.get("trend_higher_timeframe") or "").strip().lower()
    if not direction or not higher:
        return "UNKNOWN"
    if direction == "long" and higher == "bearish":
        return "against_htf"
    if direction == "short" and higher == "bullish":
        return "against_htf"
    if direction == "long" and higher == "bullish":
        return "aligned_with_htf"
    if direction == "short" and higher == "bearish":
        return "aligned_with_htf"
    return f"htf_{higher}"


def _liquidity_context(row: dict[str, Any]) -> str:
    explicit = str(row.get("liquidity_context") or "").strip()
    if explicit:
        return explicit
    sweep = str(row.get("liquidity_sweep") or "").strip()
    if sweep:
        return f"sweep:{sweep}"
    location = str(row.get("trade_location") or "").strip()
    if location and location.upper() != "UNKNOWN":
        return f"location:{location}"
    return "UNKNOWN"


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


def _profit_factor(gross_profit: float, gross_loss: float) -> float | str:
    if gross_loss > 0:
        return _round(gross_profit / gross_loss)
    if gross_profit > 0:
        return "inf"
    return 0.0


def _timestamp(row: dict[str, Any]) -> datetime | None:
    raw = str(row.get("timestamp") or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _aware(parsed)


def _tokens(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, set, tuple)):
        return {str(item).strip() for item in value if str(item).strip()}
    text = str(value).strip()
    if not text:
        return set()
    return {item.strip() for item in text.replace("|", ",").replace(";", ",").split(",") if item.strip()}


def _join(value: object) -> str:
    return "|".join(sorted(_tokens(value)))


def _value(value: object) -> object:
    parsed = _float(value)
    return parsed if parsed is not None else value or ""


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float) -> float:
    rounded = round(value, 4)
    return 0.0 if rounded == 0 else rounded


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


def _metrics_row(metrics: dict[str, Any]) -> str:
    return (
        f"| {metrics.get('trades', 0)} | {metrics.get('wins', 0)} | {metrics.get('losses', 0)} | "
        f"{metrics.get('winrate', 0)}% | {metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} |"
    )


def _period_row(name: str, payload: dict[str, Any]) -> str:
    metrics = payload.get("metrics", {}) if isinstance(payload, dict) else {}
    return (
        f"| {name} | {payload.get('records', 0) if isinstance(payload, dict) else 0} | "
        f"{payload.get('closed', 0) if isinstance(payload, dict) else 0} | {metrics.get('winrate', 0)}% | "
        f"{metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} | "
        f"{payload.get('r_avoided', 0) if isinstance(payload, dict) else 0} |"
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
