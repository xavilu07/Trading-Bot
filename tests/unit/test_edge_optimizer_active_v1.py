from __future__ import annotations

from types import SimpleNamespace

from trading_signals.application.use_cases.edge_optimizer_active_v1 import apply_edge_optimizer_active_v1


def test_flag_false_does_not_change_score() -> None:
    evaluation = _evaluation(80)
    decision = _decision(80)

    result = apply_edge_optimizer_active_v1(
        evaluation=evaluation,
        signal_decision=decision,
        edge_optimizer_shadow=_shadow(adjustment=10, confidence="HIGH"),
        enabled=False,
    )

    assert result.applied is False
    assert result.active_adjustment == 0
    assert evaluation.setup_score == 80
    assert decision.total_score == 80
    assert "edge_optimizer_active_disabled" in result.reasons


def test_flag_true_caps_positive_adjustment_to_two() -> None:
    evaluation = _evaluation(80)
    decision = _decision(80)

    result = apply_edge_optimizer_active_v1(
        evaluation=evaluation,
        signal_decision=decision,
        edge_optimizer_shadow=_shadow(adjustment=10, confidence="HIGH", matched_edges_count=3),
        enabled=True,
        max_adjustment=2.0,
    )

    assert result.applied is True
    assert result.active_adjustment == 2.0
    assert result.adjusted_score == 82.0
    assert evaluation.setup_score == 82.0
    assert decision.total_score == 82.0
    assert decision.module_scores["strategy"] == 82.0
    assert result.matched_edges_count == 3


def test_flag_true_caps_negative_adjustment_to_minus_two() -> None:
    evaluation = _evaluation(80)
    decision = _decision(80)

    result = apply_edge_optimizer_active_v1(
        evaluation=evaluation,
        signal_decision=decision,
        edge_optimizer_shadow=_shadow(adjustment=-10, confidence="HIGH"),
        enabled=True,
        max_adjustment=2.0,
    )

    assert result.applied is True
    assert result.active_adjustment == -2.0
    assert evaluation.setup_score == 78.0
    assert decision.total_score == 78.0


def test_low_confidence_adjustment_is_zero() -> None:
    evaluation = _evaluation(80)
    decision = _decision(80)

    result = apply_edge_optimizer_active_v1(
        evaluation=evaluation,
        signal_decision=decision,
        edge_optimizer_shadow=_shadow(adjustment=10, confidence="LOW"),
        enabled=True,
        min_confidence="MEDIUM",
    )

    assert result.applied is False
    assert result.active_adjustment == 0
    assert evaluation.setup_score == 80
    assert "confidence_below_minimum" in result.reasons


def test_original_score_below_70_cannot_cross_threshold() -> None:
    evaluation = _evaluation(69)
    decision = _decision(69)

    result = apply_edge_optimizer_active_v1(
        evaluation=evaluation,
        signal_decision=decision,
        edge_optimizer_shadow=_shadow(adjustment=2, confidence="HIGH"),
        enabled=True,
        max_adjustment=2.0,
    )

    assert result.applied is False
    assert result.active_adjustment == 0
    assert result.adjusted_score == 69
    assert evaluation.setup_score == 69
    assert "prevented_sub_70_threshold_cross" in result.reasons


def test_original_score_above_70_can_adjust_slightly() -> None:
    evaluation = _evaluation(70)
    decision = _decision(70)

    result = apply_edge_optimizer_active_v1(
        evaluation=evaluation,
        signal_decision=decision,
        edge_optimizer_shadow=_shadow(adjustment=2, confidence="MEDIUM"),
        enabled=True,
        max_adjustment=2.0,
    )

    assert result.applied is True
    assert result.adjusted_score == 72
    assert "edge_optimizer_active_adjusted_score=72.0" in evaluation.decision_trace


def test_result_dict_contains_log_fields() -> None:
    result = apply_edge_optimizer_active_v1(
        evaluation=_evaluation(80),
        signal_decision=_decision(80),
        edge_optimizer_shadow=_shadow(adjustment=1.5, confidence="HIGH", matched_edges_count=4),
        enabled=True,
        max_adjustment=2.0,
    )

    payload = result.to_dict()
    assert payload["original_score"] == 80
    assert payload["active_adjustment"] == 1.5
    assert payload["adjusted_score"] == 81.5
    assert payload["confidence"] == "HIGH"
    assert payload["matched_edges_count"] == 4


def _evaluation(score: float) -> SimpleNamespace:
    return SimpleNamespace(setup_score=score, decision_trace=[])


def _decision(score: float) -> SimpleNamespace:
    return SimpleNamespace(total_score=score, module_scores={"strategy": score})


def _shadow(*, adjustment: float, confidence: str, matched_edges_count: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        optimizer_adjustment=adjustment,
        optimizer_confidence=confidence,
        matched_edges_count=matched_edges_count,
    )
