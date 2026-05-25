from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


OUTPUT_FIELDS = [
    "label",
    "label_reason",
    "result_r",
    "signal_id",
    "timestamp",
    "symbol",
    "direction",
    "market_regime",
    "session",
    "entry_context",
    "trade_location",
    "setup_type",
    "score",
    "trend",
    "trend_higher_timeframe",
    "timeframe_alignment",
    "rsi",
    "body_ratio",
    "volume_ratio",
    "atr",
    "distance_to_liquidity_atr",
    "liquidity_sweep",
    "break_of_structure",
    "has_against_htf",
    "has_low_volume",
    "has_dirty_sideways_market",
    "has_market_structure_range_penalty",
    "has_timeframe_alignment_penalty",
    "has_secondary_confluence_bonus",
    "warnings_count",
    "penalties_count",
    "meta_decision_score",
    "trade_quality_score",
    "edge_confirmation_score",
]


def build_meta_dataset(*, data_path: Path, logs_path: Path, reports_path: Path) -> dict[str, Any]:
    labels = _read_csv(reports_path / "triple_barrier_labels.csv")
    signal_index = _build_signal_index(data_path / "bot_activity" / "signals_log.jsonl")
    scheduler_index = _build_signal_index(logs_path / "scheduler.log")
    audit_index = _build_row_index(_read_csv(reports_path / "recent_public_signals_audit.csv"))
    outcome_index = _build_context_index(_read_csv(reports_path / "outcome_intelligence.csv"))

    rows = []
    for label_row in labels:
        signal_id = str(label_row.get("signal_id") or "")
        source = (
            signal_index.get(signal_id)
            or scheduler_index.get(signal_id)
            or audit_index.get(signal_id)
            or _lookup_by_fallback(label_row, signal_index, scheduler_index, audit_index)
            or {}
        )
        outcome = outcome_index.get(_context_key(label_row)) or {}
        rows.append(_build_output_row(label_row, source, outcome))

    reports_path.mkdir(parents=True, exist_ok=True)
    output_path = reports_path / "meta_dataset.csv"
    _write_csv(output_path, rows)
    return {"output_path": output_path, "rows": rows, "summary": _summary(rows)}


def format_summary(summary: dict[str, Any]) -> str:
    return (
        "🧠 Meta Dataset\n"
        f"- Total rows: {summary.get('total_rows', 0)}\n"
        f"- Labels positivas (TP_HIT): {summary.get('positive_labels', 0)}\n"
        f"- Labels negativas (SL_HIT): {summary.get('negative_labels', 0)}\n"
        f"- Unknown: {summary.get('unknown_labels', 0)}\n"
        f"- Avg result R: {summary.get('avg_result_r', 0.0)}"
    )


def _build_output_row(label_row: dict[str, str], source: dict[str, Any], outcome: dict[str, str]) -> dict[str, Any]:
    warnings = _tokens(_first(source, label_row, "avoidance_warnings", "warnings"))
    penalties = _tokens(_first(source, label_row, "penalties"))
    raw_summary = _dict(source.get("raw_summary"))
    failed_conditions = _condition_map(source.get("failed_conditions"))
    metadata = _dict(source.get("metadata"))
    label_text = str(label_row.get("label") or "").strip().upper()
    trend = _first(source, label_row, "trend_entry", "trend", "trend_1h")
    trend_higher = _first(source, label_row, "trend_higher", "trend_higher_timeframe", "trend_4h")
    return {
        "label": _numeric_label(label_text),
        "label_reason": label_row.get("label_reason", ""),
        "result_r": label_row.get("result_r", ""),
        "signal_id": label_row.get("signal_id", ""),
        "timestamp": label_row.get("timestamp", ""),
        "symbol": label_row.get("symbol", ""),
        "direction": label_row.get("direction", ""),
        "market_regime": _first(source, label_row, "market_regime"),
        "session": _first(source, label_row, "session"),
        "entry_context": _first(source, label_row, "entry_context"),
        "trade_location": _first(source, label_row, "trade_location"),
        "setup_type": _first(source, label_row, "setup_type") or raw_summary.get("setup_detected", ""),
        "score": _first(source, label_row, "score") or raw_summary.get("strategy_gate_score", ""),
        "trend": trend,
        "trend_higher_timeframe": trend_higher,
        "timeframe_alignment": _timeframe_alignment(source, trend, trend_higher),
        "rsi": _first(source, metadata, "rsi") or _condition_value(failed_conditions, "long_secondary_rsi", "short_secondary_rsi"),
        "body_ratio": _first(source, metadata, "body_ratio"),
        "volume_ratio": _first(source, metadata, "volume_ratio", "volume_ratio_vs_average_20") or _condition_value(
            failed_conditions,
            "long_secondary_volume",
            "short_secondary_volume",
        ),
        "atr": _first(source, metadata, "atr"),
        "distance_to_liquidity_atr": _first(source, metadata, "distance_to_liquidity_atr", "nearest_distance_to_liquidity_atr"),
        "liquidity_sweep": _first(source, label_row, "liquidity_sweep"),
        "break_of_structure": _first(source, metadata, "break_of_structure"),
        "has_against_htf": _has_token(warnings, penalties, "against_htf"),
        "has_low_volume": _has_token(warnings, penalties, "low_volume"),
        "has_dirty_sideways_market": _has_token(warnings, penalties, "dirty_sideways_market"),
        "has_market_structure_range_penalty": _has_token(warnings, penalties, "market_structure_range_penalty"),
        "has_timeframe_alignment_penalty": _has_token(warnings, penalties, "timeframe_alignment_penalty"),
        "has_secondary_confluence_bonus": any(token.startswith("secondary_confluence_bonus") for token in penalties),
        "warnings_count": len(warnings),
        "penalties_count": len(penalties),
        "meta_decision_score": _score_from_layers(source, outcome, "meta_decision", "meta_decision_score"),
        "trade_quality_score": _score_from_layers(source, outcome, "trade_quality", "trade_quality_score"),
        "edge_confirmation_score": _score_from_layers(source, outcome, "edge_confirmation", "edge_confirmation_score"),
    }


def _build_signal_index(path: Path) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return index
    for row in _read_jsonl(path):
        raw_summary = _dict(row.get("raw_summary"))
        signal_id = str(row.get("signal_id") or raw_summary.get("signal_id") or "")
        if signal_id:
            index[signal_id] = row
    return index


def _build_row_index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {str(row.get("signal_id")): row for row in rows if row.get("signal_id")}


def _build_context_index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {_context_key(row): row for row in rows if _context_key(row)}


def _lookup_by_fallback(label_row: dict[str, str], *indexes: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    target = _fallback_key(label_row)
    if not target:
        return None
    for index in indexes:
        for row in index.values():
            if _fallback_key(row) == target:
                return row
    return None


def _fallback_key(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("timestamp") or "")[:16],
            str(row.get("symbol") or ""),
            str(row.get("direction") or ""),
        ]
    )


def _context_key(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("symbol") or ""),
            str(row.get("direction") or ""),
            str(row.get("setup_type") or ""),
            str(row.get("market_regime") or ""),
            str(row.get("session") or ""),
            str(row.get("entry_context") or ""),
            str(row.get("trade_location") or ""),
        ]
    )


def _numeric_label(label: str) -> str:
    if label == "TP_HIT":
        return "1"
    if label == "SL_HIT":
        return "0"
    return ""


def _timeframe_alignment(source: dict[str, Any], trend: Any, trend_higher: Any) -> str:
    explicit = source.get("timeframe_alignment")
    if explicit not in {None, ""}:
        return str(explicit)
    if trend and trend_higher:
        return str(str(trend).lower() == str(trend_higher).lower()).lower()
    return ""


def _score_from_layers(source: dict[str, Any], outcome: dict[str, str], layer_key: str, score_key: str) -> Any:
    layer = _dict(source.get(layer_key))
    pattern = _dict(source.get("pattern_memory"))
    if not layer:
        layer = _dict(pattern.get(layer_key))
    return layer.get(score_key) or source.get(score_key) or outcome.get(score_key) or ""


def _condition_map(value: Any) -> dict[str, Any]:
    conditions: dict[str, Any] = {}
    parsed = _parse_json(value)
    if not isinstance(parsed, list):
        return conditions
    for item in parsed:
        if isinstance(item, dict) and item.get("condition"):
            conditions[str(item["condition"])] = item.get("value")
    return conditions


def _condition_value(conditions: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in conditions:
            return conditions[name]
    return ""


def _tokens(*values: Any) -> list[str]:
    tokens: list[str] = []
    for value in values:
        parsed = _parse_json(value)
        if isinstance(parsed, list):
            iterable = parsed
        elif value in {None, ""}:
            iterable = []
        else:
            iterable = str(value).replace("|", ",").split(",")
        for item in iterable:
            text = str(item).strip()
            if not text:
                continue
            tokens.append(text)
            if ":" in text:
                tokens.append(text.split(":", 1)[0].strip())
            if "=" in text:
                tokens.append(text.split("=", 1)[0].strip())
    seen: set[str] = set()
    deduped = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            deduped.append(token)
    return deduped


def _has_token(warnings: list[str], penalties: list[str], token: str) -> bool:
    return token in set(warnings) or token in set(penalties)


def _first(*sources_and_keys: Any) -> Any:
    sources: list[dict[str, Any]] = []
    keys: list[str] = []
    for item in sources_and_keys:
        if isinstance(item, dict) and not keys:
            sources.append(item)
        else:
            keys.append(str(item))
    for source in sources:
        for key in keys:
            value = source.get(key)
            if value is not None and value != "":
                return value
    return ""


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result_values = [_float(row.get("result_r")) for row in rows if _float(row.get("result_r")) is not None]
    return {
        "total_rows": len(rows),
        "positive_labels": sum(1 for row in rows if row.get("label") == "1"),
        "negative_labels": sum(1 for row in rows if row.get("label") == "0"),
        "unknown_labels": sum(1 for row in rows if row.get("label") == ""),
        "avg_result_r": round(sum(result_values) / len(result_values), 4) if result_values else 0.0,
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except csv.Error:
        return []


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in OUTPUT_FIELDS})


def _parse_json(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="build-meta-dataset")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--logs-path", default="logs")
    parser.add_argument("--reports-path", default="reports")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = build_meta_dataset(
        data_path=Path(args.data_path),
        logs_path=Path(args.logs_path),
        reports_path=Path(args.reports_path),
    )
    print(format_summary(result["summary"]))
    print(f"Report: {result['output_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
