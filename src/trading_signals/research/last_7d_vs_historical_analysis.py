from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades, normalize_for_research


MIN_RECENT_TRADES_FOR_SHIFT = 3


def analyze_last_7d_vs_historical(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    trades = sorted(load_canonical_closed_trades(data_path), key=lambda row: _timestamp(row) or datetime.min.replace(tzinfo=UTC))
    periods = {
        "last_7d": _since(trades, now_dt - timedelta(days=7)),
        "last_30d": _since(trades, now_dt - timedelta(days=30)),
        "full_history": trades,
    }
    period_summaries = {name: _period_summary(rows) for name, rows in periods.items()}
    direction_comparison = {
        direction: _direction_comparison(periods, direction)
        for direction in ("long", "short")
    }
    symbol_changes = _improvement_table(periods["last_7d"], trades, "symbol")
    setup_changes = _improvement_table(periods["last_7d"], trades, "setup_type")
    context_changes = {
        "market_regime": _improvement_table(periods["last_7d"], trades, "market_regime"),
        "session": _improvement_table(periods["last_7d"], trades, "session"),
        "score_bucket": _improvement_table(periods["last_7d"], trades, "score_bucket"),
    }
    regime_shift = _detect_regime_shift(period_summaries["last_7d"]["metrics"], period_summaries["full_history"]["metrics"])
    executive_summary = _executive_summary(
        direction_comparison=direction_comparison,
        regime_shift=regime_shift,
        symbol_changes=symbol_changes,
        setup_changes=setup_changes,
        context_changes=context_changes,
    )
    return {
        "scope": "LAST_7D_VS_HISTORICAL_REGIME_ANALYSIS",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "periods": period_summaries,
        "direction_comparison": direction_comparison,
        "symbol_improvements": symbol_changes,
        "setup_improvements": setup_changes,
        "context_changes": context_changes,
        "regime_shift_detection": regime_shift,
        "executive_summary": executive_summary,
    }


def audit_last_7d_data_sources(*, data_path: Path, reports_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    canonical = load_canonical_closed_trades(data_path)
    paper_path = data_path / "paper_trading" / "trades.csv"
    live_path = data_path / "live_trading" / "trades.csv"
    outcome_path = reports_path / "outcome_intelligence.csv"
    bot_audit_path = reports_path / "bot_audit_ai.json"
    dashboard_path = reports_path / "dashboard.html"
    manifest_path = reports_path / "intelligence_layer_manifest.json"
    sources = {
        "canonical_closed_trades": _source_summary_from_rows(
            path=paper_path,
            raw_rows=_read_csv(paper_path),
            closed_rows=canonical,
            timestamp_field="timestamp",
            note="Canonical source used by this analysis, dashboard and BOT_AUDIT_AI in this repository.",
        ),
        "paper_trading_trades_csv": _source_summary_from_csv(path=paper_path, closed_only=True),
        "live_trading_trades_csv": _source_summary_from_csv(path=live_path, closed_only=True),
        "outcome_intelligence_csv": _source_summary_from_csv(path=outcome_path, closed_only=False),
        "bot_audit_ai_json": _bot_audit_summary(bot_audit_path),
        "dashboard_html": _file_summary(dashboard_path, note="Dashboard is generated from canonical_trade_source via scripts/generate_dashboard.py."),
        "intelligence_manifest_json": _manifest_summary(manifest_path),
    }
    canonical_latest = sources["canonical_closed_trades"].get("latest_timestamp") or ""
    last_7d_start = now_dt - timedelta(days=7)
    last_7d_count = len(_since(canonical, last_7d_start))
    visible_recent_sources = [
        name
        for name, payload in sources.items()
        if name != "canonical_closed_trades"
        and str(payload.get("latest_trade_timestamp") or "") >= last_7d_start.isoformat(timespec="seconds")
    ]
    if last_7d_count == 0 and canonical_latest:
        why = (
            f"The analysis reads `{paper_path}` through canonical_trade_source. "
            f"The latest normalized closed timestamp in that source is `{canonical_latest}`, which is older than the 7d window start `{last_7d_start.isoformat(timespec='seconds')}`."
        )
    elif not canonical:
        why = f"No normalized closed trades were found in canonical source `{paper_path}`."
    else:
        why = "Canonical source contains trades inside the requested 7d window."
    if visible_recent_sources:
        recommendation = (
            "Recent rows exist outside the canonical paper source. Confirm whether those sources must be promoted into "
            "canonical_trade_source or whether the script is being run with the wrong BOT_DATA_DIR/data path."
        )
    elif sources["bot_audit_ai_json"].get("closed_trades") not in (None, len(canonical)):
        recommendation = "BOT_AUDIT_AI reports a different closed trade count; regenerate reports with the same BOT_DATA_DIR or inspect stale JSON."
    elif last_7d_count == 0:
        recommendation = "Use the correct BOT_DATA_DIR/data path if VPS has newer trades; local canonical data is stale for the last 7 days."
    else:
        recommendation = "No data-source fix required; date windows are using the canonical closed trade source."
    return {
        "scope": "LAST_7D_DATA_SOURCE_AUDIT",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "reports_path": str(reports_path),
        "last_7d_window_start": last_7d_start.isoformat(timespec="seconds"),
        "canonical_closed_count": len(canonical),
        "canonical_last_7d_count": last_7d_count,
        "sources": sources,
        "why_last_7d_zero": why,
        "recommended_fix": recommendation,
    }


def write_last_7d_data_source_audit(audit: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "last_7d_data_source_audit.md"
    path.write_text(format_last_7d_data_source_audit_markdown(audit), encoding="utf-8")
    return path


def format_last_7d_data_source_audit_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# LAST_7D Data Source Audit",
        "",
        f"- Generated at: {audit.get('generated_at')}",
        f"- Data path: `{audit.get('data_path')}`",
        f"- Reports path: `{audit.get('reports_path')}`",
        f"- Last 7d window start: `{audit.get('last_7d_window_start')}`",
        f"- Canonical closed trades: {audit.get('canonical_closed_count', 0)}",
        f"- Canonical last 7d closed trades: {audit.get('canonical_last_7d_count', 0)}",
        "",
        "## Sources",
        "",
        "| Source | File | Exists | Raw rows | Closed rows | Latest trade timestamp | Latest report timestamp | Size bytes |",
        "|---|---|---:|---:|---:|---|---|---:|",
    ]
    for name, payload in audit.get("sources", {}).items():
        if not isinstance(payload, dict):
            continue
        lines.append(
            f"| {name} | `{payload.get('path', '')}` | {payload.get('exists', False)} | {payload.get('raw_rows', 0)} | "
            f"{payload.get('closed_rows', 0)} | {payload.get('latest_trade_timestamp') or 'n/a'} | "
            f"{payload.get('latest_report_timestamp') or 'n/a'} | {payload.get('size_bytes', 0)} |"
        )
    lines.extend(
        [
            "",
            "## Diagnosis",
            "",
            f"- Why last 7d is zero: {audit.get('why_last_7d_zero')}",
            f"- Recommended fix: {audit.get('recommended_fix')}",
            "",
            "## Source Notes",
            "",
        ]
    )
    for name, payload in audit.get("sources", {}).items():
        if isinstance(payload, dict) and payload.get("note"):
            lines.append(f"- {name}: {payload.get('note')}")
    return "\n".join(lines).rstrip() + "\n"


def write_last_7d_vs_historical_report(result: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "last_7d_vs_historical_analysis.md"
    path.write_text(format_last_7d_vs_historical_markdown(result), encoding="utf-8")
    return path


def format_last_7d_vs_historical_markdown(result: dict[str, Any]) -> str:
    summary = result.get("executive_summary", {})
    lines = [
        "# LAST_7D_VS_HISTORICAL_REGIME_ANALYSIS",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        "",
        "## Executive Summary",
        "",
        f"- What changed: {summary.get('what_changed', 'insufficient_data')}",
        f"- What did not change: {summary.get('what_did_not_change', 'insufficient_data')}",
        f"- Recommended action: {summary.get('recommended_action', 'continue monitoring')}",
        "",
        "## Period Metrics",
        "",
        "| Period | Trades | Wins | Losses | WR | PF | Total R | Avg R |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for period in ("last_7d", "last_30d", "full_history"):
        metrics = result.get("periods", {}).get(period, {}).get("metrics", {})
        lines.append(_metrics_table_row(period, metrics))
    lines.extend(
        [
            "",
            "## LONG vs SHORT",
            "",
            "| Direction | 7d Trades | 7d WR | 7d PF | 7d R | 30d Trades | 30d R | Full Trades | Full R | Classification |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for direction in ("long", "short"):
        payload = result.get("direction_comparison", {}).get(direction, {})
        lines.append(_direction_table_row(direction.upper(), payload))
    shift = result.get("regime_shift_detection", {})
    lines.extend(
        [
            "",
            "## REGIME SHIFT DETECTION",
            "",
            f"- Classification: {shift.get('classification', 'STABLE')}",
            f"- Material difference: {shift.get('material_difference', False)}",
            f"- WR delta 7d vs full: {shift.get('winrate_delta', 0)}",
            f"- Avg R delta 7d vs full: {shift.get('avg_r_delta', 0)}",
            f"- PF delta 7d vs full: {shift.get('profit_factor_delta', 0)}",
            f"- Are SHORT trades performing better recently? {result.get('direction_comparison', {}).get('short', {}).get('answer', 'unknown')}",
            f"- Is current market different from historical average? {shift.get('answer', 'unknown')}",
            "",
            "## Symbols Improved Most",
            "",
            *_change_table(result.get("symbol_improvements", {}).get("improved", []), "Symbol"),
            "",
            "## Setups Improved Most",
            "",
            *_change_table(result.get("setup_improvements", {}).get("improved", []), "Setup"),
            "",
            "## Contexts Deteriorated",
            "",
            *_context_deterioration_tables(result.get("context_changes", {})),
            "",
            "## Breakdowns",
            "",
        ]
    )
    for period in ("last_7d", "last_30d", "full_history"):
        lines.extend([f"### {period}", ""])
        period_payload = result.get("periods", {}).get(period, {})
        for breakdown_name in ("direction", "symbol", "setup_type", "market_regime", "session", "score_bucket"):
            lines.extend([f"#### {breakdown_name}", "", *_breakdown_table(period_payload.get("breakdowns", {}).get(breakdown_name, {})), ""])
    return "\n".join(lines)


def _period_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "metrics": _metrics(rows),
        "breakdowns": {
            "direction": _breakdown(rows, "direction"),
            "symbol": _breakdown(rows, "symbol"),
            "setup_type": _breakdown(rows, "setup_type"),
            "market_regime": _breakdown(rows, "market_regime"),
            "session": _breakdown(rows, "session"),
            "score_bucket": _breakdown(rows, "score_bucket"),
        },
    }


def _direction_comparison(periods: dict[str, list[dict[str, Any]]], direction: str) -> dict[str, Any]:
    rows = {
        "last_7d": [row for row in periods["last_7d"] if str(row.get("direction")).lower() == direction],
        "last_30d": [row for row in periods["last_30d"] if str(row.get("direction")).lower() == direction],
        "full_history": [row for row in periods["full_history"] if str(row.get("direction")).lower() == direction],
    }
    metrics = {period: _metrics(items) for period, items in rows.items()}
    classification = _classify_change(metrics["last_7d"], metrics["full_history"])
    return {
        "metrics": metrics,
        "classification": classification,
        "answer": _direction_answer(direction, classification, metrics["last_7d"], metrics["full_history"]),
    }


def _detect_regime_shift(recent: dict[str, Any], historical: dict[str, Any]) -> dict[str, Any]:
    classification = _classify_change(recent, historical)
    wr_delta = _round(float(recent.get("winrate", 0.0)) - float(historical.get("winrate", 0.0)))
    avg_delta = _round(float(recent.get("avg_r", 0.0)) - float(historical.get("avg_r", 0.0)))
    pf_delta = _round(_pf_float(recent.get("profit_factor")) - _pf_float(historical.get("profit_factor")))
    material = abs(wr_delta) >= 10 or abs(avg_delta) >= 0.2 or abs(pf_delta) >= 0.5
    if int(recent.get("total_trades", 0) or 0) < MIN_RECENT_TRADES_FOR_SHIFT:
        answer = "insufficient recent sample"
        material = False
    elif classification == "IMPROVING":
        answer = "recent performance is materially stronger than historical average"
    elif classification == "DETERIORATING":
        answer = "recent performance is materially weaker than historical average"
    else:
        answer = "recent performance is broadly aligned with historical average"
    return {
        "classification": classification,
        "material_difference": material,
        "winrate_delta": wr_delta,
        "avg_r_delta": avg_delta,
        "profit_factor_delta": pf_delta,
        "answer": answer,
    }


def _classify_change(recent: dict[str, Any], historical: dict[str, Any]) -> str:
    if int(recent.get("total_trades", 0) or 0) < MIN_RECENT_TRADES_FOR_SHIFT or int(historical.get("total_trades", 0) or 0) < MIN_RECENT_TRADES_FOR_SHIFT:
        return "STABLE"
    wr_delta = float(recent.get("winrate", 0.0)) - float(historical.get("winrate", 0.0))
    avg_delta = float(recent.get("avg_r", 0.0)) - float(historical.get("avg_r", 0.0))
    pf_delta = _pf_float(recent.get("profit_factor")) - _pf_float(historical.get("profit_factor"))
    if avg_delta >= 0.2 and (pf_delta >= 0.3 or wr_delta >= 10):
        return "IMPROVING"
    if avg_delta <= -0.2 and (pf_delta <= -0.3 or wr_delta <= -10):
        return "DETERIORATING"
    return "STABLE"


def _improvement_table(recent_rows: list[dict[str, Any]], historical_rows: list[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    recent_groups = _raw_groups(recent_rows, field)
    historical_groups = _raw_groups(historical_rows, field)
    rows = []
    for key, recent_items in recent_groups.items():
        historical_items = historical_groups.get(key, [])
        recent_metrics = _metrics(recent_items)
        historical_metrics = _metrics(historical_items)
        rows.append(
            {
                "value": key,
                "recent_trades": recent_metrics["total_trades"],
                "historical_trades": historical_metrics["total_trades"],
                "recent_total_r": recent_metrics["total_r"],
                "historical_total_r": historical_metrics["total_r"],
                "recent_avg_r": recent_metrics["avg_r"],
                "historical_avg_r": historical_metrics["avg_r"],
                "avg_r_delta": _round(recent_metrics["avg_r"] - historical_metrics["avg_r"]),
                "classification": _classify_change(recent_metrics, historical_metrics),
            }
        )
    improved = sorted([row for row in rows if row["avg_r_delta"] > 0], key=lambda row: (row["avg_r_delta"], row["recent_total_r"]), reverse=True)[:10]
    deteriorated = sorted([row for row in rows if row["avg_r_delta"] < 0], key=lambda row: (row["avg_r_delta"], row["recent_total_r"]))[:10]
    return {"improved": improved, "deteriorated": deteriorated}


def _executive_summary(
    *,
    direction_comparison: dict[str, Any],
    regime_shift: dict[str, Any],
    symbol_changes: dict[str, list[dict[str, Any]]],
    setup_changes: dict[str, list[dict[str, Any]]],
    context_changes: dict[str, Any],
) -> dict[str, str]:
    short_class = direction_comparison.get("short", {}).get("classification", "STABLE")
    long_class = direction_comparison.get("long", {}).get("classification", "STABLE")
    improved_symbols = ", ".join(row["value"] for row in symbol_changes.get("improved", [])[:3]) or "none"
    improved_setups = ", ".join(row["value"] for row in setup_changes.get("improved", [])[:3]) or "none"
    deteriorated_contexts = []
    for dimension, payload in context_changes.items():
        for row in payload.get("deteriorated", [])[:2]:
            deteriorated_contexts.append(f"{dimension}={row['value']}")
    if short_class == "IMPROVING":
        action = "candidate for shadow promotion"
    elif regime_shift.get("classification") == "DETERIORATING" or long_class == "DETERIORATING":
        action = "investigate further"
    elif regime_shift.get("classification") == "STABLE":
        action = "continue monitoring"
    else:
        action = "keep current policy"
    return {
        "what_changed": f"SHORT={short_class}, LONG={long_class}, improved symbols: {improved_symbols}, improved setups: {improved_setups}",
        "what_did_not_change": f"Regime shift classification: {regime_shift.get('classification', 'STABLE')}; deteriorated contexts: {', '.join(deteriorated_contexts[:5]) or 'none'}",
        "recommended_action": action,
    }


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [_float(row.get("result_r")) for row in rows]
    values = [value for value in values if value is not None]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "total_trades": len(values),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": _round(len(wins) / len(values) * 100) if values else 0.0,
        "profit_factor": _profit_factor(gross_profit, gross_loss),
        "total_r": _round(sum(values)),
        "avg_r": _round(sum(values) / len(values)) if values else 0.0,
    }


def _breakdown(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    return {key: _metrics(items) for key, items in sorted(_raw_groups(rows, field).items())}


def _raw_groups(rows: list[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = _score_bucket(row.get("score")) if field == "score_bucket" else str(row.get(field) or "UNKNOWN")
        groups[value].append(row)
    return groups


def _since(rows: list[dict[str, Any]], start: datetime) -> list[dict[str, Any]]:
    return [row for row in rows if (ts := _timestamp(row)) is not None and ts >= start]


def _source_summary_from_csv(*, path: Path, closed_only: bool) -> dict[str, Any]:
    raw = _read_csv(path)
    if closed_only:
        closed = [row for row in (normalize_for_research({**item, "source_csv": str(path)}) for item in raw) if row is not None]
    else:
        closed = raw
    return _source_summary_from_rows(path=path, raw_rows=raw, closed_rows=closed, timestamp_field="timestamp")


def _source_summary_from_rows(
    *,
    path: Path,
    raw_rows: list[dict[str, Any]],
    closed_rows: list[dict[str, Any]],
    timestamp_field: str,
    note: str = "",
) -> dict[str, Any]:
    timestamps = []
    generated_timestamps = []
    for row in closed_rows:
        value = row.get(timestamp_field) or row.get("closed_at") or row.get("updated_at") or row.get("opened_at") or row.get("generated_at")
        trade_value = row.get(timestamp_field) or row.get("closed_at") or row.get("updated_at") or row.get("opened_at")
        generated_value = row.get("generated_at")
        parsed = _timestamp({"timestamp": trade_value})
        generated_parsed = _timestamp({"timestamp": generated_value})
        if parsed is not None:
            timestamps.append(parsed)
        elif value and generated_parsed is not None:
            generated_timestamps.append(generated_parsed)
    return {
        "path": str(path),
        "exists": path.exists(),
        "raw_rows": len(raw_rows),
        "closed_rows": len(closed_rows),
        "latest_timestamp": max(timestamps or generated_timestamps).isoformat(timespec="seconds") if (timestamps or generated_timestamps) else "",
        "latest_trade_timestamp": max(timestamps).isoformat(timespec="seconds") if timestamps else "",
        "latest_report_timestamp": max(generated_timestamps).isoformat(timespec="seconds") if generated_timestamps else "",
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "note": note,
    }


def _bot_audit_summary(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    summary = payload.get("executive_summary", {}) if isinstance(payload, dict) else {}
    closed = summary.get("closed_trades") if isinstance(summary, dict) else None
    return {
        "path": str(path),
        "exists": path.exists(),
        "raw_rows": 1 if payload else 0,
        "closed_rows": closed if closed is not None else 0,
        "closed_trades": closed,
        "latest_timestamp": str(payload.get("generated_at") or "") if isinstance(payload, dict) else "",
        "latest_trade_timestamp": "",
        "latest_report_timestamp": str(payload.get("generated_at") or "") if isinstance(payload, dict) else "",
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "note": f"Dataset declared: {payload.get('dataset')}" if isinstance(payload, dict) else "",
    }


def _manifest_summary(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    rows = payload.get("rows", {}) if isinstance(payload, dict) else {}
    closed = rows.get("closed_trades") if isinstance(rows, dict) else 0
    return {
        "path": str(path),
        "exists": path.exists(),
        "raw_rows": 1 if payload else 0,
        "closed_rows": closed or 0,
        "latest_timestamp": str(payload.get("generated_at") or "") if isinstance(payload, dict) else "",
        "latest_trade_timestamp": "",
        "latest_report_timestamp": str(payload.get("generated_at") or "") if isinstance(payload, dict) else "",
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "note": f"Manifest closed_trades={closed}; canonical_rows={payload.get('data_sources', {}).get('canonical_trades_rows') if isinstance(payload, dict) else 'n/a'}",
    }


def _file_summary(path: Path, *, note: str = "") -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "raw_rows": 0,
        "closed_rows": 0,
        "latest_timestamp": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(timespec="seconds") if path.exists() else "",
        "latest_trade_timestamp": "",
        "latest_report_timestamp": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(timespec="seconds") if path.exists() else "",
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "note": note,
    }


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except csv.Error:
        return []


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _timestamp(row: dict[str, Any]) -> datetime | None:
    value = row.get("timestamp") or row.get("closed_at") or row.get("opened_at")
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


def _round(value: float) -> float:
    return round(value, 4)


def _direction_answer(direction: str, classification: str, recent: dict[str, Any], historical: dict[str, Any]) -> str:
    if int(recent.get("total_trades", 0) or 0) < MIN_RECENT_TRADES_FOR_SHIFT:
        return f"not enough recent {direction.upper()} trades"
    if classification == "IMPROVING":
        return f"yes, recent {direction.upper()} trades are outperforming historical average"
    if classification == "DETERIORATING":
        return f"no, recent {direction.upper()} trades are underperforming historical average"
    return f"recent {direction.upper()} trades are broadly stable vs historical average"


def _metrics_table_row(period: str, metrics: dict[str, Any]) -> str:
    return (
        f"| {period} | {metrics.get('total_trades', 0)} | {metrics.get('wins', 0)} | {metrics.get('losses', 0)} | "
        f"{metrics.get('winrate', 0)}% | {metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} |"
    )


def _direction_table_row(label: str, payload: dict[str, Any]) -> str:
    metrics = payload.get("metrics", {})
    m7 = metrics.get("last_7d", {})
    m30 = metrics.get("last_30d", {})
    full = metrics.get("full_history", {})
    return (
        f"| {label} | {m7.get('total_trades', 0)} | {m7.get('winrate', 0)}% | {m7.get('profit_factor', 0)} | {m7.get('total_r', 0)} | "
        f"{m30.get('total_trades', 0)} | {m30.get('total_r', 0)} | {full.get('total_trades', 0)} | {full.get('total_r', 0)} | "
        f"{payload.get('classification', 'STABLE')} |"
    )


def _change_table(rows: list[dict[str, Any]], label: str) -> list[str]:
    lines = [f"| {label} | Recent trades | Historical trades | Recent AvgR | Historical AvgR | Delta AvgR | Classification |", "|---|---:|---:|---:|---:|---:|---|"]
    if not rows:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | STABLE |")
        return lines
    for row in rows[:10]:
        lines.append(
            f"| {row['value']} | {row['recent_trades']} | {row['historical_trades']} | {row['recent_avg_r']} | "
            f"{row['historical_avg_r']} | {row['avg_r_delta']} | {row['classification']} |"
        )
    return lines


def _context_deterioration_tables(context_changes: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for dimension, payload in context_changes.items():
        lines.extend([f"### {dimension}", "", *_change_table(payload.get("deteriorated", []), dimension), ""])
    return lines


def _breakdown_table(payload: dict[str, dict[str, Any]]) -> list[str]:
    lines = ["| Value | Trades | Wins | Losses | WR | PF | Total R | Avg R |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    if not payload:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 |")
        return lines
    for key, metrics in payload.items():
        lines.append(
            f"| {key} | {metrics.get('total_trades', 0)} | {metrics.get('wins', 0)} | {metrics.get('losses', 0)} | "
            f"{metrics.get('winrate', 0)}% | {metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} |"
        )
    return lines
