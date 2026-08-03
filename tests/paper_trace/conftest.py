from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from trading_signals.paper_trace.contracts import (
    ProspectiveSignalIdentity,
    TargetRole,
    TraceCandle,
)
from trading_signals.paper_trace.policy import (
    DEFAULT_EXPIRY_POLICY_ID,
    DEFAULT_FILL_POLICY_ID,
    TRACE_MODEL_VERSION,
    trace_policy_checksum,
)
from trading_signals.paper_trace.sanitize import stable_hash


@pytest.fixture
def identity_factory():
    def factory(
        *,
        direction: str = "long",
        horizon: int = 24,
        signal_id: str = "sig-test-1",
        policy_version: str | None = None,
    ) -> ProspectiveSignalIdentity:
        digest = stable_hash({"fixture": signal_id}, namespace="fixture.v1")
        entry, stop, target = (
            (100.0, 95.0, 110.0)
            if direction == "long"
            else (100.0, 105.0, 90.0)
        )
        at = datetime(2026, 1, 1, 10, tzinfo=UTC)
        return ProspectiveSignalIdentity(
            signal_id=signal_id,
            signal_schema_version="paper.signal.identity.v1",
            created_at=at,
            decision_at=at,
            symbol="TESTUSDT",
            direction=direction,
            timeframe="1h",
            strategy_id="strategy",
            strategy_version="v1",
            strategy_commit="a" * 40,
            setup_id="setup",
            setup_version="v1",
            setup_parameters_hash=digest,
            policy_id="public-safety-policy",
            policy_version="v1",
            fill_policy_id=DEFAULT_FILL_POLICY_ID,
            fill_policy_version=policy_version or trace_policy_checksum(),
            expiry_policy_id=DEFAULT_EXPIRY_POLICY_ID,
            engine_version=TRACE_MODEL_VERSION,
            config_hash=digest,
            market_context_fingerprint=digest,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            target_role=TargetRole.FINAL_TARGET,
            target_index=2,
            horizon_candles=horizon,
            source_cycle_id="cycle-1",
            source_agent_decision_id=None,
            correlation_group_id=None,
        )

    return factory


@pytest.fixture
def candle_factory():
    base = datetime(2026, 1, 1, 10, tzinfo=UTC)

    def factory(
        index: int,
        *,
        open_price: float = 100.0,
        high: float = 102.0,
        low: float = 98.0,
        close: float = 101.0,
        closed: bool = True,
        symbol: str = "TESTUSDT",
        timeframe: str = "1h",
    ) -> TraceCandle:
        duration = timedelta(hours=4) if timeframe == "4h" else timedelta(hours=1)
        opened = base + duration * index
        return TraceCandle(
            symbol=symbol,
            timeframe=timeframe,
            open_at=opened,
            close_at=opened + duration,
            open_price=open_price,
            high_price=high,
            low_price=low,
            close_price=close,
            closed=closed,
        )

    return factory
