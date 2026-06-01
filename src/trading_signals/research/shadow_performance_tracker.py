from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def build_shadow_performance_tracker(
    *,
    data_path: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    tracked = _dedupe_records(
        [
            *_load_private_shadow_signals(data_path),
            *_load_relaxation_shadow_signals(data_path),
            *_load_high_score_rejected(data_path),
        ]
    )
    trade_index = _load_trade_index(data_path)
    tracked = [_attach_outcome(record, trade_index) for record in tracked]
    last_24h = [row for row in tracked if _within(row.get("opened_at"), now_dt, timedelta(hours=24))]
    last_7d = [row for row in tracked if _within(row.get("opened_at"), now_dt, timedelta(days=7))]
    return {
        "scope": "SHADOW_PERFORMANCE_TRACKER",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "records_total": len(tracked),
        "last_24h": _window_summary(last_24h),
        "last_7d": _window_summary(last_7d),
        "by_direction": _group_summary(tracked, "direction"),
        "by_rejection_reason": _group_by_reason(tracked),
        "by_market_regime": _group_summary(tracked, "market_regime"),
        "classification": classify_shadow_performance(_metrics(tracked)),
        "records": tracked,
    }


def classify_shadow_performance(metrics: dict[str, Any]) -> str:
    closed = int(metrics.get("closed", 0) or 0)
    if closed < 5:
        return "NEUTRAL"
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    pf = _pf_value(metrics.get("profit_factor"))
    wr = float(metrics.get("winrate", 0.0) or 0.0)
    if total_r > 0 and pf > 1.2 and wr >= 45:
        return "PROMISING"
    if total_r < 0 and pf < 1.0:
        return "TOXIC"
    return "NEUTRAL"


def compute_shadow_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return _metrics(rows)


def write_shadow_performance_tracker_report(result: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "shadow_performance_tracker.md"
    path.write_text(format_shadow_performance_tracker_markdown(result), encoding="utf-8")
    return path


def format_shadow_performance_tracker_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# SHADOW_PERFORMANCE_TRACKER",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Records tracked: {result.get('records_total', 0)}",
        f"Classification: {result.get('classification')}",
        "",
        "## Last 24h",
        "",
        _window_line(result.get("last_24h", {})),
        "",
        "## Last 7d",
        "",
        _window_line(result.get("last_7d", {})),
        "",
        "## By Direction",
        "",
        *_table_group(result.get("by_direction", {}), "Direction"),
        "",
        "## By Rejection Reason",
        "",
        *_table_group(result.get("by_rejection_reason", {}), "Rejection reason"),
        "",
        "## By Market Regime",
        "",
        *_table_group(result.get("by_market_regime", {}), "Market regime"),
        "",
        "## Recent Records",
        "",
        "| Opened | Source | Symbol | Direction | Score | Setup | Regime | Reason | Outcome | R |",
        "|---|---|---|---|---:|---|---|---|---|---:|",
    ]
    for row in sorted(result.get("records", []), key=lambda item: str(item.get("opened_at") or ""), reverse=True)[:30]:
        lines.append(
            f"| {row.get('opened_at', '')} | {row.get('source_type', '')} | {row.get('symbol', '')} | "
            f"{row.get('direction', '')} | {row.get('score', '')} | {row.get('setup', '')} | "
            f"{row.get('market_regime', '')} | {row.get('rejection_reason', '')} | {row.get('outcome', '')} | {row.get('result_r', '')} |"
        )
    if not result.get("records"):
        lines.append("| none |  |  |  |  |  |  |  |  |  |")
    lines.append("")
    return "\n".join(lines)


def _load_private_shadow_signals(data_path: Path) -> list[dict[str, Any]]:
    rows = []
    for item in _read_jsonl(data_path / "bot_activity" / "signals_log.jsonl"):
        direction = str(item.get("direction") or "").lower()
        status = str(item.get("status") or "").lower()
        score = _float(item.get("score")) or 0.0
        is_private_short = direction == "short" and status != "sent"
        is_high_score_rejected = status in {"rejected", "no_trade"} and score >= 85
        if not is_private_short and not is_high_score_rejected:
            continue
        rows.append(
            _base_record(
                source_type="private_short_signal" if is_private_short else "high_score_rejected",
                symbol=item.get("symbol"),
                direction=direction,
                score=score,
                setup=item.get("setup_type"),
                session=item.get("session"),
                market_regime=item.get("market_regime"),
                rejection_reason=_reason_string(item.get("rejection_reasons") or item.get("conditions_failed") or item.get("reasons")),
                opened_at=item.get("timestamp"),
                dedupe_key=item.get("dedupe_key"),
            )
        )
    return rows


def _load_relaxation_shadow_signals(data_path: Path) -> list[dict[str, Any]]:
    rows = []
    path = data_path / "shadow_relaxation" / "trades.csv"
    if not path.exists() or path.stat().st_size == 0:
        return rows
    for item in _read_csv(path):
        rows.append(
            _base_record(
                source_type="relaxation_shadow_v1",
                symbol=item.get("symbol"),
                direction=str(item.get("direction") or "").lower(),
                score=_float(item.get("score")),
                setup=item.get("setup_type"),
                session=item.get("session"),
                market_regime=item.get("market_regime"),
                rejection_reason=_reason_string(item.get("original_rejection_reasons") or item.get("relaxed_filters")),
                opened_at=item.get("opened_at") or item.get("timestamp"),
                closed_at=item.get("closed_at"),
                result_r=_float(item.get("result_r")),
                outcome=item.get("status"),
                dedupe_key=item.get("dedupe_key"),
            )
        )
    return rows


def _load_high_score_rejected(data_path: Path) -> list[dict[str, Any]]:
    # Keep this separate so future high-score-specific logs can be added without
    # changing the private short loader contract.
    rows = []
    for item in _read_jsonl(data_path / "bot_activity" / "signals_log.jsonl"):
        score = _float(item.get("score")) or 0.0
        status = str(item.get("status") or "").lower()
        if score < 85 or status not in {"rejected", "no_trade"}:
            continue
        rows.append(
            _base_record(
                source_type="high_score_rejected",
                symbol=item.get("symbol"),
                direction=str(item.get("direction") or "").lower(),
                score=score,
                setup=item.get("setup_type"),
                session=item.get("session"),
                market_regime=item.get("market_regime"),
                rejection_reason=_reason_string(item.get("rejection_reasons") or item.get("conditions_failed") or item.get("reasons")),
                opened_at=item.get("timestamp"),
                dedupe_key=item.get("dedupe_key"),
            )
        )
    return rows


def _base_record(
    *,
    source_type: str,
    symbol: object,
    direction: object,
    score: object,
    setup: object,
    session: object,
    market_regime: object,
    rejection_reason: object,
    opened_at: object,
    closed_at: object = "",
    result_r: float | None = None,
    outcome: object = "",
    dedupe_key: object = "",
) -> dict[str, Any]:
    return {
        "source_type": source_type,
        "symbol": str(symbol or "").upper(),
        "direction": str(direction or "").lower(),
        "score": _float(score),
        "setup": str(setup or "UNKNOWN"),
        "session": str(session or "UNKNOWN") or "UNKNOWN",
        "market_regime": str(market_regime or "UNKNOWN") or "UNKNOWN",
        "rejection_reason": str(rejection_reason or "none"),
        "opened_at": str(opened_at or ""),
        "closed_at": str(closed_at or ""),
        "result_r": result_r,
        "outcome": str(outcome or "open_or_pending"),
        "dedupe_key": str(dedupe_key or ""),
    }


def _attach_outcome(record: dict[str, Any], trade_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if record.get("result_r") is not None:
        return record
    key = str(record.get("dedupe_key") or "")
    match = trade_index.get(key) if key else None
    if match is None:
        return record
    return {
        **record,
        "closed_at": str(match.get("closed_at") or match.get("updated_at") or ""),
        "result_r": _float(match.get("result_r")),
        "outcome": str(match.get("status") or "unknown"),
    }


def _load_trade_index(data_path: Path) -> dict[str, dict[str, Any]]:
    index = {}
    for path in (data_path / "paper_trading" / "trades.csv", data_path / "live_trading" / "trades.csv"):
        for row in _read_csv(path):
            key = str(row.get("dedupe_key") or "")
            if key:
                index[key] = row
    return index


def _window_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"count": len(rows), "metrics": _metrics(rows), "classification": classify_shadow_performance(_metrics(rows))}


def _group_summary(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(field) or "UNKNOWN")].append(row)
    return {key: {"count": len(items), "metrics": _metrics(items), "classification": classify_shadow_performance(_metrics(items))} for key, items in sorted(groups.items())}


def _group_by_reason(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for reason in _tokens(row.get("rejection_reason")) or ["none"]:
            groups[reason].append(row)
    return {key: {"count": len(items), "metrics": _metrics(items), "classification": classify_shadow_performance(_metrics(items))} for key, items in sorted(groups.items())}


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [_float(row.get("result_r")) for row in rows]
    values = [value for value in values if value is not None]
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


def _dedupe_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    output = []
    for row in rows:
        key = (
            row.get("dedupe_key") or row.get("opened_at"),
            row.get("symbol"),
            row.get("direction"),
            row.get("rejection_reason"),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="", errors="replace") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _within(value: object, now: datetime, delta: timedelta) -> bool:
    parsed = _parse_datetime(value)
    return parsed is not None and now - delta <= parsed <= now


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return _aware(parsed)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _tokens(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    text = str(value).strip()
    if not text:
        return []
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        decoded = None
    if isinstance(decoded, list):
        return [str(item) for item in decoded if str(item)]
    return [item.strip() for item in text.replace(",", "|").split("|") if item.strip()]


def _reason_string(value: object) -> str:
    tokens = _tokens(value)
    return "|".join(tokens) if tokens else str(value or "none")


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pf_value(value: object) -> float:
    if value == "inf":
        return 999.0
    return _float(value) or 0.0


def _window_line(value: object) -> str:
    if not isinstance(value, dict):
        value = {}
    return f"- Count: {value.get('count', 0)} | Classification: {value.get('classification', 'NEUTRAL')} | {_metrics_line(value.get('metrics', {}))}"


def _metrics_line(metrics: object) -> str:
    if not isinstance(metrics, dict):
        metrics = {}
    return (
        f"closed {metrics.get('closed', 0)} | open/pending {metrics.get('open_pending', 0)} | "
        f"WR {metrics.get('winrate', 0)}% | PF {metrics.get('profit_factor', 0)} | Total R {metrics.get('total_r', 0)}"
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
