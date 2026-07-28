from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

CONTRACT_VERSION = "dashboard.v1"


def _utc_datetime(value: object) -> datetime:
    parsed = value
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(parsed, datetime):
        raise TypeError("expected an ISO-8601 datetime")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("datetime must include a timezone")
    return parsed.astimezone(timezone.utc)


UtcDatetime = Annotated[datetime, BeforeValidator(_utc_datetime)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OperationalStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    STOPPED = "STOPPED"
    NO_EVIDENCE = "NO_EVIDENCE"
    STALE_DATA = "STALE_DATA"


class FreshnessStatus(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class DataClassification(str, Enum):
    REAL = "REAL"
    DERIVED = "DERIVED"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"
    NO_EVIDENCE = "NO_EVIDENCE"
    NON_CANONICAL = "NON_CANONICAL"


class Canonicality(str, Enum):
    CANONICAL = "CANONICAL"
    DERIVED = "DERIVED"
    MIXED = "MIXED"
    NON_CANONICAL = "NON_CANONICAL"
    EXTERNAL = "EXTERNAL"
    UNKNOWN = "UNKNOWN"


class Availability(str, Enum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    DISABLED = "DISABLED"


class EvidenceReference(ContractModel):
    source_id: str = Field(min_length=1, max_length=100)
    reference: str = Field(min_length=1, max_length=160)

    @field_validator("reference")
    @classmethod
    def reference_must_be_safe(cls, value: str) -> str:
        lowered = value.lower()
        forbidden = ("/root/", "/home/", "token=", "api_key=", "secret=", "chat_id=")
        if value.startswith("/") or any(item in lowered for item in forbidden):
            raise ValueError("evidence reference contains a sensitive path or value")
        return value


class Freshness(ContractModel):
    status: FreshnessStatus
    age_seconds: float | None = Field(default=None, ge=0)
    expected_freshness_seconds: int | None = Field(default=None, ge=1)
    observed_event_at: UtcDatetime | None = None


class StatusEvidence(ContractModel):
    status: OperationalStatus
    reason: str = Field(min_length=1, max_length=500)
    observed_at: UtcDatetime
    source: str = Field(min_length=1, max_length=100)
    freshness: Freshness
    evidence_reference: EvidenceReference | None = None
    classification: DataClassification


class StrategyIdentity(ContractModel):
    git_commit_sha: str | None = None
    deployment_id: str | None = None
    config_hash: str | None = None
    selected_engine: str | None = None
    strategy_version: str | None = None
    policy_version: str | None = None
    experiment_id: str | None = None
    classification: DataClassification = DataClassification.NO_EVIDENCE


class CycleSummary(ContractModel):
    cycle_number: int | None = Field(default=None, ge=0)
    status: str | None = None
    started_at: UtcDatetime | None = None
    finished_at: UtcDatetime | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    error_present: bool | None = None
    classification: DataClassification


class ComponentStatus(ContractModel):
    component: str
    evidence: StatusEvidence
    expected_state: str | None = None


class SignalSummary(ContractModel):
    signal_id: str
    observation_id: str | None = None
    symbol: str | None = None
    direction: str | None = None
    timeframe: str | None = None
    decision: str | None = None
    lifecycle_status: str | None = None
    observed_at: UtcDatetime | None = None
    strategy: StrategyIdentity
    classification: DataClassification
    canonicality: Canonicality
    limitations: tuple[str, ...] = ()


class OutcomeQuality(ContractModel):
    canonical: bool
    classification: DataClassification
    reason: str
    algorithm_version: str | None = None
    issues: tuple[str, ...] = ()


class TradeSummary(ContractModel):
    trade_id: str
    signal_id: str | None = None
    symbol: str | None = None
    direction: str | None = None
    status: str | None = None
    opened_at: UtcDatetime | None = None
    closed_at: UtcDatetime | None = None
    strategy: StrategyIdentity
    outcome_quality: OutcomeQuality
    classification: DataClassification
    canonicality: Canonicality


class AgentStatus(ContractModel):
    agent: str
    evidence: StatusEvidence
    receipts_available: bool
    limitations: tuple[str, ...] = ()


class Pagination(ContractModel):
    limit: int = Field(default=50, ge=1, le=200)
    next_cursor: str | None = Field(default=None, max_length=500)
    total: int | None = Field(default=None, ge=0)


ItemT = TypeVar("ItemT")


class Page(ContractModel, Generic[ItemT]):
    items: tuple[ItemT, ...]
    pagination: Pagination
    contract_version: str = CONTRACT_VERSION


class MetadataFreshnessItem(ContractModel):
    source_id: str
    format: str
    producer: str
    availability: Availability
    canonicality: Canonicality
    classification: DataClassification
    safe_read_strategy: str
    redaction: str
    join_keys: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    evidence: StatusEvidence


class MetadataFreshness(ContractModel):
    contract_version: str = CONTRACT_VERSION
    generated_at: UtcDatetime
    items: tuple[MetadataFreshnessItem, ...]


class SystemStatus(ContractModel):
    contract_version: str = CONTRACT_VERSION
    generated_at: UtcDatetime
    scheduler: StatusEvidence
    strategy: StrategyIdentity
    last_cycle: CycleSummary
    components: tuple[ComponentStatus, ...]
    read_only: bool = True
    outcomes_canonical: bool = False


class ApiHealth(ContractModel):
    contract_version: str = CONTRACT_VERSION
    generated_at: UtcDatetime
    api: StatusEvidence
    read_model: StatusEvidence | None = None
    read_only: bool = True
    operational_controls_enabled: bool = False
    performance_metrics_enabled: bool = False


class ErrorDetail(ContractModel):
    code: str
    message: str
    evidence_reference: EvidenceReference | None = None


class ErrorResponse(ContractModel):
    contract_version: str = CONTRACT_VERSION
    generated_at: UtcDatetime
    error: ErrorDetail
