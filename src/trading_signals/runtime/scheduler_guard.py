from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
from typing import IO, Any

from trading_signals.runtime.identity import validate_runtime_identity


class DuplicateSchedulerError(RuntimeError):
    pass


class SchedulerInstanceGuard:
    """Advisory process lock kept open for the scheduler lifetime."""

    def __init__(self, path: Path, identity: dict[str, Any]) -> None:
        self.path = path
        self.identity = dict(identity)
        self._handle: IO[str] | None = None

    def acquire(self) -> "SchedulerInstanceGuard":
        validate_runtime_identity(self.identity)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.seek(0)
            owner = handle.read().strip() or "unknown owner"
            handle.close()
            raise DuplicateSchedulerError(f"scheduler already active: {owner}") from exc
        handle.seek(0)
        handle.truncate()
        json.dump({"pid": os.getpid(), **self.identity}, handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
        self._handle = handle
        return self

    def release(self) -> None:
        if self._handle is None:
            return
        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None

    def __enter__(self) -> "SchedulerInstanceGuard":
        return self.acquire()

    def __exit__(self, *_args: object) -> None:
        self.release()
