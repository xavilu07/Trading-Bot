from __future__ import annotations

from enum import StrEnum


class Trend(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class MarketStructure(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    RANGE = "range"


class LiquiditySweep(StrEnum):
    BULLISH = "bullish_sweep"
    BEARISH = "bearish_sweep"
    NONE = "none"


class SignalDecision(StrEnum):
    LONG = "long"
    SHORT = "short"
    NO_TRADE = "no_trade"


class SignalStatus(StrEnum):
    PENDING = "pending"
    VALID = "valid"
    REJECTED = "rejected"
    PUBLISHED = "published"
    FAILED = "failed"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"

