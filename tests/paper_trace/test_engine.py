from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from trading_signals.paper_trace.contracts import PaperPositionState, ReceiptEventType
from trading_signals.paper_trace.engine import TraceEngineError, advance_trace, start_trace


def _started(identity):
    return list(start_trace(identity, accepted=True, observed_at=identity.decision_at).receipts)


def _advance(identity, receipts, candle):
    result = advance_trace(identity, receipts, candle, observed_at=candle.close_at)
    receipts.extend(result.receipts)
    return result


@pytest.mark.parametrize(
    ("direction", "barrier", "expected_event", "expected_state"),
    [
        ("long", "target", ReceiptEventType.TARGET_TOUCHED, PaperPositionState.CLOSED_WIN),
        ("long", "stop", ReceiptEventType.STOP_TOUCHED, PaperPositionState.CLOSED_LOSS),
        ("short", "target", ReceiptEventType.TARGET_TOUCHED, PaperPositionState.CLOSED_WIN),
        ("short", "stop", ReceiptEventType.STOP_TOUCHED, PaperPositionState.CLOSED_LOSS),
    ],
)
def test_long_and_short_barrier_results(
    identity_factory,
    candle_factory,
    direction,
    barrier,
    expected_event,
    expected_state,
) -> None:
    identity = identity_factory(direction=direction)
    receipts = _started(identity)
    _advance(identity, receipts, candle_factory(0))
    if direction == "long" and barrier == "target":
        terminal = candle_factory(1, open_price=101, high=111, low=99, close=109)
    elif direction == "long":
        terminal = candle_factory(1, open_price=99, high=101, low=94, close=96)
    elif barrier == "target":
        terminal = candle_factory(1, open_price=99, high=101, low=89, close=91)
    else:
        terminal = candle_factory(1, open_price=101, high=106, low=99, close=104)
    result = _advance(identity, receipts, terminal)
    assert expected_event in {item.event_type for item in result.receipts}
    assert result.state.position is expected_state


def test_same_bar_touches_stop_and_target_is_ambiguous(identity_factory, candle_factory) -> None:
    identity = identity_factory()
    receipts = _started(identity)
    _advance(identity, receipts, candle_factory(0))
    result = _advance(
        identity,
        receipts,
        candle_factory(1, open_price=100, high=111, low=94, close=100),
    )
    assert result.state.position is PaperPositionState.AMBIGUOUS
    assert result.state.trace_blocked_reason is None
    assert ReceiptEventType.EXIT_AMBIGUOUS in {item.event_type for item in result.receipts}


def test_entry_and_barrier_without_intrabar_order_is_ambiguous(identity_factory, candle_factory) -> None:
    identity = identity_factory()
    receipts = _started(identity)
    result = _advance(
        identity,
        receipts,
        candle_factory(0, open_price=99, high=101, low=94, close=100),
    )
    assert result.state.position is PaperPositionState.NONE
    assert result.state.trace_blocked_reason == "ENTRY_AND_BARRIER_ORDER_UNKNOWN"
    assert ReceiptEventType.SIMULATED_FILL_CREATED not in {
        item.event_type for item in result.receipts
    }


def test_simulated_fill_is_separate_and_has_no_quantity(identity_factory, candle_factory) -> None:
    identity = identity_factory()
    receipts = _started(identity)
    result = _advance(identity, receipts, candle_factory(0))
    events = [item.event_type for item in result.receipts]
    assert events.index(ReceiptEventType.ENTRY_TOUCHED) < events.index(
        ReceiptEventType.SIMULATED_FILL_CREATED
    ) < events.index(ReceiptEventType.PAPER_POSITION_OPENED)
    fill = next(
        item
        for item in result.receipts
        if item.event_type is ReceiptEventType.SIMULATED_FILL_CREATED
    )
    assert fill.quantity is None
    assert fill.price == identity.entry_price
    assert "fill_is_simulated" in fill.payload_json


def test_closed_candle_is_required_and_prior_candle_is_ignored(identity_factory, candle_factory) -> None:
    identity = identity_factory()
    receipts = _started(identity)
    open_candle = candle_factory(0, closed=False)
    open_result = advance_trace(
        identity,
        receipts,
        open_candle,
        observed_at=open_candle.open_at + timedelta(minutes=30),
    )
    assert open_result.ignored_reason == "CANDLE_NOT_CLOSED"
    prior = candle_factory(-1)
    prior_result = advance_trace(identity, receipts, prior, observed_at=prior.close_at)
    assert prior_result.ignored_reason == "CANDLE_BEFORE_EVALUATION_START"


def test_duplicate_candle_is_idempotent_and_conflicting_ohlc_blocks(
    identity_factory,
    candle_factory,
) -> None:
    identity = identity_factory()
    receipts = _started(identity)
    candle = candle_factory(0, open_price=99, high=99.5, low=98, close=99)
    _advance(identity, receipts, candle)
    duplicate = advance_trace(identity, receipts, candle, observed_at=candle.close_at)
    assert duplicate.receipts == ()
    assert duplicate.ignored_reason == "CANDLE_ALREADY_PROCESSED"
    conflict = candle_factory(0, open_price=99, high=99.7, low=98, close=99)
    result = _advance(identity, receipts, conflict)
    assert result.state.position is PaperPositionState.NONE
    assert result.state.trace_blocked_reason == "SAME_CANDLE_DIFFERENT_OHLC"
    assert result.receipts[-1].event_type is ReceiptEventType.MARKET_DATA_CONFLICT


def test_gap_blocks_trace_and_entry_gap_never_fills(identity_factory, candle_factory) -> None:
    identity = identity_factory()
    receipts = _started(identity)
    _advance(
        identity,
        receipts,
        candle_factory(0, open_price=99, high=99.5, low=98, close=99),
    )
    gap = candle_factory(2, open_price=101, high=102, low=101, close=101.5)
    result = _advance(identity, receipts, gap)
    assert result.state.position is PaperPositionState.NONE
    assert result.state.trace_blocked_reason == "NON_CONTIGUOUS_CLOSED_CANDLES"
    assert result.receipts[-1].event_type is ReceiptEventType.MARKET_DATA_GAP


def test_entry_gap_cross_without_price_is_ambiguous(identity_factory, candle_factory) -> None:
    identity = identity_factory()
    receipts = _started(identity)
    _advance(
        identity,
        receipts,
        candle_factory(0, open_price=99, high=99.5, low=98, close=99),
    )
    result = _advance(
        identity,
        receipts,
        candle_factory(1, open_price=101, high=102, low=101, close=101.5),
    )
    assert result.state.position is PaperPositionState.NONE
    assert result.state.trace_blocked_reason == "ENTRY_GAP_CROSS_WITHOUT_EXECUTABLE_PRICE"
    assert ReceiptEventType.SIMULATED_FILL_CREATED not in {
        item.event_type for item in result.receipts
    }


def test_signal_expires_only_after_real_unique_closed_candles(identity_factory, candle_factory) -> None:
    identity = identity_factory(horizon=24)
    receipts = _started(identity)
    for index in range(24):
        result = _advance(
            identity,
            receipts,
            candle_factory(index, open_price=99, high=99.5, low=98, close=99),
        )
        if index < 23:
            assert ReceiptEventType.SIGNAL_EXPIRED_NOT_ACTIVATED not in {
                item.event_type for item in result.receipts
            }
    assert result.state.order.value == "EXPIRED"
    assert result.state.candles_before_entry == 24


def test_position_expiry_has_no_r_or_terminal_price(identity_factory, candle_factory) -> None:
    identity = identity_factory(horizon=2)
    receipts = _started(identity)
    _advance(identity, receipts, candle_factory(0))
    _advance(identity, receipts, candle_factory(1))
    result = _advance(identity, receipts, candle_factory(2))
    unresolved = next(
        item
        for item in result.receipts
        if item.event_type is ReceiptEventType.POSITION_EXPIRED_UNRESOLVED
    )
    assert unresolved.price is None
    assert '"gross_r":null' in unresolved.payload_json
    assert result.state.position is PaperPositionState.EXPIRED_UNRESOLVED


def test_gap_exit_uses_observed_open_as_simulated_price(identity_factory, candle_factory) -> None:
    identity = identity_factory()
    receipts = _started(identity)
    _advance(identity, receipts, candle_factory(0))
    result = _advance(
        identity,
        receipts,
        candle_factory(1, open_price=93, high=94, low=92, close=93),
    )
    close = next(
        item
        for item in result.receipts
        if item.event_type is ReceiptEventType.PAPER_POSITION_CLOSED
    )
    assert close.price == 93
    assert result.state.position is PaperPositionState.CLOSED_LOSS


def test_policy_or_timeframe_mismatch_fails(identity_factory, candle_factory) -> None:
    with pytest.raises(TraceEngineError, match="FILL_POLICY_CHECKSUM_MISMATCH"):
        start_trace(
            identity_factory(policy_version="0" * 64),
            accepted=True,
            observed_at=identity_factory().decision_at,
        )
    identity = identity_factory()
    receipts = _started(identity)
    with pytest.raises(TraceEngineError, match="CANDLE_TIMEFRAME_MISMATCH"):
        advance_trace(
            identity,
            receipts,
            candle_factory(0, timeframe="4h"),
            observed_at=candle_factory(0, timeframe="4h").close_at,
        )


def test_future_signal_cannot_consume_earlier_candle(identity_factory, candle_factory) -> None:
    identity = replace(
        identity_factory(),
        decision_at=identity_factory().decision_at + timedelta(hours=2),
    )
    receipts = _started(identity)
    result = advance_trace(
        identity,
        receipts,
        candle_factory(0),
        observed_at=candle_factory(0).close_at,
    )
    assert result.ignored_reason == "CANDLE_BEFORE_EVALUATION_START"


def test_rejected_signal_never_creates_order_or_consumes_candles(
    identity_factory,
    candle_factory,
) -> None:
    identity = identity_factory()
    started = start_trace(identity, accepted=False, observed_at=identity.decision_at)
    assert ReceiptEventType.PAPER_ORDER_CREATED not in {
        item.event_type for item in started.receipts
    }
    result = advance_trace(
        identity,
        started.receipts,
        candle_factory(0),
        observed_at=candle_factory(0).close_at,
    )
    assert result.receipts == ()
    assert result.ignored_reason == "TRACE_TERMINAL"
