from __future__ import annotations

import glob
import hashlib
import json
import os
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping

from trading_signals.dashboard.contracts import Availability, FreshnessStatus
from trading_signals.dashboard.ingestion.manifest import ResolvedSource, SourceCatalog
from trading_signals.dashboard.ingestion.readers import SourceReadError, read_json_snapshot
from trading_signals.dashboard.ingestion.sanitize import (
    safe_bool,
    safe_int,
    safe_relative_identity,
    safe_text,
    sanitized_error,
    sanitized_json,
)
from trading_signals.dashboard.storage import (
    apply_migrations,
    connect_read_only,
    connect_writer,
    finalize_writer,
    integrity_check,
    schema_is_current,
    validate_read_model_path,
)

PROJECTOR_VERSION = "dashboard-projector.v1"
PROJECTED_SOURCES = ("scheduler_heartbeat", "scan_runs", "trade_signals")

_HEARTBEAT_FIELDS = (
    "status",
    "cycle_number",
    "last_cycle_started_at",
    "last_cycle_finished_at",
    "last_cycle_duration_seconds",
    "last_error",
    "pid",
    "git_commit_sha",
    "deployment_id",
    "config_hash",
    "selected_engine",
    "strategy_version",
    "policy_version",
    "experiment_id",
)
_CYCLE_FIELDS = (
    "id",
    "started_at",
    "finished_at",
    "status",
    "symbols_total",
    "symbols_processed",
    "signals_emitted",
    "signals_rejected",
    "errors_count",
    "schema_version",
    "created_at",
    "updated_at",
    "config",
)
_CYCLE_CONFIG_FIELDS = (
    "strategy_id",
    "strategy_version",
    "entry_timeframe",
    "higher_timeframe",
    "scan_interval_seconds",
)
_SIGNAL_FIELDS = (
    "id",
    "observation_id",
    "scan_run_id",
    "evaluation_id",
    "risk_plan_id",
    "strategy_id",
    "strategy_version",
    "symbol",
    "decision",
    "status",
    "dedupe_key",
    "entry_timeframe",
    "higher_timeframe",
    "created_at",
    "updated_at",
    "published_at",
    "accepted_at",
    "public_published_at",
    "universe",
    "accepted",
    "public_published",
    "git_commit_sha",
    "config_hash",
    "deployment_id",
    "selected_engine",
    "policy_version",
    "experiment_id",
    "signal_type",
    "lifecycle_reason",
    "lifecycle_status",
    "expires_at",
    "close_reason",
    "closed_at",
    "schema_version",
)


@dataclass(frozen=True, slots=True)
class SourceProjectionResult:
    source: str
    status: str
    records_seen: int = 0
    records_written: int = 0
    records_skipped: int = 0
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class ProjectionSummary:
    projector_version: str
    started_at: str
    completed_at: str
    database_reference: str
    sources: tuple[SourceProjectionResult, ...]
    totals: Mapping[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProjectorConfig:
    data_root: Path
    sqlite_path: Path
    manifest_path: Path
    variables: Mapping[str, Path | None]
    selected_sources: tuple[str, ...] = PROJECTED_SOURCES


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _deterministic_key(*parts: object) -> str:
    material = "|".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _freshness(source: ResolvedSource, observed_at: datetime | None) -> str:
    expected = source.definition.expected_freshness_seconds
    if observed_at is None or expected is None:
        return FreshnessStatus.UNKNOWN.value
    age = max(0.0, (datetime.now(timezone.utc) - observed_at).total_seconds())
    return FreshnessStatus.STALE.value if age > expected else FreshnessStatus.FRESH.value


def _upsert_source_inventory(
    connection: sqlite3.Connection,
    catalog: SourceCatalog,
) -> None:
    now = _utc_now()
    connection.execute("BEGIN IMMEDIATE")
    try:
        for source in catalog.resolved_sources():
            probe = catalog.probe(source)
            observed = probe.observed_at if probe.size_bytes is not None else None
            connection.execute(
                """
                INSERT INTO source_metadata(
                    logical_source_name, source_format, source_classification,
                    availability, source_observed_at, freshness_status, projector_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(logical_source_name) DO UPDATE SET
                    source_format=excluded.source_format,
                    source_classification=excluded.source_classification,
                    availability=excluded.availability,
                    source_observed_at=excluded.source_observed_at,
                    freshness_status=excluded.freshness_status,
                    projector_version=excluded.projector_version
                """,
                (
                    source.definition.name,
                    source.definition.format,
                    source.definition.canonicality.value,
                    probe.source.availability.value,
                    observed.isoformat() if observed else None,
                    _freshness(source, observed),
                    PROJECTOR_VERSION,
                ),
            )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


def _mark_attempt(connection: sqlite3.Connection, source: ResolvedSource) -> None:
    connection.execute(
        """
        UPDATE source_metadata
        SET last_attempt_at=?, last_error_code=NULL, last_error_message=NULL,
            projector_version=?
        WHERE logical_source_name=?
        """,
        (_utc_now(), PROJECTOR_VERSION, source.definition.name),
    )


def _mark_success(
    connection: sqlite3.Connection,
    source: ResolvedSource,
    *,
    fingerprint: str,
    record_count: int,
    observed_at: str | None,
) -> None:
    now = _utc_now()
    connection.execute(
        """
        UPDATE source_metadata
        SET last_attempt_at=?, last_success_at=?, source_observed_at=?,
            source_fingerprint=?, record_count=?, last_error_code=NULL,
            last_error_message=NULL, availability=?, freshness_status=?,
            projector_version=?
        WHERE logical_source_name=?
        """,
        (
            now,
            now,
            observed_at,
            fingerprint,
            record_count,
            Availability.AVAILABLE.value,
            _freshness(
                source,
                datetime.fromisoformat(observed_at) if observed_at else None,
            ),
            PROJECTOR_VERSION,
            source.definition.name,
        ),
    )


def _mark_failure(
    connection: sqlite3.Connection,
    source: ResolvedSource,
    error: BaseException,
) -> tuple[str, str]:
    code, message = sanitized_error(error)
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            """
            UPDATE source_metadata
            SET last_attempt_at=?, last_error_code=?, last_error_message=?,
                projector_version=?
            WHERE logical_source_name=?
            """,
            (_utc_now(), code, message, PROJECTOR_VERSION, source.definition.name),
        )
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    return code, message


def _upsert_checkpoint(
    connection: sqlite3.Connection,
    *,
    source_name: str,
    source_identity: str,
    source_fingerprint: str,
    byte_offset: int | None = None,
    record_index: int | None = None,
    last_event_id: str | None = None,
    last_event_timestamp: str | None = None,
    completed: bool,
) -> None:
    connection.execute(
        """
        INSERT INTO ingestion_checkpoints(
            logical_source_name, source_identity, source_fingerprint,
            byte_offset, record_index, last_event_id, last_event_timestamp,
            completed, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(logical_source_name, source_identity) DO UPDATE SET
            source_fingerprint=excluded.source_fingerprint,
            byte_offset=excluded.byte_offset,
            record_index=excluded.record_index,
            last_event_id=excluded.last_event_id,
            last_event_timestamp=excluded.last_event_timestamp,
            completed=excluded.completed,
            updated_at=excluded.updated_at
        """,
        (
            source_name,
            source_identity,
            source_fingerprint,
            byte_offset,
            record_index,
            last_event_id,
            last_event_timestamp,
            int(completed),
            _utc_now(),
        ),
    )


def _project_heartbeat(
    connection: sqlite3.Connection,
    source: ResolvedSource,
) -> SourceProjectionResult:
    if source.path is None or source.availability is not Availability.AVAILABLE:
        return SourceProjectionResult(source.definition.name, "unavailable")
    try:
        payload, snapshot = read_json_snapshot(source.path, max_bytes=1_048_576)
        observed = datetime.fromtimestamp(snapshot.observed_at_ns / 1_000_000_000, tz=timezone.utc)
        status = str(payload.get("status", "")).lower()
        freshness = _freshness(source, observed)
        normalized = "STALE_DATA" if freshness == "STALE" else ("HEALTHY" if status == "ok" else "DEGRADED")
        reason = (
            "Scheduler heartbeat is stale."
            if normalized == "STALE_DATA"
            else "Scheduler heartbeat reports ok."
            if normalized == "HEALTHY"
            else "Scheduler heartbeat does not report ok."
        )
        snapshot_id = _deterministic_key(
            source.definition.name,
            payload.get("cycle_number"),
            payload.get("last_cycle_finished_at"),
            payload.get("deployment_id"),
        )
        connection.execute("BEGIN IMMEDIATE")
        _mark_attempt(connection, source)
        connection.execute(
            """
            INSERT INTO system_snapshots(
                snapshot_id, observed_at, component, normalized_status, reason,
                freshness_status, evidence_reference, git_commit_sha,
                deployment_id, config_hash, selected_engine, strategy_version,
                policy_version, experiment_id, payload_json,
                source_logical_name, ingested_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_id) DO UPDATE SET
                normalized_status=excluded.normalized_status,
                reason=excluded.reason,
                freshness_status=excluded.freshness_status,
                payload_json=excluded.payload_json,
                ingested_at=excluded.ingested_at
            """,
            (
                snapshot_id,
                safe_text(payload.get("last_cycle_finished_at")) or observed.isoformat(),
                "scheduler",
                normalized,
                reason,
                freshness,
                source.safe_reference,
                safe_text(payload.get("git_commit_sha")),
                safe_text(payload.get("deployment_id")),
                safe_text(payload.get("config_hash")),
                safe_text(payload.get("selected_engine")),
                safe_text(payload.get("strategy_version")),
                safe_text(payload.get("policy_version")),
                safe_text(payload.get("experiment_id")),
                sanitized_json(payload, allowed_fields=_HEARTBEAT_FIELDS),
                source.definition.name,
                _utc_now(),
            ),
        )
        _upsert_checkpoint(
            connection,
            source_name=source.definition.name,
            source_identity=snapshot.source_identity,
            source_fingerprint=snapshot.fingerprint,
            record_index=1,
            last_event_id=snapshot_id,
            last_event_timestamp=safe_text(payload.get("last_cycle_finished_at")),
            completed=True,
        )
        count = int(
            connection.execute(
                "SELECT COUNT(*) FROM system_snapshots WHERE source_logical_name=?",
                (source.definition.name,),
            ).fetchone()[0]
        )
        _mark_success(
            connection,
            source,
            fingerprint=snapshot.fingerprint,
            record_count=count,
            observed_at=observed.isoformat(),
        )
        connection.commit()
        return SourceProjectionResult(source.definition.name, "success", 1, 1)
    except BaseException as exc:
        if connection.in_transaction:
            connection.rollback()
        code, _ = _mark_failure(connection, source, exc)
        return SourceProjectionResult(source.definition.name, "failed", error_code=code)


def _glob_files(source: ResolvedSource) -> tuple[Path, ...]:
    if source.path is None:
        return ()
    return tuple(
        sorted(
            Path(item)
            for item in glob.glob(str(source.path), recursive=True)
            if Path(item).is_file() and not item.endswith(".tmp")
        )
    )


def _project_json_file_set(
    connection: sqlite3.Connection,
    source: ResolvedSource,
    *,
    data_root: Path,
    record_writer: Callable[[sqlite3.Connection, Mapping[str, object], str, str], None],
    table: str,
    event_id_field: str,
    event_time_fields: tuple[str, ...],
) -> SourceProjectionResult:
    files = _glob_files(source)
    if not files:
        return SourceProjectionResult(source.definition.name, "unavailable")
    seen = written = skipped = 0
    digest = hashlib.sha256()
    last_event_id: str | None = None
    last_event_timestamp: str | None = None
    max_observed_ns = 0
    first_error: BaseException | None = None
    connection.execute("BEGIN IMMEDIATE")
    try:
        _mark_attempt(connection, source)
        for path in files:
            seen += 1
            source_record_identity = safe_relative_identity(path, data_root, source.definition.name)
            try:
                payload, snapshot = read_json_snapshot(path, max_bytes=4 * 1024 * 1024)
                record_writer(connection, payload, source_record_identity, source.safe_reference)
            except (OSError, SourceReadError, ValueError, sqlite3.DatabaseError) as exc:
                skipped += 1
                first_error = first_error or exc
                continue
            digest.update(source_record_identity.encode("ascii"))
            digest.update(snapshot.fingerprint.encode("ascii"))
            max_observed_ns = max(max_observed_ns, snapshot.observed_at_ns)
            written += 1
            last_event_id = safe_text(payload.get(event_id_field))
            for field_name in event_time_fields:
                candidate = safe_text(payload.get(field_name))
                if candidate:
                    last_event_timestamp = candidate
                    break
        if first_error is not None:
            connection.rollback()
            code, _ = _mark_failure(connection, source, first_error)
            return SourceProjectionResult(
                source.definition.name,
                "failed",
                seen,
                0,
                skipped,
                code,
            )
        fingerprint = digest.hexdigest()
        _upsert_checkpoint(
            connection,
            source_name=source.definition.name,
            source_identity="file-set",
            source_fingerprint=fingerprint,
            record_index=written,
            last_event_id=last_event_id,
            last_event_timestamp=last_event_timestamp,
            completed=True,
        )
        count = int(
            connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE source_logical_name=?",
                (source.definition.name,),
            ).fetchone()[0]
        )
        observed = (
            datetime.fromtimestamp(max_observed_ns / 1_000_000_000, tz=timezone.utc).isoformat()
            if max_observed_ns
            else None
        )
        _mark_success(
            connection,
            source,
            fingerprint=fingerprint,
            record_count=count,
            observed_at=observed,
        )
        connection.commit()
        return SourceProjectionResult(
            source.definition.name,
            "success",
            seen,
            written,
            skipped,
            None,
        )
    except BaseException as exc:
        if connection.in_transaction:
            connection.rollback()
        code, _ = _mark_failure(connection, source, exc)
        return SourceProjectionResult(source.definition.name, "failed", seen, written, skipped, code)


def _write_cycle(
    connection: sqlite3.Connection,
    payload: Mapping[str, object],
    source_record_identity: str,
    source_reference: str,
) -> None:
    cycle_id = safe_text(payload.get("id"))
    started_at = safe_text(payload.get("started_at"))
    status = safe_text(payload.get("status"))
    if not cycle_id or not started_at or not status:
        raise ValueError("cycle is missing its real natural key or required fields")
    config = payload.get("config") if isinstance(payload.get("config"), Mapping) else {}
    connection.execute(
        """
        INSERT INTO cycles(
            cycle_id, started_at, completed_at, status, symbols_total,
            symbols_processed, signals_emitted, signals_rejected, errors_count,
            selected_engine, strategy_version, source_logical_name,
            source_record_identity, source_reference, raw_payload_json, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(cycle_id) DO UPDATE SET
            completed_at=excluded.completed_at,
            status=excluded.status,
            symbols_total=excluded.symbols_total,
            symbols_processed=excluded.symbols_processed,
            signals_emitted=excluded.signals_emitted,
            signals_rejected=excluded.signals_rejected,
            errors_count=excluded.errors_count,
            strategy_version=excluded.strategy_version,
            raw_payload_json=excluded.raw_payload_json,
            ingested_at=excluded.ingested_at
        """,
        (
            cycle_id,
            started_at,
            safe_text(payload.get("finished_at")),
            status,
            safe_int(payload.get("symbols_total")),
            safe_int(payload.get("symbols_processed")),
            safe_int(payload.get("signals_emitted")),
            safe_int(payload.get("signals_rejected")),
            safe_int(payload.get("errors_count")),
            safe_text(config.get("strategy_id")),
            safe_text(config.get("strategy_version")),
            "scan_runs",
            source_record_identity,
            source_reference,
            sanitized_json(
                payload,
                allowed_fields=_CYCLE_FIELDS,
                nested_allowlists={"config": _CYCLE_CONFIG_FIELDS},
            ),
            _utc_now(),
        ),
    )


def _write_signal(
    connection: sqlite3.Connection,
    payload: Mapping[str, object],
    source_record_identity: str,
    _source_reference: str,
) -> None:
    signal_id = safe_text(payload.get("id"))
    timestamp = safe_text(payload.get("created_at")) or safe_text(payload.get("updated_at"))
    if not timestamp:
        raise ValueError("signal is missing a reliable event timestamp")
    projection_key = _deterministic_key(
        "trade_signals",
        "signal_id" if signal_id else "source_record",
        signal_id or source_record_identity,
    )
    status = safe_text(payload.get("status"))
    decision = safe_text(payload.get("decision"))
    universe = safe_text(payload.get("universe"))
    rejected = int((status or "").lower() == "rejected")
    shadow = int((universe or "").lower() == "shadow" or (status or "").lower() == "shadow")
    connection.execute(
        """
        INSERT INTO signals(
            projection_key, signal_id, observation_id, cycle_id,
            event_timestamp, symbol, direction, timeframe, setup, decision,
            status, accepted, published, rejected, shadow, rejection_reason,
            git_commit_sha, deployment_id, config_hash, selected_engine,
            strategy_version, policy_version, experiment_id,
            source_logical_name, source_record_identity, raw_payload_json,
            ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(projection_key) DO UPDATE SET
            cycle_id=excluded.cycle_id,
            event_timestamp=excluded.event_timestamp,
            symbol=excluded.symbol,
            timeframe=excluded.timeframe,
            decision=excluded.decision,
            status=excluded.status,
            accepted=excluded.accepted,
            published=excluded.published,
            rejected=excluded.rejected,
            shadow=excluded.shadow,
            rejection_reason=excluded.rejection_reason,
            git_commit_sha=excluded.git_commit_sha,
            deployment_id=excluded.deployment_id,
            config_hash=excluded.config_hash,
            selected_engine=excluded.selected_engine,
            strategy_version=excluded.strategy_version,
            policy_version=excluded.policy_version,
            experiment_id=excluded.experiment_id,
            raw_payload_json=excluded.raw_payload_json,
            ingested_at=excluded.ingested_at
        """,
        (
            projection_key,
            signal_id,
            safe_text(payload.get("observation_id")),
            safe_text(payload.get("scan_run_id")),
            timestamp,
            safe_text(payload.get("symbol")),
            safe_text(payload.get("direction")),
            safe_text(payload.get("entry_timeframe")),
            safe_text(payload.get("setup")),
            decision,
            status,
            safe_bool(payload.get("accepted")),
            safe_bool(payload.get("public_published")),
            rejected,
            shadow,
            safe_text(payload.get("lifecycle_reason")),
            safe_text(payload.get("git_commit_sha")),
            safe_text(payload.get("deployment_id")),
            safe_text(payload.get("config_hash")),
            safe_text(payload.get("selected_engine")),
            safe_text(payload.get("strategy_version")),
            safe_text(payload.get("policy_version")),
            safe_text(payload.get("experiment_id")),
            "trade_signals",
            source_record_identity,
            sanitized_json(payload, allowed_fields=_SIGNAL_FIELDS),
            _utc_now(),
        ),
    )


def project_once(config: ProjectorConfig) -> ProjectionSummary:
    started = _utc_now()
    database = validate_read_model_path(config.sqlite_path, data_root=config.data_root)
    if not database.is_file():
        raise RuntimeError("read model does not exist; run migrate or rebuild explicitly")
    catalog = SourceCatalog.load_path(config.manifest_path, config.variables)
    connection = connect_writer(database, data_root=config.data_root)
    results: list[SourceProjectionResult] = []
    try:
        if not schema_is_current(connection):
            raise RuntimeError("read model is not migrated")
        _upsert_source_inventory(connection, catalog)
        for source_name in config.selected_sources:
            source = catalog.resolve(source_name)
            if source_name == "scheduler_heartbeat":
                result = _project_heartbeat(connection, source)
            elif source_name == "scan_runs":
                result = _project_json_file_set(
                    connection,
                    source,
                    data_root=config.data_root,
                    record_writer=_write_cycle,
                    table="cycles",
                    event_id_field="id",
                    event_time_fields=("finished_at", "started_at"),
                )
            elif source_name == "trade_signals":
                result = _project_json_file_set(
                    connection,
                    source,
                    data_root=config.data_root,
                    record_writer=_write_signal,
                    table="signals",
                    event_id_field="id",
                    event_time_fields=("updated_at", "created_at"),
                )
            else:
                result = SourceProjectionResult(source_name, "not_implemented")
            results.append(result)
    finally:
        try:
            finalize_writer(connection)
        finally:
            connection.close()
    totals = {
        "sources": len(results),
        "records_seen": sum(item.records_seen for item in results),
        "records_written": sum(item.records_written for item in results),
        "records_skipped": sum(item.records_skipped for item in results),
    }
    return ProjectionSummary(
        projector_version=PROJECTOR_VERSION,
        started_at=started,
        completed_at=_utc_now(),
        database_reference=f"read-model:{hashlib.sha256(str(database).encode()).hexdigest()[:12]}",
        sources=tuple(results),
        totals=totals,
    )


def migrate_read_model(config: ProjectorConfig) -> tuple[int, ...]:
    connection = connect_writer(config.sqlite_path, data_root=config.data_root)
    try:
        applied = apply_migrations(connection)
        finalize_writer(connection)
        return applied
    finally:
        connection.close()


def rebuild_read_model(
    config: ProjectorConfig,
    *,
    before_replace: Callable[[Path, Path], None] | None = None,
) -> ProjectionSummary:
    target = validate_read_model_path(config.sqlite_path, data_root=config.data_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    if any(Path(f"{target}{suffix}").exists() for suffix in ("-wal", "-shm")):
        raise RuntimeError("target read model has active SQLite sidecars")
    temporary = target.with_name(f".{target.name}.rebuild-{uuid.uuid4().hex}.sqlite")
    temporary_config = ProjectorConfig(
        data_root=config.data_root,
        sqlite_path=temporary,
        manifest_path=config.manifest_path,
        variables=config.variables,
        selected_sources=config.selected_sources,
    )
    try:
        migrate_read_model(temporary_config)
        summary = project_once(temporary_config)
        connection = connect_read_only(temporary)
        try:
            if integrity_check(connection) != ("ok",) or not schema_is_current(connection):
                raise RuntimeError("rebuilt read model failed validation")
        finally:
            connection.close()
        if before_replace is not None:
            before_replace(temporary, target)
        os.replace(temporary, target)
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return replace(
            summary,
            database_reference=f"read-model:{hashlib.sha256(str(target).encode()).hexdigest()[:12]}",
        )
    finally:
        for candidate in (temporary, Path(f"{temporary}-wal"), Path(f"{temporary}-shm")):
            if candidate.exists():
                candidate.unlink()


def inspect_read_model(path: Path) -> dict[str, object]:
    try:
        connection = connect_read_only(path)
    except FileNotFoundError:
        return {"status": "missing", "schema_current": False, "integrity": ()}
    except (OSError, sqlite3.DatabaseError, ValueError):
        return {"status": "unavailable", "schema_current": False, "integrity": ()}
    try:
        integrity = integrity_check(connection)
        current = schema_is_current(connection)
        counts: dict[str, int] = {}
        if current and integrity == ("ok",):
            for table in ("source_metadata", "system_snapshots", "cycles", "signals"):
                counts[table] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return {
            "status": "ready" if current and integrity == ("ok",) else "degraded",
            "schema_current": current,
            "integrity": integrity,
            "counts": counts,
        }
    except sqlite3.DatabaseError:
        return {"status": "corrupt", "schema_current": False, "integrity": ()}
    finally:
        connection.close()
