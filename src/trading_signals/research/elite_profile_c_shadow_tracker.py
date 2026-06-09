from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


CSV_FIELDS = (
    "timestamp",
    "symbol",
    "direction",
    "setup_type",
    "score",
    "score_bucket",
    "htf_alignment",
    "session",
    "market_regime",
    "entry_context",
    "trade_location",
    "liquidity_sweep",
    "status",
    "result_r",
    "source",
)


def generate_elite_profile_c_shadow_tracker(
    *,
    data_path: Path,
    reports_path: Path,
    now: datetime | None = None,
    dev_note_enabled: bool = False,
) -> dict[str, Any]:
    result = analyze_elite_profile_c_shadow_tracker(data_path=data_path, now=now, dev_note_enabled=dev_note_enabled)
    csv_path = write_elite_profile_c_shadow_csv(result["records"], data_path)
    report_path = write_elite_profile_c_shadow_report(result, reports_path)
    return {**result, "shadow_csv_path": str(csv_path), "report_path": str(report_path)}


def analyze_elite_profile_c_shadow_tracker(
    *,
    data_path: Path,
    now: datetime | None = None,
    dev_note_enabled: bool = False,
) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    trade_records = [_record_from_trade(row) for row in load_canonical_closed_trades(data_path) if matches_elite_profile_c(row)]
    signal_records = [_record_from_signal(row) for row in _load_signal_candidates(data_path / "bot_activity" / "signals_log.jsonl")]
    records = _dedupe_records([*trade_records, *signal_records])
    closed = [row for row in records if _float(row.get("result_r")) is not None]
    metrics = _metrics(closed)
    return {
        "scope": "ELITE_PROFILE_C_SHADOW_TRACKER",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "definition": {
            "setup_type": "SECONDARY_SIGNAL",
            "score_bucket": "90+",
            "htf_alignment": "aligned_with_htf",
        },
        "dev_note_enabled": bool(dev_note_enabled),
        "records": records,
        "total_tracked": len(records),
        "closed_evaluable": len(closed),
        "metrics": metrics,
        "by_symbol": _group_summary(records, "symbol"),
        "by_session": _group_summary(records, "session"),
        "by_direction": _group_summary(records, "direction"),
        "by_market_regime": _group_summary(records, "market_regime"),
        "by_entry_context": _group_summary(records, "entry_context"),
        "by_trade_location": _group_summary(records, "trade_location"),
        "recommendation": recommend_elite_profile_c(metrics),
    }


def matches_elite_profile_c(row: dict[str, Any]) -> bool:
    return _setup_type(row) == "SECONDARY_SIGNAL" and _score_bucket(row.get("score") or row.get("setup_score")) == "90+" and _htf_alignment(row) == "aligned_with_htf"


def recommend_elite_profile_c(metrics: dict[str, Any]) -> str:
    trades = int(metrics.get("trades", 0) or 0)
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    pf = _pf_float(metrics.get("profit_factor"))
    winrate = float(metrics.get("winrate", 0.0) or 0.0)
    if trades >= 40 and pf >= 2.0 and total_r > 0 and winrate >= 55:
        return "PROMOTE_TO_PRIORITY"
    if trades >= 20 and pf >= 1.5 and total_r > 0:
        return "PROMOTE_TO_PUBLIC_TAG"
    if trades >= 10 and pf >= 1.1 and total_r > 0:
        return "KEEP_SHADOW"
    if trades >= 10 and (pf < 1.0 or total_r <= 0):
        return "REJECT_PROFILE"
    return "KEEP_SHADOW"


def write_elite_profile_c_shadow_csv(records: list[dict[str, Any]], data_path: Path) -> Path:
    path = data_path / "shadow_blocks" / "elite_profile_c_shadow.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in records:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})
    return path


def write_elite_profile_c_shadow_report(result: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "elite_profile_c_shadow_tracker.md"
    path.write_text(format_elite_profile_c_shadow_markdown(result), encoding="utf-8")
    return path


def format_elite_profile_c_shadow_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# ELITE_PROFILE_C_SHADOW_TRACKER",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        f"Recommendation: {result.get('recommendation')}",
        f"DEV note enabled: {result.get('dev_note_enabled')}",
        "",
        "## Definition",
        "",
        "- setup_type == SECONDARY_SIGNAL",
        "- score_bucket == 90+",
        "- htf_alignment == aligned_with_htf",
        "",
        "## Summary",
        "",
        f"- Total tracked: {result.get('total_tracked', 0)}",
        f"- Closed/evaluable: {result.get('closed_evaluable', 0)}",
        f"- Metrics: {_metrics_inline(result.get('metrics', {}))}",
        "",
        "## Metrics",
        "",
        "| Trades | Wins | Losses | WR | PF | Total R | Avg R |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        _metrics_row(result.get("metrics", {})),
        "",
        "## By Symbol",
        "",
        *_group_table(result.get("by_symbol", {}), "Symbol"),
        "",
        "## By Session",
        "",
        *_group_table(result.get("by_session", {}), "Session"),
        "",
        "## By Direction",
        "",
        *_group_table(result.get("by_direction", {}), "Direction"),
        "",
        "## By Market Regime",
        "",
        *_group_table(result.get("by_market_regime", {}), "Market regime"),
        "",
        "## By Entry Context",
        "",
        *_group_table(result.get("by_entry_context", {}), "Entry context"),
        "",
        "## By Trade Location",
        "",
        *_group_table(result.get("by_trade_location", {}), "Trade location"),
    ]
    return "\n".join(lines).rstrip() + "\n"


def _load_signal_candidates(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and matches_elite_profile_c(item):
            rows.append(item)
    return rows


def _record_from_trade(row: dict[str, Any]) -> dict[str, Any]:
    return _record(row, source="canonical_trade")


def _record_from_signal(row: dict[str, Any]) -> dict[str, Any]:
    return _record(row, source="signals_log")


def _record(row: dict[str, Any], *, source: str) -> dict[str, Any]:
    timestamp = str(row.get("opened_at") or row.get("created_at") or row.get("timestamp") or row.get("closed_at") or "")
    symbol = str(row.get("symbol") or "UNKNOWN").upper()
    direction = str(row.get("direction") or "unknown").lower()
    return {
        "timestamp": timestamp,
        "symbol": symbol,
        "direction": direction,
        "setup_type": _setup_type(row),
        "score": _value(row.get("score") or row.get("setup_score")),
        "score_bucket": _score_bucket(row.get("score") or row.get("setup_score")),
        "htf_alignment": _htf_alignment(row),
        "session": str(row.get("session") or "UNKNOWN").upper(),
        "market_regime": str(row.get("market_regime") or "UNKNOWN").upper(),
        "entry_context": str(row.get("entry_context") or "UNKNOWN").upper(),
        "trade_location": str(row.get("trade_location") or "UNKNOWN"),
        "liquidity_sweep": _liquidity_sweep(row),
        "status": str(row.get("status") or row.get("outcome") or ""),
        "result_r": _value(row.get("result_r") or row.get("r_result")),
        "source": source,
        "_dedupe_key": _dedupe_key(timestamp, symbol, direction, row, source),
    }


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output = []
    for row in records:
        key = str(row.get("_dedupe_key") or "")
        if key in seen:
            continue
        seen.add(key)
        output.append({key: value for key, value in row.items() if key != "_dedupe_key"})
    return output


def _dedupe_key(timestamp: str, symbol: str, direction: str, row: dict[str, Any], source: str) -> str:
    candidate = str(row.get("trade_id") or row.get("signal_id") or row.get("candidate_id") or "").strip()
    if candidate:
        return f"{source}:{candidate}"
    candle = timestamp[:16] if timestamp else "unknown"
    return f"{source}:{symbol}:{direction}:{_setup_type(row)}:{_score_bucket(row.get('score') or row.get('setup_score'))}:{candle}"


def _group_summary(records: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        groups[str(row.get(field) or "UNKNOWN")].append(row)
    return {key: _record_summary(rows) for key, rows in sorted(groups.items())}


def _record_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [row for row in records if _float(row.get("result_r")) is not None]
    return {"tracked": len(records), "closed": len(closed), "metrics": _metrics(closed)}


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


def _setup_type(row: dict[str, Any]) -> str:
    return str(row.get("setup_type") or "UNKNOWN").strip().upper()


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


def _htf_alignment(row: dict[str, Any]) -> str:
    explicit = str(row.get("htf_alignment") or "").strip().lower()
    if explicit:
        return explicit
    direction = str(row.get("direction") or "unknown").strip().lower()
    higher = str(row.get("trend_higher") or row.get("trend_4h") or row.get("trend_higher_timeframe") or "").strip().lower()
    if not direction or not higher:
        return "UNKNOWN"
    if direction == "long" and higher == "bullish":
        return "aligned_with_htf"
    if direction == "short" and higher == "bearish":
        return "aligned_with_htf"
    if direction == "long" and higher == "bearish":
        return "against_htf"
    if direction == "short" and higher == "bullish":
        return "against_htf"
    return f"htf_{higher}"


def _liquidity_sweep(row: dict[str, Any]) -> str:
    sweep = str(row.get("liquidity_sweep") or "").strip()
    if sweep:
        return sweep
    context = str(row.get("liquidity_context") or "").strip().lower()
    if context.startswith("sweep:"):
        return context.split(":", 1)[1]
    return "none"


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _value(value: object) -> object:
    number = _float(value)
    return "" if number is None else _round(number)


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


def _metrics_inline(metrics: object) -> str:
    if not isinstance(metrics, dict):
        metrics = {}
    return (
        f"trades={metrics.get('trades', 0)}, WR={metrics.get('winrate', 0)}%, "
        f"PF={metrics.get('profit_factor', 0)}, TotalR={metrics.get('total_r', 0)}, AvgR={metrics.get('avg_r', 0)}"
    )


def _metrics_row(metrics: object) -> str:
    payload = metrics if isinstance(metrics, dict) else {}
    return (
        f"| {payload.get('trades', 0)} | {payload.get('wins', 0)} | {payload.get('losses', 0)} | "
        f"{payload.get('winrate', 0)}% | {payload.get('profit_factor', 0)} | "
        f"{payload.get('total_r', 0)} | {payload.get('avg_r', 0)} |"
    )


def _group_table(payload: object, label: str) -> list[str]:
    lines = [f"| {label} | Tracked | Closed | WR | PF | Total R | Avg R |", "|---|---:|---:|---:|---:|---:|---:|"]
    if not isinstance(payload, dict) or not payload:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 |")
        return lines
    ranked = sorted(payload.items(), key=lambda item: (float(item[1].get("metrics", {}).get("total_r", 0.0)), int(item[1].get("tracked", 0))), reverse=True)
    for key, value in ranked:
        metrics = value.get("metrics", {}) if isinstance(value, dict) else {}
        lines.append(
            f"| {key} | {value.get('tracked', 0)} | {value.get('closed', 0)} | {metrics.get('winrate', 0)}% | "
            f"{metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} |"
        )
    return lines
