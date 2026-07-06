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


def test_determine_htf_alignment_matches_quant_research_logic() -> None:
    assert determine_htf_alignment(direction="long", higher_trend="bullish") == "aligned"
    assert determine_htf_alignment(direction="short", higher_trend="bearish") == "aligned"
    assert determine_htf_alignment(direction="long", higher_trend="bearish") == "against"
    assert determine_htf_alignment(direction="short", higher_trend="bullish") == "against"
    assert determine_htf_alignment(direction="long", higher_trend="sideways") == "unknown"


def test_flag_false_does_nothing() -> None:
    evaluation = Evaluation()
    signal = Signal()

    status, result = apply_strategy_v2_1_htf_alignment_filter(
        evaluation=evaluation,
        signal=signal,
        status="valid",
        enabled=False,
        mode="hard_block",
        direction="long",
        higher_trend="bearish",
    )

    assert status == "valid"
    assert result.would_block is True
    assert result.blocked is False
    assert evaluation.decision == "long"
    assert signal.decision == "long"
    assert evaluation.decision_trace == []
    assert evaluation.rejection_reasons == []


def test_shadow_mode_does_not_block_against_htf() -> None:
    evaluation = Evaluation()
    signal = Signal()

    status, result = apply_strategy_v2_1_htf_alignment_filter(
        evaluation=evaluation,
        signal=signal,
        status="valid",
        enabled=True,
        mode="shadow",
        direction="long",
        higher_trend="bearish",
    )

    assert status == "valid"
    assert result.htf_alignment == "against"
    assert result.would_block is True
    assert result.blocked is False
    assert evaluation.decision == "long"
    assert signal.status == "valid"
    assert "strategy_v2_1_htf_alignment=against" in evaluation.decision_trace
    assert "strategy_v2_1_would_block=true" in evaluation.decision_trace
    assert "strategy_v2_1_mode=shadow" in evaluation.decision_trace


def test_hard_block_blocks_against_htf() -> None:
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
    assert result.blocked is True
    assert evaluation.decision == "no_trade"
    assert signal.decision == "no_trade"
    assert signal.status == "rejected"
    assert BLOCK_REASON in evaluation.rejection_reasons
    assert BLOCK_REASON in evaluation.failed_filters


def test_hard_block_does_not_block_aligned_or_unknown() -> None:
    for higher_trend, expected_alignment in [("bullish", "aligned"), ("sideways", "unknown")]:
        evaluation = Evaluation()
        signal = Signal()

        status, result = apply_strategy_v2_1_htf_alignment_filter(
            evaluation=evaluation,
            signal=signal,
            status="valid",
            enabled=True,
            mode="hard_block",
            direction="long",
            higher_trend=higher_trend,
        )

        assert status == "valid"
        assert result.htf_alignment == expected_alignment
        assert result.blocked is False
        assert evaluation.decision == "long"
        assert signal.status == "valid"
        assert BLOCK_REASON not in evaluation.rejection_reasons


def test_result_payload_contains_log_fields() -> None:
    result = evaluate_strategy_v2_1_htf_alignment_filter(
        enabled=True,
        mode="shadow",
        direction="short",
        higher_trend="bullish",
    )

    payload = result.to_dict()

    assert payload["strategy_v2_1_htf_alignment"] == "against"
    assert payload["strategy_v2_1_would_block"] is True
    assert payload["strategy_v2_1_mode"] == "shadow"
    assert payload["reason"] == BLOCK_REASON
