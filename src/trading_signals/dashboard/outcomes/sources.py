from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from trading_signals.dashboard.ingestion.readers import read_json_snapshot
from trading_signals.dashboard.outcomes.engine import MarketCandle, timeframe_duration


class OutcomeSourceError(RuntimeError):
    """A safe source-loading failure with no path in its public message."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def validate_source_directory(path: Path, *, data_root: Path) -> Path:
    candidate = path.expanduser()
    if not candidate.is_absolute():
        raise OutcomeSourceError("SOURCE_PATH_NOT_ABSOLUTE")
    if candidate.is_symlink():
        raise OutcomeSourceError("SOURCE_PATH_IS_SYMLINK")
    resolved = candidate.resolve(strict=False)
    source_root = data_root.expanduser().resolve(strict=True)
    try:
        resolved.relative_to(source_root)
    except ValueError as exc:
        raise OutcomeSourceError("SOURCE_PATH_OUTSIDE_DATA_ROOT") from exc
    if not resolved.is_dir():
        raise OutcomeSourceError("SOURCE_DIRECTORY_MISSING")
    return resolved


@dataclass(frozen=True, slots=True)
class RiskPlanRecord:
    risk_plan_id: str
    entry: float
    stop_loss: float
    take_profit: float


@dataclass(frozen=True, slots=True)
class RiskPlanCatalog:
    records: dict[str, RiskPlanRecord]
    source_fingerprint: str


@dataclass(frozen=True, slots=True)
class MarketCandleCatalog:
    records: dict[tuple[str, str], tuple[MarketCandle, ...]]
    source_fingerprint: str
    records_seen: int

    def series(self, symbol: str, timeframe: str) -> tuple[MarketCandle, ...]:
        return self.records.get((symbol, timeframe), ())


def _json_files(root: Path) -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(root.glob("**/*.json"))
        if path.is_file() and not path.is_symlink() and not path.name.endswith(".tmp")
    )


def load_risk_plans(path: Path, *, data_root: Path) -> RiskPlanCatalog:
    root = validate_source_directory(path, data_root=data_root)
    records: dict[str, RiskPlanRecord] = {}
    payload_fingerprints: list[str] = []
    for source_path in _json_files(root):
        try:
            payload, snapshot = read_json_snapshot(source_path, max_bytes=4 * 1024 * 1024)
            identifier = str(payload["id"])
            record = RiskPlanRecord(
                risk_plan_id=identifier,
                entry=float(payload["entry"]),
                stop_loss=float(payload["stop_loss"]),
                take_profit=float(payload["take_profit"]),
            )
        except (KeyError, TypeError, ValueError, OSError) as exc:
            raise OutcomeSourceError("RISK_PLAN_SOURCE_INVALID") from exc
        existing = records.get(identifier)
        if existing is not None and existing != record:
            raise OutcomeSourceError("RISK_PLAN_ID_CONFLICT")
        records[identifier] = record
        payload_fingerprints.append(snapshot.fingerprint)
    digest = hashlib.sha256()
    for fingerprint in sorted(payload_fingerprints):
        digest.update(fingerprint.encode("ascii"))
    return RiskPlanCatalog(records=records, source_fingerprint=digest.hexdigest())


def load_market_snapshots(path: Path, *, data_root: Path) -> MarketCandleCatalog:
    root = validate_source_directory(path, data_root=data_root)
    records: dict[tuple[str, str], list[MarketCandle]] = {}
    payload_fingerprints: list[str] = []
    count = 0
    for source_path in _json_files(root):
        try:
            payload, snapshot = read_json_snapshot(source_path, max_bytes=4 * 1024 * 1024)
            symbol = str(payload["symbol"])
            timeframe = str(payload["timeframe"])
            inclusive_close = _parse_utc(str(payload["timestamp"]))
            duration = timeframe_duration(timeframe)
            close_at = inclusive_close + timedelta(milliseconds=1)
            candle = MarketCandle(
                symbol=symbol,
                timeframe=timeframe,
                open_at=close_at - duration,
                close_at=close_at,
                open=float(payload["open"]),
                high=float(payload["high"]),
                low=float(payload["low"]),
                close=float(payload["close"]),
                closed=True,
            )
        except (KeyError, TypeError, ValueError, OSError) as exc:
            raise OutcomeSourceError("MARKET_SNAPSHOT_SOURCE_INVALID") from exc
        records.setdefault((symbol, timeframe), []).append(candle)
        payload_fingerprints.append(snapshot.fingerprint)
        count += 1
    normalized = {
        key: tuple(sorted(items, key=lambda item: item.open_at))
        for key, items in records.items()
    }
    digest = hashlib.sha256()
    for fingerprint in sorted(payload_fingerprints):
        digest.update(fingerprint.encode("ascii"))
    return MarketCandleCatalog(
        records=normalized,
        source_fingerprint=digest.hexdigest(),
        records_seen=count,
    )


def _parse_utc(raw: str):
    from datetime import UTC, datetime

    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp is not timezone-aware")
    return parsed.astimezone(UTC)
