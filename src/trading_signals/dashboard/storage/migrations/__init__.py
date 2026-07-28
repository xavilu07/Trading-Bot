from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_MIGRATION_NAME = re.compile(r"^(?P<version>[0-9]{4})_[a-z0-9_]+\.sql$")


class MigrationError(RuntimeError):
    """Base migration failure."""


class MigrationChecksumError(MigrationError):
    """An applied migration no longer matches its recorded checksum."""


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    sql: str
    checksum: str


def default_migrations_dir() -> Path:
    return Path(__file__).resolve().parent


def load_migrations(directory: Path | None = None) -> tuple[Migration, ...]:
    root = directory or default_migrations_dir()
    migrations: list[Migration] = []
    for path in sorted(root.glob("*.sql")):
        match = _MIGRATION_NAME.fullmatch(path.name)
        if match is None:
            continue
        sql = path.read_text(encoding="utf-8")
        migrations.append(
            Migration(
                version=int(match.group("version")),
                name=path.name,
                sql=sql,
                checksum=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
            )
        )
    versions = [migration.version for migration in migrations]
    if not migrations or versions != sorted(set(versions)):
        raise MigrationError("migrations must have unique ordered versions")
    if versions != list(range(1, len(versions) + 1)):
        raise MigrationError("migration versions must be contiguous from 0001")
    return tuple(migrations)


def _bootstrap(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL,
            checksum TEXT NOT NULL
        )
        """
    )


def apply_migrations(
    connection: sqlite3.Connection,
    *,
    migrations_dir: Path | None = None,
) -> tuple[int, ...]:
    migrations = load_migrations(migrations_dir)
    _bootstrap(connection)
    applied = {
        int(row[0]): str(row[1])
        for row in connection.execute("SELECT version, checksum FROM schema_migrations ORDER BY version")
    }
    known_versions = {migration.version for migration in migrations}
    if set(applied) - known_versions:
        raise MigrationError("database contains an unknown migration version")
    for migration in migrations:
        recorded = applied.get(migration.version)
        if recorded is not None and recorded != migration.checksum:
            raise MigrationChecksumError(f"migration {migration.version:04d} checksum mismatch")

    newly_applied: list[int] = []
    for migration in migrations:
        if migration.version in applied:
            continue
        applied_at = datetime.now(timezone.utc).isoformat()
        checksum = migration.checksum
        script = (
            "BEGIN IMMEDIATE;\n"
            f"{migration.sql}\n"
            "INSERT INTO schema_migrations(version, applied_at, checksum) "
            f"VALUES ({migration.version}, '{applied_at}', '{checksum}');\n"
            "COMMIT;\n"
        )
        try:
            connection.executescript(script)
        except sqlite3.DatabaseError as exc:
            if connection.in_transaction:
                connection.rollback()
            raise MigrationError(f"migration {migration.version:04d} failed") from exc
        newly_applied.append(migration.version)
    return tuple(newly_applied)


def schema_is_current(
    connection: sqlite3.Connection,
    *,
    migrations_dir: Path | None = None,
) -> bool:
    migrations = load_migrations(migrations_dir)
    try:
        rows = tuple(connection.execute("SELECT version, checksum FROM schema_migrations ORDER BY version"))
    except sqlite3.DatabaseError:
        return False
    expected = tuple((item.version, item.checksum) for item in migrations)
    actual = tuple((int(row[0]), str(row[1])) for row in rows)
    return actual == expected
