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


TARGET_REASON = "directional_confluence_failed"
CLOSED_STATUSES = {"expired", "sl_hit", "tp1_hit", "tp2_hit", "tp_hit", "closed", "win", "loss"}
CODE_PATH = "src/trading_signals/domain/strategies/liquidity_sweep_mtf_v1.py"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser = argparse.ArgumentParser(prog="directional-confluence-failed-deep-dive")
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
    print("DIRECTIONAL_CONFLUENCE_FAILED_DEEP_DIVE")
    print(f"- signals_log hits: {result['source_counts']['signals_log']}")
    print(f"- shadow_signals hits: {result['source_counts']['shadow_signals']}")
    print(f"- scheduler log lines: {result['source_counts']['scheduler_log_lines']}")
    print(f"- paper context rows: {result['source_counts']['paper_rejection_context']}")
    print(f"- closed paper evidence: {result['paper_evidence']['overall']['closed_trades']}")
    print(f"- recommendation: {result['conclusion']['recommended_action']}")
    print(f"- Markdown: {paths['markdown']}")
    print(f"- JSON: {paths['json']}")
    return 0


def analyze(*, data_path: Path, reports_path: Path, logs_path: Path, top: int = 12) -> dict[str, Any]:
    generated_at = datetime.now(tz=UTC).isoformat(timespec="seconds")
    signals = _load_signals_log(data_path / "bot_activity" / "signals_log.jsonl")
    shadow = _load_csv(data_path / "paper_trading" / "shadow_signals.csv")
    paper_rows = _load_csv(data_path / "paper_trading" / "trades.csv")
    scheduler = _scan_scheduler_log(logs_path / "scheduler.log")

    signal_hits = [row for row in signals if _contains_target(row)]
    shadow_hits = [row for row in shadow if _contains_target(row)]
    paper_hits = [row for row in paper_rows if _contains_target(row)]
    rejected_candidates = [
        row
        for row in signal_hits
        if str(row.get("status") or "").lower() in {"rejected", "no_trade", "paper", "experimental"}
        or str(_nested(row, "raw_summary", "signal_decision") or "").upper() == "REJECT"
    ]

    unified = [_normalize_signal(row, "signals_log") for row in signal_hits]
    unified.extend(_normalize_shadow(row, "shadow_signals") for row in shadow_hits)
    unified.extend(_normalize_paper(row, "paper_trading") for row in paper_hits)

    paper_closed_hits = [_normalize_paper(row, "paper_trading") for row in paper_hits if _is_closed(row)]
    paper_all_closed = [_normalize_paper(row, "paper_trading") for row in paper_rows if _is_closed(row)]

    severe_cases = _severe_cases(unified)
    paper_evidence = _paper_evidence(paper_closed_hits, paper_all_closed)
    result = {
        "scope": "DIRECTIONAL_CONFLUENCE_FAILED_DEEP_DIVE",
        "generated_at": generated_at,
        "mode": "offline_analysis_only",
        "target_reason": TARGET_REASON,
        "data_path": str(data_path),
        "reports_path": str(reports_path),
        "logs_path": str(logs_path),
        "code_origin": _code_origin(),
        "source_files": {
            "shadow_signals": str(data_path / "paper_trading" / "shadow_signals.csv"),
            "signals_log": str(data_path / "bot_activity" / "signals_log.jsonl"),
            "paper_trades": str(data_path / "paper_trading" / "trades.csv"),
            "scheduler_log": str(logs_path / "scheduler.log"),
        },
        "source_counts": {
            "shadow_signals": len(shadow_hits),
            "scheduler_log_lines": scheduler["line_hits"],
            "scheduler_log_json_events": scheduler["json_hits"],
            "signals_log": len(signal_hits),
            "candidates_rejected": len(rejected_candidates),
            "paper_rejection_context": len(paper_hits),
            "paper_closed_with_target": len(paper_closed_hits),
        },
        "breakdowns": _breakdowns(unified, top=top),
        "internal_condition_failures": _failed_condition_breakdown(signal_hits, top=top),
        "setup_path_breakdown": _setup_path_breakdown(unified),
        "co_occurring_reasons": _co_occurring_reasons(unified, top=top),
        "severe_cases": severe_cases,
        "paper_evidence": paper_evidence,
        "top_examples": _top_examples(unified, top=top),
        "data_gaps": _data_gaps(signal_hits, shadow_hits, paper_hits, scheduler),
        "conclusion": _conclusion(severe_cases, paper_evidence),
    }
    return result


def write_reports(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    markdown = reports_path / "directional_confluence_failed_deep_dive.md"
    json_path = reports_path / "directional_confluence_failed_deep_dive.json"
    markdown.write_text(format_markdown(result), encoding="utf-8")
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return {"markdown": markdown, "json": json_path}


def format_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# directional_confluence_failed Deep Dive",
        "",
        f"Generated at: {result['generated_at']}",
        "Mode: offline analysis only. No strategy, scheduler, Telegram, filters or production behavior changed.",
        "",
        "## 1. Exact origin",
        "",
        f"File: `{result['code_origin']['file']}`",
        "",
        "The veto is generated in the final fallback branch after primary sweep and secondary setup paths fail.",
        "",
        "### Internal conditions",
    ]
    for item in result["code_origin"]["conditions"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "### Interpretation",
            result["code_origin"]["interpretation"],
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

    lines.extend(["## 4. Setup path split", "", "| Path | Count | Closed | WR | PF | Total R |", "|---|---:|---:|---:|---:|---:|"])
    for row in result["setup_path_breakdown"]:
        lines.append(f"| {row['path']} | {row['count']} | {row['closed_trades']} | {row['winrate']}% | {row['profit_factor']} | {row['total_r']} |")

    lines.extend(["", "## 5. Internal failed conditions from `signals_log`", "", "| Condition | Count |", "|---|---:|"])
    for item in result["internal_condition_failures"]:
        lines.append(f"| {item['condition']} | {item['count']} |")

    lines.extend(["", "## 6. Co-occurring reasons", "", "| Reason | Count |", "|---|---:|"])
    for item in result["co_occurring_reasons"]:
        lines.append(f"| {item['reason']} | {item['count']} |")

    severe = result["severe_cases"]
    lines.extend(
        [
            "",
            "## 7. Severe cases",
            "",
            f"- Score >= 70 blocked: {severe['score_gte_70']['count']}",
            f"- Score >= 80 blocked: {severe['score_gte_80']['count']}",
            f"- Score >= 90 blocked: {severe['score_gte_90']['count']}",
            f"- RR valid but blocked: {severe['rr_valid']['count']}",
            f"- Trend aligned but blocked: {severe['trend_aligned']['count']}",
            f"- Liquidity distance passed but blocked: {severe['liquidity_distance_passed']['count']}",
            f"- Primary path-like blocked: {severe['primary_path_like']['count']}",
            f"- Secondary path-like blocked: {severe['secondary_path_like']['count']}",
            "",
            "### Highest-score examples",
            "",
            "| Symbol | Direction | Score | Setup | Session | Regime | Context | Location | Reasons |",
            "|---|---|---:|---|---|---|---|---|---|",
        ]
    )
    for row in severe["highest_score_examples"]:
        lines.append(
            f"| {row['symbol']} | {row['direction']} | {row['score']} | {row['setup_type']} | {row['session']} | "
            f"{row['market_regime']} | {row['entry_context']} | {row['trade_location']} | {', '.join(row['reasons'])} |"
        )

    lines.extend(["", "## 8. Paper evidence", ""])
    evidence = result["paper_evidence"]
    overall = evidence["overall"]
    baseline = evidence["baseline_all_closed"]
    lines.extend(
        [
            "### Target rows with closed paper outcome",
            "",
            f"- Closed trades/candidates with target: {overall['closed_trades']}",
            f"- WR: {overall['winrate']}%",
            f"- PF: {overall['profit_factor']}",
            f"- Total R: {overall['total_r']}",
            f"- Avg R: {overall['avg_r']}",
            "",
            "### Baseline all closed paper trades",
            "",
            f"- Closed trades: {baseline['closed_trades']}",
            f"- WR: {baseline['winrate']}%",
            f"- PF: {baseline['profit_factor']}",
            f"- Total R: {baseline['total_r']}",
            f"- Avg R: {baseline['avg_r']}",
            "",
            "### Best similar contexts",
            "",
            "| Context | Closed | WR | PF | Total R | Avg R |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in evidence["best_contexts"]:
        lines.append(f"| {row['context']} | {row['closed_trades']} | {row['winrate']}% | {row['profit_factor']} | {row['total_r']} | {row['avg_r']} |")
    if not evidence["best_contexts"]:
        lines.append("| no_data | 0 | 0 | 0 | 0 | 0 |")
    lines.extend(["", "### Worst similar contexts", "", "| Context | Closed | WR | PF | Total R | Avg R |", "|---|---:|---:|---:|---:|---:|"])
    for row in evidence["worst_contexts"]:
        lines.append(f"| {row['context']} | {row['closed_trades']} | {row['winrate']}% | {row['profit_factor']} | {row['total_r']} | {row['avg_r']} |")
    if not evidence["worst_contexts"]:
        lines.append("| no_data | 0 | 0 | 0 | 0 | 0 |")

    lines.extend(["", "## 9. Data gaps", ""])
    for gap in result["data_gaps"]:
        lines.append(f"- {gap}")

    lines.extend(
        [
            "",
            "## 10. Conclusion",
            "",
            f"- Evidence classification: {result['conclusion']['evidence_classification']}",
            f"- Recommended action: {result['conclusion']['recommended_action']}",
            f"- Rationale: {result['conclusion']['rationale']}",
            "",
            "Allowed action labels considered: mantener como hard veto, convertir parcialmente en penalty, relajar solo por contexto, crear shadow relaxation, datos insuficientes.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _code_origin() -> dict[str, Any]:
    return {
        "file": CODE_PATH,
        "approx_lines": "evaluate(): primary paths around lines 220-244, secondary paths around lines 245-281, fallback around lines 282-323",
        "conditions": [
            "Primary LONG passes only when entry trend is bullish, liquidity_sweep is bullish_sweep, market_structure is bullish/range, HTF is not bearish unless counter-HTF reversal is allowed, distance is not extreme, range quality is allowed when in range, and ASIA score is >= 85.",
            "Primary SHORT passes only when entry trend is bearish, liquidity_sweep is bearish_sweep, market_structure is bearish/range, HTF is not bullish, distance is not extreme, range quality is allowed when in range, and ASIA score is >= 85.",
            "Secondary LONG passes only outside ASIA with entry and HTF bullish, liquidity_sweep none, bullish BOS, volume confirmation, RSI alignment, nearest liquidity valid, structure valid, and score >= secondary threshold.",
            "Secondary SHORT passes only outside ASIA with entry and HTF bearish, liquidity_sweep none, bearish BOS, volume confirmation, RSI alignment, nearest liquidity valid, structure valid, and score >= secondary threshold.",
            "If neither primary nor secondary path passes, fallback_direction is inferred from liquidity_sweep or BOS.",
            "If bullish entry contradicts bearish HTF and counter-HTF reversal is not allowed, the code records higher_timeframe_contradicts_long instead of directional_confluence_failed.",
            "If bearish entry contradicts bullish HTF, the code records higher_timeframe_contradicts_short instead of directional_confluence_failed.",
            "`directional_confluence_failed` is appended when no valid primary/secondary path exists, no HTF contradiction-specific reason is selected, and relaxed soft allowance is disabled or unavailable.",
            "Soft allowance requires relaxed gates enabled, fallback direction present, score >= 80, no HTF contradiction for fallback, no distance_to_liquidity_extreme, and non-ASIA session.",
        ],
        "interpretation": (
            "`directional_confluence_failed` is not a single indicator failure. It is a final aggregate veto meaning the candidate "
            "could not satisfy the directional recipe for primary sweep, secondary continuation, or allowed relaxed fallback."
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
    return {
        "source": source,
        "timestamp": str(row.get("timestamp") or ""),
        "symbol": _upper(row.get("symbol")),
        "direction": _lower(row.get("direction")),
        "setup_type": _upper(row.get("setup_type") or _nested(row, "raw_summary", "setup_detected")),
        "market_regime": _upper(row.get("market_regime")),
        "session": _upper(row.get("session")),
        "entry_context": _upper(row.get("entry_context")),
        "trade_location": str(row.get("trade_location") or "UNKNOWN").strip() or "UNKNOWN",
        "score": _float(row.get("score") or _nested(row, "raw_summary", "strategy_gate_score")),
        "rr_valid": _bool(row.get("rr_valid")),
        "trend_entry": _lower(row.get("trend_entry")),
        "trend_higher": _lower(row.get("trend_higher")),
        "conditions_passed": _tokens(row.get("conditions_passed")),
        "conditions_failed": _tokens(row.get("conditions_failed")),
        "rejection_reasons": _tokens(row.get("rejection_reasons") or row.get("reasons")),
        "penalties": _tokens(row.get("penalties")),
        "avoidance_warnings": _tokens(row.get("avoidance_warnings")),
        "failed_conditions": row.get("failed_conditions") if isinstance(row.get("failed_conditions"), list) else [],
        "liquidity_sweep": _lower(row.get("liquidity_sweep")),
        "result_r": None,
        "status": _lower(row.get("status") or _nested(row, "raw_summary", "signal_status")),
    }


def _normalize_shadow(row: dict[str, Any], source: str) -> dict[str, Any]:
    module_scores = _json_dict(row.get("module_scores"))
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
        "trend_ok": _bool(row.get("trend_ok")),
        "momentum_ok": _bool(row.get("momentum_ok")),
        "liquidity_ok": _bool(row.get("liquidity_ok")),
        "conditions_passed": [],
        "conditions_failed": _tokens(row.get("current_rejection_reasons")),
        "rejection_reasons": _tokens(row.get("current_rejection_reasons")),
        "penalties": [],
        "avoidance_warnings": [],
        "failed_conditions": [],
        "liquidity_sweep": "",
        "module_scores": module_scores,
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
        "failed_conditions": [],
        "liquidity_sweep": _lower(row.get("liquidity_sweep")),
        "nearest_distance_to_liquidity_atr": _float(row.get("nearest_distance_to_liquidity_atr")),
        "directional_distance_to_liquidity_atr": _float(row.get("directional_distance_to_liquidity_atr")),
        "result_r": _float(row.get("result_r")),
        "status": _lower(row.get("status")),
    }


def _breakdowns(rows: list[dict[str, Any]], *, top: int) -> dict[str, list[dict[str, Any]]]:
    dimensions = ["symbol", "direction", "setup_type", "market_regime", "session", "entry_context", "trade_location", "score_bucket"]
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


def _failed_condition_breakdown(rows: list[dict[str, Any]], *, top: int) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for row in rows:
        for condition in row.get("failed_conditions") or []:
            if not isinstance(condition, dict):
                continue
            if condition.get("passed") is False:
                counter[str(condition.get("condition") or "unknown")] += 1
    return [{"condition": key, "count": value} for key, value in counter.most_common(top)]


def _setup_path_breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_setup_path(row)].append(row)
    return [
        {"path": path, "count": len(items), **_metrics_from_values([_float(row.get("result_r")) for row in items if _float(row.get("result_r")) is not None and _is_closed(row)])}
        for path, items in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)
    ]


def _setup_path(row: dict[str, Any]) -> str:
    setup = _upper(row.get("setup_type"))
    passed = set(row.get("conditions_passed", []))
    failed = set(row.get("conditions_failed", []) + row.get("rejection_reasons", []))
    sweep = _lower(row.get("liquidity_sweep"))
    if "primary_sweep_setup" in passed or sweep in {"bullish_sweep", "bearish_sweep"} or setup in {"MAIN_SIGNAL", "PRIMARY_SWEEP_SIGNAL"}:
        return "primary_path_like"
    if "secondary_setup" in passed or setup == "SECONDARY_SIGNAL" or "secondary_setup_requirements_failed" in failed:
        return "secondary_path_like"
    return "unknown_path"


def _co_occurring_reasons(rows: list[dict[str, Any]], *, top: int) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for row in rows:
        tokens = row.get("rejection_reasons", []) + row.get("conditions_failed", []) + row.get("penalties", []) + row.get("avoidance_warnings", [])
        for reason in set(tokens):
            if reason and TARGET_REASON not in reason:
                counter[reason] += 1
    return [{"reason": key, "count": value} for key, value in counter.most_common(top)]


def _severe_cases(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def matching(predicate) -> list[dict[str, Any]]:
        return [row for row in rows if predicate(row)]

    score70 = matching(lambda row: (_float(row.get("score")) or -1) >= 70)
    score80 = matching(lambda row: (_float(row.get("score")) or -1) >= 80)
    score90 = matching(lambda row: (_float(row.get("score")) or -1) >= 90)
    rr_valid = matching(lambda row: row.get("rr_valid") is True)
    trend_aligned = matching(_trend_aligned)
    liquidity_passed = matching(_liquidity_distance_passed)
    primary = matching(lambda row: _setup_path(row) == "primary_path_like")
    secondary = matching(lambda row: _setup_path(row) == "secondary_path_like")
    highest = sorted(rows, key=lambda row: _float(row.get("score")) or -1, reverse=True)[:15]
    return {
        "score_gte_70": _case_summary(score70),
        "score_gte_80": _case_summary(score80),
        "score_gte_90": _case_summary(score90),
        "rr_valid": _case_summary(rr_valid),
        "trend_aligned": _case_summary(trend_aligned),
        "liquidity_distance_passed": _case_summary(liquidity_passed),
        "primary_path_like": _case_summary(primary),
        "secondary_path_like": _case_summary(secondary),
        "highest_score_examples": [_example(row) for row in highest],
    }


def _case_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"count": len(rows), **_metrics_from_values([_float(row.get("result_r")) for row in rows if _float(row.get("result_r")) is not None and _is_closed(row)])}


def _paper_evidence(target_closed: list[dict[str, Any]], all_closed: list[dict[str, Any]]) -> dict[str, Any]:
    contexts: list[tuple[str, str]] = [
        ("direction", "direction"),
        ("setup_type", "setup_type"),
        ("session", "session"),
        ("market_regime", "market_regime"),
        ("entry_context", "entry_context"),
        ("trade_location", "trade_location"),
        ("direction+session", "direction|session"),
        ("direction+entry_context", "direction|entry_context"),
        ("session+market_regime", "session|market_regime"),
        ("setup_path", "setup_path"),
    ]
    summaries: list[dict[str, Any]] = []
    for label, spec in contexts:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in target_closed:
            if spec == "setup_path":
                key = _setup_path(row)
            else:
                key = " + ".join(str(row.get(part) or "UNKNOWN") for part in spec.split("|"))
            groups[key].append(row)
        for key, rows in groups.items():
            values = [_float(row.get("result_r")) for row in rows if _float(row.get("result_r")) is not None]
            summaries.append({"context": f"{label}: {key}", **_metrics_from_values(values)})
    evaluable = [row for row in summaries if row["closed_trades"] > 0]
    return {
        "overall": _metrics_from_values([_float(row.get("result_r")) for row in target_closed if _float(row.get("result_r")) is not None]),
        "baseline_all_closed": _metrics_from_values([_float(row.get("result_r")) for row in all_closed if _float(row.get("result_r")) is not None]),
        "best_contexts": sorted(evaluable, key=lambda row: (float(row["total_r"]), _pf_sort(row["profit_factor"])), reverse=True)[:10],
        "worst_contexts": sorted(evaluable, key=lambda row: (float(row["total_r"]), _pf_sort(row["profit_factor"])))[:10],
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
        "trade_location": row.get("trade_location") or "UNKNOWN",
        "reasons": sorted(set(row.get("rejection_reasons", []) + row.get("conditions_failed", [])))[:8],
        "result_r": row.get("result_r"),
    }


def _data_gaps(signal_hits: list[dict[str, Any]], shadow_hits: list[dict[str, Any]], paper_hits: list[dict[str, Any]], scheduler: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    if not signal_hits:
        gaps.append("No target records found in data/bot_activity/signals_log.jsonl.")
    if not shadow_hits:
        gaps.append("No target records found in data/paper_trading/shadow_signals.csv.")
    if not paper_hits:
        gaps.append("No target records found in data/paper_trading/trades.csv.")
    if scheduler.get("line_hits", 0) == 0:
        gaps.append("No target lines found in logs/scheduler.log.")
    closed = [row for row in paper_hits if _is_closed(row)]
    if not closed:
        gaps.append("No closed paper outcomes exist for target rows; outcome comparison is weak.")
    if not gaps:
        gaps.append("No major data gaps detected in local files.")
    return gaps


def _conclusion(severe: dict[str, Any], evidence: dict[str, Any]) -> dict[str, str]:
    overall = evidence["overall"]
    closed = int(overall.get("closed_trades", 0) or 0)
    total_r = float(overall.get("total_r", 0.0) or 0.0)
    pf = _pf_float(overall.get("profit_factor"))
    score80_count = int(severe["score_gte_80"]["count"])
    if closed < 10:
        return {
            "evidence_classification": "INSUFFICIENT_DATA",
            "recommended_action": "datos insuficientes",
            "rationale": "Hay pocos resultados paper cerrados asociados a este veto; no conviene convertirlo en penalty ni relajar todavía.",
        }
    if total_r < 0 and pf < 0.9:
        return {
            "evidence_classification": "PROTECTIVE",
            "recommended_action": "mantener como hard veto",
            "rationale": f"Los casos cerrados asociados al veto muestran TotalR {total_r} y PF {pf}; la evidencia favorece protección.",
        }
    if total_r > 0 and pf >= 1.2 and score80_count >= 5:
        return {
            "evidence_classification": "BLOCKING_EDGE",
            "recommended_action": "crear shadow relaxation",
            "rationale": "Hay edge positivo en casos similares, pero debe validarse en shadow antes de cualquier cambio real.",
        }
    return {
        "evidence_classification": "MIXED",
        "recommended_action": "relajar solo por contexto",
        "rationale": "La evidencia es mixta; cualquier relajación futura debería ser contextual, no global.",
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


def _nested(row: dict[str, Any], *keys: str) -> Any:
    value: Any = row
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        decoded = json.loads(str(value or ""))
    except json.JSONDecodeError:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _is_closed(row: dict[str, Any]) -> bool:
    status = _lower(row.get("status") or row.get("outcome"))
    return status in CLOSED_STATUSES or bool(str(row.get("closed_at") or "").strip())


def _trend_aligned(row: dict[str, Any]) -> bool:
    if row.get("trend_ok") is True:
        return True
    entry = _lower(row.get("trend_entry"))
    higher = _lower(row.get("trend_higher"))
    return bool(entry and higher and entry == higher and entry in {"bullish", "bearish"})


def _liquidity_distance_passed(row: dict[str, Any]) -> bool:
    failed = set(row.get("conditions_failed", []) + row.get("rejection_reasons", []))
    if "distance_to_liquidity" in set(row.get("conditions_passed", [])):
        return True
    if row.get("liquidity_ok") is True:
        return True
    nearest = _float(row.get("nearest_distance_to_liquidity_atr"))
    directional = _float(row.get("directional_distance_to_liquidity_atr"))
    if nearest is not None and nearest <= 2.5:
        return True
    if directional is not None and directional <= 2.5:
        return True
    return "distance_to_liquidity_extreme" not in failed and "distance_to_liquidity_penalty" not in failed


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


def _pf_sort(value: Any) -> float:
    if value == "inf":
        return 999999.0
    return _pf_float(value)


def _pf_float(value: Any) -> float:
    if value == "inf":
        return 999999.0
    parsed = _float(value)
    return parsed if parsed is not None else 0.0


def _upper(value: Any) -> str:
    text = str(value or "").strip()
    return text.upper() if text else "UNKNOWN"


def _lower(value: Any) -> str:
    return str(value or "").strip().lower()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
