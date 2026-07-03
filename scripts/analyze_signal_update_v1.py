from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from trading_signals.application.use_cases.signal_update_v1 import (
    write_signal_update_v1_design_report,
    write_signal_update_v1_shadow_report,
)


TARGET_REASON = "duplicate_signal_suppressed"


def main() -> int:
    data_path = Path(os.getenv("DATA_STORAGE_PATH", "./data"))
    reports_path = Path("reports")
    logs_path = Path("logs")
    reports_path.mkdir(parents=True, exist_ok=True)
    design_path = write_signal_update_v1_design_report(reports_path)
    shadow_path = write_signal_update_v1_shadow_report(reports_path=reports_path)
    diagnostics = build_historical_diagnostics(data_path)
    runtime = build_runtime_diagnostics(logs_path / "scheduler.log")
    shadow = _read_json(shadow_path)
    shadow["historical_duplicate_diagnostics"] = diagnostics
    shadow["runtime_signal_update_diagnostics"] = runtime
    shadow_path.write_text(json.dumps(shadow, indent=2, sort_keys=True), encoding="utf-8")

    print("SIGNAL_UPDATE_V1")
    print(f"Design report: {design_path}")
    print(f"Shadow report: {shadow_path}")
    print(f"Historical duplicate_signal_suppressed: {diagnostics['total']}")
    print(f"Runtime detected: {runtime['detected']}")
    print(f"Runtime skipped: {runtime['skipped']}")
    return 0


def build_historical_diagnostics(data_path: Path) -> dict[str, Any]:
    rows = _read_signal_log_rows(data_path / "bot_activity" / "signals_log.jsonl")
    matches = [row for row in rows if _contains_reason(row, TARGET_REASON)]
    return {
        "source": str(data_path / "bot_activity" / "signals_log.jsonl"),
        "total": len(matches),
        "by_symbol": dict(_counter(matches, "symbol").most_common(10)),
        "by_direction": dict(_counter(matches, "direction").most_common(10)),
        "by_setup_type": dict(_counter(matches, "setup_type").most_common(10)),
        "by_score_bucket": dict(_score_buckets(matches).most_common()),
        "note": (
            "Historical rows are diagnostic only. Runtime classification needs the active signal repository "
            "to compare current candidate against the latest published same symbol+direction signal."
        ),
    }


def build_runtime_diagnostics(log_file: Path) -> dict[str, Any]:
    events = _read_scheduler_events(log_file)
    detected = [event for event in events if event.get("event") == "signal_update_v1_detected"]
    classified = [event for event in events if event.get("event") == "signal_update_v1_classified"]
    skipped = [event for event in events if event.get("event") == "signal_update_v1_skipped"]
    shadow_decisions = [event for event in events if event.get("event") == "signal_update_v1_shadow_decision"]
    return {
        "source": str(log_file),
        "detected": len(detected),
        "classified": len(classified),
        "skipped": len(skipped),
        "shadow_decision": len(shadow_decisions),
        "by_update_type": dict(Counter(str(event.get("update_type") or "UNKNOWN") for event in classified).most_common()),
        "by_skip_reason": dict(Counter(str(event.get("skip_reason") or "UNKNOWN") for event in skipped).most_common()),
        "latest_detected": detected[-1] if detected else None,
        "latest_classified": classified[-1] if classified else None,
        "latest_skipped": skipped[-1] if skipped else None,
        "latest_shadow_decision": shadow_decisions[-1] if shadow_decisions else None,
        "note": "SIGNAL_UPDATE_V1_DEV_NOTE_ENABLED only controls DEV Telegram notes; runtime logs should exist even when it is false.",
    }


def _read_signal_log_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _read_scheduler_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        row = _parse_json_line(line)
        if row:
            rows.append(row)
    return rows


def _parse_json_line(line: str) -> dict[str, Any] | None:
    raw = line.strip()
    if not raw:
        return None
    candidates = [raw]
    brace = raw.find("{")
    if brace > 0:
        candidates.append(raw[brace:])
    for candidate in candidates:
        try:
            row = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            return row
    return None


def _contains_reason(row: dict[str, Any], reason: str) -> bool:
    values: list[str] = []
    for key in ("rejection_reasons", "conditions_failed", "failed_conditions"):
        raw = row.get(key)
        if isinstance(raw, list):
            values.extend(str(item) for item in raw)
        elif raw:
            values.append(str(raw))
    values.append(str(row.get("reasons", "")))
    raw_summary = row.get("raw_summary")
    if isinstance(raw_summary, dict):
        values.append(str(raw_summary.get("publish_filter_reason", "")))
    return any(reason in value for value in values)


def _counter(rows: list[dict[str, Any]], key: str) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        value = str(row.get(key) or "UNKNOWN")
        counter[value] += 1
    return counter


def _score_buckets(rows: list[dict[str, Any]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        score = _float(row.get("score"))
        if score is None:
            bucket = "UNKNOWN"
        elif score < 70:
            bucket = "<70"
        elif score < 80:
            bucket = "70-79"
        elif score < 90:
            bucket = "80-89"
        else:
            bucket = "90+"
        counter[bucket] += 1
    return counter


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
