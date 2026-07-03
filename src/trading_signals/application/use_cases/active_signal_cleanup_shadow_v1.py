from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from trading_signals.application.use_cases.signal_lifecycle import active_published_signals


CLEANUP_LIKELY_ZOMBIE = "LIKELY_ZOMBIE"
CLEANUP_STALE = "STALE"
CLEANUP_RECENT = "RECENT"
CLEANUP_UNKNOWN = "UNKNOWN"


@dataclass(slots=True)
class ActiveSignalCleanupAssessment:
    signal_id: str
    symbol: str
    direction: str
    active_key: str
    classification: str
    age_hours: float | None
    created_at: str | None
    published_at: str | None
    expires_at: str | None
    close_reason: str | None
    reasons: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "active_key": self.active_key,
            "classification": self.classification,
            "age_hours": self.age_hours,
            "created_at": self.created_at,
            "published_at": self.published_at,
            "expires_at": self.expires_at,
            "close_reason": self.close_reason,
            "reasons": list(self.reasons),
        }


def classify_active_signal_for_cleanup(
    signal: dict[str, Any],
    *,
    now: datetime | None = None,
) -> ActiveSignalCleanupAssessment:
    now = now or datetime.now(tz=UTC)
    symbol = str(signal.get("symbol") or "UNKNOWN")
    direction = str(signal.get("decision") or signal.get("direction") or "UNKNOWN")
    published_at = _optional_text(signal.get("published_at"))
    created_at = _optional_text(signal.get("created_at"))
    expires_at = _optional_text(signal.get("expires_at"))
    close_reason = _optional_text(signal.get("close_reason") or signal.get("exit_reason"))
    timestamp = published_at or created_at
    age_hours = _age_hours(timestamp, now)
    has_expiration = bool(expires_at)
    has_close_reason = bool(close_reason)
    reasons: list[str] = []

    if age_hours is None:
        classification = CLEANUP_UNKNOWN
        reasons.append("missing_published_at_or_created_at")
    elif age_hours > 48 and not has_expiration and not has_close_reason:
        classification = CLEANUP_LIKELY_ZOMBIE
        reasons.extend(["age_gt_48h", "missing_expires_at", "missing_close_reason"])
    elif age_hours > 24:
        classification = CLEANUP_STALE
        reasons.append("age_gt_24h")
        if not has_expiration:
            reasons.append("missing_expires_at")
        if not has_close_reason:
            reasons.append("missing_close_reason")
    else:
        classification = CLEANUP_RECENT
        reasons.append("age_lte_24h")

    return ActiveSignalCleanupAssessment(
        signal_id=str(signal.get("id") or ""),
        symbol=symbol,
        direction=direction,
        active_key=f"{symbol}|{direction}",
        classification=classification,
        age_hours=age_hours,
        created_at=created_at,
        published_at=published_at,
        expires_at=expires_at,
        close_reason=close_reason,
        reasons=reasons,
    )


def evaluate_active_signal_cleanup_shadow_v1(
    *,
    signal_repo,
    signal,
    is_duplicate: bool,
    lifecycle=None,
    now: datetime | None = None,
) -> dict[str, object] | None:
    lifecycle_reason = str(getattr(lifecycle, "reason", "") or "")
    duplicate_or_lifecycle_block = is_duplicate or lifecycle_reason in {
        "active_same_symbol_direction_without_reentry",
        "max_reentries_reached",
    }
    if not duplicate_or_lifecycle_block:
        return None

    symbol = str(getattr(signal, "symbol", "") or "")
    direction = str(getattr(signal, "decision", "") or "")
    active = active_published_signals(signal_repo, symbol=symbol, direction=direction, limit=500)
    if not active:
        return {
            "symbol": symbol,
            "direction": direction,
            "active_key": f"{symbol}|{direction}",
            "shadow_only": True,
            "public_allowed": False,
            "is_duplicate": is_duplicate,
            "lifecycle_reason": lifecycle_reason or None,
            "blocking_active_count": 0,
            "cleanup_classification": CLEANUP_UNKNOWN,
            "blocking_active_signals": [],
            "estimated_released_candidate_if_cleanup": False,
            "skip_reason": "active_signal_not_found",
        }

    assessments = [classify_active_signal_for_cleanup(item, now=now) for item in active]
    priority = {
        CLEANUP_LIKELY_ZOMBIE: 4,
        CLEANUP_STALE: 3,
        CLEANUP_UNKNOWN: 2,
        CLEANUP_RECENT: 1,
    }
    strongest = max(assessments, key=lambda item: priority.get(item.classification, 0))
    return {
        "symbol": symbol,
        "direction": direction,
        "active_key": f"{symbol}|{direction}",
        "shadow_only": True,
        "public_allowed": False,
        "is_duplicate": is_duplicate,
        "lifecycle_reason": lifecycle_reason or None,
        "blocking_active_count": len(assessments),
        "cleanup_classification": strongest.classification,
        "likely_zombie_count": sum(1 for item in assessments if item.classification == CLEANUP_LIKELY_ZOMBIE),
        "stale_count": sum(1 for item in assessments if item.classification == CLEANUP_STALE),
        "recent_count": sum(1 for item in assessments if item.classification == CLEANUP_RECENT),
        "unknown_count": sum(1 for item in assessments if item.classification == CLEANUP_UNKNOWN),
        "blocking_active_signals": [item.to_dict() for item in assessments],
        "estimated_released_candidate_if_cleanup": strongest.classification in {CLEANUP_LIKELY_ZOMBIE, CLEANUP_STALE},
    }


def _age_hours(timestamp: str | None, now: datetime) -> float | None:
    parsed = _parse_datetime(timestamp)
    if parsed is None:
        return None
    return round((now - parsed).total_seconds() / 3600, 2)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
