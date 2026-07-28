from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from trading_signals.dashboard.contracts.metrics import EligibilityStatus
from trading_signals.dashboard.metrics.engine import (
    MetricObservation,
    activated_metrics,
    bootstrap_expectancy_interval,
    classify_eligibility,
    gross_plan_r,
    resolved_metrics,
    sample_label,
    wilson_interval,
)
from trading_signals.dashboard.metrics.policy import (
    frozen_policy_checksum,
    frozen_policy_specification,
)


def _observation(**overrides: object) -> MetricObservation:
    values: dict[str, object] = {
        "outcome_id": "outcome-1",
        "signal_projection_key": "signal-1",
        "symbol": "BTCUSDT",
        "direction": "long",
        "timeframe": "1h",
        "setup": "MAIN_SIGNAL",
        "strategy_version": "v1",
        "policy_version": "closed-bars-entry-touch-v1",
        "engine_version": "canonical-outcomes.v1",
        "market_data_fingerprint": "a" * 64,
        "data_quality": "COMPLETE",
        "terminal_status": "WIN",
        "entry_timestamp": datetime(2026, 7, 1, tzinfo=UTC),
        "entry_price": 100.0,
        "stop_price": 95.0,
        "target_price": 110.0,
        "entry_activated": True,
        "entry_activated_at": None,
        "entry_activation_candle_open": datetime(2026, 7, 1, 1, tzinfo=UTC),
        "candles_until_entry": 1,
        "candles_after_entry": 2,
        "ambiguity_reason": None,
    }
    values.update(overrides)
    return MetricObservation(**values)


def test_frozen_policy_checksum_is_stable() -> None:
    assert (
        frozen_policy_checksum()
        == "8a36d59b1beca1fe0463399f83aa035ce6a488ea4b062592e35a2f6d22b0897f"
    )
    specification = frozen_policy_specification()
    assert specification["target_rule"] == (
        "fixed_single_risk_plan_take_profit_not_tracker_tp1"
    )
    assert "tp2" not in str(specification["target_rule"]).lower()


def test_long_and_short_plan_r_and_loss_convention() -> None:
    assert gross_plan_r(_observation()) == 2.0
    short = _observation(
        outcome_id="short",
        direction="short",
        entry_price=100.0,
        stop_price=102.0,
        target_price=94.0,
    )
    assert gross_plan_r(short) == 3.0
    loss = replace(_observation(), outcome_id="loss", terminal_status="LOSS")
    assert gross_plan_r(loss) == -1.0


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"entry_activated": False, "terminal_status": "EXPIRED"}, "NOT_ACTIVATED"),
        ({"entry_activated": True, "terminal_status": "EXPIRED"}, "ELIGIBLE_ACTIVATED"),
        ({"terminal_status": "AMBIGUOUS"}, "EXCLUDED_AMBIGUOUS"),
        ({"terminal_status": "NO_MARKET_DATA", "data_quality": "GAP"}, "EXCLUDED_NO_MARKET_DATA"),
        ({"data_quality": "CONFLICT"}, "EXCLUDED_CONFLICTING_DATA"),
        ({"strategy_version": None}, "EXCLUDED_IDENTITY"),
        ({"policy_version": "other"}, "EXCLUDED_POLICY_MISMATCH"),
        ({"stop_price": 101.0}, "EXCLUDED_INVALID_LEVELS"),
        ({"data_quality": "NON_CANONICAL"}, "EXCLUDED_NON_CANONICAL"),
    ],
)
def test_eligibility_reasoned_exclusions(
    overrides: dict[str, object],
    expected: str,
) -> None:
    assert classify_eligibility(_observation(**overrides)).status.value == expected


def test_expired_activated_never_receives_invented_r() -> None:
    expired = _observation(terminal_status="EXPIRED")
    with pytest.raises(ValueError, match="OUTCOME_NOT_RESOLVED_ELIGIBLE"):
        gross_plan_r(expired)
    metrics = {item.name: item for item in activated_metrics((expired,))}
    assert metrics["activated_expired"].value == 1.0
    assert metrics["activated_expired"].details == {
        "r_assigned": False,
        "reason": "NO_DEMONSTRATED_EXIT_FILL",
    }
    assert "expectancy" not in metrics


def test_resolved_metrics_denominators_intervals_and_streaks() -> None:
    rows = (
        _observation(outcome_id="one", entry_timestamp=datetime(2026, 7, 1, tzinfo=UTC)),
        _observation(
            outcome_id="two",
            terminal_status="LOSS",
            entry_timestamp=datetime(2026, 7, 2, tzinfo=UTC),
        ),
        _observation(
            outcome_id="three",
            terminal_status="LOSS",
            entry_timestamp=datetime(2026, 7, 3, tzinfo=UTC),
        ),
    )
    metrics = {
        item.name: item
        for item in resolved_metrics(rows, cohort_fingerprint="b" * 64)
    }
    assert metrics["wins"].value == 1
    assert metrics["losses"].value == 2
    assert metrics["resolved_win_rate"].value == pytest.approx(1 / 3)
    assert metrics["total_gross_plan_r"].value == 0
    assert metrics["average_gross_plan_r"].value == 0
    assert metrics["median_gross_plan_r"].value == -1
    assert metrics["gross_plan_profit_factor"].value == 1
    assert metrics["max_win_streak"].value == 1
    assert metrics["max_loss_streak"].value == 2
    assert metrics["resolved_win_rate"].denominator == 3
    assert metrics["resolved_win_rate"].confidence_lower is not None
    assert metrics["resolved_win_rate"].confidence_upper is not None


def test_wilson_and_bootstrap_are_deterministic() -> None:
    lower, upper = wilson_interval(51, 237)
    assert 0 < lower < 51 / 237 < upper < 1
    first = bootstrap_expectancy_interval(
        (-1.0, -1.0, 2.0, 2.0),
        cohort_fingerprint="c" * 64,
    )
    second = bootstrap_expectancy_interval(
        (-1.0, -1.0, 2.0, 2.0),
        cohort_fingerprint="c" * 64,
    )
    assert first == second


@pytest.mark.parametrize(
    ("size", "expected"),
    [(0, "ANECDOTAL"), (19, "ANECDOTAL"), (20, "INSUFFICIENT"), (50, "PRELIMINARY"), (100, "ANALYZABLE")],
)
def test_small_sample_labels_are_explicit(size: int, expected: str) -> None:
    assert sample_label(size).value == expected
