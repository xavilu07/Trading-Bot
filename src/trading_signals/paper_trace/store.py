from __future__ import annotations

import errno
import fcntl
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from trading_signals.paper_trace.contracts import PaperTraceReceipt, TraceContractError
from trading_signals.paper_trace.sanitize import canonical_json


class TraceStoreError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def validate_store_path(path: Path, *, data_root: Path | None = None) -> Path:
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
    return resolved


@dataclass(frozen=True, slots=True)
class TraceStoreHealth:
    status: str
    receipt_count: int
    trace_count: int
    last_sequence_by_trace: dict[str, int]
    error_code: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "receipt_count": self.receipt_count,
            "trace_count": self.trace_count,
            "last_sequence_by_trace": self.last_sequence_by_trace,
            "error_code": self.error_code,
        }


class JsonlTraceStore:
    """Small append-only store.

    A process-wide advisory lock, O_APPEND and fsync make each complete JSON
    line durable before the method returns. The hash chain is per trace, so
    unrelated traces can be interleaved safely.
    """

    def __init__(self, path: Path, *, data_root: Path | None = None) -> None:
        self.path = validate_store_path(path, data_root=data_root)

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
        if not self.path.exists():
            return ()
        if not self.path.is_file() or self.path.is_symlink():
            raise TraceStoreError("TRACE_STORE_NOT_REGULAR_FILE")
        try:
            with self.path.open("rb") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
                raw = handle.read()
        except OSError as exc:
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
        flags = os.O_RDWR | os.O_APPEND | os.O_CREAT
        try:
            descriptor = os.open(self.path, flags, 0o600)
        except OSError as exc:
            raise TraceStoreError("TRACE_STORE_OPEN_FAILED") from exc
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
                handle.seek(0, os.SEEK_END)
                for receipt in pending:
                    line = (canonical_json(receipt.to_dict()) + "\n").encode("utf-8")
                    written = handle.write(line)
                    if written != len(line):
                        raise TraceStoreError("TRACE_STORE_SHORT_WRITE")
                handle.flush()
                os.fsync(handle.fileno())
                return len(pending)
        except OSError as exc:
            if exc.errno in {errno.ENOSPC, errno.EDQUOT}:
                raise TraceStoreError("TRACE_STORE_CAPACITY_FAILED") from exc
            raise TraceStoreError("TRACE_STORE_WRITE_FAILED") from exc

    def health(self) -> TraceStoreHealth:
        try:
            receipts = self.read_all()
        except TraceStoreError as exc:
            return TraceStoreHealth("CORRUPT", 0, 0, {}, exc.code)
        last: dict[str, int] = {}
        for receipt in receipts:
            last[receipt.trace_id] = receipt.event_sequence
        return TraceStoreHealth(
            status="HEALTHY" if receipts else "EMPTY",
            receipt_count=len(receipts),
            trace_count=len(last),
            last_sequence_by_trace=last,
        )
