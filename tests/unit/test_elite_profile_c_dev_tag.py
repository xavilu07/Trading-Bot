from __future__ import annotations

from dataclasses import dataclass, field

from trading_signals.app.settings import Settings
from trading_signals.application.use_cases.elite_profile_c_dev_tag import (
    apply_elite_profile_c_dev_tag,
    format_elite_profile_c_dev_note,
    matches_elite_profile_c,
    resolve_htf_alignment,
    score_bucket,
)


@dataclass
class DummyEvaluation:
    setup_score: float
    decision_trace: list[str] = field(default_factory=list)


def test_matches_only_secondary_signal() -> None:
    assert matches_elite_profile_c(setup_type="SECONDARY_SIGNAL", score=90, direction="short", higher_trend="bearish")
    assert not matches_elite_profile_c(setup_type="MAIN_SIGNAL", score=90, direction="short", higher_trend="bearish")


def test_matches_score_90_plus() -> None:
    assert score_bucket(90) == "90+"
    assert score_bucket(100) == "90+"
    assert not matches_elite_profile_c(setup_type="SECONDARY_SIGNAL", score=89.99, direction="short", higher_trend="bearish")


def test_matches_aligned_with_htf() -> None:
    assert resolve_htf_alignment(direction="short", higher_trend="bearish") == "aligned_with_htf"
    assert resolve_htf_alignment(direction="long", higher_trend="bullish") == "aligned_with_htf"
    assert matches_elite_profile_c(setup_type="SECONDARY_SIGNAL", score=95, direction="long", higher_trend="bullish")


def test_does_not_match_against_htf() -> None:
    assert resolve_htf_alignment(direction="long", higher_trend="bearish") == "against_htf"
    assert not matches_elite_profile_c(setup_type="SECONDARY_SIGNAL", score=95, direction="long", higher_trend="bearish")
    assert not matches_elite_profile_c(
        setup_type="SECONDARY_SIGNAL",
        score=95,
        direction="long",
        htf_alignment="against_htf",
    )


def test_default_env_disabled(monkeypatch) -> None:
    monkeypatch.delenv("ELITE_PROFILE_C_DEV_NOTE_ENABLED", raising=False)

    assert Settings().elite_profile_c_dev_note_enabled is False


def test_env_can_enable_dev_note(monkeypatch) -> None:
    monkeypatch.setenv("ELITE_PROFILE_C_DEV_NOTE_ENABLED", "true")

    assert Settings().elite_profile_c_dev_note_enabled is True


def test_decision_trace_includes_elite_profile_c_when_matched() -> None:
    evaluation = DummyEvaluation(setup_score=95)

    result = apply_elite_profile_c_dev_tag(
        evaluation,
        setup_type="SECONDARY_SIGNAL",
        direction="short",
        higher_trend="bearish",
    )

    assert result.matched is True
    assert "elite_profile_c=true" in evaluation.decision_trace


def test_decision_trace_not_modified_when_not_matched() -> None:
    evaluation = DummyEvaluation(setup_score=95)

    result = apply_elite_profile_c_dev_tag(
        evaluation,
        setup_type="MAIN_SIGNAL",
        direction="short",
        higher_trend="bearish",
    )

    assert result.matched is False
    assert "elite_profile_c=true" not in evaluation.decision_trace


def test_dev_note_format_is_private_observability_text() -> None:
    message = format_elite_profile_c_dev_note(symbol="btcusdt", direction="short", score=95)

    assert "🔥 ELITE PROFILE C" in message
    assert "BTCUSDT SHORT" in message
    assert "Score 90+" in message
    assert "Historical PF: 2.64" in message
