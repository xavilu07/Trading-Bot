from __future__ import annotations

import errno
import fcntl
import json
import os
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from trading_signals.paper_trace.contracts import PaperTraceReceipt, TraceContractError
from trading_signals.paper_trace.sanitize import canonical_json


class TraceStoreError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def validate_store_path(
    path: Path,
    *,
    data_root: Path | None = None,
    allowed_root: Path | None = None,
) -> Path:
    candidate = path.expanduser()
    if not candidate.is_absolute() or candidate.name in {"", ".", ".."}:
        raise TraceStoreError("TRACE_STORE_PATH_UNSAFE")
    if candidate.suffix.lower() != ".jsonl":
        raise TraceStoreError("TRACE_STORE_EXTENSION_INVALID")
    if candidate.is_symlink() or candidate.parent.is_symlink():
        raise TraceStoreError("TRACE_STORE_SYMLINK_REJECTED")
    parent = candidate.parent.resolve(strict=True)
    resolved = parent / candidate.name
    if resolved == Path("/") or len(resolved.parts) < 4:
        raise TraceStoreError("TRACE_STORE_PATH_UNSAFE")
    if data_root is not None:
        protected = data_root.resolve(strict=False)
        try:
            resolved.relative_to(protected)
        except ValueError:
            pass
        else:
            raise TraceStoreError("TRACE_STORE_DATA_ROOT_REJECTED")
    if allowed_root is not None:
        root = allowed_root.expanduser().resolve(strict=True)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise TraceStoreError("TRACE_STORE_OUTSIDE_ALLOWED_ROOT") from exc
    parent_stat = parent.stat()
    if parent_stat.st_uid != os.geteuid() or parent_stat.st_mode & 0o077:
        raise TraceStoreError("TRACE_STORE_PARENT_PERMISSIONS_UNSAFE")
    return resolved


@dataclass(frozen=True, slots=True)
class TraceStoreHealth:
    status: str
    receipt_count: int
    trace_count: int
    last_sequence_by_trace: dict[str, int]
    error_code: str | None = None
    size_bytes: int = 0
    max_bytes: int | None = None
    free_bytes: int | None = None
    segment_count: int = 0
    rotation_enabled: bool = False
    last_receipt_id: str | None = None
    last_write_at: str | None = None
    active_trace_count: int = 0
    duplicate_count: int = 0
    invalid_chain_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "receipt_count": self.receipt_count,
            "trace_count": self.trace_count,
            "last_sequence_by_trace": self.last_sequence_by_trace,
            "error_code": self.error_code,
            "size_bytes": self.size_bytes,
            "max_bytes": self.max_bytes,
            "free_bytes": self.free_bytes,
            "segment_count": self.segment_count,
            "rotation_enabled": self.rotation_enabled,
            "last_receipt_id": self.last_receipt_id,
            "last_write_at": self.last_write_at,
            "active_trace_count": self.active_trace_count,
            "duplicate_count": self.duplicate_count,
            "invalid_chain_count": self.invalid_chain_count,
        }


class JsonlTraceStore:
    """Small append-only store.

    A process-wide advisory lock, O_APPEND and fsync make each complete JSON
    line durable before the method returns. The hash chain is per trace, so
    unrelated traces can be interleaved safely.
    """

    def __init__(
        self,
        path: Path,
        *,
        data_root: Path | None = None,
        allowed_root: Path | None = None,
        max_bytes: int | None = None,
    ) -> None:
        self.path = validate_store_path(
            path,
            data_root=data_root,
            allowed_root=allowed_root,
        )
        if max_bytes is not None and max_bytes <= 0:
            raise TraceStoreError("TRACE_STORE_MAX_BYTES_INVALID")
        self.max_bytes = max_bytes

    @staticmethod
    def _secure_open_flags(flags: int) -> int:
        return flags | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)

    @staticmethod
    def _validate_descriptor(descriptor: int) -> None:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise TraceStoreError("TRACE_STORE_NOT_REGULAR_FILE")
        if metadata.st_uid != os.geteuid() or metadata.st_mode & 0o077:
            raise TraceStoreError("TRACE_STORE_FILE_PERMISSIONS_UNSAFE")

    @staticmethod
    def _parse_raw(raw: bytes) -> tuple[PaperTraceReceipt, ...]:
        if raw and not raw.endswith(b"\n"):
            raise TraceStoreError("TRACE_STORE_TRUNCATED_LINE")
        receipts: list[PaperTraceReceipt] = []
        for line_number, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                raise TraceStoreError("TRACE_STORE_EMPTY_LINE")
            try:
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise ValueError
                receipts.append(PaperTraceReceipt.from_dict(payload))
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, KeyError, TypeError, TraceContractError) as exc:
                raise TraceStoreError(f"TRACE_STORE_INVALID_RECEIPT_LINE_{line_number}") from exc
        JsonlTraceStore._validate_receipts(receipts)
        return tuple(receipts)

    def _read_handle(self) -> Iterable[PaperTraceReceipt]:
        try:
            descriptor = os.open(
                self.path,
                self._secure_open_flags(os.O_RDONLY),
            )
        except FileNotFoundError:
            return ()
        except OSError as exc:
            raise TraceStoreError("TRACE_STORE_READ_FAILED") from exc
        try:
            self._validate_descriptor(descriptor)
            with os.fdopen(descriptor, "rb") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
                raw = handle.read()
                descriptor = -1
        except TraceStoreError:
            if descriptor >= 0:
                os.close(descriptor)
            raise
        except OSError as exc:
            if descriptor >= 0:
                os.close(descriptor)
            raise TraceStoreError("TRACE_STORE_READ_FAILED") from exc
        return self._parse_raw(raw)

    @staticmethod
    def _validate_receipts(receipts: Iterable[PaperTraceReceipt]) -> None:
        last_by_trace: dict[str, PaperTraceReceipt] = {}
        ids: dict[str, str] = {}
        for receipt in receipts:
            existing_hash = ids.get(receipt.receipt_id)
            if existing_hash is not None:
                if existing_hash != receipt.receipt_hash:
                    raise TraceStoreError("TRACE_STORE_RECEIPT_ID_COLLISION")
                raise TraceStoreError("TRACE_STORE_DUPLICATE_RECEIPT")
            ids[receipt.receipt_id] = receipt.receipt_hash
            previous = last_by_trace.get(receipt.trace_id)
            expected_sequence = 1 if previous is None else previous.event_sequence + 1
            expected_previous = None if previous is None else previous.receipt_id
            if (
                receipt.event_sequence != expected_sequence
                or receipt.previous_receipt_id != expected_previous
            ):
                raise TraceStoreError("TRACE_STORE_CHAIN_BROKEN")
            last_by_trace[receipt.trace_id] = receipt

    def read_all(self) -> tuple[PaperTraceReceipt, ...]:
        return tuple(self._read_handle())

    def read_trace(self, trace_id: str) -> tuple[PaperTraceReceipt, ...]:
        return tuple(item for item in self.read_all() if item.trace_id == trace_id)

    def append(self, receipts: Iterable[PaperTraceReceipt]) -> int:
        incoming = tuple(receipts)
        if not incoming:
            return 0
        flags = self._secure_open_flags(os.O_RDWR | os.O_APPEND | os.O_CREAT)
        try:
            descriptor = os.open(self.path, flags, 0o600)
        except OSError as exc:
            raise TraceStoreError("TRACE_STORE_OPEN_FAILED") from exc
        try:
            self._validate_descriptor(descriptor)
        except TraceStoreError:
            os.close(descriptor)
            raise
        try:
            with os.fdopen(descriptor, "a+b", buffering=0) as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                handle.seek(0)
                existing = self._parse_raw(handle.read())
                known = {receipt.receipt_id: receipt for receipt in existing}
                pending: list[PaperTraceReceipt] = []
                for receipt in incoming:
                    prior = known.get(receipt.receipt_id)
                    if prior is not None:
                        if prior.receipt_hash != receipt.receipt_hash:
                            raise TraceStoreError("TRACE_STORE_RECEIPT_ID_COLLISION")
                        continue
                    pending.append(receipt)
                    known[receipt.receipt_id] = receipt
                combined = (*existing, *pending)
                self._validate_receipts(combined)
                encoded = [
                    (canonical_json(receipt.to_dict()) + "\n").encode("utf-8")
                    for receipt in pending
                ]
                current_size = handle.seek(0, os.SEEK_END)
                if (
                    self.max_bytes is not None
                    and current_size + sum(map(len, encoded)) > self.max_bytes
                ):
                    raise TraceStoreError("TRACE_STORE_MAX_BYTES_EXCEEDED")
                for line in encoded:
                    written = handle.write(line)
                    if written != len(line):
                        raise TraceStoreError("TRACE_STORE_SHORT_WRITE")
                handle.flush()
                os.fsync(handle.fileno())
            parent_descriptor = os.open(
                self.path.parent,
                self._secure_open_flags(os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)),
            )
            try:
                os.fsync(parent_descriptor)
            finally:
                os.close(parent_descriptor)
            return len(pending)
        except OSError as exc:
            if exc.errno in {errno.ENOSPC, errno.EDQUOT}:
                raise TraceStoreError("TRACE_STORE_CAPACITY_FAILED") from exc
            raise TraceStoreError("TRACE_STORE_WRITE_FAILED") from exc

    def health(self) -> TraceStoreHealth:
        size_bytes = 0
        last_write_at = None
        segment_count = 0
        try:
            metadata = self.path.stat()
            size_bytes = metadata.st_size
            last_write_at = datetime.fromtimestamp(
                metadata.st_mtime,
                tz=UTC,
            ).isoformat()
            segment_count = 1
        except FileNotFoundError:
            pass
        try:
            free_bytes = os.statvfs(self.path.parent).f_bavail * os.statvfs(
                self.path.parent
            ).f_frsize
        except OSError:
            free_bytes = None
        try:
            receipts = self.read_all()
        except TraceStoreError as exc:
            return TraceStoreHealth(
                "CORRUPT",
                0,
                0,
                {},
                exc.code,
                size_bytes=size_bytes,
                max_bytes=self.max_bytes,
                free_bytes=free_bytes,
                segment_count=segment_count,
                invalid_chain_count=1,
            )
        last: dict[str, int] = {}
        by_trace: dict[str, list[PaperTraceReceipt]] = {}
        for receipt in receipts:
            last[receipt.trace_id] = receipt.event_sequence
            by_trace.setdefault(receipt.trace_id, []).append(receipt)
        from trading_signals.paper_trace.state_machine import (
            TraceTransitionError,
            replay_receipts,
        )

        active = 0
        try:
            for trace_receipts in by_trace.values():
                state = replay_receipts(trace_receipts)
                if (
                    state.signal.value == "ACCEPTED"
                    and state.order.value not in {"CANCELLED", "EXPIRED"}
                    and state.position.value
                    not in {
                        "CLOSED_WIN",
                        "CLOSED_LOSS",
                        "CLOSED_TIME_EXIT",
                        "EXPIRED_UNRESOLVED",
                        "AMBIGUOUS",
                        "DATA_BLOCKED",
                    }
                ):
                    active += 1
        except TraceTransitionError:
            return TraceStoreHealth(
                "CORRUPT",
                len(receipts),
                len(last),
                last,
                "TRACE_STORE_STATE_INVALID",
                size_bytes=size_bytes,
                max_bytes=self.max_bytes,
                free_bytes=free_bytes,
                segment_count=segment_count,
                invalid_chain_count=1,
            )
        return TraceStoreHealth(
            status="HEALTHY" if receipts else "EMPTY",
            receipt_count=len(receipts),
            trace_count=len(last),
            last_sequence_by_trace=last,
            size_bytes=size_bytes,
            max_bytes=self.max_bytes,
            free_bytes=free_bytes,
            segment_count=segment_count,
            last_receipt_id=receipts[-1].receipt_id if receipts else None,
            last_write_at=last_write_at,
            active_trace_count=active,
        )
