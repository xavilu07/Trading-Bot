#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.application.use_cases.active_signal_cleanup_shadow_v1 import (
    CLEANUP_LIKELY_ZOMBIE,
    CLEANUP_STALE,
    classify_active_signal_for_cleanup,
)


TARGET_DUPLICATE = "duplicate_signal_suppressed"
REPORT_JSON = "active_signal_cleanup_shadow_v1.json"
REPORT_MD = "active_signal_cleanup_shadow_v1.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    root = Path(os.getenv("BOT_DATA_DIR", "."))
    parser = argparse.ArgumentParser(description="Analyze shadow cleanup opportunities for active/zombie signals.")
    parser.add_argument("--data-path", type=Path, default=root / "data")
    parser.add_argument("--logs-path", type=Path, default=root / "logs")
    parser.add_argument("--reports-path", type=Path, default=root / "reports")
    return parser.parse_args(argv)


def analyze(*, data_path: Path, logs_path: Path, reports_path: Path | None = None) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    trade_signals = _load_json_files(data_path / "trade_signals")
    signals_log = _load_jsonl(data_path / "bot_activity" / "signals_log.jsonl")
    scheduler_events = _load_scheduler_events(logs_path / "scheduler.log")
    published = [row for row in trade_signals if row.get("published_at")]
    active_assessments = [classify_active_signal_for_cleanup(row, now=now).to_dict() for row in published]
    duplicates = _duplicate_events(signals_log=signals_log, scheduler_events=scheduler_events)
    runtime_events = _runtime_cleanup_events(scheduler_events)
    duplicates_by_pair = _duplicates_by_pair(duplicates)
    pairs_with_likely_zombie = {
        str(row.get("active_key"))
        for row in active_assessments
        if row.get("classification") == CLEANUP_LIKELY_ZOMBIE
    }
    pairs_with_stale = {
        str(row.get("active_key"))
        for row in active_assessments
        if row.get("classification") == CLEANUP_STALE
    }
    affected = _affected_pairs(
        active_assessments=active_assessments,
        duplicates_by_pair=duplicates_by_pair,
        pairs_with_likely_zombie=pairs_with_likely_zombie,
        pairs_with_stale=pairs_with_stale,
    )
    duplicates_blocked_by_likely_zombie = sum(
        duplicates_by_pair.get(pair, {}).get("count", 0) for pair in pairs_with_likely_zombie
    )
    high_score_duplicates_blocked_by_likely_zombie = sum(
        duplicates_by_pair.get(pair, {}).get("score_gte_90", 0) for pair in pairs_with_likely_zombie
    )
    result = {
        "scope": "ACTIVE_SIGNAL_CLEANUP_SHADOW_V1",
        "generated_at": now.isoformat(timespec="seconds"),
        "mode": "shadow_diagnostic_only",
        "production_changed": False,
        "source_files": {
            "trade_signals_dir": str(data_path / "trade_signals"),
            "signals_log": str(data_path / "bot_activity" / "signals_log.jsonl"),
            "scheduler_log": str(logs_path / "scheduler.log"),
        },
        "metrics": {
            "total_active_signals": len(active_assessments),
            "likely_zombie_count": sum(1 for row in active_assessments if row.get("classification") == CLEANUP_LIKELY_ZOMBIE),
            "stale_count": sum(1 for row in active_assessments if row.get("classification") == CLEANUP_STALE),
            "recent_count": sum(1 for row in active_assessments if row.get("classification") == "RECENT"),
            "unknown_count": sum(1 for row in active_assessments if row.get("classification") == "UNKNOWN"),
            "duplicate_signal_suppressed_events": len(duplicates),
            "duplicates_blocked_by_likely_zombie": duplicates_blocked_by_likely_zombie,
            "high_score_duplicates_blocked_by_likely_zombie": high_score_duplicates_blocked_by_likely_zombie,
            "estimated_released_candidates_if_cleanup": duplicates_blocked_by_likely_zombie,
            "runtime_cleanup_analysis_events": len(runtime_events["analysis"]),
            "runtime_cleanup_candidate_events": len(runtime_events["candidate"]),
        },
        "affected_symbol_direction": affected,
        "active_signals": sorted(
            active_assessments,
            key=lambda row: (row.get("classification") != CLEANUP_LIKELY_ZOMBIE, -(float(row.get("age_hours") or 0))),
        ),
        "runtime_events": runtime_events,
        "conclusion": _conclusion(
            likely_zombie_count=sum(1 for row in active_assessments if row.get("classification") == CLEANUP_LIKELY_ZOMBIE),
            duplicates_blocked_by_likely_zombie=duplicates_blocked_by_likely_zombie,
            total_active=len(active_assessments),
        ),
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
        "# ACTIVE_SIGNAL_CLEANUP_SHADOW_V1",
        "",
        f"Generated at: {result['generated_at']}",
        "Mode: shadow diagnostic only. No active signal was closed, deleted, expired or republished.",
        "",
        "## Executive Summary",
        "",
        f"- Total active signals: {metrics['total_active_signals']}",
        f"- Likely zombie count: {metrics['likely_zombie_count']}",
        f"- Stale count: {metrics['stale_count']}",
        f"- duplicate_signal_suppressed events: {metrics['duplicate_signal_suppressed_events']}",
        f"- Duplicates blocked by likely zombie: {metrics['duplicates_blocked_by_likely_zombie']}",
        f"- High score duplicates blocked by likely zombie: {metrics['high_score_duplicates_blocked_by_likely_zombie']}",
        f"- Estimated released candidates if cleanup: {metrics['estimated_released_candidates_if_cleanup']}",
        f"- Runtime cleanup analysis events: {metrics['runtime_cleanup_analysis_events']}",
        f"- Runtime cleanup candidate events: {metrics['runtime_cleanup_candidate_events']}",
        f"- Recommendation: {result['conclusion']['recommended_action']}",
        "",
        "## Affected Symbol/Direction",
        "",
        "| Pair | Active | Likely zombies | Stale | Duplicates | Score >= 90 duplicates |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in result["affected_symbol_direction"]:
        lines.append(
            f"| {_md_cell(row['pair'])} | {row['active_count']} | {row['likely_zombie_count']} | {row['stale_count']} | "
            f"{row['duplicates_blocked']} | {row['score_gte_90_duplicates']} |"
        )
    if not result["affected_symbol_direction"]:
        lines.append("| no_data | 0 | 0 | 0 | 0 | 0 |")

    lines.extend(
        [
            "",
            "## Active Signal Classifications",
            "",
            "| Signal | Pair | Classification | Age h | Published at | Expires at | Close reason | Reasons |",
            "|---|---|---|---:|---|---|---|---|",
        ]
    )
    for row in result["active_signals"]:
        lines.append(
            f"| `{row['signal_id']}` | {_md_cell(row['active_key'])} | {row['classification']} | {row['age_hours']} | "
            f"{row['published_at'] or 'missing'} | {row['expires_at'] or 'missing'} | {row['close_reason'] or 'missing'} | "
            f"{', '.join(row['reasons'])} |"
        )
    if not result["active_signals"]:
        lines.append("| no_data | n/a | UNKNOWN | n/a | n/a | n/a | n/a | n/a |")

    lines.extend(["", "## Runtime Shadow Logs", ""])
    lines.append(f"- `active_signal_cleanup_shadow_analysis`: {metrics['runtime_cleanup_analysis_events']}")
    lines.append(f"- `active_signal_cleanup_shadow_candidate`: {metrics['runtime_cleanup_candidate_events']}")

    lines.extend(["", "## Actionable Conclusion", "", f"Recommended action: **{result['conclusion']['recommended_action']}**", ""])
    for reason in result["conclusion"]["reasons"]:
        lines.append(f"- {reason}")
    lines.extend(
        [
            "",
            "### Actions explicitly not taken",
            "",
            "- No files deleted.",
            "- No active signals closed.",
            "- No duplicate publication enabled.",
            "- No Telegram public changes.",
        ]
    )
    return "\n".join(lines) + "\n"


def _affected_pairs(
    *,
    active_assessments: list[dict[str, Any]],
    duplicates_by_pair: dict[str, dict[str, int]],
    pairs_with_likely_zombie: set[str],
    pairs_with_stale: set[str],
) -> list[dict[str, Any]]:
    active_by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in active_assessments:
        active_by_pair[str(row.get("active_key"))].append(row)
    pairs = set(active_by_pair) | set(duplicates_by_pair)
    rows = []
    for pair in sorted(pairs):
        active_rows = active_by_pair.get(pair, [])
        duplicate_stats = duplicates_by_pair.get(pair, {})
        rows.append(
            {
                "pair": pair,
                "active_count": len(active_rows),
                "likely_zombie_count": sum(1 for row in active_rows if row.get("classification") == CLEANUP_LIKELY_ZOMBIE),
                "stale_count": sum(1 for row in active_rows if row.get("classification") == CLEANUP_STALE),
                "duplicates_blocked": duplicate_stats.get("count", 0),
                "score_gte_90_duplicates": duplicate_stats.get("score_gte_90", 0),
                "cleanup_would_release": pair in pairs_with_likely_zombie or pair in pairs_with_stale,
            }
        )
    return sorted(rows, key=lambda row: row["duplicates_blocked"], reverse=True)


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
    }


def _duplicates_by_pair(duplicates: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    grouped: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "score_gte_90": 0})
    for row in duplicates:
        pair = f"{row.get('symbol')}|{row.get('direction')}"
        grouped[pair]["count"] += 1
        if (_float(row.get("score")) or 0) >= 90:
            grouped[pair]["score_gte_90"] += 1
    return dict(grouped)


def _runtime_cleanup_events(scheduler_events: list[dict[str, Any]]) -> dict[str, Any]:
    analysis = [row for row in scheduler_events if row.get("event") == "active_signal_cleanup_shadow_analysis"]
    candidate = [row for row in scheduler_events if row.get("event") == "active_signal_cleanup_shadow_candidate"]
    return {
        "analysis": analysis[-20:],
        "candidate": candidate[-20:],
        "analysis_by_classification": dict(Counter(str(row.get("cleanup_classification") or "UNKNOWN") for row in analysis).most_common()),
        "candidate_by_classification": dict(Counter(str(row.get("cleanup_classification") or "UNKNOWN") for row in candidate).most_common()),
    }


def _conclusion(*, likely_zombie_count: int, duplicates_blocked_by_likely_zombie: int, total_active: int) -> dict[str, Any]:
    if likely_zombie_count > 0 and duplicates_blocked_by_likely_zombie > 0:
        action = "activar cleanup real"
        reasons = [
            "Hay señales activas clasificadas como LIKELY_ZOMBIE que están bloqueando candidatos nuevos.",
            "El siguiente paso seguro sería implementar cleanup real detrás de flag, no permitir duplicados directamente.",
        ]
    elif likely_zombie_count > 0:
        action = "mantener shadow"
        reasons = [
            "Hay señales LIKELY_ZOMBIE, pero no se observaron duplicados bloqueados atribuibles con los datos actuales.",
        ]
    elif total_active == 0:
        action = "datos insuficientes"
        reasons = ["No hay señales activas publicadas para evaluar cleanup."]
    else:
        action = "mantener shadow"
        reasons = ["No hay evidencia suficiente de zombies bloqueando candidatos."]
    return {
        "recommended_action": action,
        "options_considered": ["activar cleanup real", "mantener shadow", "datos insuficientes"],
        "reasons": reasons,
    }


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


def _contains(value: Any, needle: str) -> bool:
    if isinstance(value, dict):
        return any(_contains(child, needle) for child in value.values())
    if isinstance(value, list):
        return any(_contains(child, needle) for child in value)
    return needle in str(value)


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


def _text(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "UNKNOWN"


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _md_cell(value: Any) -> str:
    return str(value).replace("|", "\\|")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze(data_path=args.data_path, logs_path=args.logs_path, reports_path=args.reports_path)
    paths = write_reports(result, args.reports_path)
    print("ACTIVE_SIGNAL_CLEANUP_SHADOW_V1")
    print(f"- total_active_signals: {result['metrics']['total_active_signals']}")
    print(f"- likely_zombie_count: {result['metrics']['likely_zombie_count']}")
    print(f"- duplicates_blocked_by_likely_zombie: {result['metrics']['duplicates_blocked_by_likely_zombie']}")
    print(f"- estimated_released_candidates_if_cleanup: {result['metrics']['estimated_released_candidates_if_cleanup']}")
    print(f"- recommendation: {result['conclusion']['recommended_action']}")
    print(f"- Markdown: {paths['markdown']}")
    print(f"- JSON: {paths['json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
