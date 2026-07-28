from __future__ import annotations

from enum import Enum

from pydantic import Field

from trading_signals.dashboard.contracts.models import ContractModel, UtcDatetime

METRIC_CONTRACT_VERSION = "dashboard.metrics.v1"


class EntryLifecycleStatus(str, Enum):
    SIGNAL_OBSERVED = "SIGNAL_OBSERVED"
    ENTRY_NOT_ACTIVATED = "ENTRY_NOT_ACTIVATED"
    ENTRY_ACTIVATED = "ENTRY_ACTIVATED"
    RESOLVED_WIN = "RESOLVED_WIN"
    RESOLVED_LOSS = "RESOLVED_LOSS"
    ACTIVATED_EXPIRED = "ACTIVATED_EXPIRED"
    UNRESOLVED_AMBIGUOUS = "UNRESOLVED_AMBIGUOUS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class EligibilityStatus(str, Enum):
    ELIGIBLE_RESOLVED = "ELIGIBLE_RESOLVED"
    ELIGIBLE_ACTIVATED = "ELIGIBLE_ACTIVATED"
    NOT_ACTIVATED = "NOT_ACTIVATED"
    EXCLUDED_AMBIGUOUS = "EXCLUDED_AMBIGUOUS"
    EXCLUDED_NO_MARKET_DATA = "EXCLUDED_NO_MARKET_DATA"
    EXCLUDED_CONFLICTING_DATA = "EXCLUDED_CONFLICTING_DATA"
    EXCLUDED_IDENTITY = "EXCLUDED_IDENTITY"
    EXCLUDED_POLICY_MISMATCH = "EXCLUDED_POLICY_MISMATCH"
    EXCLUDED_INVALID_LEVELS = "EXCLUDED_INVALID_LEVELS"
    EXCLUDED_NON_CANONICAL = "EXCLUDED_NON_CANONICAL"
    EXCLUDED_INCOMPLETE_EVIDENCE = "EXCLUDED_INCOMPLETE_EVIDENCE"


class SampleEvidenceLabel(str, Enum):
    ANECDOTAL = "ANECDOTAL"
    INSUFFICIENT = "INSUFFICIENT"
    PRELIMINARY = "PRELIMINARY"
    ANALYZABLE = "ANALYZABLE"


class MetricValueContract(ContractModel):
    contract_version: str = METRIC_CONTRACT_VERSION
    metric_name: str = Field(min_length=1, max_length=100)
    cohort_name: str = Field(min_length=1, max_length=100)
    value: float | None = None
    unit: str
    numerator: float | None = None
    denominator: int = Field(ge=0)
    confidence_lower: float | None = None
    confidence_upper: float | None = None
    policy_version: str
    engine_version: str
    outcome_dataset_fingerprint: str = Field(min_length=64, max_length=64)
    period_start: UtcDatetime | None = None
    period_end: UtcDatetime | None = None
    sample_label: SampleEvidenceLabel
    computed_at: UtcDatetime
