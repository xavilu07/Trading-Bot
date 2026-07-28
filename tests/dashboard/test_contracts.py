from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from trading_signals.dashboard.contracts import (
    CONTRACT_VERSION,
    DataClassification,
    EvidenceReference,
    Freshness,
    FreshnessStatus,
    OperationalStatus,
    OutcomeQuality,
    Pagination,
    StatusEvidence,
)


def test_contract_version_and_normalized_statuses_are_stable() -> None:
    assert CONTRACT_VERSION == "dashboard.v1"
    assert {item.value for item in OperationalStatus} == {
        "HEALTHY",
        "DEGRADED",
        "STOPPED",
        "NO_EVIDENCE",
        "STALE_DATA",
    }
    assert {item.value for item in DataClassification} >= {
        "REAL",
        "DERIVED",
        "UNAVAILABLE",
        "STALE",
        "NO_EVIDENCE",
        "NON_CANONICAL",
    }


def test_datetimes_require_timezone_and_serialize_as_utc() -> None:
    madrid = timezone(timedelta(hours=2))
    evidence = StatusEvidence(
        status=OperationalStatus.HEALTHY,
        reason="test evidence",
        observed_at=datetime(2026, 7, 28, 13, 0, tzinfo=madrid),
        source="test",
        freshness=Freshness(
            status=FreshnessStatus.FRESH,
            age_seconds=0,
            expected_freshness_seconds=60,
            observed_event_at=datetime(2026, 7, 28, 13, 0, tzinfo=madrid),
        ),
        classification=DataClassification.REAL,
    )
    assert evidence.observed_at == datetime(2026, 7, 28, 11, 0, tzinfo=timezone.utc)
    assert '"observed_at":"2026-07-28T11:00:00Z"' in evidence.model_dump_json()

    with pytest.raises(ValidationError):
        StatusEvidence(
            status=OperationalStatus.HEALTHY,
            reason="naive timestamp is forbidden",
            observed_at=datetime(2026, 7, 28, 11, 0),
            source="test",
            freshness=Freshness(status=FreshnessStatus.UNKNOWN),
            classification=DataClassification.NO_EVIDENCE,
        )


@pytest.mark.parametrize(
    "reference",
    [
        "/root/bot/data/runtime/scheduler_heartbeat.json",
        "source:test#token=secret-value",
        "source:test#chat_id=12345678",
    ],
)
def test_evidence_references_reject_sensitive_paths_and_values(reference: str) -> None:
    with pytest.raises(ValidationError):
        EvidenceReference(source_id="test", reference=reference)


def test_non_canonical_outcome_is_explicit() -> None:
    quality = OutcomeQuality(
        canonical=False,
        classification=DataClassification.NON_CANONICAL,
        reason="Current paper tracker can reuse the entry candle.",
        issues=("pre_entry_contamination", "duplicate_candle_updates"),
    )
    assert quality.canonical is False
    assert quality.classification is DataClassification.NON_CANONICAL


def test_pagination_is_bounded_and_versioned() -> None:
    assert Pagination().limit == 50
    assert Pagination(limit=200).limit == 200
    with pytest.raises(ValidationError):
        Pagination(limit=201)
