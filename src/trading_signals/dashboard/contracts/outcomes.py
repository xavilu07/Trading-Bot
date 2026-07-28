from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import Field, field_validator, model_validator

from trading_signals.dashboard.contracts.models import ContractModel, UtcDatetime

OUTCOME_CONTRACT_VERSION = "dashboard.outcome.v1"
OUTCOME_ENGINE_VERSION = "canonical-outcomes.v1"


class OutcomeStatus(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    EXPIRED = "EXPIRED"
    OPEN = "OPEN"
    AMBIGUOUS = "AMBIGUOUS"
    INVALID = "INVALID"
    NO_MARKET_DATA = "NO_MARKET_DATA"
    NON_CANONICAL = "NON_CANONICAL"


class OutcomeDataQuality(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    GAP = "GAP"
    CONFLICT = "CONFLICT"
    NO_DATA = "NO_DATA"
    NON_CANONICAL = "NON_CANONICAL"


class EntryActivationPolicy(str, Enum):
    REQUIRE_POST_DECISION_TOUCH = "REQUIRE_POST_DECISION_TOUCH"
    ASSUME_FILLED_AT_DECISION = "ASSUME_FILLED_AT_DECISION"


class CollisionPolicy(str, Enum):
    AMBIGUOUS = "AMBIGUOUS"
    CONSERVATIVE_STOP_FIRST = "CONSERVATIVE_STOP_FIRST"
    OPTIMISTIC_TARGET_FIRST = "OPTIMISTIC_TARGET_FIRST"


class OutcomeSignalIdentity(ContractModel):
    projection_key: str = Field(max_length=128)
    signal_id: str | None = Field(default=None, max_length=128)
    symbol: str = Field(min_length=1, max_length=40)
    strategy_version: str | None = Field(default=None, max_length=100)
    signal_policy_version: str | None = Field(default=None, max_length=100)


class OutcomeEvaluationPolicy(ContractModel):
    policy_version: str = Field(min_length=1, max_length=100)
    engine_version: str = OUTCOME_ENGINE_VERSION
    timeframe: str = Field(min_length=1, max_length=10)
    horizon_candles: int = Field(ge=1, le=10_000)
    entry_activation_policy: EntryActivationPolicy = (
        EntryActivationPolicy.REQUIRE_POST_DECISION_TOUCH
    )
    collision_policy: CollisionPolicy = CollisionPolicy.AMBIGUOUS
    require_contiguous_candles: bool = True
    closed_candles_only: bool = True


class OutcomeMarketSource(ContractModel):
    logical_source_name: str = Field(min_length=1, max_length=100)
    source_format: str = Field(min_length=1, max_length=40)
    timeframe: str = Field(min_length=1, max_length=10)
    source_fingerprint: str = Field(min_length=64, max_length=64)
    coverage_start: UtcDatetime | None = None
    coverage_end: UtcDatetime | None = None
    candles_count: int = Field(ge=0)
    data_quality: OutcomeDataQuality
    source_reference: str = Field(min_length=1, max_length=160)

    @field_validator("source_reference")
    @classmethod
    def source_reference_is_safe(cls, value: str) -> str:
        if value.startswith("/") or "/root/" in value.lower():
            raise ValueError("market source reference must not expose an absolute path")
        return value


class OutcomeCandleEvidence(ContractModel):
    candle_index: int = Field(ge=1)
    open_at: UtcDatetime
    close_at: UtcDatetime
    open_price: float = Field(gt=0)
    high_price: float = Field(gt=0)
    low_price: float = Field(gt=0)
    close_price: float = Field(gt=0)
    entry_touched: bool
    stop_touched: bool
    target_touched: bool

    @model_validator(mode="after")
    def valid_ohlc(self) -> "OutcomeCandleEvidence":
        if self.low_price > min(self.open_price, self.close_price):
            raise ValueError("low price is inconsistent with open/close")
        if self.high_price < max(self.open_price, self.close_price):
            raise ValueError("high price is inconsistent with open/close")
        if self.low_price > self.high_price:
            raise ValueError("low price exceeds high price")
        if self.close_at <= self.open_at:
            raise ValueError("candle close must be after candle open")
        return self


class SignalOutcome(ContractModel):
    contract_version: str = OUTCOME_CONTRACT_VERSION
    identity: OutcomeSignalIdentity
    policy: OutcomeEvaluationPolicy
    market_source: OutcomeMarketSource
    direction: str
    timeframe: str
    entry_timestamp: UtcDatetime
    evaluation_start: UtcDatetime | None = None
    evaluation_end: UtcDatetime | None = None
    entry_price: float | None = Field(default=None, gt=0)
    stop_price: float | None = Field(default=None, gt=0)
    target_price: float | None = Field(default=None, gt=0)
    candles_expected: int = Field(ge=1)
    candles_observed: int = Field(ge=0)
    first_stop_touch: UtcDatetime | None = None
    first_target_touch: UtcDatetime | None = None
    terminal_status: OutcomeStatus
    terminal_timestamp: UtcDatetime | None = None
    terminal_price: float | None = Field(default=None, gt=0)
    ambiguity_reason: str | None = Field(default=None, max_length=500)
    data_quality: OutcomeDataQuality
    policy_version: str
    engine_version: str
    source_fingerprint: str = Field(min_length=64, max_length=64)
    computed_at: UtcDatetime
    evidence: tuple[OutcomeCandleEvidence, ...] = ()

    @field_validator("direction")
    @classmethod
    def valid_direction(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"long", "short"}:
            raise ValueError("direction must be long or short")
        return normalized

    @field_validator("computed_at")
    @classmethod
    def computed_at_is_utc(cls, value: datetime) -> datetime:
        return value
