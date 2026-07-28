from __future__ import annotations

import hashlib
import math
import random
import statistics
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable, Mapping, Sequence

from trading_signals.dashboard.contracts.metrics import (
    EligibilityStatus,
    EntryLifecycleStatus,
    SampleEvidenceLabel,
)
from trading_signals.dashboard.metrics.policy import (
    BOOTSTRAP_SEED_VERSION,
    FROZEN_ENGINE_VERSION,
    FROZEN_POLICY_VERSION,
)

ELIGIBLE_RESOLVED = "ELIGIBLE_RESOLVED"
ELIGIBLE_ACTIVATED = "ELIGIBLE_ACTIVATED"


@dataclass(frozen=True, slots=True)
class MetricObservation:
    outcome_id: str
    signal_projection_key: str
    symbol: str
    direction: str
    timeframe: str
    setup: str | None
    strategy_version: str | None
    policy_version: str
    engine_version: str
    market_data_fingerprint: str
    data_quality: str
    terminal_status: str
    entry_timestamp: datetime
    entry_price: float | None
    stop_price: float | None
    target_price: float | None
    entry_activated: bool
    entry_activated_at: datetime | None
    entry_activation_candle_open: datetime | None
    candles_until_entry: int | None
    candles_after_entry: int | None
    ambiguity_reason: str | None = None


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    status: EligibilityStatus
    reason_code: str
    lifecycle: EntryLifecycleStatus


@dataclass(frozen=True, slots=True)
class ComputedMetric:
    name: str
    unit: str
    value: float | None
    numerator: float | None
    denominator: int
    confidence_lower: float | None = None
    confidence_upper: float | None = None
    details: Mapping[str, object] | None = None


def sample_label(size: int) -> SampleEvidenceLabel:
    if size < 20:
        return SampleEvidenceLabel.ANECDOTAL
    if size < 50:
        return SampleEvidenceLabel.INSUFFICIENT
    if size < 100:
        return SampleEvidenceLabel.PRELIMINARY
    return SampleEvidenceLabel.ANALYZABLE


def _valid_fingerprint(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def levels_are_valid(observation: MetricObservation) -> bool:
    prices = (
        observation.entry_price,
        observation.stop_price,
        observation.target_price,
    )
    if not all(
        value is not None and math.isfinite(value) and value > 0 for value in prices
    ):
        return False
    entry = float(observation.entry_price)
    stop = float(observation.stop_price)
    target = float(observation.target_price)
    if observation.direction == "long":
        return stop < entry < target
    if observation.direction == "short":
        return target < entry < stop
    return False


def classify_eligibility(observation: MetricObservation) -> EligibilityDecision:
    if (
        observation.policy_version != FROZEN_POLICY_VERSION
        or observation.engine_version != FROZEN_ENGINE_VERSION
    ):
        return EligibilityDecision(
            EligibilityStatus.EXCLUDED_POLICY_MISMATCH,
            "POLICY_OR_ENGINE_VERSION_MISMATCH",
            EntryLifecycleStatus.INSUFFICIENT_EVIDENCE,
        )
    if not observation.strategy_version or observation.strategy_version.lower() == "unknown":
        return EligibilityDecision(
            EligibilityStatus.EXCLUDED_IDENTITY,
            "STRATEGY_IDENTITY_MISSING",
            EntryLifecycleStatus.INSUFFICIENT_EVIDENCE,
        )
    if not levels_are_valid(observation):
        return EligibilityDecision(
            EligibilityStatus.EXCLUDED_INVALID_LEVELS,
            "SIGNAL_LEVELS_INVALID",
            EntryLifecycleStatus.INSUFFICIENT_EVIDENCE,
        )
    if not _valid_fingerprint(observation.market_data_fingerprint):
        return EligibilityDecision(
            EligibilityStatus.EXCLUDED_CONFLICTING_DATA,
            "MARKET_FINGERPRINT_INVALID",
            EntryLifecycleStatus.INSUFFICIENT_EVIDENCE,
        )
    if observation.data_quality == "CONFLICT":
        return EligibilityDecision(
            EligibilityStatus.EXCLUDED_CONFLICTING_DATA,
            "MARKET_EVIDENCE_CONFLICT",
            EntryLifecycleStatus.INSUFFICIENT_EVIDENCE,
        )
    if observation.data_quality == "NON_CANONICAL" or observation.terminal_status == "NON_CANONICAL":
        return EligibilityDecision(
            EligibilityStatus.EXCLUDED_NON_CANONICAL,
            "OUTCOME_NON_CANONICAL",
            EntryLifecycleStatus.INSUFFICIENT_EVIDENCE,
        )
    if observation.terminal_status == "AMBIGUOUS":
        return EligibilityDecision(
            EligibilityStatus.EXCLUDED_AMBIGUOUS,
            "OHLC_INTRABAR_ORDER_AMBIGUOUS",
            EntryLifecycleStatus.UNRESOLVED_AMBIGUOUS,
        )
    if observation.terminal_status == "NO_MARKET_DATA" or observation.data_quality in {
        "GAP",
        "NO_DATA",
    }:
        return EligibilityDecision(
            EligibilityStatus.EXCLUDED_NO_MARKET_DATA,
            "MARKET_EVIDENCE_INCOMPLETE",
            EntryLifecycleStatus.INSUFFICIENT_EVIDENCE,
        )
    if observation.data_quality != "COMPLETE":
        return EligibilityDecision(
            EligibilityStatus.EXCLUDED_INCOMPLETE_EVIDENCE,
            "EVIDENCE_NOT_COMPLETE",
            EntryLifecycleStatus.INSUFFICIENT_EVIDENCE,
        )
    if not observation.entry_activated:
        return EligibilityDecision(
            EligibilityStatus.NOT_ACTIVATED,
            "ENTRY_NOT_TOUCHED_WITHIN_HORIZON",
            EntryLifecycleStatus.ENTRY_NOT_ACTIVATED,
        )
    if observation.terminal_status == "WIN":
        return EligibilityDecision(
            EligibilityStatus.ELIGIBLE_RESOLVED,
            "ENTRY_ACTIVATED_TARGET_RESOLVED",
            EntryLifecycleStatus.RESOLVED_WIN,
        )
    if observation.terminal_status == "LOSS":
        return EligibilityDecision(
            EligibilityStatus.ELIGIBLE_RESOLVED,
            "ENTRY_ACTIVATED_STOP_RESOLVED",
            EntryLifecycleStatus.RESOLVED_LOSS,
        )
    if observation.terminal_status == "EXPIRED":
        return EligibilityDecision(
            EligibilityStatus.ELIGIBLE_ACTIVATED,
            "ENTRY_ACTIVATED_HORIZON_EXPIRED",
            EntryLifecycleStatus.ACTIVATED_EXPIRED,
        )
    if observation.terminal_status == "OPEN":
        return EligibilityDecision(
            EligibilityStatus.EXCLUDED_INCOMPLETE_EVIDENCE,
            "OUTCOME_HORIZON_INCOMPLETE",
            EntryLifecycleStatus.ENTRY_ACTIVATED,
        )
    return EligibilityDecision(
        EligibilityStatus.EXCLUDED_INCOMPLETE_EVIDENCE,
        "TERMINAL_STATUS_NOT_METRIC_ELIGIBLE",
        EntryLifecycleStatus.INSUFFICIENT_EVIDENCE,
    )


def gross_plan_r(observation: MetricObservation) -> float:
    decision = classify_eligibility(observation)
    if decision.status is not EligibilityStatus.ELIGIBLE_RESOLVED:
        raise ValueError("OUTCOME_NOT_RESOLVED_ELIGIBLE")
    if observation.terminal_status == "LOSS":
        return -1.0
    entry = float(observation.entry_price)
    stop = float(observation.stop_price)
    target = float(observation.target_price)
    risk = abs(entry - stop)
    reward = (
        target - entry
        if observation.direction == "long"
        else entry - target
    )
    return reward / risk


def wilson_interval(wins: int, total: int, *, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 0.0)
    proportion = wins / total
    denominator = 1.0 + (z * z / total)
    centre = (proportion + z * z / (2.0 * total)) / denominator
    radius = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / total
            + z * z / (4.0 * total * total)
        )
        / denominator
    )
    return (max(0.0, centre - radius), min(1.0, centre + radius))


def bootstrap_expectancy_interval(
    values: Sequence[float],
    *,
    cohort_fingerprint: str,
    samples: int = 2_000,
) -> tuple[float, float] | None:
    if not values:
        return None
    seed_material = f"{BOOTSTRAP_SEED_VERSION}|{cohort_fingerprint}".encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big")
    generator = random.Random(seed)
    size = len(values)
    means = sorted(
        sum(values[generator.randrange(size)] for _ in range(size)) / size
        for _ in range(samples)
    )
    lower_index = max(0, math.floor(samples * 0.025))
    upper_index = min(samples - 1, math.ceil(samples * 0.975) - 1)
    return (means[lower_index], means[upper_index])


def _max_streak(statuses: Iterable[str], wanted: str) -> int:
    longest = current = 0
    for status in statuses:
        if status == wanted:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def resolved_metrics(
    observations: Sequence[MetricObservation],
    *,
    cohort_fingerprint: str,
) -> tuple[ComputedMetric, ...]:
    ordered = sorted(observations, key=lambda item: (item.entry_timestamp, item.outcome_id))
    eligible = [
        item
        for item in ordered
        if classify_eligibility(item).status is EligibilityStatus.ELIGIBLE_RESOLVED
    ]
    values = [gross_plan_r(item) for item in eligible]
    wins = sum(item.terminal_status == "WIN" for item in eligible)
    losses = sum(item.terminal_status == "LOSS" for item in eligible)
    total = len(eligible)
    win_lower, win_upper = wilson_interval(wins, total)
    positive = sum(value for value in values if value > 0)
    negative = abs(sum(value for value in values if value < 0))
    bootstrap = bootstrap_expectancy_interval(
        values,
        cohort_fingerprint=cohort_fingerprint,
    )
    average = statistics.fmean(values) if values else None
    median = statistics.median(values) if values else None
    return (
        ComputedMetric("wins", "COUNT", float(wins), float(wins), total),
        ComputedMetric("losses", "COUNT", float(losses), float(losses), total),
        ComputedMetric(
            "resolved_win_rate",
            "RATE",
            wins / total if total else None,
            float(wins),
            total,
            win_lower if total else None,
            win_upper if total else None,
        ),
        ComputedMetric(
            "resolved_loss_rate",
            "RATE",
            losses / total if total else None,
            float(losses),
            total,
        ),
        ComputedMetric("total_gross_plan_r", "R", sum(values) if values else None, None, total),
        ComputedMetric("average_gross_plan_r", "R", average, None, total),
        ComputedMetric("median_gross_plan_r", "R", median, None, total),
        ComputedMetric(
            "gross_plan_expectancy_r",
            "R",
            average,
            None,
            total,
            bootstrap[0] if bootstrap else None,
            bootstrap[1] if bootstrap else None,
            {"bootstrap_seed_version": BOOTSTRAP_SEED_VERSION, "samples": 2_000},
        ),
        ComputedMetric(
            "gross_plan_profit_factor",
            "RATE",
            positive / negative if negative else None,
            positive,
            total,
            details={"gross_loss_r": negative},
        ),
        ComputedMetric(
            "max_win_streak",
            "COUNT",
            float(_max_streak((item.terminal_status for item in eligible), "WIN")),
            None,
            total,
        ),
        ComputedMetric(
            "max_loss_streak",
            "COUNT",
            float(_max_streak((item.terminal_status for item in eligible), "LOSS")),
            None,
            total,
        ),
    )


def activation_metrics(
    observations: Sequence[MetricObservation],
    *,
    total_signals_observed: int,
) -> tuple[ComputedMetric, ...]:
    directional = len(observations)
    activated = sum(item.entry_activated for item in observations)
    not_activated = sum(
        classify_eligibility(item).status is EligibilityStatus.NOT_ACTIVATED
        for item in observations
    )
    complete = sum(item.data_quality == "COMPLETE" for item in observations)
    candles = [
        item.candles_until_entry
        for item in observations
        if item.entry_activated and item.candles_until_entry is not None
    ]
    return (
        ComputedMetric(
            "signals_observed",
            "COUNT",
            float(total_signals_observed),
            float(total_signals_observed),
            total_signals_observed,
        ),
        ComputedMetric(
            "directional_signals_evaluated",
            "COUNT",
            float(directional),
            float(directional),
            total_signals_observed,
        ),
        ComputedMetric(
            "entry_activated",
            "COUNT",
            float(activated),
            float(activated),
            directional,
        ),
        ComputedMetric(
            "entry_activation_rate",
            "RATE",
            activated / directional if directional else None,
            float(activated),
            directional,
        ),
        ComputedMetric(
            "entry_not_activated",
            "COUNT",
            float(not_activated),
            float(not_activated),
            directional,
        ),
        ComputedMetric(
            "complete_evidence_coverage",
            "RATE",
            complete / directional if directional else None,
            float(complete),
            directional,
        ),
        ComputedMetric(
            "average_candles_until_entry",
            "CANDLES",
            statistics.fmean(candles) if candles else None,
            None,
            len(candles),
        ),
        ComputedMetric(
            "median_candles_until_entry",
            "CANDLES",
            statistics.median(candles) if candles else None,
            None,
            len(candles),
        ),
    )


def activated_metrics(
    observations: Sequence[MetricObservation],
) -> tuple[ComputedMetric, ...]:
    decisions = [(item, classify_eligibility(item)) for item in observations]
    eligible = [
        item
        for item, decision in decisions
        if decision.status in {
            EligibilityStatus.ELIGIBLE_RESOLVED,
            EligibilityStatus.ELIGIBLE_ACTIVATED,
        }
    ]
    wins = sum(item.terminal_status == "WIN" for item in eligible)
    losses = sum(item.terminal_status == "LOSS" for item in eligible)
    expired = sum(item.terminal_status == "EXPIRED" for item in eligible)
    resolved = wins + losses
    total = len(eligible)
    return (
        ComputedMetric("activated_wins", "COUNT", float(wins), float(wins), total),
        ComputedMetric("activated_losses", "COUNT", float(losses), float(losses), total),
        ComputedMetric(
            "activated_expired",
            "COUNT",
            float(expired),
            float(expired),
            total,
            details={"r_assigned": False, "reason": "NO_DEMONSTRATED_EXIT_FILL"},
        ),
        ComputedMetric(
            "resolved_outcome_rate_on_activated",
            "RATE",
            resolved / total if total else None,
            float(resolved),
            total,
        ),
    )
