from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


TARGET_REASON = "duplicate_signal_suppressed"
CLOSED_STATUSES = {"expired", "sl_hit", "tp1_hit", "tp2_hit", "tp_hit", "closed", "win", "loss"}
CODE_PATH = "src/trading_signals/application/use_cases/run_market_scan.py"
LIFECYCLE_PATH = "src/trading_signals/application/use_cases/signal_lifecycle.py"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser = argparse.ArgumentParser(prog="duplicate-signal-suppressed-deep-dive")
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    parser.add_argument("--logs-path", default=str(bot_data_dir / "logs"))
    parser.add_argument("--top", type=int, default=12)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze(
        data_path=Path(args.data_path),
        reports_path=Path(args.reports_path),
        logs_path=Path(args.logs_path),
        top=args.top,
    )
    paths = write_reports(result, Path(args.reports_path))
    print("DUPLICATE_SIGNAL_SUPPRESSED_DEEP_DIVE")
    print(f"- signals_log hits: {result['source_counts']['signals_log']}")
    print(f"- shadow_signals hits: {result['source_counts']['shadow_signals']}")
    print(f"- scheduler log lines: {result['source_counts']['scheduler_log_lines']}")
    print(f"- paper rows: {result['source_counts']['paper_rejection_context']}")
    print(f"- exact dedupe matches: {result['dedupe_analysis']['exact_key_matches']}")
    print(f"- broad active matches: {result['dedupe_analysis']['broad_symbol_direction_matches']}")
    print(f"- recommendation: {result['conclusion']['recommended_action']}")
    print(f"- Markdown: {paths['markdown']}")
    print(f"- JSON: {paths['json']}")
    return 0


def analyze(*, data_path: Path, reports_path: Path, logs_path: Path, top: int = 12) -> dict[str, Any]:
    generated_at = datetime.now(tz=UTC).isoformat(timespec="seconds")
    signals_log = _load_signals_log(data_path / "bot_activity" / "signals_log.jsonl")
    shadow_rows = _load_csv(data_path / "paper_trading" / "shadow_signals.csv")
    paper_rows = _load_csv(data_path / "paper_trading" / "trades.csv")
    scheduler = _scan_scheduler_log(logs_path / "scheduler.log")
    trade_signals = _load_trade_signals(data_path / "trade_signals")

    signal_hits = [row for row in signals_log if _contains_target(row)]
    shadow_hits = [row for row in shadow_rows if _contains_target(row)]
    paper_hits = [row for row in paper_rows if _contains_target(row)]
    unified = [_normalize_signal(row, "signals_log") for row in signal_hits]
    unified.extend(_normalize_shadow(row, "shadow_signals") for row in shadow_hits)
    unified.extend(_normalize_paper(row, "paper_trading") for row in paper_hits)

    published = [row for row in trade_signals if row.get("published_at")]
    dedupe = _dedupe_analysis(unified, published)
    paper_closed_hits = [_normalize_paper(row, "paper_trading") for row in paper_hits if _is_closed(row)]
    paper_all_closed = [_normalize_paper(row, "paper_trading") for row in paper_rows if _is_closed(row)]
    severe_cases = _severe_cases(unified)
    result = {
        "scope": "DUPLICATE_SIGNAL_SUPPRESSED_DEEP_DIVE",
        "generated_at": generated_at,
        "mode": "offline_analysis_only",
        "target_reason": TARGET_REASON,
        "data_path": str(data_path),
        "reports_path": str(reports_path),
        "logs_path": str(logs_path),
        "code_origin": _code_origin(),
        "source_files": {
            "signals_log": str(data_path / "bot_activity" / "signals_log.jsonl"),
            "shadow_signals": str(data_path / "paper_trading" / "shadow_signals.csv"),
            "paper_trades": str(data_path / "paper_trading" / "trades.csv"),
            "scheduler_log": str(logs_path / "scheduler.log"),
            "trade_signals_dir": str(data_path / "trade_signals"),
        },
        "source_counts": {
            "scheduler_log_lines": scheduler["line_hits"],
            "scheduler_log_json_events": scheduler["json_hits"],
            "signals_log": len(signal_hits),
            "shadow_signals": len(shadow_hits),
            "paper_rejection_context": len(paper_hits),
            "trade_signals_total": len(trade_signals),
            "published_trade_signals": len(published),
            "paper_closed_with_target": len(paper_closed_hits),
        },
        "breakdowns": _breakdowns(unified, top=top),
        "severe_cases": severe_cases,
        "dedupe_analysis": dedupe,
        "paper_evidence": _paper_evidence(paper_closed_hits, paper_all_closed),
        "top_examples": _top_examples(unified, top=top),
        "data_gaps": _data_gaps(signal_hits, shadow_hits, paper_hits, scheduler, published),
        "conclusion": _conclusion(severe=severe_cases, dedupe=dedupe, paper_closed_count=len(paper_closed_hits)),
    }
    return result


def write_reports(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    markdown = reports_path / "duplicate_signal_suppressed_deep_dive.md"
    json_path = reports_path / "duplicate_signal_suppressed_deep_dive.json"
    markdown.write_text(format_markdown(result), encoding="utf-8")
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return {"markdown": markdown, "json": json_path}


def format_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# duplicate_signal_suppressed Deep Dive",
        "",
        f"Generated at: {result['generated_at']}",
        "Mode: offline analysis only. No strategy, scheduler, Telegram, filters or production behavior changed.",
        "",
        "## 1. Exact origin",
        "",
        f"Primary file: `{result['code_origin']['file']}`",
        f"Lifecycle file: `{result['code_origin']['lifecycle_file']}`",
        "",
        "### How it is generated",
    ]
    for item in result["code_origin"]["conditions"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "### Dedupe key",
            f"`{result['code_origin']['dedupe_key_formula']}`",
            "",
            f"Window/cooldown: {result['code_origin']['window_or_cooldown']}",
            "",
            f"Scope impact: {result['code_origin']['scope_impact']}",
            "",
            "## 2. Source counts",
            "",
            "| Source | Count |",
            "|---|---:|",
        ]
    )
    for key, value in result["source_counts"].items():
        lines.append(f"| {key} | {value} |")

    lines.extend(["", "## 3. Breakdowns", ""])
    for dimension, rows in result["breakdowns"].items():
        lines.extend([f"### {dimension}", "", "| Value | Count | Avg score | Closed | WR | PF | Total R |", "|---|---:|---:|---:|---:|---:|---:|"])
        if rows:
            for row in rows:
                lines.append(
                    f"| {row['value']} | {row['count']} | {row['avg_score']} | {row['closed_trades']} | "
                    f"{row['winrate']}% | {row['profit_factor']} | {row['total_r']} |"
                )
        else:
            lines.append("| no_data | 0 | 0 | 0 | 0 | 0 | 0 |")
        lines.append("")

    severe = result["severe_cases"]
    lines.extend(
        [
            "## 4. Severe cases",
            "",
            f"- Score >= 70 blocked: {severe['score_gte_70']['count']}",
            f"- Score >= 80 blocked: {severe['score_gte_80']['count']}",
            f"- Score >= 90 blocked: {severe['score_gte_90']['count']}",
            f"- RR valid blocked: {severe['rr_valid']['count']}",
            f"- Directional confluence passed blocked: {severe['directional_confluence_passed']['count']}",
            f"- Signal status valid blocked: {severe['signal_status_valid']['count']}",
            "",
            "### Highest-score examples",
            "",
            "| Symbol | Direction | Score | Setup | Session | Regime | Context | Dedupe key |",
            "|---|---|---:|---|---|---|---|---|",
        ]
    )
    for row in severe["highest_score_examples"]:
        lines.append(
            f"| {row['symbol']} | {row['direction']} | {row['score']} | {row['setup_type']} | "
            f"{row['session']} | {row['market_regime']} | {row['entry_context']} | `{row['dedupe_key']}` |"
        )

    dedupe = result["dedupe_analysis"]
    lines.extend(
        [
            "",
            "## 5. Dedupe width analysis",
            "",
            f"- Events analyzed: {dedupe['events_analyzed']}",
            f"- Exact key matches against published signals: {dedupe['exact_key_matches']}",
            f"- Broad symbol+direction matches against published signals: {dedupe['broad_symbol_direction_matches']}",
            f"- Events with exact key unavailable: {dedupe['missing_dedupe_key_events']}",
            f"- Unique symbols: {dedupe['unique_symbols']}",
            f"- Unique symbol+direction pairs: {dedupe['unique_symbol_direction_pairs']}",
            f"- Potentially too broad: {dedupe['potentially_too_broad']}",
            "",
            "### Top duplicate keys",
            "",
            "| Dedupe key | Count |",
            "|---|---:|",
        ]
    )
    for item in dedupe["top_dedupe_keys"]:
        lines.append(f"| `{item['dedupe_key']}` | {item['count']} |")
    if not dedupe["top_dedupe_keys"]:
        lines.append("| no_data | 0 |")

    lines.extend(["", "### Top broad symbol+direction pairs", "", "| Pair | Count | Published active refs |", "|---|---:|---:|"])
    for item in dedupe["top_symbol_direction_pairs"]:
        lines.append(f"| {item['pair']} | {item['count']} | {item['published_refs']} |")
    if not dedupe["top_symbol_direction_pairs"]:
        lines.append("| no_data | 0 | 0 |")

    lines.extend(["", "## 6. Paper evidence", ""])
    evidence = result["paper_evidence"]
    overall = evidence["overall"]
    lines.extend(
        [
            f"- Closed paper rows with target: {overall['closed_trades']}",
            f"- WR: {overall['winrate']}%",
            f"- PF: {overall['profit_factor']}",
            f"- Total R: {overall['total_r']}",
            f"- Avg R: {overall['avg_r']}",
            "",
            "Note: duplicate suppression is primarily a publication/lifecycle gate, so paper rows may be absent even when public publishing is blocked.",
            "",
            "## 7. Data gaps",
            "",
        ]
    )
    for gap in result["data_gaps"]:
        lines.append(f"- {gap}")

    lines.extend(
        [
            "",
            "## 8. Conclusion",
            "",
            f"- Evidence classification: {result['conclusion']['evidence_classification']}",
            f"- Recommended action: {result['conclusion']['recommended_action']}",
            f"- Rationale: {result['conclusion']['rationale']}",
            "",
            "Allowed actions considered: mantener dedupe actual, reducir ventana, hacer dedupe por dirección/símbolo/timeframe, permitir updates en vez de bloquear, permitir paper aunque público se bloquee, datos insuficientes.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _code_origin() -> dict[str, Any]:
    return {
        "file": CODE_PATH,
        "lifecycle_file": LIFECYCLE_PATH,
        "conditions": [
            "`run_market_scan.build_signal_dedupe_key()` builds the signal dedupe key when each `TradeSignal` is created.",
            "`signal_repo.has_published_dedupe_key(signal.dedupe_key)` checks the latest 500 stored trade signals and returns true only if the exact same dedupe key already has `published_at`.",
            "`_no_send_reason()` returns `duplicate_signal_suppressed` when a valid signal is publishable by decision but exact dedupe is true.",
            "Later, valid but unpublished signals append `duplicate_signal_suppressed` to `evaluation.rejection_reasons` when `is_duplicate` is true.",
            "A second lifecycle layer, `classify_signal_lifecycle()`, blocks active same symbol+direction published signals unless reentry confirmation exists. That layer records reasons such as `active_same_symbol_direction_without_reentry`, not `duplicate_signal_suppressed`.",
        ],
        "dedupe_key_formula": "symbol|decision|strategy_id|strategy_version|entry_timeframe|entry_snapshot.timestamp",
        "window_or_cooldown": (
            "Exact dedupe has no time TTL; it scans the latest 500 stored trade signals for the same dedupe key with published_at. "
            "Lifecycle duplicate also has no fixed time TTL; it considers active published same symbol+direction entries from latest 500 signals."
        ),
        "scope_impact": (
            "The exact duplicate check sits before publish_signal and blocks public publish path. Paper/shadow paths are handled separately later; "
            "paper can still be rejected by its own candidate dedupe, but `duplicate_signal_suppressed` itself is a public/lifecycle publishing reason."
        ),
    }


def _load_signals_log(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists() or path.stat().st_size == 0:
        return rows
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if TARGET_REASON not in line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _load_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except csv.Error:
        return []


def _load_trade_signals(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for file_path in sorted(path.glob("*/*.json")):
        try:
            value = json.loads(file_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(value, dict):
            value["_source_file"] = str(file_path)
            rows.append(value)
    return rows


def _scan_scheduler_log(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {"line_hits": 0, "json_hits": 0}
    line_hits = 0
    json_hits = 0
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if TARGET_REASON not in line:
                continue
            line_hits += 1
            try:
                json.loads(_json_part(line))
            except json.JSONDecodeError:
                continue
            json_hits += 1
    return {"line_hits": line_hits, "json_hits": json_hits}


def _json_part(line: str) -> str:
    idx = line.find("{")
    return line[idx:] if idx >= 0 else line


def _contains_target(row: dict[str, Any]) -> bool:
    return any(TARGET_REASON in str(value or "") for value in row.values())


def _normalize_signal(row: dict[str, Any], source: str) -> dict[str, Any]:
    raw = row.get("raw_summary") if isinstance(row.get("raw_summary"), dict) else {}
    return {
        "source": source,
        "timestamp": str(row.get("timestamp") or ""),
        "symbol": _upper(row.get("symbol")),
        "direction": _lower(row.get("direction")),
        "setup_type": _upper(row.get("setup_type") or raw.get("setup_detected")),
        "market_regime": _upper(row.get("market_regime")),
        "session": _upper(row.get("session")),
        "entry_context": _upper(row.get("entry_context")),
        "trade_location": str(row.get("trade_location") or "UNKNOWN").strip() or "UNKNOWN",
        "score": _float(row.get("score") or raw.get("strategy_gate_score")),
        "rr_valid": _bool(row.get("rr_valid")) if row.get("rr_valid") is not None else (_float(row.get("rr")) is not None and (_float(row.get("rr")) or 0) > 0),
        "rr": _float(row.get("rr")),
        "trend_entry": _lower(row.get("trend_entry")),
        "trend_higher": _lower(row.get("trend_higher")),
        "conditions_passed": _tokens(row.get("conditions_passed")),
        "conditions_failed": _tokens(row.get("conditions_failed")),
        "rejection_reasons": _tokens(row.get("rejection_reasons") or row.get("reasons")),
        "penalties": _tokens(row.get("penalties")),
        "avoidance_warnings": _tokens(row.get("avoidance_warnings")),
        "failed_conditions": row.get("failed_conditions") if isinstance(row.get("failed_conditions"), list) else [],
        "dedupe_key": str(row.get("dedupe_key") or ""),
        "signal_status": _lower(raw.get("signal_status") or row.get("status")),
        "signal_decision": _upper(raw.get("signal_decision") or row.get("decision")),
        "result_r": None,
        "status": _lower(row.get("status")),
    }


def _normalize_shadow(row: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "source": source,
        "timestamp": str(row.get("timestamp") or ""),
        "symbol": _upper(row.get("symbol")),
        "direction": _lower(row.get("direction")),
        "setup_type": "UNKNOWN",
        "market_regime": _upper(row.get("market_regime")),
        "session": "UNKNOWN",
        "entry_context": "UNKNOWN",
        "trade_location": "UNKNOWN",
        "score": _float(row.get("shadow_score")),
        "rr_valid": None,
        "trend_entry": "",
        "trend_higher": "",
        "conditions_passed": [],
        "conditions_failed": _tokens(row.get("current_rejection_reasons")),
        "rejection_reasons": _tokens(row.get("current_rejection_reasons")),
        "penalties": [],
        "avoidance_warnings": [],
        "dedupe_key": "",
        "signal_status": "",
        "signal_decision": _upper(row.get("shadow_decision")),
        "result_r": _float(row.get("result_r")),
        "status": _lower(row.get("outcome")),
    }


def _normalize_paper(row: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "source": source,
        "timestamp": str(row.get("opened_at") or row.get("timestamp") or ""),
        "symbol": _upper(row.get("symbol")),
        "direction": _lower(row.get("direction")),
        "setup_type": _upper(row.get("setup_type")),
        "market_regime": _upper(row.get("market_regime")),
        "session": _upper(row.get("session")),
        "entry_context": _upper(row.get("entry_context")),
        "trade_location": str(row.get("trade_location") or "UNKNOWN").strip() or "UNKNOWN",
        "score": _float(row.get("score")),
        "rr_valid": _bool(row.get("rr_valid")),
        "trend_entry": _lower(row.get("trend_1h") or row.get("trend_entry")),
        "trend_higher": _lower(row.get("trend_4h") or row.get("trend_higher")),
        "conditions_passed": _tokens(row.get("conditions_passed")),
        "conditions_failed": _tokens(row.get("conditions_failed") or row.get("entry_or_rejection_reason")),
        "rejection_reasons": _tokens(row.get("rejection_reasons") or row.get("conditions_failed") or row.get("entry_or_rejection_reason")),
        "penalties": _tokens(row.get("penalties")),
        "avoidance_warnings": _tokens(row.get("avoidance_warnings")),
        "dedupe_key": str(row.get("dedupe_key") or ""),
        "signal_status": _lower(row.get("status")),
        "signal_decision": _upper(row.get("direction")),
        "result_r": _float(row.get("result_r")),
        "status": _lower(row.get("status")),
    }


def _breakdowns(rows: list[dict[str, Any]], *, top: int) -> dict[str, list[dict[str, Any]]]:
    dimensions = ["symbol", "direction", "setup_type", "session", "market_regime", "entry_context", "score_bucket"]
    output: dict[str, list[dict[str, Any]]] = {}
    for dimension in dimensions:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            value = _score_bucket(row.get("score")) if dimension == "score_bucket" else str(row.get(dimension) or "UNKNOWN")
            grouped[value].append(row)
        output[dimension] = sorted((_group_summary(value, items) for value, items in grouped.items()), key=lambda item: item["count"], reverse=True)[:top]
    return output


def _group_summary(value: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [_float(row.get("score")) for row in rows]
    scores = [score for score in scores if score is not None]
    closed_values = [_float(row.get("result_r")) for row in rows if _float(row.get("result_r")) is not None and _is_closed(row)]
    return {
        "value": value or "UNKNOWN",
        "count": len(rows),
        "avg_score": _round(sum(scores) / len(scores)) if scores else 0.0,
        **_metrics_from_values(closed_values),
    }


def _severe_cases(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def matching(predicate) -> list[dict[str, Any]]:
        return [row for row in rows if predicate(row)]

    score70 = matching(lambda row: (_float(row.get("score")) or -1) >= 70)
    score80 = matching(lambda row: (_float(row.get("score")) or -1) >= 80)
    score90 = matching(lambda row: (_float(row.get("score")) or -1) >= 90)
    rr_valid = matching(lambda row: row.get("rr_valid") is True)
    directional_passed = matching(lambda row: "directional_confluence" in set(row.get("conditions_passed", [])) or (not row.get("conditions_failed") and row.get("signal_decision") == "SEND"))
    valid_status = matching(lambda row: row.get("signal_status") == "valid" or row.get("signal_decision") == "SEND")
    highest = sorted(rows, key=lambda row: _float(row.get("score")) or -1, reverse=True)[:15]
    return {
        "score_gte_70": _case_summary(score70),
        "score_gte_80": _case_summary(score80),
        "score_gte_90": _case_summary(score90),
        "rr_valid": _case_summary(rr_valid),
        "directional_confluence_passed": _case_summary(directional_passed),
        "signal_status_valid": _case_summary(valid_status),
        "highest_score_examples": [_example(row) for row in highest],
    }


def _case_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"count": len(rows), **_metrics_from_values([_float(row.get("result_r")) for row in rows if _float(row.get("result_r")) is not None and _is_closed(row)])}


def _dedupe_analysis(events: list[dict[str, Any]], published: list[dict[str, Any]]) -> dict[str, Any]:
    published_by_key = {str(row.get("dedupe_key") or ""): row for row in published if row.get("dedupe_key")}
    published_pairs = Counter(f"{_upper(row.get('symbol'))}|{_lower(row.get('decision'))}" for row in published)
    exact = 0
    broad = 0
    missing = 0
    key_counter: Counter[str] = Counter()
    pair_counter: Counter[str] = Counter()
    exact_examples = []
    broad_examples = []
    for event in events:
        key = str(event.get("dedupe_key") or "")
        pair = f"{event.get('symbol')}|{event.get('direction')}"
        if key:
            key_counter[key] += 1
            if key in published_by_key:
                exact += 1
                if len(exact_examples) < 10:
                    exact_examples.append({"event": _example(event), "published": _published_ref(published_by_key[key])})
        else:
            missing += 1
        pair_counter[pair] += 1
        if published_pairs.get(pair, 0) > 0:
            broad += 1
            if len(broad_examples) < 10:
                broad_examples.append({"event": _example(event), "published_refs": published_pairs[pair]})
    top_pairs = [
        {"pair": pair, "count": count, "published_refs": published_pairs.get(pair, 0)}
        for pair, count in pair_counter.most_common(12)
    ]
    return {
        "events_analyzed": len(events),
        "exact_key_matches": exact,
        "broad_symbol_direction_matches": broad,
        "missing_dedupe_key_events": missing,
        "unique_symbols": len({str(row.get("symbol")) for row in events if row.get("symbol")}),
        "unique_symbol_direction_pairs": len(pair_counter),
        "potentially_too_broad": exact == 0 and broad > 0,
        "top_dedupe_keys": [{"dedupe_key": key, "count": count} for key, count in key_counter.most_common(12)],
        "top_symbol_direction_pairs": top_pairs,
        "exact_match_examples": exact_examples,
        "broad_match_examples": broad_examples,
    }


def _published_ref(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "signal_id": row.get("id"),
        "symbol": row.get("symbol"),
        "decision": row.get("decision"),
        "dedupe_key": row.get("dedupe_key"),
        "published_at": row.get("published_at"),
        "status": row.get("status"),
    }


def _paper_evidence(target_closed: list[dict[str, Any]], all_closed: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "overall": _metrics_from_values([_float(row.get("result_r")) for row in target_closed if _float(row.get("result_r")) is not None]),
        "baseline_all_closed": _metrics_from_values([_float(row.get("result_r")) for row in all_closed if _float(row.get("result_r")) is not None]),
    }


def _top_examples(rows: list[dict[str, Any]], *, top: int) -> list[dict[str, Any]]:
    return [_example(row) for row in sorted(rows, key=lambda row: _float(row.get("score")) or -1, reverse=True)[:top]]


def _example(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": row.get("source"),
        "timestamp": row.get("timestamp"),
        "symbol": row.get("symbol"),
        "direction": row.get("direction"),
        "score": _float(row.get("score")) or 0.0,
        "setup_type": row.get("setup_type") or "UNKNOWN",
        "session": row.get("session") or "UNKNOWN",
        "market_regime": row.get("market_regime") or "UNKNOWN",
        "entry_context": row.get("entry_context") or "UNKNOWN",
        "dedupe_key": row.get("dedupe_key") or "",
        "rr_valid": row.get("rr_valid"),
        "signal_status": row.get("signal_status"),
        "signal_decision": row.get("signal_decision"),
    }


def _data_gaps(signal_hits: list[dict[str, Any]], shadow_hits: list[dict[str, Any]], paper_hits: list[dict[str, Any]], scheduler: dict[str, Any], published: list[dict[str, Any]]) -> list[str]:
    gaps: list[str] = []
    if not signal_hits:
        gaps.append("No target records found in data/bot_activity/signals_log.jsonl.")
    if not shadow_hits:
        gaps.append("No target records found in data/paper_trading/shadow_signals.csv.")
    if not paper_hits:
        gaps.append("No target rows found in data/paper_trading/trades.csv; duplicate suppression likely blocks publication, not paper outcomes.")
    if scheduler.get("line_hits", 0) == 0:
        gaps.append("No target lines found in logs/scheduler.log.")
    if not published:
        gaps.append("No published trade signals found under data/trade_signals; exact dedupe comparison is limited.")
    if not gaps:
        gaps.append("No major data gaps detected in local files.")
    return gaps


def _conclusion(*, severe: dict[str, Any], dedupe: dict[str, Any], paper_closed_count: int) -> dict[str, str]:
    valid_count = int(severe["signal_status_valid"]["count"])
    exact = int(dedupe["exact_key_matches"])
    broad = int(dedupe["broad_symbol_direction_matches"])
    if valid_count == 0:
        return {
            "evidence_classification": "INSUFFICIENT_DATA",
            "recommended_action": "datos insuficientes",
            "rationale": "No hay suficientes eventos válidos bloqueados por duplicado.",
        }
    if exact > 0:
        return {
            "evidence_classification": "EXACT_DUPLICATE",
            "recommended_action": "mantener dedupe actual",
            "rationale": "Hay coincidencias exactas de dedupe_key contra señales ya publicadas; el bloqueo parece intencionado.",
        }
    if broad > 0:
        return {
            "evidence_classification": "BROAD_ACTIVE_DUPLICATE",
            "recommended_action": "permitir updates en vez de bloquear",
            "rationale": "No se observan coincidencias exactas, pero sí muchas coincidencias símbolo+dirección; conviene considerar updates/reentry controlado antes que republicar la misma operación.",
        }
    if paper_closed_count == 0:
        return {
            "evidence_classification": "NO_OUTCOME_EVIDENCE",
            "recommended_action": "permitir paper aunque público se bloquee",
            "rationale": "No hay outcomes paper directos para medir si los duplicados habrían aportado edge.",
        }
    return {
        "evidence_classification": "MIXED",
        "recommended_action": "hacer dedupe por dirección/símbolo/timeframe",
        "rationale": "La evidencia no prueba duplicado exacto ni edge; revisar granularidad antes de tocar publicación.",
    }


def _metrics_from_values(values: list[float | None]) -> dict[str, Any]:
    clean = [float(value) for value in values if value is not None]
    wins = [value for value in clean if value > 0]
    losses = [value for value in clean if value < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "closed_trades": len(clean),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": _round(len(wins) / len(clean) * 100) if clean else 0.0,
        "gross_win_r": _round(gross_win),
        "gross_loss_r": _round(gross_loss),
        "profit_factor": _profit_factor(gross_win, gross_loss),
        "total_r": _round(sum(clean)),
        "avg_r": _round(sum(clean) / len(clean)) if clean else 0.0,
    }


def _profit_factor(gross_win: float, gross_loss: float) -> float | str:
    if gross_loss > 0:
        return _round(gross_win / gross_loss)
    if gross_win > 0:
        return "inf"
    return 0.0


def _score_bucket(value: Any) -> str:
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


def _tokens(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        decoded = None
    if isinstance(decoded, list):
        return [str(item).strip() for item in decoded if str(item).strip()]
    return [item.strip() for item in re.split(r"[|,;]", text) if item.strip()]


def _is_closed(row: dict[str, Any]) -> bool:
    status = _lower(row.get("status") or row.get("outcome"))
    return status in CLOSED_STATUSES or bool(str(row.get("closed_at") or "").strip())


def _nested(row: dict[str, Any], *keys: str) -> Any:
    value: Any = row
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float) -> float:
    return round(float(value), 4)


def _upper(value: Any) -> str:
    text = str(value or "").strip()
    return text.upper() if text else "UNKNOWN"


def _lower(value: Any) -> str:
    return str(value or "").strip().lower()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
