#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any


TARGET_DUPLICATE = "duplicate_signal_suppressed"
TARGET_PAPER_DUPLICATE = "paper_rejected_duplicate"
UPDATE_TYPES = ("STRENGTHENED_SIGNAL", "REENTRY_CANDIDATE", "INVALIDATION_WARNING", "NO_UPDATE")
REPORT_JSON = "lifecycle_dedupe_deep_dive_v1.json"
REPORT_MD = "lifecycle_dedupe_deep_dive_v1.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    root = Path(os.getenv("BOT_DATA_DIR", "."))
    parser = argparse.ArgumentParser(description="Offline lifecycle/dedupe deep dive diagnostics.")
    parser.add_argument("--data-path", type=Path, default=root / "data")
    parser.add_argument("--logs-path", type=Path, default=root / "logs")
    parser.add_argument("--reports-path", type=Path, default=root / "reports")
    parser.add_argument("--top", type=int, default=15)
    return parser.parse_args(argv)


def analyze(
    *,
    data_path: Path,
    logs_path: Path,
    reports_path: Path,
    top: int = 15,
) -> dict[str, Any]:
    signals_log = _load_jsonl(data_path / "bot_activity" / "signals_log.jsonl")
    scheduler_events = _load_scheduler_events(logs_path / "scheduler.log")
    trade_signals = _load_json_files(data_path / "trade_signals")
    deliveries = _load_json_files(data_path / "signal_deliveries")
    paper_trades = _load_csv(data_path / "paper_trading" / "trades.csv")
    signal_update_report = _load_json(reports_path / "signal_update_v1_shadow.json")

    duplicate_events = _collect_duplicate_events(signals_log, scheduler_events)
    paper_duplicate_events = _collect_paper_duplicate_events(scheduler_events, paper_trades)
    published_signals = [row for row in trade_signals if row.get("published_at")]
    active_signal_state = _active_signal_state(published_signals)
    signal_update = _signal_update_summary(signal_update_report, scheduler_events)
    lifecycle = _lifecycle_summary(scheduler_events)
    dedupe_width = _dedupe_width_analysis(duplicate_events, published_signals, active_signal_state, top=top)
    severe = _severe_cases(duplicate_events, signal_update, top=top)
    paper = _paper_duplicate_summary(paper_duplicate_events, paper_trades, top=top)

    result = {
        "scope": "LIFECYCLE_DEDUPE_DEEP_DIVE_V1",
        "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "mode": "offline_diagnostic_only",
        "production_changed": False,
        "source_files": {
            "scheduler_log": str(logs_path / "scheduler.log"),
            "signals_log": str(data_path / "bot_activity" / "signals_log.jsonl"),
            "trade_signals_dir": str(data_path / "trade_signals"),
            "signal_deliveries_dir": str(data_path / "signal_deliveries"),
            "paper_trades": str(data_path / "paper_trading" / "trades.csv"),
            "signal_update_shadow": str(reports_path / "signal_update_v1_shadow.json"),
        },
        "code_origin": _code_origin(),
        "source_counts": {
            "signals_log_rows": len(signals_log),
            "scheduler_json_events": len(scheduler_events),
            "trade_signals_json": len(trade_signals),
            "published_trade_signals": len(published_signals),
            "signal_deliveries_json": len(deliveries),
            "paper_trade_rows": len(paper_trades),
            "duplicate_signal_suppressed": len(duplicate_events),
            "paper_rejected_duplicate": len(paper_duplicate_events),
        },
        "metrics": {
            "total_duplicate_signal_suppressed": len(duplicate_events),
            "total_paper_rejected_duplicate": len(paper_duplicate_events),
            "score_gte_90": severe["score_gte_90"]["count"],
            "rr_valid": severe["rr_valid"]["count"],
            "directional_confluence_passed": severe["directional_confluence_passed"]["count"],
            "new_snapshot_distinct": signal_update["new_snapshot_true"],
            "would_be_reentry_candidate": signal_update["by_update_type"].get("REENTRY_CANDIDATE", 0),
            "would_be_strengthened_signal": signal_update["by_update_type"].get("STRENGTHENED_SIGNAL", 0),
            "no_material_update": signal_update["by_update_type"].get("NO_UPDATE", 0),
        },
        "breakdowns": _breakdowns(duplicate_events, top=top),
        "paper_duplicate_breakdowns": paper["breakdowns"],
        "severe_cases": severe,
        "dedupe_width_analysis": dedupe_width,
        "active_signal_state": active_signal_state,
        "lifecycle_summary": lifecycle,
        "signal_update_v1_summary": signal_update,
        "paper_duplicate_summary": paper,
        "data_gaps": _data_gaps(
            duplicate_events=duplicate_events,
            paper_duplicate_events=paper_duplicate_events,
            published_signals=published_signals,
            signal_update=signal_update,
            active_signal_state=active_signal_state,
        ),
        "conclusion": _conclusion(
            duplicate_events=duplicate_events,
            paper_duplicate_events=paper_duplicate_events,
            signal_update=signal_update,
            dedupe_width=dedupe_width,
            active_signal_state=active_signal_state,
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
    lines = [
        "# LIFECYCLE_DEDUPE_DEEP_DIVE_V1",
        "",
        f"Generated at: {result['generated_at']}",
        "Mode: offline diagnostic only. No production behavior changed.",
        "",
        "## Executive Summary",
        "",
        f"- duplicate_signal_suppressed: {result['metrics']['total_duplicate_signal_suppressed']}",
        f"- paper_rejected_duplicate: {result['metrics']['total_paper_rejected_duplicate']}",
        f"- score >= 90 duplicates: {result['metrics']['score_gte_90']}",
        f"- RR valid duplicates: {result['metrics']['rr_valid']}",
        f"- Directional confluence passed duplicates: {result['metrics']['directional_confluence_passed']}",
        f"- SIGNAL_UPDATE_V1 events: {result['signal_update_v1_summary']['total_events']}",
        f"- Recommendation: {result['conclusion']['recommended_action']}",
        "",
        "## 1. Code Origin",
        "",
    ]
    for item in result["code_origin"]["duplicate_signal_suppressed"]:
        lines.append(f"- {item}")
    lines.extend(["", "### paper_rejected_duplicate", ""])
    for item in result["code_origin"]["paper_rejected_duplicate"]:
        lines.append(f"- {item}")
    lines.extend(["", "### Active signal state", ""])
    for item in result["code_origin"]["active_signal_state"]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## 2. Source Counts",
            "",
            "| Source | Count |",
            "|---|---:|",
        ]
    )
    for key, value in result["source_counts"].items():
        lines.append(f"| {key} | {value} |")

    lines.extend(["", "## 3. Dedupe Width", ""])
    dedupe = result["dedupe_width_analysis"]
    lines.extend(
        [
            f"- Events analyzed: {dedupe['events_analyzed']}",
            f"- Exact dedupe key matches: {dedupe['exact_key_matches']}",
            f"- Missing dedupe key events: {dedupe['missing_dedupe_key_events']}",
            f"- Broad symbol+direction active matches: {dedupe['broad_symbol_direction_active_matches']}",
            f"- Potentially too broad: {dedupe['potentially_too_broad']}",
            "",
            "### Top symbol+direction pairs",
            "",
            "| Pair | Duplicates | Published refs |",
            "|---|---:|---:|",
        ]
    )
    for row in dedupe["top_symbol_direction_pairs"]:
        lines.append(f"| {row['pair']} | {row['count']} | {row['published_refs']} |")
    if not dedupe["top_symbol_direction_pairs"]:
        lines.append("| no_data | 0 | 0 |")

    lines.extend(["", "## 4. Duplicate Breakdowns", ""])
    for dimension, rows in result["breakdowns"].items():
        lines.extend([f"### {dimension}", "", "| Value | Count | Avg score | Score >= 90 | RR valid | Confluence passed |", "|---|---:|---:|---:|---:|---:|"])
        for row in rows:
            lines.append(
                f"| {row['value']} | {row['count']} | {row['avg_score']} | {row['score_gte_90']} | "
                f"{row['rr_valid']} | {row['directional_confluence_passed']} |"
            )
        if not rows:
            lines.append("| no_data | 0 | 0 | 0 | 0 | 0 |")
        lines.append("")

    lines.extend(
        [
            "## 5. Severe Cases",
            "",
            f"- Score >= 70: {result['severe_cases']['score_gte_70']['count']}",
            f"- Score >= 80: {result['severe_cases']['score_gte_80']['count']}",
            f"- Score >= 90: {result['severe_cases']['score_gte_90']['count']}",
            f"- RR valid: {result['severe_cases']['rr_valid']['count']}",
            f"- Directional confluence passed: {result['severe_cases']['directional_confluence_passed']['count']}",
            f"- Signal status valid: {result['severe_cases']['signal_status_valid']['count']}",
            "",
            "### Highest score examples",
            "",
            "| Symbol | Direction | Score | Setup | Session | Regime | Entry context | Reason source |",
            "|---|---|---:|---|---|---|---|---|",
        ]
    )
    for row in result["severe_cases"]["highest_score_examples"]:
        lines.append(
            f"| {row['symbol']} | {row['direction']} | {row['score']} | {row['setup_type']} | "
            f"{row['session']} | {row['market_regime']} | {row['entry_context']} | {row['source']} |"
        )

    lines.extend(["", "## 6. SIGNAL_UPDATE_V1 Coverage", ""])
    update = result["signal_update_v1_summary"]
    lines.extend(
        [
            f"- Total events: {update['total_events']}",
            f"- New snapshot true: {update['new_snapshot_true']}",
            f"- Reentry confirmation true: {update['reentry_confirmation_true']}",
            "",
            "| Update type | Count |",
            "|---|---:|",
        ]
    )
    for update_type in UPDATE_TYPES:
        lines.append(f"| {update_type} | {update['by_update_type'].get(update_type, 0)} |")
    lines.extend(["", "### SIGNAL_UPDATE_V1 assessment", ""])
    for item in update["assessment"]:
        lines.append(f"- {item}")

    lines.extend(["", "## 7. Paper duplicate diagnostics", ""])
    paper = result["paper_duplicate_summary"]
    lines.extend(
        [
            f"- Scheduler paper duplicates: {paper['scheduler_events']}",
            f"- Paper CSV rows containing duplicate reason: {paper['paper_rows_with_duplicate_reason']}",
            f"- Existing open paper trades: {paper['open_paper_trades']}",
            "",
            "| Dimension | Top value | Count |",
            "|---|---|---:|",
        ]
    )
    for dimension, rows in result["paper_duplicate_breakdowns"].items():
        top = rows[0] if rows else {"value": "no_data", "count": 0}
        lines.append(f"| {dimension} | {top['value']} | {top['count']} |")

    lines.extend(["", "## 8. Data gaps", ""])
    for gap in result["data_gaps"]:
        lines.append(f"- {gap}")

    lines.extend(
        [
            "",
            "## 9. Actionable conclusion",
            "",
            f"Recommended action: **{result['conclusion']['recommended_action']}**",
            "",
        ]
    )
    for reason in result["conclusion"]["reasons"]:
        lines.append(f"- {reason}")
    lines.extend(["", "### Actions explicitly not taken", "", "- No duplicate publication enabled.", "- No Telegram public changes.", "- No filter or strategy changes."])
    return "\n".join(lines) + "\n"


def _code_origin() -> dict[str, Any]:
    return {
        "duplicate_signal_suppressed": [
            "`run_market_scan.build_signal_dedupe_key()` builds `symbol|decision|strategy_id|strategy_version|entry_timeframe|entry_snapshot.timestamp`.",
            "`FileSignalRepository.has_published_dedupe_key()` checks latest 500 `trade_signals` for the exact same `dedupe_key` with `published_at`.",
            "`_no_send_reason()` returns `duplicate_signal_suppressed` when a valid publishable signal has exact duplicate=true.",
            "Later in the valid-but-not-published branch, `evaluation.rejection_reasons.append('duplicate_signal_suppressed')` records the block.",
        ],
        "paper_rejected_duplicate": [
            "`PaperTradingStore.upsert_candidate()` rejects if any existing paper trade has the same candidate `dedupe_key`.",
            "`run_market_scan.py` maps that false upsert to `paper_rejected_duplicate` for main paper and candidate paper flows.",
            "Paper dedupe is separate from public signal dedupe; it does not require Telegram publication.",
        ],
        "active_signal_state": [
            "`signal_lifecycle.active_published_signals()` treats any latest-500 signal with matching `symbol`, `decision` and `published_at` as active.",
            "There is no explicit TTL/expiry check in `active_published_signals()`; active state is inferred from published signal records.",
            "`classify_signal_lifecycle()` allows `REENTRY` only when max reentries not exceeded and `has_reentry_confirmation()` passes.",
            "`SIGNAL_UPDATE_V1` observes duplicate/lifecycle blocks only after the valid signal reaches the duplicate/lifecycle branch.",
        ],
        "dedupe_key_formula": "symbol|decision|strategy_id|strategy_version|entry_timeframe|entry_snapshot.timestamp",
        "active_signal_scope": "latest 500 trade_signals, published_at not null, same symbol + direction",
    }


def _collect_duplicate_events(signals_log: list[dict[str, Any]], scheduler_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    for row in signals_log:
        if _contains(row, TARGET_DUPLICATE):
            events.append(_normalize_signal_event(row, "signals_log"))
    for row in scheduler_events:
        if _contains(row, TARGET_DUPLICATE):
            events.append(_normalize_signal_event(row, "scheduler_log"))
    return _dedupe_events(events)


def _collect_paper_duplicate_events(scheduler_events: list[dict[str, Any]], paper_trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = []
    for row in scheduler_events:
        if str(row.get("paper_trade_rejection_reason") or "") == TARGET_PAPER_DUPLICATE or _contains(row, TARGET_PAPER_DUPLICATE):
            events.append(_normalize_paper_event(row, "scheduler_log"))
    for row in paper_trades:
        if _contains(row, TARGET_PAPER_DUPLICATE):
            events.append(_normalize_paper_event(row, "paper_trading_csv"))
    return events


def _normalize_signal_event(row: dict[str, Any], source: str) -> dict[str, Any]:
    raw = row.get("raw_summary") if isinstance(row.get("raw_summary"), dict) else {}
    risk_context = row.get("risk_context") if isinstance(row.get("risk_context"), dict) else {}
    rejection_reasons = _listify(row.get("rejection_reasons")) or _listify(raw.get("rejection_reasons"))
    return {
        "source": source,
        "event": row.get("event"),
        "timestamp": row.get("timestamp") or row.get("created_at") or row.get("recorded_at"),
        "symbol": _text(row.get("symbol")),
        "direction": _text(row.get("direction") or row.get("decision")),
        "setup_type": _text(row.get("setup_type") or raw.get("setup_type")),
        "score": _float(row.get("score") or row.get("setup_score_final") or row.get("current_score")),
        "score_bucket": _score_bucket(_float(row.get("score") or row.get("setup_score_final") or row.get("current_score"))),
        "session": _text(row.get("session")),
        "market_regime": _text(row.get("market_regime")),
        "entry_context": _text(row.get("entry_context")),
        "trade_location": _text(row.get("trade_location")),
        "dedupe_key": _signal_dedupe_key(row, raw),
        "activity_log_dedupe_key": _text(row.get("dedupe_key")),
        "signal_id": _text(row.get("signal_id") or raw.get("signal_id")),
        "signal_status": _text(row.get("signal_status") or raw.get("signal_status")),
        "rejection_reasons": rejection_reasons,
        "conditions_passed": _listify(row.get("conditions_passed")),
        "conditions_failed": _listify(row.get("conditions_failed")),
        "rr_valid": _truthy(row.get("rr_valid") or risk_context.get("rr_valid")),
        "directional_confluence_passed": _directional_confluence_passed(row),
    }


def _normalize_paper_event(row: dict[str, Any], source: str) -> dict[str, Any]:
    risk_context = row.get("risk_context") if isinstance(row.get("risk_context"), dict) else {}
    return {
        "source": source,
        "event": row.get("event"),
        "timestamp": row.get("timestamp") or row.get("opened_at"),
        "symbol": _text(row.get("symbol")),
        "direction": _text(row.get("direction")),
        "setup_type": _text(row.get("setup_type")),
        "score": _float(row.get("score")),
        "score_bucket": _score_bucket(_float(row.get("score"))),
        "session": _text(row.get("session")),
        "market_regime": _text(row.get("market_regime")),
        "entry_context": _text(row.get("entry_context")),
        "trade_location": _text(row.get("trade_location")),
        "paper_trade_rejection_reason": _text(row.get("paper_trade_rejection_reason") or row.get("entry_or_rejection_reason")),
        "dedupe_key": _text(row.get("dedupe_key")),
        "rr_valid": _truthy(row.get("rr_valid") or risk_context.get("rr_valid")),
    }


def _breakdowns(events: list[dict[str, Any]], *, top: int) -> dict[str, list[dict[str, Any]]]:
    dimensions = ["symbol", "direction", "setup_type", "score_bucket", "session", "market_regime", "entry_context", "trade_location"]
    return {dimension: _breakdown(events, dimension, top=top) for dimension in dimensions}


def _breakdown(events: list[dict[str, Any]], dimension: str, *, top: int) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        groups[_text(event.get(dimension))].append(event)
    rows = []
    for value, group in groups.items():
        scores = [_float(item.get("score")) for item in group if _float(item.get("score")) is not None]
        rows.append(
            {
                "value": value,
                "count": len(group),
                "avg_score": round(mean(scores), 4) if scores else 0.0,
                "score_gte_90": sum(1 for item in group if (_float(item.get("score")) or 0) >= 90),
                "rr_valid": sum(1 for item in group if bool(item.get("rr_valid"))),
                "directional_confluence_passed": sum(1 for item in group if bool(item.get("directional_confluence_passed"))),
            }
        )
    return sorted(rows, key=lambda item: item["count"], reverse=True)[:top]


def _severe_cases(events: list[dict[str, Any]], signal_update: dict[str, Any], *, top: int) -> dict[str, Any]:
    def count_where(predicate) -> dict[str, Any]:
        rows = [event for event in events if predicate(event)]
        return {"count": len(rows), "examples": _examples(rows, top=top)}

    high = sorted(events, key=lambda event: _float(event.get("score")) or -1, reverse=True)
    return {
        "score_gte_70": count_where(lambda event: (_float(event.get("score")) or 0) >= 70),
        "score_gte_80": count_where(lambda event: (_float(event.get("score")) or 0) >= 80),
        "score_gte_90": count_where(lambda event: (_float(event.get("score")) or 0) >= 90),
        "rr_valid": count_where(lambda event: bool(event.get("rr_valid"))),
        "directional_confluence_passed": count_where(lambda event: bool(event.get("directional_confluence_passed"))),
        "signal_status_valid": count_where(lambda event: str(event.get("signal_status")).lower() == "valid"),
        "new_snapshot_distinct": signal_update["new_snapshot_true"],
        "highest_score_examples": _examples(high, top=top),
    }


def _examples(events: list[dict[str, Any]], *, top: int) -> list[dict[str, Any]]:
    return [
        {
            "symbol": item.get("symbol"),
            "direction": item.get("direction"),
            "score": item.get("score"),
            "setup_type": item.get("setup_type"),
            "session": item.get("session"),
            "market_regime": item.get("market_regime"),
            "entry_context": item.get("entry_context"),
            "dedupe_key": item.get("dedupe_key"),
            "source": item.get("source"),
        }
        for item in events[:top]
    ]


def _dedupe_width_analysis(
    events: list[dict[str, Any]],
    published_signals: list[dict[str, Any]],
    active_state: dict[str, Any],
    *,
    top: int,
) -> dict[str, Any]:
    published_keys = {str(row.get("dedupe_key") or "") for row in published_signals if row.get("dedupe_key")}
    published_pairs = Counter(f"{row.get('symbol')}|{row.get('decision')}" for row in published_signals if row.get("symbol") and row.get("decision"))
    exact_matches = 0
    missing = 0
    broad_matches = 0
    key_counter: Counter[str] = Counter()
    pair_counter: Counter[str] = Counter()
    for event in events:
        key = str(event.get("dedupe_key") or "")
        if key:
            key_counter[key] += 1
            if key in published_keys:
                exact_matches += 1
        else:
            missing += 1
        pair = f"{event.get('symbol')}|{event.get('direction')}"
        pair_counter[pair] += 1
        if published_pairs.get(pair, 0) > 0:
            broad_matches += 1
    return {
        "events_analyzed": len(events),
        "exact_key_matches": exact_matches,
        "missing_dedupe_key_events": missing,
        "broad_symbol_direction_active_matches": broad_matches,
        "unique_dedupe_keys": len(key_counter),
        "unique_symbol_direction_pairs": len(pair_counter),
        "potentially_too_broad": broad_matches > exact_matches and missing > 0,
        "top_dedupe_keys": [{"dedupe_key": key, "count": count} for key, count in key_counter.most_common(top)],
        "top_symbol_direction_pairs": [
            {"pair": pair, "count": count, "published_refs": published_pairs.get(pair, 0)}
            for pair, count in pair_counter.most_common(top)
        ],
        "published_pair_counts": dict(published_pairs.most_common(top)),
        "active_state_total_pairs": active_state.get("published_symbol_direction_pairs", 0),
    }


def _active_signal_state(published_signals: list[dict[str, Any]]) -> dict[str, Any]:
    by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in published_signals:
        by_pair[f"{row.get('symbol')}|{row.get('decision')}"].append(row)
    stale = []
    for pair, rows in by_pair.items():
        latest = sorted(rows, key=lambda row: str(row.get("published_at") or row.get("created_at") or ""), reverse=True)[0]
        stale.append(
            {
                "pair": pair,
                "published_count": len(rows),
                "latest_published_at": latest.get("published_at"),
                "latest_signal_id": latest.get("id"),
                "latest_dedupe_key": latest.get("dedupe_key"),
            }
        )
    stale.sort(key=lambda item: item["published_count"], reverse=True)
    return {
        "published_signals": len(published_signals),
        "published_symbol_direction_pairs": len(by_pair),
        "active_state_has_explicit_expiration": False,
        "active_state_expiration_source": "none_found_in_trade_signal_schema",
        "active_scope": "latest 500 published trade_signals with same symbol+direction",
        "top_active_pairs": stale[:15],
        "closure_detection": {
            "tp": "not stored on trade_signal active state",
            "sl": "not stored on trade_signal active state",
            "expiration": "not stored on trade_signal active state",
            "invalidation": "not stored on trade_signal active state",
            "manual_lifecycle": "not stored on trade_signal active state",
        },
    }


def _lifecycle_summary(scheduler_events: list[dict[str, Any]]) -> dict[str, Any]:
    lifecycle_reasons = Counter()
    signal_types = Counter()
    for row in scheduler_events:
        reason = row.get("lifecycle_reason") or row.get("reason")
        if reason in {"active_same_symbol_direction_without_reentry", "max_reentries_reached", "pullback_and_confirmation", "new_signal"}:
            lifecycle_reasons[str(reason)] += 1
        signal_type = row.get("signal_type")
        if signal_type:
            signal_types[str(signal_type)] += 1
    return {
        "reasons_from_logs": dict(lifecycle_reasons),
        "signal_types_from_logs": dict(signal_types),
        "distinguishes_exact_same_entry": "exact dedupe handled before lifecycle through has_published_dedupe_key",
        "distinguishes_new_snapshot": "SIGNAL_UPDATE_V1 compares active_dedupe_key != current_dedupe_key when active reference is available",
        "distinguishes_reentry": "has_reentry_confirmation requires pullback_clear and BOS/candle/secondary confirmation",
        "distinguishes_update": "SIGNAL_UPDATE_V1 classifies STRENGTHENED_SIGNAL, REENTRY_CANDIDATE, INVALIDATION_WARNING, NO_UPDATE",
    }


def _signal_update_summary(signal_update_report: dict[str, Any], scheduler_events: list[dict[str, Any]]) -> dict[str, Any]:
    events = []
    report_events = signal_update_report.get("events", [])
    if isinstance(report_events, list):
        events.extend([item for item in report_events if isinstance(item, dict)])
    for row in scheduler_events:
        if row.get("event") in {"signal_update_v1_detected", "signal_update_v1_classified", "signal_update_v1_shadow_decision"}:
            events.append(row)
    by_update_type = Counter(str(row.get("update_type") or "UNKNOWN") for row in events if row.get("update_type"))
    summary = {
        "total_events": len(events),
        "by_update_type": {update_type: by_update_type.get(update_type, 0) for update_type in UPDATE_TYPES},
        "raw_by_update_type": dict(by_update_type),
        "new_snapshot_true": sum(1 for row in events if _truthy(row.get("new_snapshot"))),
        "reentry_confirmation_true": sum(1 for row in events if _truthy(row.get("reentry_confirmation"))),
        "latest_events": events[-10:],
        "report_summary": signal_update_report.get("summary", {}) if isinstance(signal_update_report.get("summary"), dict) else {},
        "assessment": [],
    }
    if not events:
        summary["assessment"].append("No runtime SIGNAL_UPDATE_V1 events found; current duplicate cases are not being captured or local logs predate runtime deployment.")
    if signal_update_report.get("duplicate_signal_suppressed_still_blocks") is True:
        summary["assessment"].append("SIGNAL_UPDATE_V1 report confirms duplicate_signal_suppressed still blocks publication.")
    if summary["total_events"] and not any(summary["by_update_type"].values()):
        summary["assessment"].append("Signal update events exist but no known update_type was parsed.")
    return summary


def _paper_duplicate_summary(events: list[dict[str, Any]], paper_trades: list[dict[str, Any]], *, top: int) -> dict[str, Any]:
    open_trades = [row for row in paper_trades if str(row.get("status") or "").lower() == "open"]
    rows_with_duplicate = [row for row in paper_trades if _contains(row, TARGET_PAPER_DUPLICATE)]
    return {
        "scheduler_events": len(events),
        "paper_rows_with_duplicate_reason": len(rows_with_duplicate),
        "open_paper_trades": len(open_trades),
        "breakdowns": {
            "symbol": _simple_breakdown(events, "symbol", top=top),
            "direction": _simple_breakdown(events, "direction", top=top),
            "session": _simple_breakdown(events, "session", top=top),
            "market_regime": _simple_breakdown(events, "market_regime", top=top),
            "entry_context": _simple_breakdown(events, "entry_context", top=top),
            "score_bucket": _simple_breakdown(events, "score_bucket", top=top),
        },
    }


def _simple_breakdown(events: list[dict[str, Any]], key: str, *, top: int) -> list[dict[str, Any]]:
    counter = Counter(_text(row.get(key)) for row in events)
    return [{"value": value, "count": count} for value, count in counter.most_common(top)]


def _data_gaps(
    *,
    duplicate_events: list[dict[str, Any]],
    paper_duplicate_events: list[dict[str, Any]],
    published_signals: list[dict[str, Any]],
    signal_update: dict[str, Any],
    active_signal_state: dict[str, Any],
) -> list[str]:
    gaps = []
    if not duplicate_events:
        gaps.append("No duplicate_signal_suppressed events found in local logs/signals_log.")
    if not paper_duplicate_events:
        gaps.append("No paper_rejected_duplicate events found in scheduler log or paper CSV.")
    if not published_signals:
        gaps.append("No published trade_signal records found; exact active-state comparison unavailable.")
    if signal_update["total_events"] == 0:
        gaps.append("No SIGNAL_UPDATE_V1 runtime events found; cannot verify live classification coverage.")
    if not active_signal_state.get("active_state_has_explicit_expiration"):
        gaps.append("trade_signals active-state model has no explicit TP/SL/expiration/invalidation close marker.")
    if any(not row.get("dedupe_key") for row in duplicate_events):
        gaps.append("Some duplicate events lack the original signal dedupe key; exact-vs-broad analysis is partial.")
    return gaps


def _conclusion(
    *,
    duplicate_events: list[dict[str, Any]],
    paper_duplicate_events: list[dict[str, Any]],
    signal_update: dict[str, Any],
    dedupe_width: dict[str, Any],
    active_signal_state: dict[str, Any],
) -> dict[str, Any]:
    reasons = []
    action = "datos insuficientes"
    if duplicate_events and signal_update["total_events"] == 0:
        action = "mejorar SIGNAL_UPDATE_V1"
        reasons.append("Hay duplicados, pero no hay eventos runtime de SIGNAL_UPDATE_V1 que demuestren clasificación efectiva.")
    if active_signal_state.get("active_state_has_explicit_expiration") is False:
        reasons.append("La capa active same symbol+direction no tiene expiración efectiva en trade_signals; cualquier señal publicada reciente puede permanecer activa en la ventana latest-500.")
    if dedupe_width.get("potentially_too_broad"):
        reasons.append("La evidencia disponible sugiere mezcla entre dedupe exacto y bloqueo amplio symbol+direction; conviene separar dedupe público exacto de lifecycle/reentry.")
    if paper_duplicate_events:
        reasons.append("paper_rejected_duplicate usa dedupe independiente de paper; conviene auditar si paper debe permitir reentries aunque público siga bloqueado.")
    if signal_update["by_update_type"].get("STRENGTHENED_SIGNAL", 0) or signal_update["by_update_type"].get("REENTRY_CANDIDATE", 0):
        action = "permitir reentry controlado en shadow"
        reasons.append("SIGNAL_UPDATE_V1 ya detecta strengthened/reentry candidates; siguiente paso prudente es shadow tracking, no publicación.")
    elif duplicate_events and not reasons:
        action = "mantener dedupe actual"
        reasons.append("No hay evidencia suficiente de que los duplicados aporten información nueva.")
    if not reasons:
        reasons.append("No hay datos suficientes para cambiar lifecycle/dedupe.")
    return {
        "recommended_action": action,
        "options_considered": [
            "mantener dedupe actual",
            "reducir ventana",
            "cerrar señales activas antes",
            "permitir reentry controlado",
            "mejorar SIGNAL_UPDATE_V1",
            "separar dedupe público vs paper",
            "datos insuficientes",
        ],
        "reasons": reasons,
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
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
    events = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parsed = _parse_json_line(line)
        if parsed is not None:
            events.append(parsed)
    return events


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


def _load_json_files(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for file_path in sorted(path.glob("**/*.json")):
        parsed = _load_json(file_path)
        if parsed:
            rows.append(parsed)
    return rows


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _load_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _contains(row: Any, needle: str) -> bool:
    if isinstance(row, dict):
        return any(_contains(value, needle) for value in row.values())
    if isinstance(row, list):
        return any(_contains(value, needle) for value in row)
    return needle in str(row)


def _directional_confluence_passed(row: dict[str, Any]) -> bool:
    passed = _listify(row.get("conditions_passed"))
    failed = _listify(row.get("conditions_failed"))
    rejection = _listify(row.get("rejection_reasons"))
    if "directional_confluence" in passed:
        return True
    if "directional_confluence_failed" in failed or "directional_confluence_failed" in rejection:
        return False
    no_signal_reason = str(row.get("no_signal_reason") or "")
    return "directional_confluence_failed" not in no_signal_reason and bool(passed)


def _dedupe_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    deduped = []
    for event in events:
        key = (
            event.get("source"),
            event.get("timestamp"),
            event.get("symbol"),
            event.get("direction"),
            event.get("score"),
            event.get("dedupe_key"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)
    return deduped


def _listify(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return [item.strip() for item in stripped.split("|") if item.strip()]
        return parsed if isinstance(parsed, list) else [parsed]
    return []


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "passed", "valid"}


def _score_bucket(score: float | None) -> str:
    if score is None:
        return "UNKNOWN"
    if score < 50:
        return "0-49"
    if score < 60:
        return "50-59"
    if score < 70:
        return "60-69"
    if score < 80:
        return "70-79"
    if score < 90:
        return "80-89"
    return "90+"


def _text(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "UNKNOWN"


def _signal_dedupe_key(row: dict[str, Any], raw: dict[str, Any]) -> str:
    for value in (row.get("signal_dedupe_key"), raw.get("signal_dedupe_key"), raw.get("dedupe_key")):
        text = str(value or "").strip()
        if "|" in text:
            return text
    text = str(row.get("dedupe_key") or "").strip()
    return text if "|" in text else ""


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze(data_path=args.data_path, logs_path=args.logs_path, reports_path=args.reports_path, top=args.top)
    paths = write_reports(result, args.reports_path)
    print("LIFECYCLE_DEDUPE_DEEP_DIVE_V1")
    print(f"- duplicate_signal_suppressed: {result['metrics']['total_duplicate_signal_suppressed']}")
    print(f"- paper_rejected_duplicate: {result['metrics']['total_paper_rejected_duplicate']}")
    print(f"- SIGNAL_UPDATE_V1 events: {result['signal_update_v1_summary']['total_events']}")
    print(f"- recommendation: {result['conclusion']['recommended_action']}")
    print(f"- Markdown: {paths['markdown']}")
    print(f"- JSON: {paths['json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
