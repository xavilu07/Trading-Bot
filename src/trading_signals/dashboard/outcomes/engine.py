from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Iterable

from trading_signals.dashboard.contracts import (
    CollisionPolicy,
    EntryActivationPolicy,
    OutcomeCandleEvidence,
    OutcomeDataQuality,
    OutcomeEvaluationPolicy,
    OutcomeMarketSource,
    OutcomeSignalIdentity,
    OutcomeStatus,
    SignalOutcome,
)


class OutcomeEngineError(ValueError):
    """Typed, non-sensitive validation error raised by the pure engine."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class OutcomeSignal:
    projection_key: str
    signal_id: str | None
    symbol: str
    direction: str
    timeframe: str
    decision_at: datetime
    entry_price: float | None
    stop_price: float | None
    target_price: float | None
    strategy_version: str | None = None
    signal_policy_version: str | None = None


@dataclass(frozen=True, slots=True)
class MarketCandle:
    symbol: str
    timeframe: str
    open_at: datetime
    close_at: datetime
    open: float
    high: float
    low: float
    close: float
    closed: bool = True


def timeframe_duration(timeframe: str) -> timedelta:
    unit_seconds = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3_600,
        "4h": 14_400,
        "1d": 86_400,
    }
    try:
        return timedelta(seconds=unit_seconds[timeframe])
    except KeyError as exc:
        raise OutcomeEngineError("UNSUPPORTED_TIMEFRAME") from exc


def _utc(value: datetime, *, code: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise OutcomeEngineError(code)
    return value.astimezone(UTC)


def _ceil_boundary(value: datetime, duration: timedelta) -> datetime:
    seconds = int(duration.total_seconds())
    epoch_seconds = value.timestamp()
    quotient = math.ceil(epoch_seconds / seconds)
    boundary = datetime.fromtimestamp(quotient * seconds, tz=UTC)
    if value == boundary:
        return value
    return boundary


def _stable_fingerprint(
    *,
    source_name: str,
    timeframe: str,
    evidence: Iterable[OutcomeCandleEvidence],
    marker: str,
) -> str:
    payload = {
        "source": source_name,
        "timeframe": timeframe,
        "marker": marker,
        "candles": [
            {
                "open_at": item.open_at.isoformat(),
                "close_at": item.close_at.isoformat(),
                "open": item.open_price,
                "high": item.high_price,
                "low": item.low_price,
                "close": item.close_price,
            }
            for item in evidence
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _valid_levels(signal: OutcomeSignal) -> bool:
    prices = (signal.entry_price, signal.stop_price, signal.target_price)
    if not all(item is not None and math.isfinite(item) and item > 0 for item in prices):
        return False
    entry_price = float(signal.entry_price)
    stop_price = float(signal.stop_price)
    target_price = float(signal.target_price)
    if signal.direction == "long":
        return stop_price < entry_price < target_price
    if signal.direction == "short":
        return target_price < entry_price < stop_price
    return False


def _touches(candle: MarketCandle, price: float) -> bool:
    return candle.low <= price <= candle.high


def _market_source(
    *,
    source_name: str,
    timeframe: str,
    source_format: str,
    fingerprint: str,
    evidence: tuple[OutcomeCandleEvidence, ...],
    quality: OutcomeDataQuality,
) -> OutcomeMarketSource:
    return OutcomeMarketSource(
        logical_source_name=source_name,
        source_format=source_format,
        timeframe=timeframe,
        source_fingerprint=fingerprint,
        coverage_start=evidence[0].open_at if evidence else None,
        coverage_end=evidence[-1].close_at if evidence else None,
        candles_count=len(evidence),
        data_quality=quality,
        source_reference=f"source:{source_name}",
    )


def _result(
    *,
    signal: OutcomeSignal,
    policy: OutcomeEvaluationPolicy,
    source_name: str,
    source_format: str,
    evidence: list[OutcomeCandleEvidence],
    status: OutcomeStatus,
    quality: OutcomeDataQuality,
    computed_at: datetime,
    evaluation_start: datetime | None,
    terminal_timestamp: datetime | None = None,
    terminal_price: float | None = None,
    ambiguity_reason: str | None = None,
    first_stop_touch: datetime | None = None,
    first_target_touch: datetime | None = None,
    fingerprint_marker: str = "observed",
) -> SignalOutcome:
    evidence_tuple = tuple(evidence)
    fingerprint = _stable_fingerprint(
        source_name=source_name,
        timeframe=signal.timeframe,
        evidence=evidence_tuple,
        marker=fingerprint_marker,
    )
    return SignalOutcome(
        identity=OutcomeSignalIdentity(
            projection_key=signal.projection_key,
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            strategy_version=signal.strategy_version,
            signal_policy_version=signal.signal_policy_version,
        ),
        policy=policy,
        market_source=_market_source(
            source_name=source_name,
            timeframe=signal.timeframe,
            source_format=source_format,
            fingerprint=fingerprint,
            evidence=evidence_tuple,
            quality=quality,
        ),
        direction=signal.direction,
        timeframe=signal.timeframe,
        entry_timestamp=signal.decision_at,
        evaluation_start=evaluation_start,
        evaluation_end=evidence_tuple[-1].close_at if evidence_tuple else None,
        entry_price=signal.entry_price,
        stop_price=signal.stop_price,
        target_price=signal.target_price,
        candles_expected=policy.horizon_candles,
        candles_observed=len(evidence_tuple),
        first_stop_touch=first_stop_touch,
        first_target_touch=first_target_touch,
        terminal_status=status,
        terminal_timestamp=terminal_timestamp,
        terminal_price=terminal_price,
        ambiguity_reason=ambiguity_reason,
        data_quality=quality,
        policy_version=policy.policy_version,
        engine_version=policy.engine_version,
        source_fingerprint=fingerprint,
        computed_at=computed_at,
        evidence=evidence_tuple,
    )


def _invalid_result(
    *,
    signal: OutcomeSignal,
    policy: OutcomeEvaluationPolicy,
    source_name: str,
    source_format: str,
    computed_at: datetime,
    reason: str,
) -> SignalOutcome:
    return _result(
        signal=signal,
        policy=policy,
        source_name=source_name,
        source_format=source_format,
        evidence=[],
        status=OutcomeStatus.INVALID,
        quality=OutcomeDataQuality.NO_DATA,
        computed_at=computed_at,
        evaluation_start=None,
        ambiguity_reason=reason,
        fingerprint_marker=f"invalid:{reason}",
    )


def _normalize_candles(
    signal: OutcomeSignal,
    candles: Iterable[MarketCandle],
    *,
    duration: timedelta,
    as_of: datetime,
    window_start: datetime,
    window_end: datetime,
) -> tuple[list[MarketCandle], str | None]:
    original = list(candles)
    previous_open: datetime | None = None
    unique: dict[datetime, MarketCandle] = {}
    for candle in original:
        try:
            open_at = _utc(candle.open_at, code="CANDLE_TIMESTAMP_NOT_UTC")
            close_at = _utc(candle.close_at, code="CANDLE_TIMESTAMP_NOT_UTC")
        except OutcomeEngineError as exc:
            return [], exc.code
        if open_at < window_start or open_at >= window_end:
            continue
        if previous_open is not None and open_at < previous_open:
            return [], "CANDLES_OUT_OF_ORDER"
        previous_open = open_at
        normalized = MarketCandle(
            symbol=candle.symbol,
            timeframe=candle.timeframe,
            open_at=open_at,
            close_at=close_at,
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            closed=candle.closed,
        )
        if normalized.symbol != signal.symbol or normalized.timeframe != signal.timeframe:
            return [], "CANDLE_IDENTITY_MISMATCH"
        prices = (normalized.open, normalized.high, normalized.low, normalized.close)
        if (
            not all(math.isfinite(item) and item > 0 for item in prices)
            or normalized.low > min(normalized.open, normalized.close)
            or normalized.high < max(normalized.open, normalized.close)
            or normalized.low > normalized.high
        ):
            return [], "INVALID_CANDLE"
        if normalized.close_at - normalized.open_at != duration:
            return [], "INVALID_CANDLE_INTERVAL"
        existing = unique.get(open_at)
        if existing is not None:
            if existing != normalized:
                return [], "CONFLICTING_DUPLICATE_CANDLE"
            continue
        if not normalized.closed or normalized.close_at > as_of:
            continue
        unique[open_at] = normalized
    return list(unique.values()), None


def evaluate_signal_outcome(
    signal: OutcomeSignal,
    candles: Iterable[MarketCandle],
    *,
    policy: OutcomeEvaluationPolicy,
    as_of: datetime,
    source_name: str = "market_snapshots",
    source_format: str = "json_files",
    computed_at: datetime | None = None,
) -> SignalOutcome:
    """Evaluate one signal using only closed, full post-decision candles.

    The default policy requires a demonstrable post-decision touch of the
    intended entry. It never infers intrabar ordering from OHLC.
    """

    computed = _utc(computed_at or datetime.now(tz=UTC), code="COMPUTED_AT_NOT_UTC")
    cutoff = _utc(as_of, code="AS_OF_NOT_UTC")
    try:
        decision_at = _utc(signal.decision_at, code="SIGNAL_TIMESTAMP_NOT_UTC")
        duration = timeframe_duration(signal.timeframe)
    except OutcomeEngineError as exc:
        return _invalid_result(
            signal=signal,
            policy=policy,
            source_name=source_name,
            source_format=source_format,
            computed_at=computed,
            reason=exc.code,
        )
    normalized_signal = OutcomeSignal(
        projection_key=signal.projection_key,
        signal_id=signal.signal_id,
        symbol=signal.symbol,
        direction=signal.direction.lower(),
        timeframe=signal.timeframe,
        decision_at=decision_at,
        entry_price=signal.entry_price,
        stop_price=signal.stop_price,
        target_price=signal.target_price,
        strategy_version=signal.strategy_version,
        signal_policy_version=signal.signal_policy_version,
    )
    signal = normalized_signal
    if not signal.projection_key or not signal.symbol:
        return _invalid_result(
            signal=signal,
            policy=policy,
            source_name=source_name,
            source_format=source_format,
            computed_at=computed,
            reason="SIGNAL_IDENTITY_MISSING",
        )
    if policy.timeframe != signal.timeframe:
        return _invalid_result(
            signal=signal,
            policy=policy,
            source_name=source_name,
            source_format=source_format,
            computed_at=computed,
            reason="POLICY_TIMEFRAME_MISMATCH",
        )
    if decision_at > cutoff:
        return _invalid_result(
            signal=signal,
            policy=policy,
            source_name=source_name,
            source_format=source_format,
            computed_at=computed,
            reason="SIGNAL_IN_FUTURE",
        )
    if not _valid_levels(signal):
        return _invalid_result(
            signal=signal,
            policy=policy,
            source_name=source_name,
            source_format=source_format,
            computed_at=computed,
            reason="INVALID_SIGNAL_LEVELS",
        )

    evaluation_start = _ceil_boundary(decision_at, duration)
    normalized, candle_error = _normalize_candles(
        signal,
        candles,
        duration=duration,
        as_of=cutoff,
        window_start=evaluation_start,
        window_end=evaluation_start + duration * policy.horizon_candles,
    )
    if candle_error is not None:
        quality = (
            OutcomeDataQuality.CONFLICT
            if candle_error == "CONFLICTING_DUPLICATE_CANDLE"
            else OutcomeDataQuality.NO_DATA
        )
        return _result(
            signal=signal,
            policy=policy,
            source_name=source_name,
            source_format=source_format,
            evidence=[],
            status=(
                OutcomeStatus.NO_MARKET_DATA
                if candle_error == "CONFLICTING_DUPLICATE_CANDLE"
                else OutcomeStatus.INVALID
            ),
            quality=quality,
            computed_at=computed,
            evaluation_start=None,
            ambiguity_reason=candle_error,
            fingerprint_marker=f"candle-error:{candle_error}",
        )

    candle_by_open = {
        candle.open_at: candle
        for candle in normalized
        if candle.open_at >= evaluation_start
    }
    evidence: list[OutcomeCandleEvidence] = []
    first_stop_touch: datetime | None = None
    first_target_touch: datetime | None = None
    activated = policy.entry_activation_policy is EntryActivationPolicy.ASSUME_FILLED_AT_DECISION
    non_canonical_policy = activated or policy.collision_policy is not CollisionPolicy.AMBIGUOUS

    for index in range(1, policy.horizon_candles + 1):
        expected_open = evaluation_start + (duration * (index - 1))
        expected_close = expected_open + duration
        candle = candle_by_open.get(expected_open)
        if candle is None:
            horizon_not_yet_observable = expected_close > cutoff
            status = OutcomeStatus.OPEN if horizon_not_yet_observable else OutcomeStatus.NO_MARKET_DATA
            quality = (
                OutcomeDataQuality.PARTIAL
                if horizon_not_yet_observable
                else OutcomeDataQuality.GAP
            )
            return _result(
                signal=signal,
                policy=policy,
                source_name=source_name,
                source_format=source_format,
                evidence=evidence,
                status=status,
                quality=quality,
                computed_at=computed,
                evaluation_start=evaluation_start,
                ambiguity_reason=(
                    "HORIZON_STILL_OPEN"
                    if horizon_not_yet_observable
                    else "MISSING_EXPECTED_CANDLE"
                ),
                first_stop_touch=first_stop_touch,
                first_target_touch=first_target_touch,
                fingerprint_marker=f"missing:{expected_open.isoformat()}",
            )

        entry_touched = _touches(candle, signal.entry_price)
        stop_touched = _touches(candle, signal.stop_price)
        target_touched = _touches(candle, signal.target_price)
        if stop_touched and first_stop_touch is None:
            stop_at_open = (
                candle.open <= signal.stop_price
                if signal.direction == "long"
                else candle.open >= signal.stop_price
            )
            first_stop_touch = candle.open_at if stop_at_open else candle.close_at
        if target_touched and first_target_touch is None:
            target_at_open = (
                candle.open >= signal.target_price
                if signal.direction == "long"
                else candle.open <= signal.target_price
            )
            first_target_touch = (
                candle.open_at if target_at_open else candle.close_at
            )
        item = OutcomeCandleEvidence(
            candle_index=index,
            open_at=candle.open_at,
            close_at=candle.close_at,
            open_price=candle.open,
            high_price=candle.high,
            low_price=candle.low,
            close_price=candle.close,
            entry_touched=entry_touched,
            stop_touched=stop_touched,
            target_touched=target_touched,
        )
        evidence.append(item)

        activated_this_candle = False
        if not activated and entry_touched:
            activated = True
            activated_this_candle = True
            if candle.open != signal.entry_price and (stop_touched or target_touched):
                return _result(
                    signal=signal,
                    policy=policy,
                    source_name=source_name,
                    source_format=source_format,
                    evidence=evidence,
                    status=OutcomeStatus.AMBIGUOUS,
                    quality=OutcomeDataQuality.COMPLETE,
                    computed_at=computed,
                    evaluation_start=evaluation_start,
                    terminal_timestamp=candle.close_at,
                    ambiguity_reason="ENTRY_AND_BARRIER_ORDER_UNKNOWN_WITHIN_CANDLE",
                    first_stop_touch=first_stop_touch,
                    first_target_touch=first_target_touch,
                )
        if not activated:
            continue

        if not activated_this_candle:
            if signal.direction == "long":
                if candle.open <= signal.stop_price:
                    stop_touched = True
                    first_stop_touch = first_stop_touch or candle.open_at
                    return _result(
                        signal=signal,
                        policy=policy,
                        source_name=source_name,
                        source_format=source_format,
                        evidence=evidence,
                        status=OutcomeStatus.LOSS,
                        quality=(
                            OutcomeDataQuality.NON_CANONICAL
                            if non_canonical_policy
                            else OutcomeDataQuality.COMPLETE
                        ),
                        computed_at=computed,
                        evaluation_start=evaluation_start,
                        terminal_timestamp=candle.open_at,
                        terminal_price=candle.open,
                        first_stop_touch=first_stop_touch,
                        first_target_touch=first_target_touch,
                    )
                if candle.open >= signal.target_price:
                    target_touched = True
                    first_target_touch = first_target_touch or candle.open_at
                    return _result(
                        signal=signal,
                        policy=policy,
                        source_name=source_name,
                        source_format=source_format,
                        evidence=evidence,
                        status=OutcomeStatus.WIN,
                        quality=(
                            OutcomeDataQuality.NON_CANONICAL
                            if non_canonical_policy
                            else OutcomeDataQuality.COMPLETE
                        ),
                        computed_at=computed,
                        evaluation_start=evaluation_start,
                        terminal_timestamp=candle.open_at,
                        terminal_price=candle.open,
                        first_stop_touch=first_stop_touch,
                        first_target_touch=first_target_touch,
                    )
            else:
                if candle.open >= signal.stop_price:
                    stop_touched = True
                    first_stop_touch = first_stop_touch or candle.open_at
                    return _result(
                        signal=signal,
                        policy=policy,
                        source_name=source_name,
                        source_format=source_format,
                        evidence=evidence,
                        status=OutcomeStatus.LOSS,
                        quality=(
                            OutcomeDataQuality.NON_CANONICAL
                            if non_canonical_policy
                            else OutcomeDataQuality.COMPLETE
                        ),
                        computed_at=computed,
                        evaluation_start=evaluation_start,
                        terminal_timestamp=candle.open_at,
                        terminal_price=candle.open,
                        first_stop_touch=first_stop_touch,
                        first_target_touch=first_target_touch,
                    )
                if candle.open <= signal.target_price:
                    target_touched = True
                    first_target_touch = first_target_touch or candle.open_at
                    return _result(
                        signal=signal,
                        policy=policy,
                        source_name=source_name,
                        source_format=source_format,
                        evidence=evidence,
                        status=OutcomeStatus.WIN,
                        quality=(
                            OutcomeDataQuality.NON_CANONICAL
                            if non_canonical_policy
                            else OutcomeDataQuality.COMPLETE
                        ),
                        computed_at=computed,
                        evaluation_start=evaluation_start,
                        terminal_timestamp=candle.open_at,
                        terminal_price=candle.open,
                        first_stop_touch=first_stop_touch,
                        first_target_touch=first_target_touch,
                    )

        if stop_touched and target_touched:
            if policy.collision_policy is CollisionPolicy.AMBIGUOUS:
                return _result(
                    signal=signal,
                    policy=policy,
                    source_name=source_name,
                    source_format=source_format,
                    evidence=evidence,
                    status=OutcomeStatus.AMBIGUOUS,
                    quality=OutcomeDataQuality.COMPLETE,
                    computed_at=computed,
                    evaluation_start=evaluation_start,
                    terminal_timestamp=candle.close_at,
                    ambiguity_reason="STOP_AND_TARGET_TOUCHED_WITHIN_SAME_OHLC_CANDLE",
                    first_stop_touch=first_stop_touch,
                    first_target_touch=first_target_touch,
                )
            collision_status = (
                OutcomeStatus.LOSS
                if policy.collision_policy is CollisionPolicy.CONSERVATIVE_STOP_FIRST
                else OutcomeStatus.WIN
            )
            terminal_price = (
                signal.stop_price
                if collision_status is OutcomeStatus.LOSS
                else signal.target_price
            )
            return _result(
                signal=signal,
                policy=policy,
                source_name=source_name,
                source_format=source_format,
                evidence=evidence,
                status=collision_status,
                quality=OutcomeDataQuality.NON_CANONICAL,
                computed_at=computed,
                evaluation_start=evaluation_start,
                terminal_timestamp=candle.close_at,
                terminal_price=terminal_price,
                ambiguity_reason=f"ANALYTICAL_{policy.collision_policy.value}",
                first_stop_touch=first_stop_touch,
                first_target_touch=first_target_touch,
            )
        if stop_touched:
            return _result(
                signal=signal,
                policy=policy,
                source_name=source_name,
                source_format=source_format,
                evidence=evidence,
                status=OutcomeStatus.LOSS,
                quality=(
                    OutcomeDataQuality.NON_CANONICAL
                    if non_canonical_policy
                    else OutcomeDataQuality.COMPLETE
                ),
                computed_at=computed,
                evaluation_start=evaluation_start,
                terminal_timestamp=candle.close_at,
                terminal_price=signal.stop_price,
                first_stop_touch=first_stop_touch,
                first_target_touch=first_target_touch,
            )
        if target_touched:
            return _result(
                signal=signal,
                policy=policy,
                source_name=source_name,
                source_format=source_format,
                evidence=evidence,
                status=OutcomeStatus.WIN,
                quality=(
                    OutcomeDataQuality.NON_CANONICAL
                    if non_canonical_policy
                    else OutcomeDataQuality.COMPLETE
                ),
                computed_at=computed,
                evaluation_start=evaluation_start,
                terminal_timestamp=candle.close_at,
                terminal_price=signal.target_price,
                first_stop_touch=first_stop_touch,
                first_target_touch=first_target_touch,
            )

    final = evidence[-1]
    return _result(
        signal=signal,
        policy=policy,
        source_name=source_name,
        source_format=source_format,
        evidence=evidence,
        status=OutcomeStatus.EXPIRED,
        quality=(
            OutcomeDataQuality.NON_CANONICAL
            if non_canonical_policy
            else OutcomeDataQuality.COMPLETE
        ),
        computed_at=computed,
        evaluation_start=evaluation_start,
        terminal_timestamp=final.close_at,
        terminal_price=final.close_price if activated else None,
        ambiguity_reason=None if activated else "ENTRY_NOT_ACTIVATED_WITHIN_HORIZON",
        first_stop_touch=first_stop_touch,
        first_target_touch=first_target_touch,
    )
