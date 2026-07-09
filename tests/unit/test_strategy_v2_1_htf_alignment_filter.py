from __future__ import annotations

from dataclasses import dataclass, field

from trading_signals.application.use_cases.strategy_v2_1_htf_alignment_filter import (
    BLOCK_REASON,
    apply_strategy_v2_1_htf_alignment_filter,
    determine_htf_alignment,
    evaluate_strategy_v2_1_htf_alignment_filter,
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


def test_flag_false_no_block() -> None:
    result = evaluate_strategy_v2_1_htf_alignment_filter(enabled=False, mode="hard_block", htf_alignment="against")

    assert result["blocked"] is False
    assert result["would_block"] is False
    assert result["rejection_reason"] is None


def test_shadow_no_block_but_would_block() -> None:
    result = evaluate_strategy_v2_1_htf_alignment_filter(enabled=True, mode="shadow", htf_alignment="against")

    assert result["blocked"] is False
    assert result["would_block"] is True
    assert result["reason"] == "shadow_would_block"


def test_hard_block_blocks_against() -> None:
    result = evaluate_strategy_v2_1_htf_alignment_filter(enabled=True, mode="hard_block", htf_alignment="against")

    assert result["blocked"] is True
    assert result["would_block"] is True
    assert result["rejection_reason"] == BLOCK_REASON


def test_hard_block_does_not_block_aligned() -> None:
    result = evaluate_strategy_v2_1_htf_alignment_filter(enabled=True, mode="hard_block", htf_alignment="aligned")

    assert result["blocked"] is False
    assert result["would_block"] is False


def test_unknown_or_none_never_blocks() -> None:
    for value in ("unknown", None):
        result = evaluate_strategy_v2_1_htf_alignment_filter(enabled=True, mode="hard_block", htf_alignment=value)
        assert result["blocked"] is False
        assert result["would_block"] is False


def test_invalid_mode_fails_safe_as_shadow() -> None:
    result = evaluate_strategy_v2_1_htf_alignment_filter(enabled=True, mode="invalid", htf_alignment="against")

    assert result["mode"] == "shadow"
    assert result["blocked"] is False
    assert result["would_block"] is True


def test_determine_htf_alignment() -> None:
    assert determine_htf_alignment(direction="long", higher_trend="bullish") == "aligned"
    assert determine_htf_alignment(direction="short", higher_trend="bearish") == "aligned"
    assert determine_htf_alignment(direction="long", higher_trend="bearish") == "against"
    assert determine_htf_alignment(direction="short", higher_trend="bullish") == "against"
    assert determine_htf_alignment(direction="long", higher_trend="sideways") == "unknown"


def test_minimal_integration_blocks_when_enabled() -> None:
    evaluation = Evaluation()
    signal = Signal()

    status, result = apply_strategy_v2_1_htf_alignment_filter(
        evaluation=evaluation,
        signal=signal,
        status="valid",
        enabled=True,
        mode="hard_block",
        direction="long",
        higher_trend="bearish",
    )

    assert status == "rejected"
    assert result["blocked"] is True
    assert BLOCK_REASON in evaluation.rejection_reasons
    assert signal.status == "rejected"
