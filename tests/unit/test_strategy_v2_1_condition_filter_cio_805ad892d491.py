from __future__ import annotations

from dataclasses import dataclass, field

from trading_signals.application.use_cases.strategy_v2_1_condition_filter_cio_805ad892d491 import (
    BLOCK_REASON,
    CONDITIONS,
    apply_strategy_v2_1_condition_filter_cio_805ad892d491,
    evaluate_strategy_v2_1_condition_filter_cio_805ad892d491,
)


@dataclass
class Evaluation:
    decision: str = "long"
    decision_trace: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    failed_filters: list[str] = field(default_factory=list)


@dataclass
class Signal:
    decision: str = "long"
    status: str = "valid"


MATCHING_CONTEXT = {"liquidity_distance_bucket": "2-4atr"}


def test_flag_false_no_block() -> None:
    result = evaluate_strategy_v2_1_condition_filter_cio_805ad892d491(enabled=False, mode="hard_block", context=MATCHING_CONTEXT)

    assert result["blocked"] is False
    assert result["would_block"] is False
    assert result["rejection_reason"] is None


def test_shadow_no_block_but_would_block() -> None:
    result = evaluate_strategy_v2_1_condition_filter_cio_805ad892d491(enabled=True, mode="shadow", context=MATCHING_CONTEXT)

    assert result["blocked"] is False
    assert result["would_block"] is True
    assert result["reason"] == "shadow_would_block"


def test_hard_block_blocks_when_all_conditions_match() -> None:
    result = evaluate_strategy_v2_1_condition_filter_cio_805ad892d491(enabled=True, mode="hard_block", context=MATCHING_CONTEXT)

    assert result["blocked"] is True
    assert result["would_block"] is True
    assert result["rejection_reason"] == BLOCK_REASON


def test_hard_block_does_not_block_when_a_condition_differs() -> None:
    context = dict(MATCHING_CONTEXT)
    context["liquidity_distance_bucket"] = "__no_match__"
    result = evaluate_strategy_v2_1_condition_filter_cio_805ad892d491(enabled=True, mode="hard_block", context=context)

    assert result["blocked"] is False
    assert result["would_block"] is False


def test_empty_context_never_blocks() -> None:
    result = evaluate_strategy_v2_1_condition_filter_cio_805ad892d491(enabled=True, mode="hard_block", context={})

    assert result["blocked"] is False
    assert result["would_block"] is False


def test_invalid_mode_fails_safe_as_shadow() -> None:
    result = evaluate_strategy_v2_1_condition_filter_cio_805ad892d491(enabled=True, mode="invalid", context=MATCHING_CONTEXT)

    assert result["mode"] == "shadow"
    assert result["blocked"] is False
    assert result["would_block"] is True


def test_conditions_match_the_proposal() -> None:
    assert CONDITIONS == [{"feature": "liquidity_distance_bucket", "operator": "==", "value": "2-4atr"}]


def test_minimal_integration_blocks_when_enabled() -> None:
    evaluation = Evaluation()
    signal = Signal()

    status, result = apply_strategy_v2_1_condition_filter_cio_805ad892d491(
        evaluation=evaluation,
        signal=signal,
        status="valid",
        enabled=True,
        mode="hard_block",
        context=MATCHING_CONTEXT,
    )

    assert status == "rejected"
    assert result["blocked"] is True
    assert BLOCK_REASON in evaluation.rejection_reasons
    assert signal.status == "rejected"
