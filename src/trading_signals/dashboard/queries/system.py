from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
from trading_signals.dashboard.ingestion import ResolvedSource, SourceCatalog, SourceProbe

_MAX_HEARTBEAT_BYTES = 1_048_576


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _freshness(probe: SourceProbe, now: datetime) -> Freshness:
    expected = probe.source.definition.expected_freshness_seconds
    if probe.size_bytes is None:
        return Freshness(
            status=FreshnessStatus.UNKNOWN,
            expected_freshness_seconds=expected,
            observed_event_at=None,
        )
    age = max(0.0, (now - probe.observed_at).total_seconds())
    if expected is None:
        status = FreshnessStatus.UNKNOWN
    else:
        status = FreshnessStatus.STALE if age > expected else FreshnessStatus.FRESH
    return Freshness(
        status=status,
        age_seconds=age,
        expected_freshness_seconds=expected,
        observed_event_at=probe.observed_at,
    )


def _classification(source: ResolvedSource, freshness: Freshness) -> DataClassification:
    if source.availability in {Availability.DISABLED, Availability.MISSING, Availability.NOT_CONFIGURED}:
        return DataClassification.UNAVAILABLE
    if freshness.status is FreshnessStatus.UNKNOWN:
        return DataClassification.NO_EVIDENCE
    if freshness.status is FreshnessStatus.STALE:
        return DataClassification.STALE
    if source.definition.canonicality in {Canonicality.MIXED, Canonicality.NON_CANONICAL}:
        return DataClassification.NON_CANONICAL
    if source.definition.canonicality is Canonicality.DERIVED:
        return DataClassification.DERIVED
    return DataClassification.REAL


def _source_evidence(source: ResolvedSource, probe: SourceProbe, now: datetime) -> StatusEvidence:
    freshness = _freshness(probe, now)
    classification = _classification(source, freshness)
    if source.availability is Availability.DISABLED:
        status = OperationalStatus.NO_EVIDENCE
        reason = "Source is intentionally disabled in the foundation phase."
    elif source.availability is Availability.NOT_CONFIGURED:
        status = OperationalStatus.NO_EVIDENCE
        reason = "Source requires explicit configuration."
    elif source.availability is Availability.MISSING:
        status = OperationalStatus.NO_EVIDENCE
        reason = "Configured source is not present."
    elif freshness.status is FreshnessStatus.STALE:
        status = OperationalStatus.STALE_DATA
        reason = "Source evidence is older than its declared freshness threshold."
    elif freshness.status is FreshnessStatus.UNKNOWN:
        status = OperationalStatus.NO_EVIDENCE
        reason = "Source exists, but no reliable freshness threshold is declared."
    else:
        status = OperationalStatus.HEALTHY
        reason = "Source is available; this status does not validate its semantic contents."
    return StatusEvidence(
        status=status,
        reason=reason,
        observed_at=now,
        source=source.definition.name,
        freshness=freshness,
        evidence_reference=EvidenceReference(
            source_id=source.definition.name,
            reference=source.safe_reference,
        ),
        classification=classification,
    )


def build_freshness(catalog: SourceCatalog, *, now: datetime | None = None) -> MetadataFreshness:
    observed_now = now or _now()
    items: list[MetadataFreshnessItem] = []
    for source in catalog.resolved_sources():
        probe = catalog.probe(source)
        observed_source = probe.source
        items.append(
            MetadataFreshnessItem(
                source_id=observed_source.definition.name,
                format=observed_source.definition.format,
                producer=observed_source.definition.producer,
                availability=observed_source.availability,
                canonicality=observed_source.definition.canonicality,
                classification=_classification(observed_source, _freshness(probe, observed_now)),
                safe_read_strategy=observed_source.definition.read_strategy,
                redaction=observed_source.definition.redaction,
                join_keys=observed_source.definition.join_keys,
                limitations=observed_source.definition.limitations,
                evidence=_source_evidence(observed_source, probe, observed_now),
            )
        )
    return MetadataFreshness(generated_at=observed_now, items=tuple(items))


def _read_json_snapshot(path: Path) -> dict[str, Any]:
    for _ in range(2):
        before = path.stat()
        if before.st_size > _MAX_HEARTBEAT_BYTES:
            raise ValueError("JSON source exceeds the foundation size limit")
        payload = path.read_bytes()
        after = path.stat()
        if (before.st_ino, before.st_size, before.st_mtime_ns) == (
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            parsed = json.loads(payload)
            if not isinstance(parsed, dict):
                raise ValueError("expected a JSON object")
            return parsed
    raise RuntimeError("source changed during both snapshot reads")


def build_system_status(catalog: SourceCatalog, *, now: datetime | None = None) -> SystemStatus:
    observed_now = now or _now()
    heartbeat = catalog.resolve("scheduler_heartbeat")
    probe = catalog.probe(heartbeat)
    base_evidence = _source_evidence(heartbeat, probe, observed_now)
    empty_identity = StrategyIdentity(classification=DataClassification.NO_EVIDENCE)
    empty_cycle = CycleSummary(classification=DataClassification.NO_EVIDENCE)

    if heartbeat.path is None or heartbeat.availability is not Availability.AVAILABLE:
        return SystemStatus(
            generated_at=observed_now,
            scheduler=base_evidence,
            strategy=empty_identity,
            last_cycle=empty_cycle,
            components=(ComponentStatus(component="scheduler", evidence=base_evidence, expected_state="running"),),
        )

    try:
        payload = _read_json_snapshot(heartbeat.path)
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError):
        failed = base_evidence.model_copy(
            update={
                "status": OperationalStatus.DEGRADED,
                "reason": "Heartbeat exists but could not be read as a stable bounded JSON object.",
                "classification": DataClassification.NO_EVIDENCE,
            }
        )
        return SystemStatus(
            generated_at=observed_now,
            scheduler=failed,
            strategy=empty_identity,
            last_cycle=empty_cycle,
            components=(ComponentStatus(component="scheduler", evidence=failed, expected_state="running"),),
        )

    heartbeat_status = str(payload.get("status", "")).lower()
    freshness = _freshness(probe, observed_now)
    if freshness.status is FreshnessStatus.STALE:
        status = OperationalStatus.STALE_DATA
        reason = "Scheduler heartbeat is stale."
        classification = DataClassification.STALE
    elif heartbeat_status == "ok":
        status = OperationalStatus.HEALTHY
        reason = "Scheduler heartbeat reports ok and is within the declared freshness threshold."
        classification = DataClassification.REAL
    else:
        status = OperationalStatus.DEGRADED
        reason = "Scheduler heartbeat is fresh but does not report ok."
        classification = DataClassification.REAL

    scheduler = base_evidence.model_copy(
        update={"status": status, "reason": reason, "classification": classification}
    )
    strategy = StrategyIdentity(
        git_commit_sha=_safe_text(payload.get("git_commit_sha")),
        deployment_id=_safe_text(payload.get("deployment_id")),
        config_hash=_safe_text(payload.get("config_hash")),
        selected_engine=_safe_text(payload.get("selected_engine")),
        strategy_version=_safe_text(payload.get("strategy_version")),
        policy_version=_safe_text(payload.get("policy_version")),
        experiment_id=_safe_text(payload.get("experiment_id")),
        classification=DataClassification.REAL,
    )
    cycle = CycleSummary(
        cycle_number=_safe_int(payload.get("cycle_number")),
        status=_safe_text(payload.get("status")),
        started_at=_safe_datetime(payload.get("last_cycle_started_at")),
        finished_at=_safe_datetime(payload.get("last_cycle_finished_at")),
        duration_seconds=_safe_nonnegative_float(payload.get("last_cycle_duration_seconds")),
        error_present=payload.get("last_error") is not None,
        classification=DataClassification.REAL,
    )
    return SystemStatus(
        generated_at=observed_now,
        scheduler=scheduler,
        strategy=strategy,
        last_cycle=cycle,
        components=(ComponentStatus(component="scheduler", evidence=scheduler, expected_state="running"),),
    )


def _safe_text(value: object) -> str | None:
    if value is None or not isinstance(value, (str, int, float)):
        return None
    text = str(value)[:200]
    lowered = text.lower()
    if (
        text.startswith(("/", "\\"))
        or "/" in text
        or "\\" in text
        or any(marker in lowered for marker in ("token=", "api_key=", "secret=", "chat_id="))
    ):
        return None
    return text


def _safe_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _safe_nonnegative_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _safe_datetime(value: object) -> datetime | None:
    if not isinstance(value, (str, datetime)):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)
