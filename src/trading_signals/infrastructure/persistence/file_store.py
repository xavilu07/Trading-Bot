from __future__ import annotations

import csv
import json
import threading
from pathlib import Path


class FileStore:
    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self._lock = threading.Lock()

    def write_json(self, category: str, date_key: str, entity_id: str, payload: dict[str, object]) -> Path:
        target_dir = self.base_path / category / date_key
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{entity_id}.json"
        temp = target.with_suffix(".json.tmp")
        with self._lock:
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            temp.replace(target)
        return target

    def read_json(self, category: str, entity_id: str) -> dict[str, object] | None:
        category_dir = self.base_path / category
        for file in category_dir.glob(f"**/{entity_id}.json"):
            return json.loads(file.read_text(encoding="utf-8"))
        return None

    def list_json(self, category: str, limit: int = 20) -> list[dict[str, object]]:
        category_dir = self.base_path / category
        if not category_dir.exists():
            return []
        files = sorted(category_dir.glob("**/*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        return [json.loads(path.read_text(encoding="utf-8")) for path in files[:limit]]

    def append_csv_row(
        self,
        category: str,
        date_key: str,
        row: dict[str, object],
        fieldnames: list[str],
    ) -> Path:
        target_dir = self.base_path / category
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{date_key}.csv"
        with self._lock:
            file_exists = target.exists()
            with target.open("a", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(row)
        return target
