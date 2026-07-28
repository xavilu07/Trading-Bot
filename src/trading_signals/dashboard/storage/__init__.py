"""SQLite storage boundary for the rebuildable dashboard read model."""

from trading_signals.dashboard.storage.database import (
    ReadModelPathError,
    connect_read_only,
    connect_writer,
    finalize_writer,
    integrity_check,
    validate_read_model_path,
)
from trading_signals.dashboard.storage.migrations import (
    MigrationChecksumError,
    MigrationError,
    apply_migrations,
    schema_is_current,
)

__all__ = [
    "MigrationChecksumError",
    "MigrationError",
    "ReadModelPathError",
    "apply_migrations",
    "connect_read_only",
    "connect_writer",
    "finalize_writer",
    "integrity_check",
    "schema_is_current",
    "validate_read_model_path",
]
