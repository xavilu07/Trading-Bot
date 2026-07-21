from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(tz=UTC).isoformat()


def read_json_safe(path: Path, default: Any = None, *, recover: bool = True) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        if recover:
            backup = path.with_suffix(path.suffix + ".last_good")
            if backup.exists():
                try:
                    return json.loads(backup.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    pass
        return default


def atomic_write_json(path: Path, payload: Any, *, keep_last_good: bool = True) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if keep_last_good and path.exists():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            current = None
        if current is not None:
            _atomic_text(path.with_suffix(path.suffix + ".last_good"), json.dumps(current, indent=2, sort_keys=True))
    _atomic_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return path


def atomic_write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_text(path, content)
    return path


def append_jsonl(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
    return path


def file_age_seconds(path: Path, *, now: float | None = None) -> float | None:
    if not path.exists():
        return None
    return max(0.0, (time.time() if now is None else now) - path.stat().st_mtime)


class ProcessLock(AbstractContextManager["ProcessLock"]):
    def __init__(self, path: Path, *, stale_after_seconds: float = 7200) -> None:
        self.path = path
        self.stale_after_seconds = max(1.0, stale_after_seconds)
        self.acquired = False

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and self._is_stale():
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return False
        payload = json.dumps({"pid": os.getpid(), "created_at": utc_now()}).encode("utf-8")
        os.write(descriptor, payload)
        os.close(descriptor)
        self.acquired = True
        return True

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        self.acquired = False

    def __enter__(self) -> "ProcessLock":
        if not self.acquire():
            raise RuntimeError(f"lock_already_held:{self.path}")
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()

    def _is_stale(self) -> bool:
        age = file_age_seconds(self.path)
        if age is None or age <= self.stale_after_seconds:
            return False
        payload = read_json_safe(self.path, {})
        pid = int(payload.get("pid") or 0) if isinstance(payload, dict) else 0
        return not _pid_exists(pid)


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            if not content.endswith("\n"):
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
