from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import quote

BUSY_TIMEOUT_MS = 2_500


class ReadModelPathError(ValueError):
    """Raised when a configured read-model path is unsafe or ambiguous."""


def validate_read_model_path(path: Path, *, data_root: Path | None = None) -> Path:
    candidate = path.expanduser()
    if not candidate.is_absolute():
        raise ReadModelPathError("read-model path must be absolute")
    if candidate.suffix != ".sqlite":
        raise ReadModelPathError("read-model path must end in .sqlite")
    if candidate.exists() and candidate.is_symlink():
        raise ReadModelPathError("read-model path must not be a symbolic link")

    resolved = candidate.resolve(strict=False)
    forbidden_exact = {Path("/"), Path.home().resolve(strict=False)}
    if resolved in forbidden_exact or resolved.parent == Path("/"):
        raise ReadModelPathError("read-model path is too broad")
    if data_root is not None:
        source_root = data_root.expanduser().resolve(strict=False)
        try:
            resolved.relative_to(source_root)
        except ValueError:
            pass
        else:
            raise ReadModelPathError("read-model path must be outside the source data root")
    return resolved


def connect_writer(path: Path, *, data_root: Path | None = None) -> sqlite3.Connection:
    resolved = validate_read_model_path(path, data_root=data_root)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(resolved, timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def connect_read_only(path: Path) -> sqlite3.Connection:
    resolved = validate_read_model_path(path)
    if not resolved.is_file():
        raise FileNotFoundError("read model is not available")
    uri = f"file:{quote(resolved.as_posix(), safe='/')}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    return connection


def finalize_writer(connection: sqlite3.Connection) -> None:
    if connection.in_transaction:
        raise sqlite3.OperationalError("cannot finalize a writer with an active transaction")
    connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    connection.execute("PRAGMA journal_mode = DELETE")


def integrity_check(connection: sqlite3.Connection) -> tuple[str, ...]:
    return tuple(str(row[0]) for row in connection.execute("PRAGMA integrity_check"))
