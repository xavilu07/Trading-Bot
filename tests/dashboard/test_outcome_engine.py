from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from trading_signals.dashboard.contracts import (
    CollisionPolicy,
    OutcomeDataQuality,
    OutcomeStatus,
)
from trading_signals.dashboard.outcomes.engine import (
    MarketCandle,
    OutcomeSignal,
    evaluate_signal_outcome,
)
from trading_signals.dashboard.outcomes.projector import default_outcome_policy


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 7, 28, tzinfo=UTC) + timedelta(
        hours=hour,
        minutes=minute,
    )


def _signal(
    *,
    direction: str = "long",
    decision_at: datetime | None = None,
    projection_key: str = "projection-one",
    entry: float | None = 100,
    stop: float | None = None,
    target: float | None = None,
) -> OutcomeSignal:
    if stop is None:
        stop = 95 if direction == "long" else 105
    if target is None:
        target = 110 if direction == "long" else 90
    return OutcomeSignal(
        projection_key=projection_key,
        signal_id="sig-one",
        symbol="BTCUSDT",
        direction=direction,
        timeframe="1h",
        decision_at=decision_at or _dt(10, 15),
        entry_price=entry,
        stop_price=stop,
        target_price=target,
        strategy_version="v1",
        signal_policy_version="runtime-v1",
    )


def _candle(
    hour: int,
    *,
    open_price: float = 100,
    high: float = 104,
    low: float = 96,
    close: float = 101,
    closed: bool = True,
) -> MarketCandle:
    return MarketCandle(
        symbol="BTCUSDT",
        timeframe="1h",
        open_at=_dt(hour),
        close_at=_dt(hour) + timedelta(hours=1),
        open=open_price,
        high=high,
        low=low,
        close=close,
        closed=closed,
    )


def _evaluate(
    signal: OutcomeSignal,
    candles: list[MarketCandle],
    *,
    horizon: int = 2,
    collision: CollisionPolicy = CollisionPolicy.AMBIGUOUS,
    as_of: datetime | None = None,
    policy_version: str = "test-policy-v1",
):
    return evaluate_signal_outcome(
        signal,
        candles,
        policy=default_outcome_policy(
            horizon_candles=horizon,
            policy_version=policy_version,
            collision_policy=collision,
        ),
        as_of=as_of or _dt(15),
        computed_at=_dt(16),
    )


@pytest.mark.parametrize(
    ("direction", "candle", "expected"),
    [
        ("long", _candle(11, high=111, low=99, close=110), OutcomeStatus.WIN),
        ("long", _candle(11, high=101, low=94, close=95), OutcomeStatus.LOSS),
        (
            "short",
            _candle(11, high=101, low=89, close=90),
            OutcomeStatus.WIN,
        ),
        (
            "short",
            _candle(11, high=106, low=99, close=105),
            OutcomeStatus.LOSS,
        ),
    ],
)
def test_long_and_short_terminal_barriers(
    direction: str,
    candle: MarketCandle,
    expected: OutcomeStatus,
) -> None:
    result = _evaluate(_signal(direction=direction), [candle], horizon=1)
    assert result.terminal_status is expected
    assert result.candles_observed == 1


def test_expiration_occurs_exactly_after_unique_horizon_candles() -> None:
    candles = [_candle(hour) for hour in range(11, 15)]
    before = _evaluate(_signal(), candles[:3], horizon=4, as_of=_dt(14))
    complete = _evaluate(_signal(), candles, horizon=4, as_of=_dt(15))
    assert before.terminal_status is OutcomeStatus.OPEN
    assert complete.terminal_status is OutcomeStatus.EXPIRED
    assert complete.candles_observed == 4


def test_24_one_hour_bars_are_not_scheduler_cycles() -> None:
    candles = [_candle(11 + index) for index in range(24)]
    result = _evaluate(
        _signal(),
        candles,
        horizon=24,
        as_of=_dt(11) + timedelta(hours=25),
    )
    assert result.terminal_status is OutcomeStatus.EXPIRED
    assert result.evaluation_end - result.evaluation_start == timedelta(hours=24)


def test_pre_decision_candle_is_never_used() -> None:
    lookahead = _candle(10, high=120, low=90, close=110)
    valid = _candle(11)
    result = _evaluate(_signal(), [lookahead, valid], horizon=1, as_of=_dt(12))
    assert result.terminal_status is OutcomeStatus.EXPIRED
    assert result.evidence[0].open_at == _dt(11)


def test_open_candle_is_excluded() -> None:
    result = _evaluate(
        _signal(),
        [_candle(11, closed=False)],
        horizon=1,
        as_of=_dt(11, 30),
    )
    assert result.terminal_status is OutcomeStatus.OPEN
    assert result.candles_observed == 0


def test_same_candle_stop_and_target_is_ambiguous() -> None:
    result = _evaluate(
        _signal(),
        [_candle(11, high=111, low=94, close=102)],
        horizon=1,
    )
    assert result.terminal_status is OutcomeStatus.AMBIGUOUS
    assert result.first_stop_touch == _dt(12)
    assert result.first_target_touch == _dt(12)


@pytest.mark.parametrize(
    ("policy", "status"),
    [
        (CollisionPolicy.CONSERVATIVE_STOP_FIRST, OutcomeStatus.LOSS),
        (CollisionPolicy.OPTIMISTIC_TARGET_FIRST, OutcomeStatus.WIN),
    ],
)
def test_collision_alternatives_are_explicitly_non_canonical(
    policy: CollisionPolicy,
    status: OutcomeStatus,
) -> None:
    result = _evaluate(
        _signal(),
        [_candle(11, high=111, low=94, close=102)],
        horizon=1,
        collision=policy,
    )
    assert result.terminal_status is status
    assert result.data_quality is OutcomeDataQuality.NON_CANONICAL


def test_intrabar_entry_activation_and_barrier_order_is_ambiguous() -> None:
    result = _evaluate(
        _signal(),
        [_candle(11, open_price=103, high=111, low=99, close=105)],
        horizon=1,
    )
    assert result.terminal_status is OutcomeStatus.AMBIGUOUS
    assert result.ambiguity_reason == "ENTRY_AND_BARRIER_ORDER_UNKNOWN_WITHIN_CANDLE"


def test_entry_not_activated_expires_without_terminal_price() -> None:
    result = _evaluate(
        _signal(),
        [_candle(11, open_price=103, high=106, low=102, close=104)],
        horizon=1,
    )
    assert result.terminal_status is OutcomeStatus.EXPIRED
    assert result.terminal_price is None
    assert result.ambiguity_reason == "ENTRY_NOT_ACTIVATED_WITHIN_HORIZON"


def test_gap_beyond_target_after_activation_uses_demonstrable_open() -> None:
    first = _candle(11, high=104, low=96, close=102)
    gap = _candle(12, open_price=112, high=114, low=111, close=113)
    result = _evaluate(_signal(), [first, gap], horizon=2)
    assert result.terminal_status is OutcomeStatus.WIN
    assert result.terminal_timestamp == _dt(12)
    assert result.terminal_price == 112
    assert result.first_target_touch == _dt(12)


def test_missing_temporal_bar_is_no_market_data() -> None:
    result = _evaluate(
        _signal(),
        [_candle(12)],
        horizon=2,
        as_of=_dt(14),
    )
    assert result.terminal_status is OutcomeStatus.NO_MARKET_DATA
    assert result.data_quality is OutcomeDataQuality.GAP


def test_identical_duplicate_candle_is_processed_once() -> None:
    candle = _candle(11)
    result = _evaluate(_signal(), [candle, candle], horizon=1)
    assert result.terminal_status is OutcomeStatus.EXPIRED
    assert result.candles_observed == 1


def test_conflicting_duplicate_candle_is_not_forced_to_win_or_loss() -> None:
    result = _evaluate(
        _signal(),
        [_candle(11), _candle(11, close=102)],
        horizon=1,
    )
    assert result.terminal_status is OutcomeStatus.NO_MARKET_DATA
    assert result.data_quality is OutcomeDataQuality.CONFLICT


def test_out_of_order_candles_are_invalid() -> None:
    result = _evaluate(_signal(), [_candle(12), _candle(11)], horizon=2)
    assert result.terminal_status is OutcomeStatus.INVALID
    assert result.ambiguity_reason == "CANDLES_OUT_OF_ORDER"


def test_naive_candle_timestamp_is_invalid_not_assumed_utc() -> None:
    candle = _candle(11)
    naive = MarketCandle(
        symbol=candle.symbol,
        timeframe=candle.timeframe,
        open_at=candle.open_at.replace(tzinfo=None),
        close_at=candle.close_at.replace(tzinfo=None),
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
    )
    result = _evaluate(_signal(), [naive], horizon=1)
    assert result.terminal_status is OutcomeStatus.INVALID
    assert result.ambiguity_reason == "CANDLE_TIMESTAMP_NOT_UTC"


@pytest.mark.parametrize(
    ("signal", "reason"),
    [
        (_signal(entry=100, stop=101, target=110), "INVALID_SIGNAL_LEVELS"),
        (_signal(decision_at=_dt(20)), "SIGNAL_IN_FUTURE"),
        (_signal(projection_key=""), "SIGNAL_IDENTITY_MISSING"),
    ],
)
def test_invalid_signal_inputs_are_structured(
    signal: OutcomeSignal,
    reason: str,
) -> None:
    result = _evaluate(signal, [], horizon=1, as_of=_dt(15))
    assert result.terminal_status is OutcomeStatus.INVALID
    assert result.ambiguity_reason == reason


def test_wrong_policy_timeframe_is_invalid() -> None:
    policy = default_outcome_policy(timeframe="4h", horizon_candles=1)
    result = evaluate_signal_outcome(
        _signal(),
        [],
        policy=policy,
        as_of=_dt(15),
        computed_at=_dt(16),
    )
    assert result.terminal_status is OutcomeStatus.INVALID
    assert result.ambiguity_reason == "POLICY_TIMEFRAME_MISMATCH"


def test_fingerprints_change_with_market_evidence_and_policy_versions_do_not_collide() -> None:
    first = _evaluate(_signal(), [_candle(11)], horizon=1, policy_version="v1")
    changed = _evaluate(
        _signal(),
        [_candle(11, close=102)],
        horizon=1,
        policy_version="v1",
    )
    policy_changed = _evaluate(
        _signal(),
        [_candle(11)],
        horizon=1,
        policy_version="v2",
    )
    assert first.source_fingerprint != changed.source_fingerprint
    assert first.policy_version != policy_changed.policy_version
    assert first.source_fingerprint == policy_changed.source_fingerprint


def test_all_serialized_timestamps_are_utc() -> None:
    result = _evaluate(_signal(), [_candle(11)], horizon=1)
    payload = result.model_dump(mode="json")
    assert payload["entry_timestamp"].endswith("Z")
    assert payload["evaluation_start"].endswith("Z")
    assert payload["evidence"][0]["open_at"].endswith("Z")
