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
    reports_path.mkdir(parents=True, exist_ok=True)
    design_path = write_signal_update_v1_design_report(reports_path)
    shadow_path = write_signal_update_v1_shadow_report(reports_path=reports_path)
    diagnostics = build_historical_diagnostics(data_path)
    shadow = _read_json(shadow_path)
    shadow["historical_duplicate_diagnostics"] = diagnostics
    shadow_path.write_text(json.dumps(shadow, indent=2, sort_keys=True), encoding="utf-8")

    print("SIGNAL_UPDATE_V1")
    print(f"Design report: {design_path}")
    print(f"Shadow report: {shadow_path}")
    print(f"Historical duplicate_signal_suppressed: {diagnostics['total']}")
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
