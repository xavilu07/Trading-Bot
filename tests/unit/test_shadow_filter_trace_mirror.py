from __future__ import annotations

from dataclasses import dataclass, field

from trading_signals.application.use_cases.run_market_scan import _mirror_shadow_filter_trace
from trading_signals.application.use_cases.strategy_v2_1_condition_filter_cio_805ad892d491 import (
    apply_strategy_v2_1_condition_filter_cio_805ad892d491,
)
from trading_signals.application.use_cases.setup_score_threshold_filter import (
    apply_setup_score_threshold_filter,
)
from trading_signals.application.use_cases.strategy_v2_1_htf_alignment_filter import (
    apply_strategy_v2_1_htf_alignment_filter,
)


@dataclass
class _Evaluation:
    decision: str = "long"
    setup_score: float = 72.0
    decision_trace: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    failed_filters: list[str] = field(default_factory=list)


@dataclass
class _Signal:
    decision: str = "long"
    status: str = "accepted"


@dataclass
class _SignalDecision:
    """Stands in for the object every persisted trade record is actually built from."""

    decision: str = "long"
    decision_trace: list[str] = field(default_factory=lambda: ["trend_1h=bullish"])


def test_shadow_condition_filter_verdict_reaches_the_persisted_decision_trace() -> None:
    evaluation = _Evaluation()
    signal_decision = _SignalDecision()

    apply_strategy_v2_1_condition_filter_cio_805ad892d491(
        evaluation=evaluation,
        signal=_Signal(),
        status="accepted",
        enabled=True,
        mode="shadow",
        context={"liquidity_distance_bucket": "2-4atr"},
    )
    _mirror_shadow_filter_trace(evaluation, signal_decision)

    assert "strategy_v2_1_condition_filter_cio_805ad892d491_would_block=true" in signal_decision.decision_trace
    # the record's own pre-existing trace must survive untouched
    assert signal_decision.decision_trace[0] == "trend_1h=bullish"


def test_shadow_htf_filter_verdict_reaches_the_persisted_decision_trace() -> None:
    evaluation = _Evaluation(decision="long")
    signal_decision = _SignalDecision()

    apply_strategy_v2_1_htf_alignment_filter(
        evaluation=evaluation,
        signal=_Signal(),
        status="accepted",
        enabled=True,
        mode="shadow",
        direction="long",
        higher_trend="bearish",
    )
    _mirror_shadow_filter_trace(evaluation, signal_decision)

    assert "strategy_v2_1_would_block=true" in signal_decision.decision_trace


def test_shadow_score_threshold_verdict_reaches_the_persisted_decision_trace() -> None:
    evaluation = _Evaluation()
    evaluation.setup_score = 72.0
    signal_decision = _SignalDecision()

    apply_setup_score_threshold_filter(
        evaluation=evaluation,
        signal=_Signal(),
        status="accepted",
        enabled=True,
        mode="shadow",
        min_score=90,
    )
    _mirror_shadow_filter_trace(evaluation, signal_decision)

    assert "setup_score_threshold_filter_would_block=true" in signal_decision.decision_trace
    assert "setup_score_threshold_filter_min_score=90" in signal_decision.decision_trace
    assert signal_decision.decision_trace[0] == "trend_1h=bullish"


def test_mirror_is_idempotent_and_ignores_unrelated_tokens() -> None:
    evaluation = _Evaluation(decision_trace=["strategy_v2_1_mode=shadow", "base_setup_score=85.0"])
    signal_decision = _SignalDecision()

    _mirror_shadow_filter_trace(evaluation, signal_decision)
    _mirror_shadow_filter_trace(evaluation, signal_decision)

    assert signal_decision.decision_trace.count("strategy_v2_1_mode=shadow") == 1
    assert "base_setup_score=85.0" not in signal_decision.decision_trace


def test_mirror_tolerates_a_decision_object_without_a_trace() -> None:
    _mirror_shadow_filter_trace(_Evaluation(decision_trace=["strategy_v2_1_mode=shadow"]), object())
