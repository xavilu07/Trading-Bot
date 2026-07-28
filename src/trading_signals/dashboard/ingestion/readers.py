from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

AfterReadHook = Callable[[Path], None]


class SourceReadError(RuntimeError):
    code = "SOURCE_READ_ERROR"


class SourceChangedError(SourceReadError):
    code = "SOURCE_CHANGED_DURING_READ"


class SourceCorruptError(SourceReadError):
    code = "SOURCE_CORRUPT"


class SourceSchemaError(SourceReadError):
    code = "SOURCE_SCHEMA_INVALID"


@dataclass(frozen=True, slots=True)
class ConsistentSnapshot:
    payload: bytes
    source_identity: str
    fingerprint: str
    observed_at_ns: int


@dataclass(frozen=True, slots=True)
class JsonlCheckpoint:
    source_identity: str | None = None
    byte_offset: int = 0
    source_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class JsonlBatch:
    records: tuple[dict[str, object], ...]
    source_identity: str
    source_fingerprint: str
    next_byte_offset: int
    reset_from_checkpoint: bool
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class CsvSnapshot:
    rows: tuple[dict[str, str], ...]
    source_identity: str
    fingerprint: str
    observed_at_ns: int


def _identity(stat: os.stat_result) -> str:
    material = f"{stat.st_dev}:{stat.st_ino}"
    return hashlib.sha256(material.encode("ascii")).hexdigest()


def read_consistent_bytes(
    path: Path,
    *,
    retries: int = 2,
    max_bytes: int = 64 * 1024 * 1024,
    after_read: AfterReadHook | None = None,
) -> ConsistentSnapshot:
    if retries < 1:
        raise ValueError("retries must be positive")
    for _ in range(retries):
        before = path.stat()
        if not path.is_file() or path.is_symlink():
            raise SourceReadError("source must be a regular non-symlink file")
        if before.st_size > max_bytes:
            raise SourceReadError("source exceeds the configured read limit")
        payload = path.read_bytes()
        if after_read is not None:
            after_read(path)
        after = path.stat()
        before_identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        if before_identity == after_identity and len(payload) == before.st_size:
            return ConsistentSnapshot(
                payload=payload,
                source_identity=_identity(before),
                fingerprint=hashlib.sha256(payload).hexdigest(),
                observed_at_ns=before.st_mtime_ns,
            )
    raise SourceChangedError("source changed during bounded snapshot reads")


def read_json_snapshot(
    path: Path,
    *,
    retries: int = 2,
    max_bytes: int = 64 * 1024 * 1024,
    after_read: AfterReadHook | None = None,
) -> tuple[dict[str, object], ConsistentSnapshot]:
    snapshot = read_consistent_bytes(
        path,
        retries=retries,
        max_bytes=max_bytes,
        after_read=after_read,
    )
    try:
        parsed = json.loads(snapshot.payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceCorruptError("invalid JSON document") from exc
    if not isinstance(parsed, dict):
        raise SourceSchemaError("expected a JSON object")
    return parsed, snapshot


def read_jsonl_increment(
    path: Path,
    checkpoint: JsonlCheckpoint | None = None,
    *,
    max_bytes: int = 64 * 1024 * 1024,
    after_read: AfterReadHook | None = None,
) -> JsonlBatch:
    current = checkpoint or JsonlCheckpoint()
    before = path.stat()
    if not path.is_file() or path.is_symlink():
        raise SourceReadError("source must be a regular non-symlink file")
    identity = _identity(before)
    reset = current.source_identity not in {None, identity} or before.st_size < current.byte_offset
    prefix = b""
    if not reset and current.byte_offset:
        with path.open("rb") as handle:
            prefix = handle.read(current.byte_offset)
        if len(prefix) != current.byte_offset:
            reset = True
        elif (
            current.source_fingerprint is not None
            and hashlib.sha256(prefix).hexdigest() != current.source_fingerprint
        ):
            reset = True
    offset = 0 if reset else current.byte_offset
    if reset:
        prefix = b""
    available = before.st_size - offset
    if available > max_bytes:
        raise SourceReadError("JSONL increment exceeds the configured read limit")
    with path.open("rb") as handle:
        handle.seek(offset)
        payload = handle.read(available)
    if after_read is not None:
        after_read(path)
    after = path.stat()
    if (after.st_dev, after.st_ino) != (before.st_dev, before.st_ino) or after.st_size < before.st_size:
        raise SourceChangedError("JSONL source was replaced or truncated during read")

    records: list[dict[str, object]] = []
    consumed = 0
    error_code: str | None = None
    for line in payload.splitlines(keepends=True):
        if not line.endswith(b"\n"):
            break
        try:
            parsed = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            error_code = SourceCorruptError.code
            break
        if not isinstance(parsed, dict):
            error_code = SourceSchemaError.code
            break
        records.append(parsed)
        consumed += len(line)
    consumed_prefix = prefix + payload[:consumed]
    return JsonlBatch(
        records=tuple(records),
        source_identity=identity,
        source_fingerprint=hashlib.sha256(consumed_prefix).hexdigest(),
        next_byte_offset=offset + consumed,
        reset_from_checkpoint=reset,
        error_code=error_code,
    )


def read_csv_snapshot(
    path: Path,
    *,
    required_columns: tuple[str, ...],
    retries: int = 2,
    max_bytes: int = 64 * 1024 * 1024,
    after_read: AfterReadHook | None = None,
) -> CsvSnapshot:
    snapshot = read_consistent_bytes(
        path,
        retries=retries,
        max_bytes=max_bytes,
        after_read=after_read,
    )
    try:
        text = snapshot.payload.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        header = tuple(reader.fieldnames or ())
        if not header or len(set(header)) != len(header):
            raise SourceSchemaError("CSV header is missing or duplicated")
        missing = set(required_columns) - set(header)
        if missing:
            raise SourceSchemaError("CSV header is incompatible")
        rows: list[dict[str, str]] = []
        for raw in reader:
            if None in raw or any(value is None for value in raw.values()):
                raise SourceSchemaError("CSV row does not match the header")
            rows.append({str(key): str(value) for key, value in raw.items()})
    except (UnicodeDecodeError, csv.Error) as exc:
        raise SourceCorruptError("invalid CSV document") from exc
    return CsvSnapshot(
        rows=tuple(rows),
        source_identity=snapshot.source_identity,
        fingerprint=snapshot.fingerprint,
        observed_at_ns=snapshot.observed_at_ns,
    )
