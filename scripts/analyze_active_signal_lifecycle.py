#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any


TARGET_DUPLICATE = "duplicate_signal_suppressed"
REPORT_JSON = "active_signal_lifecycle_audit_v1.json"
REPORT_MD = "active_signal_lifecycle_audit_v1.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    root = Path(os.getenv("BOT_DATA_DIR", "."))
    parser = argparse.ArgumentParser(description="Audit active published signals that drive lifecycle/dedupe blocking.")
    parser.add_argument("--data-path", type=Path, default=root / "data")
    parser.add_argument("--logs-path", type=Path, default=root / "logs")
    parser.add_argument("--reports-path", type=Path, default=root / "reports")
    parser.add_argument("--top", type=int, default=20)
    return parser.parse_args(argv)


def analyze(*, data_path: Path, logs_path: Path, reports_path: Path, top: int = 20) -> dict[str, Any]:
    generated_at = datetime.now(tz=UTC)
    trade_signals = _load_json_files(data_path / "trade_signals")
    risk_plans = {str(row.get("id")): row for row in _load_json_files(data_path / "risk_plans") if row.get("id")}
    deliveries = _load_json_files(data_path / "signal_deliveries")
    signals_log = _load_jsonl(data_path / "bot_activity" / "signals_log.jsonl")
    scheduler_events = _load_scheduler_events(logs_path / "scheduler.log")

    published = [row for row in trade_signals if row.get("published_at")]
    rejected = [row for row in trade_signals if str(row.get("status") or "").lower() == "rejected"]
    valid_unpublished = [
        row
        for row in trade_signals
        if str(row.get("status") or "").lower() == "valid" and not row.get("published_at")
    ]
    active = _build_active_signals(published, risk_plans=risk_plans, deliveries=deliveries, now=generated_at)
    duplicate_events = _duplicate_events(signals_log=signals_log, scheduler_events=scheduler_events)
    duplicate_map = _duplicates_by_active_signal(active, duplicate_events)
    for item in active:
        stats = duplicate_map.get(item["active_key"], {})
        item["duplicates_blocked"] = stats.get("count", 0)
        item["duplicate_score_gte_90"] = stats.get("score_gte_90", 0)
        item["latest_duplicate_at"] = stats.get("latest_duplicate_at")

    active_by_pair = _active_by_pair(active)
    result = {
        "scope": "ACTIVE_SIGNAL_LIFECYCLE_AUDIT_V1",
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "mode": "offline_diagnostic_only",
        "production_changed": False,
        "source_files": {
            "trade_signals_dir": str(data_path / "trade_signals"),
            "risk_plans_dir": str(data_path / "risk_plans"),
            "signals_log": str(data_path / "bot_activity" / "signals_log.jsonl"),
            "signal_deliveries_dir": str(data_path / "signal_deliveries"),
            "scheduler_log": str(logs_path / "scheduler.log"),
            "signal_lifecycle_code": "src/trading_signals/application/use_cases/signal_lifecycle.py",
            "run_market_scan_code": "src/trading_signals/application/use_cases/run_market_scan.py",
        },
        "code_origin": _code_origin(),
        "metrics": {
            "active_signals_count": len(active),
            "published_signals_count": len(published),
            "rejected_signals_count": len(rejected),
            "valid_unpublished_count": len(valid_unpublished),
            "active_without_expiration": sum(1 for item in active if not item["expires_at"]),
            "active_without_close_reason": sum(1 for item in active if not item["close_reason"]),
            "duplicate_signal_suppressed_events": len(duplicate_events),
            "oldest_active_signal_age_hours": _oldest_age_hours(active),
        },
        "active_by_symbol_direction": active_by_pair,
        "active_signals": sorted(active, key=lambda item: item.get("duplicates_blocked", 0), reverse=True)[:top],
        "duplicates_blocked_by_active_signal": _duplicate_block_rows(active, top=top),
        "storage_mix": {
            "trade_signals_total": len(trade_signals),
            "published": len(published),
            "rejected": len(rejected),
            "valid_unpublished": len(valid_unpublished),
            "other_status": len(trade_signals) - len(published) - len(rejected) - len(valid_unpublished),
            "published_and_rejected_mixed_in_same_store": bool(published and rejected),
        },
        "closure_capability": _closure_capability(active),
        "current_price_invalidation": _current_price_invalidation(active, scheduler_events),
        "data_gaps": _data_gaps(active, duplicate_events, risk_plans, deliveries),
        "conclusion": _conclusion(active, duplicate_events, active_by_pair),
    }
    return result


def write_reports(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / REPORT_JSON
    md_path = reports_path / REPORT_MD
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(format_markdown(result), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def format_markdown(result: dict[str, Any]) -> str:
    metrics = result["metrics"]
    lines = [
        "# ACTIVE_SIGNAL_LIFECYCLE_AUDIT_V1",
        "",
        f"Generated at: {result['generated_at']}",
        "Mode: offline diagnostic only. No signals were closed, deleted, republished or modified.",
        "",
        "## Executive Summary",
        "",
        f"- Active signals count: {metrics['active_signals_count']}",
        f"- Published signals count: {metrics['published_signals_count']}",
        f"- Rejected signals count: {metrics['rejected_signals_count']}",
        f"- Valid unpublished count: {metrics['valid_unpublished_count']}",
        f"- Active without explicit expiration: {metrics['active_without_expiration']}",
        f"- Active without close reason: {metrics['active_without_close_reason']}",
        f"- duplicate_signal_suppressed events: {metrics['duplicate_signal_suppressed_events']}",
        f"- Oldest active signal age hours: {metrics['oldest_active_signal_age_hours']}",
        f"- Recommendation: {result['conclusion']['recommended_action']}",
        "",
        "## 1. Lifecycle Code Behavior",
        "",
    ]
    for item in result["code_origin"]:
        lines.append(f"- {item}")

    lines.extend(["", "## 2. Active By Symbol/Direction", "", "| Pair | Active | Duplicates blocked | Oldest published at |", "|---|---:|---:|---|"])
    for row in result["active_by_symbol_direction"]:
        lines.append(
            f"| {_md_cell(row['pair'])} | {row['active_count']} | {row['duplicates_blocked']} | {row['oldest_published_at']} |"
        )
    if not result["active_by_symbol_direction"]:
        lines.append("| no_data | 0 | 0 | n/a |")

    lines.extend(
        [
            "",
            "## 3. Active Signals",
            "",
            "| Signal | Pair | Published at | Age h | Entry | SL | TP | Status | Lifecycle | Expiration | Close reason | Duplicates |",
            "|---|---|---|---:|---:|---:|---:|---|---|---|---|---:|",
        ]
    )
    for row in result["active_signals"]:
        lines.append(
            f"| `{row['id']}` | {_md_cell(row['pair'])} | {row['published_at']} | {row['age_hours']} | "
            f"{row['entry']} | {row['stop_loss']} | {row['take_profit']} | {row['status']} | "
            f"{row['lifecycle_status']} | {row['expires_at'] or 'missing'} | {row['close_reason'] or 'missing'} | "
            f"{row['duplicates_blocked']} |"
        )
    if not result["active_signals"]:
        lines.append("| no_data | n/a | n/a | 0 | 0 | 0 | 0 | n/a | n/a | n/a | n/a | 0 |")

    lines.extend(
        [
            "",
            "## 4. Duplicate Attribution",
            "",
            "| Active key | Signal | Pair | Duplicates | Score >= 90 | Latest duplicate |",
            "|---|---|---|---:|---:|---|",
        ]
    )
    for row in result["duplicates_blocked_by_active_signal"]:
        lines.append(
            f"| `{_md_cell(row['active_key'])}` | `{row['signal_id']}` | {_md_cell(row['pair'])} | {row['duplicates_blocked']} | "
            f"{row['duplicate_score_gte_90']} | {row['latest_duplicate_at']} |"
        )
    if not result["duplicates_blocked_by_active_signal"]:
        lines.append("| no_data | n/a | n/a | 0 | 0 | n/a |")

    storage = result["storage_mix"]
    lines.extend(
        [
            "",
            "## 5. Store Mixing",
            "",
            f"- trade_signals total: {storage['trade_signals_total']}",
            f"- published: {storage['published']}",
            f"- rejected: {storage['rejected']}",
            f"- valid_unpublished: {storage['valid_unpublished']}",
            f"- published and rejected mixed in same store: {storage['published_and_rejected_mixed_in_same_store']}",
            "",
            "## 6. Closure / Invalidation",
            "",
        ]
    )
    for item in result["closure_capability"]["findings"]:
        lines.append(f"- {item}")
    lines.extend(["", "### Current price invalidation", ""])
    for item in result["current_price_invalidation"]["findings"]:
        lines.append(f"- {item}")

    lines.extend(["", "## 7. Data Gaps", ""])
    for item in result["data_gaps"]:
        lines.append(f"- {item}")
    if not result["data_gaps"]:
        lines.append("- none")

    lines.extend(["", "## 8. Actionable Conclusion", "", f"Recommended action: **{result['conclusion']['recommended_action']}**", ""])
    for item in result["conclusion"]["reasons"]:
        lines.append(f"- {item}")
    lines.extend(["", "### Actions explicitly not taken", "", "- No files deleted.", "- No active signals closed.", "- No duplicate publication enabled.", "- No Telegram public changes."])
    return "\n".join(lines) + "\n"


def _build_active_signals(
    published: list[dict[str, Any]],
    *,
    risk_plans: dict[str, dict[str, Any]],
    deliveries: list[dict[str, Any]],
    now: datetime,
) -> list[dict[str, Any]]:
    delivery_by_signal = defaultdict(list)
    for delivery in deliveries:
        delivery_by_signal[str(delivery.get("signal_id") or "")].append(delivery)
    active = []
    for signal in published:
        risk = risk_plans.get(str(signal.get("risk_plan_id") or ""), {})
        delivery_values = _extract_trade_values_from_deliveries(delivery_by_signal.get(str(signal.get("id") or ""), []))
        published_at = str(signal.get("published_at") or "")
        pair = f"{signal.get('symbol')}|{signal.get('decision')}"
        active.append(
            {
                "id": signal.get("id"),
                "pair": pair,
                "symbol": signal.get("symbol"),
                "direction": signal.get("decision"),
                "dedupe_key": signal.get("dedupe_key"),
                "active_key": pair,
                "created_at": signal.get("created_at"),
                "published_at": published_at,
                "age_hours": _age_hours(published_at, now),
                "entry": _first_value(risk.get("entry"), delivery_values.get("entry")),
                "stop_loss": _first_value(risk.get("stop_loss"), delivery_values.get("stop_loss")),
                "take_profit": _first_value(risk.get("take_profit"), delivery_values.get("take_profit")),
                "expires_at": signal.get("expires_at"),
                "status": signal.get("status"),
                "lifecycle_status": signal.get("lifecycle_status") or signal.get("signal_type"),
                "close_reason": signal.get("close_reason") or signal.get("exit_reason"),
                "risk_plan_id": signal.get("risk_plan_id"),
                "has_risk_plan": bool(risk),
                "deliveries_count": len(delivery_by_signal.get(str(signal.get("id") or ""), [])),
            }
        )
    return active


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|")


def _duplicate_events(*, signals_log: list[dict[str, Any]], scheduler_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    for row in signals_log:
        if _contains(row, TARGET_DUPLICATE):
            events.append(_normalize_duplicate(row, "signals_log"))
    for row in scheduler_events:
        if _contains(row, TARGET_DUPLICATE):
            events.append(_normalize_duplicate(row, "scheduler_log"))
    return _dedupe(events)


def _normalize_duplicate(row: dict[str, Any], source: str) -> dict[str, Any]:
    raw = row.get("raw_summary") if isinstance(row.get("raw_summary"), dict) else {}
    return {
        "source": source,
        "timestamp": row.get("timestamp") or row.get("created_at"),
        "symbol": _text(row.get("symbol")),
        "direction": _text(row.get("direction") or row.get("decision")),
        "score": _float(row.get("score") or row.get("setup_score_final")),
        "setup_type": _text(row.get("setup_type") or raw.get("setup_type")),
        "dedupe_key": _signal_dedupe_key(row, raw),
    }


def _duplicates_by_active_signal(active: list[dict[str, Any]], duplicates: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    active_pairs = {str(item["pair"]) for item in active}
    stats: dict[str, dict[str, Any]] = {}
    for pair in active_pairs:
        rows = [row for row in duplicates if f"{row.get('symbol')}|{row.get('direction')}" == pair]
        timestamps = sorted(str(row.get("timestamp") or "") for row in rows if row.get("timestamp"))
        stats[pair] = {
            "count": len(rows),
            "score_gte_90": sum(1 for row in rows if (_float(row.get("score")) or 0) >= 90),
            "latest_duplicate_at": timestamps[-1] if timestamps else None,
        }
    return stats


def _active_by_pair(active: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in active:
        grouped[str(item["pair"])].append(item)
    rows = []
    for pair, items in grouped.items():
        rows.append(
            {
                "pair": pair,
                "active_count": len(items),
                "duplicates_blocked": sum(int(item.get("duplicates_blocked") or 0) for item in items),
                "oldest_published_at": min(str(item.get("published_at") or "") for item in items),
                "latest_published_at": max(str(item.get("published_at") or "") for item in items),
            }
        )
    return sorted(rows, key=lambda row: row["duplicates_blocked"], reverse=True)


def _duplicate_block_rows(active: list[dict[str, Any]], *, top: int) -> list[dict[str, Any]]:
    rows = [
        {
            "active_key": item["active_key"],
            "signal_id": item["id"],
            "pair": item["pair"],
            "duplicates_blocked": item.get("duplicates_blocked", 0),
            "duplicate_score_gte_90": item.get("duplicate_score_gte_90", 0),
            "latest_duplicate_at": item.get("latest_duplicate_at"),
        }
        for item in active
    ]
    return sorted(rows, key=lambda row: row["duplicates_blocked"], reverse=True)[:top]


def _closure_capability(active: list[dict[str, Any]]) -> dict[str, Any]:
    findings = [
        "`signal_lifecycle.py` only reads published signals and returns NEW/REENTRY/DUPLICATE; it does not clean or expire active records.",
        "`trade_signals` published records do not store TP/SL/expiration close state directly.",
        "Live/paper outcomes may exist elsewhere, but lifecycle active state is not derived from those close events.",
    ]
    if any(item.get("close_reason") for item in active):
        findings.append("Some active records contain close_reason, but this is not enforced by active_published_signals().")
    else:
        findings.append("No active published signal has close_reason in the inspected data.")
    return {"can_close_active_signals_from_lifecycle": False, "findings": findings}


def _current_price_invalidation(active: list[dict[str, Any]], scheduler_events: list[dict[str, Any]]) -> dict[str, Any]:
    latest_price_by_symbol = {}
    for event in scheduler_events:
        symbol = event.get("symbol")
        price = _float(event.get("current_price"))
        if symbol and price is not None:
            latest_price_by_symbol[str(symbol)] = price
    findings = []
    invalidated = []
    for item in active:
        price = latest_price_by_symbol.get(str(item.get("symbol")))
        entry = _float(item.get("entry"))
        stop = _float(item.get("stop_loss"))
        take = _float(item.get("take_profit"))
        direction = str(item.get("direction") or "").lower()
        if price is None or entry is None or stop is None or take is None:
            continue
        hit_sl = price <= stop if direction == "long" else price >= stop
        hit_tp = price >= take if direction == "long" else price <= take
        if hit_sl or hit_tp:
            invalidated.append({"signal_id": item.get("id"), "symbol": item.get("symbol"), "direction": direction, "current_price": price, "hit_sl": hit_sl, "hit_tp": hit_tp})
    if not latest_price_by_symbol:
        findings.append("No current_price values found in scheduler logs; price invalidation cannot be evaluated.")
    if not invalidated:
        findings.append("No active signal could be proven invalidated from available current_price + entry/SL/TP data.")
    else:
        findings.append(f"{len(invalidated)} active signals appear invalidated by latest available current_price.")
    return {"latest_price_symbols": len(latest_price_by_symbol), "potential_invalidations": invalidated, "findings": findings}


def _data_gaps(
    active: list[dict[str, Any]],
    duplicates: list[dict[str, Any]],
    risk_plans: dict[str, dict[str, Any]],
    deliveries: list[dict[str, Any]],
) -> list[str]:
    gaps = []
    if not active:
        gaps.append("No published signals found, so active lifecycle state cannot be audited.")
    if not duplicates:
        gaps.append("No duplicate_signal_suppressed events found in local logs/signals_log.")
    if any(not item.get("expires_at") for item in active):
        gaps.append("Active published signals lack explicit expires_at.")
    if any(not item.get("close_reason") for item in active):
        gaps.append("Active published signals lack close_reason/exit_reason.")
    if any(not item.get("has_risk_plan") for item in active):
        gaps.append("Some active signals do not have readable risk_plan records.")
    if not deliveries:
        gaps.append("No signal_deliveries found; message payload fallback for entry/SL/TP unavailable.")
    if not risk_plans:
        gaps.append("No risk_plans found; entry/SL/TP availability is limited.")
    return gaps


def _conclusion(active: list[dict[str, Any]], duplicates: list[dict[str, Any]], active_by_pair: list[dict[str, Any]]) -> dict[str, Any]:
    reasons = []
    recommendation = "datos insuficientes"
    if active and any(not item.get("expires_at") for item in active):
        recommendation = "añadir expiration cleanup"
        reasons.append("Las señales publicadas se consideran activas por published_at y same symbol/direction, pero no tienen expiration explícita.")
    if active and any(not item.get("close_reason") for item in active):
        reasons.append("No hay close_reason en señales activas; lifecycle no sabe si TP/SL/expiration ya cerró la idea.")
    if duplicates and active_by_pair and active_by_pair[0]["duplicates_blocked"] > 0:
        reasons.append("Hay duplicados atribuidos a señales activas; antes de permitir reentry conviene registrar/limpiar estado activo.")
    if len(active) and len(active) < len(active_by_pair):
        reasons.append("Hay mezcla de múltiples señales activas por par; revisar max_reentries.")
    if not reasons:
        reasons.append("No hay evidencia suficiente para cambiar lifecycle.")
    return {
        "recommended_action": recommendation,
        "options_considered": [
            "mantener lifecycle",
            "añadir expiration cleanup",
            "añadir invalidation cleanup",
            "separar active store de historical rejected store",
            "permitir reentry controlado",
            "datos insuficientes",
        ],
        "reasons": reasons,
    }


def _code_origin() -> list[str]:
    return [
        "`active_published_signals()` treats any latest-500 `trade_signals` record with `published_at` and same symbol/direction as active.",
        "`signal_lifecycle.py` blocks when active count is too high or reentry confirmation fails; it does not expire or close active signals.",
        "`run_market_scan.py` saves published signals with `status=published` and `published_at`, but no lifecycle expiration is stored there.",
        "`trade_signals` stores rejected, valid-unpublished and published records together by date folders.",
    ]


def _extract_trade_values_from_deliveries(deliveries: list[dict[str, Any]]) -> dict[str, Any]:
    text = "\n".join(str((delivery.get("payload") or {}).get("message") or "") for delivery in deliveries if isinstance(delivery.get("payload"), dict))
    return {
        "entry": _regex_number(text, r"Entry:\s*([0-9]+(?:\.[0-9]+)?)"),
        "stop_loss": _regex_number(text, r"Stop Loss:\s*([0-9]+(?:\.[0-9]+)?)"),
        "take_profit": _regex_number(text, r"Take Profit:\s*([0-9]+(?:\.[0-9]+)?)"),
    }


def _regex_number(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return _float(match.group(1)) if match else None


def _load_json_files(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for file_path in sorted(path.glob("**/*.json")):
        try:
            parsed = json.loads(file_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _load_scheduler_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parsed = _parse_json_line(line)
        if parsed:
            rows.append(parsed)
    return rows


def _parse_json_line(line: str) -> dict[str, Any] | None:
    raw = line.strip()
    candidates = [raw]
    brace = raw.find("{")
    if brace > 0:
        candidates.append(raw[brace:])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    output = []
    for row in rows:
        key = (row.get("timestamp"), row.get("symbol"), row.get("direction"), row.get("score"), row.get("source"))
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def _contains(value: Any, needle: str) -> bool:
    if isinstance(value, dict):
        return any(_contains(child, needle) for child in value.values())
    if isinstance(value, list):
        return any(_contains(child, needle) for child in value)
    return needle in str(value)


def _signal_dedupe_key(row: dict[str, Any], raw: dict[str, Any]) -> str:
    for value in (row.get("signal_dedupe_key"), raw.get("signal_dedupe_key"), raw.get("dedupe_key")):
        text = str(value or "").strip()
        if "|" in text:
            return text
    return ""


def _oldest_age_hours(active: list[dict[str, Any]]) -> float:
    ages = [_float(item.get("age_hours")) for item in active if _float(item.get("age_hours")) is not None]
    return round(max(ages), 2) if ages else 0.0


def _age_hours(timestamp: str, now: datetime) -> float | None:
    parsed = _parse_datetime(timestamp)
    if parsed is None:
        return None
    return round((now - parsed).total_seconds() / 3600, 2)


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _first_value(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _text(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "UNKNOWN"


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze(data_path=args.data_path, logs_path=args.logs_path, reports_path=args.reports_path, top=args.top)
    paths = write_reports(result, args.reports_path)
    print("ACTIVE_SIGNAL_LIFECYCLE_AUDIT_V1")
    print(f"- active_signals_count: {result['metrics']['active_signals_count']}")
    print(f"- duplicate_signal_suppressed_events: {result['metrics']['duplicate_signal_suppressed_events']}")
    print(f"- active_without_expiration: {result['metrics']['active_without_expiration']}")
    print(f"- recommendation: {result['conclusion']['recommended_action']}")
    print(f"- Markdown: {paths['markdown']}")
    print(f"- JSON: {paths['json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
