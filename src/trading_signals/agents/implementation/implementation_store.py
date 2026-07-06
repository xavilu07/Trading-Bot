from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_IMPLEMENTATION_STORE_PATH = Path("data") / "qic" / "implementation_reviews.jsonl"


def append_implementation_record(record: dict[str, Any], path: Path = DEFAULT_IMPLEMENTATION_STORE_PATH) -> dict[str, Any]:
    payload = dict(record)
    payload.setdefault("stored_at", datetime.now(tz=UTC).isoformat())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return payload


def load_implementation_records(path: Path = DEFAULT_IMPLEMENTATION_STORE_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(raw, dict):
            records.append(raw)
    return records
