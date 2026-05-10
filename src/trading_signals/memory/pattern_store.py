from __future__ import annotations

import json
import threading
from pathlib import Path


class PatternMemoryStore:
    def __init__(self, data_path: Path) -> None:
        self.path = data_path / "pattern_memory" / "patterns.jsonl"
        self._lock = threading.Lock()

    def append(self, record: dict[str, object]) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return self.path

    def list_records(self, limit: int | None = None) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        records: list[dict[str, object]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    records.append(item)
        if limit is not None and limit >= 0:
            return records[-limit:]
        return records
