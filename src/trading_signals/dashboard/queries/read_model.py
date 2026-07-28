from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from trading_signals.dashboard.contracts import (
    Availability,
    Canonicality,
    ComponentStatus,
    CycleSummary,
    DataClassification,
    EvidenceReference,
    Freshness,
    FreshnessStatus,
    MetadataFreshness,
    MetadataFreshnessItem,
    OperationalStatus,
    StatusEvidence,
    StrategyIdentity,
    SystemStatus,
)
from trading_signals.dashboard.ingestion.projector import inspect_read_model
from trading_signals.dashboard.storage import connect_read_only


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def read_model_evidence(path: Path, *, now: datetime | None = None) -> StatusEvidence:
    observed = now or _now()
    state = inspect_read_model(path)
    status_name = str(state["status"])
    if status_name == "ready":
        status = OperationalStatus.HEALTHY
        classification = DataClassification.DERIVED
        reason = "SQLite read model is available, migrated, and passes integrity_check."
    elif status_name == "missing":
        status = OperationalStatus.NO_EVIDENCE
        classification = DataClassification.UNAVAILABLE
        reason = "SQLite read model does not exist; the API did not create it."
    elif status_name in {"corrupt", "unavailable"}:
        status = OperationalStatus.DEGRADED
        classification = DataClassification.NO_EVIDENCE
        reason = "SQLite read model cannot be opened or fails a safe integrity read."
    else:
        status = OperationalStatus.DEGRADED
        classification = DataClassification.NO_EVIDENCE
        reason = "SQLite read model exists but its schema is not current."
    return StatusEvidence(
        status=status,
        reason=reason,
        observed_at=observed,
        source="dashboard_read_model",
        freshness=Freshness(status=FreshnessStatus.UNKNOWN),
        evidence_reference=EvidenceReference(
            source_id="dashboard_read_model",
            reference="source:dashboard_read_model#configured",
        ),
        classification=classification,
    )


def _empty_system(evidence: StatusEvidence, now: datetime) -> SystemStatus:
    scheduler = StatusEvidence(
        status=OperationalStatus.NO_EVIDENCE,
        reason="No readable scheduler projection is available in the SQLite read model.",
        observed_at=now,
        source="scheduler_heartbeat",
        freshness=Freshness(status=FreshnessStatus.UNKNOWN),
        evidence_reference=EvidenceReference(
            source_id="scheduler_heartbeat",
            reference="source:scheduler_heartbeat#read-model",
        ),
        classification=DataClassification.NO_EVIDENCE,
    )
    return SystemStatus(
        generated_at=now,
        scheduler=scheduler,
        strategy=StrategyIdentity(classification=DataClassification.NO_EVIDENCE),
        last_cycle=CycleSummary(classification=DataClassification.NO_EVIDENCE),
        components=(
            ComponentStatus(component="dashboard_read_model", evidence=evidence, expected_state="available"),
            ComponentStatus(component="scheduler", evidence=scheduler, expected_state="running"),
        ),
    )


def build_system_from_read_model(path: Path, *, now: datetime | None = None) -> SystemStatus:
    observed = now or _now()
    model_evidence = read_model_evidence(path, now=observed)
    if model_evidence.status is not OperationalStatus.HEALTHY:
        return _empty_system(model_evidence, observed)
    try:
        connection = connect_read_only(path)
        snapshot = connection.execute(
            """
            SELECT * FROM system_snapshots
            WHERE component='scheduler'
            ORDER BY observed_at DESC, snapshot_id DESC
            LIMIT 1
            """
        ).fetchone()
        cycle = connection.execute(
            "SELECT * FROM cycles ORDER BY started_at DESC, cycle_id DESC LIMIT 1"
        ).fetchone()
    except (sqlite3.DatabaseError, OSError):
        degraded = model_evidence.model_copy(
            update={
                "status": OperationalStatus.DEGRADED,
                "reason": "SQLite read model query failed safely.",
                "classification": DataClassification.NO_EVIDENCE,
            }
        )
        return _empty_system(degraded, observed)
    finally:
        if "connection" in locals():
            connection.close()
    if snapshot is None:
        return _empty_system(model_evidence, observed)

    snapshot_time = _safe_datetime(snapshot["observed_at"])
    freshness_name = str(snapshot["freshness_status"])
    try:
        freshness_status = FreshnessStatus(freshness_name)
    except ValueError:
        freshness_status = FreshnessStatus.UNKNOWN
    age = max(0.0, (observed - snapshot_time).total_seconds()) if snapshot_time else None
    try:
        scheduler_status = OperationalStatus(str(snapshot["normalized_status"]))
    except ValueError:
        scheduler_status = OperationalStatus.NO_EVIDENCE
    scheduler = StatusEvidence(
        status=scheduler_status,
        reason=str(snapshot["reason"])[:500],
        observed_at=observed,
        source="scheduler_heartbeat",
        freshness=Freshness(
            status=freshness_status,
            age_seconds=age,
            observed_event_at=snapshot_time,
        ),
        evidence_reference=EvidenceReference(
            source_id="scheduler_heartbeat",
            reference=str(snapshot["evidence_reference"]),
        ),
        classification=DataClassification.DERIVED,
    )
    strategy = StrategyIdentity(
        git_commit_sha=snapshot["git_commit_sha"],
        deployment_id=snapshot["deployment_id"],
        config_hash=snapshot["config_hash"],
        selected_engine=snapshot["selected_engine"],
        strategy_version=snapshot["strategy_version"],
        policy_version=snapshot["policy_version"],
        experiment_id=snapshot["experiment_id"],
        classification=DataClassification.DERIVED,
    )
    try:
        snapshot_payload = json.loads(str(snapshot["payload_json"]))
    except (TypeError, ValueError, json.JSONDecodeError):
        snapshot_payload = {}
    raw_cycle_number = snapshot_payload.get("cycle_number") if isinstance(snapshot_payload, dict) else None
    cycle_number = (
        int(raw_cycle_number)
        if isinstance(raw_cycle_number, int) and not isinstance(raw_cycle_number, bool) and raw_cycle_number >= 0
        else None
    )
    raw_duration = (
        snapshot_payload.get("last_cycle_duration_seconds")
        if isinstance(snapshot_payload, dict)
        else None
    )
    duration = (
        float(raw_duration)
        if isinstance(raw_duration, (int, float))
        and not isinstance(raw_duration, bool)
        and float(raw_duration) >= 0
        else None
    )
    last_cycle = (
        CycleSummary(
            cycle_number=cycle_number,
            status=cycle["status"],
            started_at=_safe_datetime(cycle["started_at"]),
            finished_at=_safe_datetime(cycle["completed_at"]),
            duration_seconds=duration,
            error_present=(int(cycle["errors_count"]) > 0 if cycle["errors_count"] is not None else None),
            classification=DataClassification.DERIVED,
        )
        if cycle is not None
        else CycleSummary(classification=DataClassification.NO_EVIDENCE)
    )
    return SystemStatus(
        generated_at=observed,
        scheduler=scheduler,
        strategy=strategy,
        last_cycle=last_cycle,
        components=(
            ComponentStatus(component="dashboard_read_model", evidence=model_evidence, expected_state="available"),
            ComponentStatus(component="scheduler", evidence=scheduler, expected_state="running"),
        ),
    )


def build_freshness_from_read_model(path: Path, *, now: datetime | None = None) -> MetadataFreshness:
    observed = now or _now()
    evidence = read_model_evidence(path, now=observed)
    if evidence.status is not OperationalStatus.HEALTHY:
        return MetadataFreshness(generated_at=observed, items=())
    try:
        connection = connect_read_only(path)
        rows = tuple(connection.execute("SELECT * FROM source_metadata ORDER BY logical_source_name"))
    except (sqlite3.DatabaseError, OSError):
        return MetadataFreshness(generated_at=observed, items=())
    finally:
        if "connection" in locals():
            connection.close()
    items: list[MetadataFreshnessItem] = []
    for row in rows:
        try:
            availability = Availability(str(row["availability"]))
        except ValueError:
            availability = Availability.MISSING
        try:
            canonicality = Canonicality(str(row["source_classification"]))
        except ValueError:
            canonicality = Canonicality.UNKNOWN
        try:
            freshness_status = FreshnessStatus(str(row["freshness_status"]))
        except ValueError:
            freshness_status = FreshnessStatus.UNKNOWN
        event_at = _safe_datetime(row["source_observed_at"])
        age = max(0.0, (observed - event_at).total_seconds()) if event_at else None
        if availability in {Availability.MISSING, Availability.NOT_CONFIGURED, Availability.DISABLED}:
            status = OperationalStatus.NO_EVIDENCE
            classification = DataClassification.UNAVAILABLE
            reason = "Source is unavailable to the projector."
        elif row["last_error_code"]:
            status = OperationalStatus.DEGRADED
            classification = DataClassification.NO_EVIDENCE
            reason = f"Last projection attempt failed safely ({str(row['last_error_code'])[:80]})."
        elif freshness_status is FreshnessStatus.STALE:
            status = OperationalStatus.STALE_DATA
            classification = DataClassification.STALE
            reason = "Projected source evidence is stale."
        elif freshness_status is FreshnessStatus.UNKNOWN:
            status = OperationalStatus.NO_EVIDENCE
            classification = DataClassification.NO_EVIDENCE
            reason = "Source has no reliable freshness evidence."
        else:
            status = OperationalStatus.HEALTHY
            classification = (
                DataClassification.DERIVED
                if canonicality is Canonicality.DERIVED
                else DataClassification.NON_CANONICAL
                if canonicality in {Canonicality.MIXED, Canonicality.NON_CANONICAL}
                else DataClassification.REAL
            )
            reason = "Source projection is available and within its freshness threshold."
        source_id = str(row["logical_source_name"])
        status_evidence = StatusEvidence(
            status=status,
            reason=reason,
            observed_at=observed,
            source=source_id,
            freshness=Freshness(
                status=freshness_status,
                age_seconds=age,
                observed_event_at=event_at,
            ),
            evidence_reference=EvidenceReference(
                source_id=source_id,
                reference=f"source:{source_id}#read-model",
            ),
            classification=classification,
        )
        items.append(
            MetadataFreshnessItem(
                source_id=source_id,
                format=str(row["source_format"]),
                producer="dashboard projector",
                availability=availability,
                canonicality=canonicality,
                classification=classification,
                safe_read_strategy="projected_sqlite",
                redaction="projection_allowlist",
                evidence=status_evidence,
            )
        )
    return MetadataFreshness(generated_at=observed, items=tuple(items))
