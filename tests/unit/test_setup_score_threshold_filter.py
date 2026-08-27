from __future__ import annotations

from dataclasses import dataclass, field

from trading_signals.app.settings import Settings
from trading_signals.application.use_cases.analyze_symbol import analyze_symbol
from trading_signals.domain.strategies.liquidity_sweep_mtf_v1 import LiquiditySweepMTFV1
from trading_signals.application.use_cases.setup_score_threshold_filter import (
    BLOCK_REASON,
    DEFAULT_MIN_SCORE,
    SHADOW_MARKER,
    apply_setup_score_threshold_filter,
    evaluate_setup_score_threshold_filter,
)
from tests.fixtures.market_data import FakeMarketDataClient, generate_trend_dataset


@dataclass
class Evaluation:
    decision: str = "long"
    setup_score: float = 72.0
    decision_trace: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    failed_filters: list[str] = field(default_factory=list)
    passed_filters: list[str] = field(default_factory=list)


@dataclass
class Signal:
    decision: str = "long"
    status: str = "valid"


def test_flag_false_never_blocks() -> None:
    result = evaluate_setup_score_threshold_filter(
        enabled=False, mode="hard_block", min_score=90, setup_score=50.0, current_decision="long"
    )

    assert result["would_block"] is False
    assert result["blocked"] is False
    assert result["reason"] == "disabled"


def test_shadow_records_the_verdict_without_blocking() -> None:
    result = evaluate_setup_score_threshold_filter(
        enabled=True, mode="shadow", min_score=90, setup_score=72.0, current_decision="long"
    )

    assert result["would_block"] is True
    assert result["blocked"] is False
    assert result["reason"] == "shadow_would_block"
    assert result["rejection_reason"] is None


def test_hard_block_blocks_below_the_threshold() -> None:
    result = evaluate_setup_score_threshold_filter(
        enabled=True, mode="hard_block", min_score=90, setup_score=89.99, current_decision="short"
    )

    assert result["blocked"] is True
    assert result["rejection_reason"] == BLOCK_REASON


def test_a_score_exactly_at_the_threshold_passes() -> None:
    """score>=90 is the measured population, so 90.0 itself must survive."""
    result = evaluate_setup_score_threshold_filter(
        enabled=True, mode="hard_block", min_score=90, setup_score=90.0, current_decision="long"
    )

    assert result["would_block"] is False
    assert result["reason"] == "score_above_threshold"


def test_non_candidates_are_left_alone() -> None:
    """A setup the strategy already declined is not this filter's counterfactual."""
    result = evaluate_setup_score_threshold_filter(
        enabled=True, mode="hard_block", min_score=90, setup_score=20.0, current_decision="no_trade"
    )

    assert result["would_block"] is False
    assert result["reason"] == "no_candidate"


def test_invalid_mode_fails_safe_as_shadow() -> None:
    result = evaluate_setup_score_threshold_filter(
        enabled=True, mode="enforce", min_score=90, setup_score=50.0, current_decision="long"
    )

    assert result["mode"] == "shadow"
    assert result["blocked"] is False
    assert result["would_block"] is True


def test_an_unusable_threshold_falls_back_to_the_measured_one() -> None:
    for bad in ("", None, "abc", -1, 101):
        result = evaluate_setup_score_threshold_filter(
            enabled=True, mode="shadow", min_score=bad, setup_score=50.0, current_decision="long"
        )
        assert result["min_score"] == DEFAULT_MIN_SCORE


def test_a_missing_score_never_blocks() -> None:
    result = evaluate_setup_score_threshold_filter(
        enabled=True, mode="hard_block", min_score=90, setup_score=None, current_decision="long"
    )

    assert result["would_block"] is False
    assert result["reason"] == "score_unavailable"


def test_threshold_is_configurable_between_85_and_95() -> None:
    below_85 = evaluate_setup_score_threshold_filter(
        enabled=True, mode="shadow", min_score=85, setup_score=87.0, current_decision="long"
    )
    below_95 = evaluate_setup_score_threshold_filter(
        enabled=True, mode="shadow", min_score=95, setup_score=87.0, current_decision="long"
    )

    assert below_85["would_block"] is False
    assert below_95["would_block"] is True


def test_shadow_leaves_the_trade_untouched_but_marks_the_record() -> None:
    evaluation = Evaluation(setup_score=72.0)
    signal = Signal()

    status, result = apply_setup_score_threshold_filter(
        evaluation=evaluation, signal=signal, status="valid", enabled=True, mode="shadow", min_score=90
    )

    assert status == "valid"
    assert evaluation.decision == "long"
    assert signal.status == "valid"
    assert result["blocked"] is False
    assert SHADOW_MARKER in evaluation.failed_filters
    assert BLOCK_REASON not in evaluation.failed_filters
    assert BLOCK_REASON not in evaluation.rejection_reasons
    assert "setup_score_threshold_filter_would_block=true" in evaluation.decision_trace
    assert "setup_score_threshold_filter_min_score=90" in evaluation.decision_trace
    assert "setup_score_threshold_filter_mode=shadow" in evaluation.decision_trace


def test_hard_block_rejects_the_signal() -> None:
    evaluation = Evaluation(setup_score=72.0)
    signal = Signal()

    status, result = apply_setup_score_threshold_filter(
        evaluation=evaluation, signal=signal, status="valid", enabled=True, mode="hard_block", min_score=90
    )

    assert status == "rejected"
    assert result["blocked"] is True
    assert evaluation.decision == "no_trade"
    assert signal.decision == "no_trade"
    assert signal.status == "rejected"
    assert BLOCK_REASON in evaluation.rejection_reasons
    assert BLOCK_REASON in evaluation.failed_filters
    assert SHADOW_MARKER not in evaluation.failed_filters


def test_a_passing_score_leaves_no_marker_behind() -> None:
    evaluation = Evaluation(setup_score=93.0)
    signal = Signal()

    status, _ = apply_setup_score_threshold_filter(
        evaluation=evaluation, signal=signal, status="valid", enabled=True, mode="hard_block", min_score=90
    )

    assert status == "valid"
    assert evaluation.failed_filters == []
    assert "setup_score_threshold_filter_would_block=false" in evaluation.decision_trace


def test_applying_twice_does_not_duplicate_the_marker() -> None:
    evaluation = Evaluation(setup_score=72.0)
    signal = Signal()

    for _ in range(2):
        apply_setup_score_threshold_filter(
            evaluation=evaluation, signal=signal, status="valid", enabled=True, mode="shadow", min_score=90
        )

    assert evaluation.failed_filters.count(SHADOW_MARKER) == 1
    assert evaluation.decision_trace.count("setup_score_threshold_filter_mode=shadow") == 1


def _real_long_evaluation(tmp_path):
    """A genuine strategy evaluation, not a stand-in - the apply path mutates it."""
    settings = Settings(data_storage_path=tmp_path)
    dataset = generate_trend_dataset(direction="up")
    market_data = FakeMarketDataClient({
        ("BTCUSDT", "1h"): dataset,
        ("BTCUSDT", "4h"): dataset,
    })
    analysis = analyze_symbol(
        market_data=market_data, settings=settings, scan_run_id="run_test", symbol="BTCUSDT"
    )
    return LiquiditySweepMTFV1(settings).evaluate(analysis, "eval_test", analysis.entry_snapshot.created_at)


def test_a_real_signal_above_the_floor_passes_through_untouched(tmp_path) -> None:
    """The fixture setup scores 100, so the 90 floor must leave it exactly as it was."""
    evaluation = _real_long_evaluation(tmp_path)
    signal = Signal()
    assert evaluation.decision == "long"
    assert evaluation.setup_score >= 90.0
    failed_before = list(evaluation.failed_filters)

    status, result = apply_setup_score_threshold_filter(
        evaluation=evaluation, signal=signal, status="valid", enabled=True, mode="hard_block", min_score=90
    )

    assert status == "valid"
    assert evaluation.decision == "long"
    assert signal.decision == "long"
    assert result["reason"] == "score_above_threshold"
    assert evaluation.failed_filters == failed_before


def test_shadow_marks_a_real_signal_below_the_floor_without_changing_it(tmp_path) -> None:
    evaluation = _real_long_evaluation(tmp_path)
    evaluation.setup_score = 72.0
    signal = Signal()

    status, result = apply_setup_score_threshold_filter(
        evaluation=evaluation, signal=signal, status="valid", enabled=True, mode="shadow", min_score=90
    )

    assert status == "valid"
    assert evaluation.decision == "long"
    assert signal.decision == "long"
    assert result["reason"] == "shadow_would_block"
    assert SHADOW_MARKER in evaluation.failed_filters
    assert "setup_score_threshold_filter_would_block=true" in evaluation.decision_trace


def test_hard_block_would_have_refused_that_same_real_signal(tmp_path) -> None:
    evaluation = _real_long_evaluation(tmp_path)
    evaluation.setup_score = 72.0
    signal = Signal()

    status, _ = apply_setup_score_threshold_filter(
        evaluation=evaluation, signal=signal, status="valid", enabled=True, mode="hard_block", min_score=90
    )

    assert status == "rejected"
    assert evaluation.decision == "no_trade"
    assert signal.status == "rejected"
    assert BLOCK_REASON in evaluation.rejection_reasons
