from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


CLEANUP_VERSION = "ACTIVE_SIGNAL_CLEANUP_V1"
CLOSE_REASON = "cleanup_zombie_expired"
LIFECYCLE_STATUS = "expired_zombie"


@dataclass(slots=True)
class ActiveSignalCleanupConfig:
    enabled: bool = False
    dry_run: bool = True
    zombie_hours: float = 48.0
    backup_root: Path | None = None


@dataclass(slots=True)
class ActiveSignalCleanupCandidate:
    path: Path
    signal_id: str
    symbol: str
    direction: str
    age_hours: float
    published_at: str | None
    created_at: str | None
    status: str | None
    reason: str = CLOSE_REASON

    def to_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "age_hours": self.age_hours,
            "published_at": self.published_at,
            "created_at": self.created_at,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(slots=True)
class ActiveSignalCleanupResult:
    enabled: bool
    dry_run: bool
    zombie_hours: float
    scanned: int = 0
    candidates: list[ActiveSignalCleanupCandidate] = field(default_factory=list)
    closed: list[dict[str, object]] = field(default_factory=list)
    skipped: list[dict[str, object]] = field(default_factory=list)
    backup_dir: Path | None = None
    events: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "dry_run": self.dry_run,
            "zombie_hours": self.zombie_hours,
            "scanned": self.scanned,
            "candidate_count": len(self.candidates),
            "closed_count": len(self.closed),
            "skipped_count": len(self.skipped),
            "backup_dir": str(self.backup_dir) if self.backup_dir else None,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "closed": self.closed,
            "skipped": self.skipped,
            "events": self.events,
        }


def run_active_signal_cleanup_v1(
    *,
    data_path: Path,
    config: ActiveSignalCleanupConfig,
    now: datetime | None = None,
) -> ActiveSignalCleanupResult:
    now = now or datetime.now(tz=UTC)
    result = ActiveSignalCleanupResult(
        enabled=config.enabled,
        dry_run=config.dry_run,
        zombie_hours=config.zombie_hours,
    )
    _event(
        result,
        "active_signal_cleanup_v1_started",
        enabled=config.enabled,
        dry_run=config.dry_run,
        zombie_hours=config.zombie_hours,
        data_path=str(data_path),
    )
    signal_files = sorted((data_path / "trade_signals").glob("**/*.json"))
    result.scanned = len(signal_files)
    for path in signal_files:
        payload = _read_json(path)
        candidate = detect_zombie_signal(path=path, payload=payload, zombie_hours=config.zombie_hours, now=now)
        if candidate is None:
            continue
        result.candidates.append(candidate)
        _event(result, "active_signal_cleanup_v1_candidate", **candidate.to_dict())

    if not config.enabled:
        result.skipped.extend(
            {"signal_id": candidate.signal_id, "path": str(candidate.path), "reason": "cleanup_disabled"}
            for candidate in result.candidates
        )
        _event(result, "active_signal_cleanup_v1_summary", **_summary_payload(result))
        return result

    if config.dry_run:
        result.skipped.extend(
            {"signal_id": candidate.signal_id, "path": str(candidate.path), "reason": "dry_run"}
            for candidate in result.candidates
        )
        _event(result, "active_signal_cleanup_v1_summary", **_summary_payload(result))
        return result

    if result.candidates:
        backup_root = config.backup_root or data_path / "trade_signals_backups" / "active_cleanup_v1"
        result.backup_dir = backup_root / now.strftime("%Y%m%dT%H%M%SZ")
        result.backup_dir.mkdir(parents=True, exist_ok=True)

    for candidate in result.candidates:
        close_result = close_zombie_signal(candidate=candidate, backup_dir=result.backup_dir, now=now)
        result.closed.append(close_result)
        _event(result, "active_signal_cleanup_v1_closed_signal", **close_result)
    _event(result, "active_signal_cleanup_v1_summary", **_summary_payload(result))
    return result


def detect_zombie_signal(
    *,
    path: Path,
    payload: dict[str, Any],
    zombie_hours: float,
    now: datetime,
) -> ActiveSignalCleanupCandidate | None:
    status = str(payload.get("status") or "").lower()
    if status not in {"published", "active"}:
        return None
    if payload.get("closed_at") or payload.get("close_reason") or payload.get("exit_reason"):
        return None
    if payload.get("expires_at"):
        return None
    timestamp = str(payload.get("published_at") or payload.get("created_at") or "")
    age_hours = _age_hours(timestamp, now)
    if age_hours is None or age_hours <= zombie_hours:
        return None
    return ActiveSignalCleanupCandidate(
        path=path,
        signal_id=str(payload.get("id") or path.stem),
        symbol=str(payload.get("symbol") or "UNKNOWN"),
        direction=str(payload.get("decision") or payload.get("direction") or "UNKNOWN"),
        age_hours=age_hours,
        published_at=_optional_text(payload.get("published_at")),
        created_at=_optional_text(payload.get("created_at")),
        status=str(payload.get("status") or ""),
    )


def close_zombie_signal(
    *,
    candidate: ActiveSignalCleanupCandidate,
    backup_dir: Path | None,
    now: datetime,
) -> dict[str, object]:
    payload = _read_json(candidate.path)
    if str(payload.get("status") or "").lower() == "closed" or payload.get("close_reason"):
        return {
            "signal_id": candidate.signal_id,
            "path": str(candidate.path),
            "closed": False,
            "reason": "already_closed_or_has_close_reason",
        }
    if backup_dir is None:
        raise ValueError("backup_dir is required before modifying a signal")
    backup_path = backup_dir / candidate.path.name
    if backup_path.exists():
        backup_path = backup_dir / f"{candidate.path.stem}_{candidate.signal_id}{candidate.path.suffix}"
    shutil.copy2(candidate.path, backup_path)
    closed_at = now.isoformat(timespec="seconds")
    payload.update(
        {
            "status": "closed",
            "lifecycle_status": LIFECYCLE_STATUS,
            "close_reason": CLOSE_REASON,
            "closed_at": closed_at,
            "cleanup_version": CLEANUP_VERSION,
        }
    )
    candidate.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "signal_id": candidate.signal_id,
        "path": str(candidate.path),
        "backup_path": str(backup_path),
        "closed": True,
        "status": "closed",
        "lifecycle_status": LIFECYCLE_STATUS,
        "close_reason": CLOSE_REASON,
        "closed_at": closed_at,
        "cleanup_version": CLEANUP_VERSION,
    }


def write_active_signal_cleanup_v1_design_report(reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "active_signal_cleanup_v1_design.md"
    path.write_text(
        "\n".join(
            [
                "# ACTIVE_SIGNAL_CLEANUP_V1 Design",
                "",
                "Purpose: close active zombie signal records without deleting historical files.",
                "",
                "Default safety:",
                "- `ACTIVE_SIGNAL_CLEANUP_ENABLED=false`",
                "- `ACTIVE_SIGNAL_CLEANUP_DRY_RUN=true`",
                "- Manual script only; not integrated into scheduler.",
                "",
                "Zombie criteria:",
                "- `status` is `published` or `active`",
                "- has `published_at` or `created_at`",
                "- no `expires_at`",
                "- no `closed_at`",
                "- no `close_reason` / `exit_reason`",
                "- age greater than configured zombie hours",
                "",
                "Apply behavior:",
                "- creates backup under `data/trade_signals_backups/active_cleanup_v1/<timestamp>/`",
                "- updates JSON in place with `status=closed`",
                "- sets `lifecycle_status=expired_zombie`",
                "- sets `close_reason=cleanup_zombie_expired`",
                "- sets `closed_at` and `cleanup_version=ACTIVE_SIGNAL_CLEANUP_V1`",
                "",
                "Non-goals:",
                "- does not publish duplicates",
                "- does not delete historical files",
                "- does not change filters",
                "- does not touch Telegram public routing",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _summary_payload(result: ActiveSignalCleanupResult) -> dict[str, object]:
    return {
        "enabled": result.enabled,
        "dry_run": result.dry_run,
        "scanned": result.scanned,
        "candidate_count": len(result.candidates),
        "closed_count": len(result.closed),
        "skipped_count": len(result.skipped),
        "backup_dir": str(result.backup_dir) if result.backup_dir else None,
    }


def _event(result: ActiveSignalCleanupResult, event: str, **payload: object) -> None:
    result.events.append({"event": event, **payload})


def _read_json(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _age_hours(timestamp: str, now: datetime) -> float | None:
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
