from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from trading_signals.dashboard.storage import (
    MigrationChecksumError,
    ReadModelPathError,
    apply_migrations,
    connect_read_only,
    connect_writer,
    integrity_check,
    schema_is_current,
    validate_read_model_path,
)
from trading_signals.dashboard.storage.migrations import default_migrations_dir, load_migrations

EXPECTED_TABLES = {
    "schema_migrations",
    "source_metadata",
    "ingestion_checkpoints",
    "system_snapshots",
    "cycles",
    "signals",
}


def test_empty_database_migrates_once_and_repeats_without_changes(tmp_path: Path) -> None:
    database = tmp_path / "runtime/read-model.sqlite"
    connection = connect_writer(database, data_root=tmp_path / "data")
    try:
        assert apply_migrations(connection) == (1,)
        before = tuple(connection.execute("SELECT * FROM schema_migrations"))
        assert apply_migrations(connection) == ()
        assert tuple(connection.execute("SELECT * FROM schema_migrations")) == before
        assert schema_is_current(connection)
    finally:
        connection.close()


def test_schema_contains_only_declared_tables_and_required_indexes(tmp_path: Path) -> None:
    connection = connect_writer(tmp_path / "runtime/model.sqlite", data_root=tmp_path / "data")
    try:
        apply_migrations(connection)
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        assert tables == EXPECTED_TABLES
        indexes = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            )
        }
        assert {
            "idx_system_snapshots_observed_at",
            "idx_cycles_started_at",
            "idx_cycles_source",
            "idx_cycles_status",
            "idx_cycles_strategy",
            "idx_signals_timestamp",
            "idx_signals_source",
            "idx_signals_cycle",
            "idx_signals_symbol",
            "idx_signals_decision",
            "idx_signals_strategy",
        } <= indexes
        assert integrity_check(connection) == ("ok",)
        assert int(connection.execute("PRAGMA foreign_keys").fetchone()[0]) == 1
        assert str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
        assert int(connection.execute("PRAGMA busy_timeout").fetchone()[0]) == 2500
    finally:
        connection.close()


def test_migration_versions_are_ordered_and_contiguous() -> None:
    migrations = load_migrations()
    assert [item.version for item in migrations] == list(range(1, len(migrations) + 1))


def test_applied_migration_checksum_mismatch_fails_safely(tmp_path: Path) -> None:
    migrations_dir = tmp_path / "migrations"
    shutil.copytree(default_migrations_dir(), migrations_dir)
    database = tmp_path / "runtime/model.sqlite"
    connection = connect_writer(database, data_root=tmp_path / "data")
    try:
        assert apply_migrations(connection, migrations_dir=migrations_dir) == (1,)
        migration = migrations_dir / "0001_initial.sql"
        migration.write_text(migration.read_text(encoding="utf-8") + "\n-- incompatible\n", encoding="utf-8")
        with pytest.raises(MigrationChecksumError):
            apply_migrations(connection, migrations_dir=migrations_dir)
        assert integrity_check(connection) == ("ok",)
    finally:
        connection.close()


def test_read_only_connection_never_creates_missing_database(tmp_path: Path) -> None:
    database = tmp_path / "runtime/missing.sqlite"
    with pytest.raises(FileNotFoundError):
        connect_read_only(database)
    assert not database.exists()
    assert not database.parent.exists()


def test_read_only_connection_rejects_writes(tmp_path: Path) -> None:
    database = tmp_path / "runtime/model.sqlite"
    writer = connect_writer(database, data_root=tmp_path / "data")
    apply_migrations(writer)
    writer.close()
    reader = connect_read_only(database)
    try:
        assert int(reader.execute("PRAGMA query_only").fetchone()[0]) == 1
        with pytest.raises(sqlite3.OperationalError):
            reader.execute(
                "INSERT INTO source_metadata("
                "logical_source_name,source_format,source_classification,"
                "availability,freshness_status,projector_version"
                ") VALUES ('x','json','CANONICAL','AVAILABLE','FRESH','test')"
            )
    finally:
        reader.close()


@pytest.mark.parametrize("candidate", [Path("relative.sqlite"), Path("/model.sqlite")])
def test_dangerous_read_model_paths_are_rejected(candidate: Path, tmp_path: Path) -> None:
    with pytest.raises(ReadModelPathError):
        validate_read_model_path(candidate, data_root=tmp_path / "data")


def test_database_inside_source_data_root_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ReadModelPathError):
        validate_read_model_path(tmp_path / "data/model.sqlite", data_root=tmp_path / "data")


def test_symbolic_link_target_is_rejected(tmp_path: Path) -> None:
    real = tmp_path / "runtime/real.sqlite"
    real.parent.mkdir(parents=True)
    sqlite3.connect(real).close()
    link = tmp_path / "runtime/link.sqlite"
    link.symlink_to(real)
    with pytest.raises(ReadModelPathError):
        validate_read_model_path(link, data_root=tmp_path / "data")
