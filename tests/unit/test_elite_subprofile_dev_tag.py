from __future__ import annotations

import inspect
from dataclasses import dataclass, field

from trading_signals.app.settings import Settings
from trading_signals.application.use_cases import elite_subprofile_dev_tag
from trading_signals.application.use_cases.elite_subprofile_dev_tag import (
    apply_elite_subprofile_dev_tag,
    format_elite_subprofile_dev_note,
    matches_elite_subprofile_g,
    matches_elite_subprofile_h,
)


@dataclass
class DummyEvaluation:
    setup_score: float
    decision_trace: list[str] = field(default_factory=list)


def test_profile_g_requires_exact_subprofile_context() -> None:
    assert matches_elite_subprofile_g(
        setup_type="SECONDARY_SIGNAL",
        score=95,
        direction="long",
        higher_trend="bullish",
        session="OVERLAP",
        trade_location="near_resistance",
    )
    assert not matches_elite_subprofile_g(
        setup_type="SECONDARY_SIGNAL",
        score=95,
        direction="short",
        higher_trend="bearish",
        session="OVERLAP",
        trade_location="near_resistance",
    )
    assert not matches_elite_subprofile_g(
        setup_type="SECONDARY_SIGNAL",
        score=95,
        direction="long",
        higher_trend="bullish",
        session="LONDON",
        trade_location="near_resistance",
    )
    assert not matches_elite_subprofile_g(
        setup_type="SECONDARY_SIGNAL",
        score=95,
        direction="long",
        higher_trend="bullish",
        session="OVERLAP",
        trade_location="mid_range",
    )


def test_profile_h_requires_high_volatility_long_aligned_profile_c() -> None:
    assert matches_elite_subprofile_h(
        setup_type="SECONDARY_SIGNAL",
        score=95,
        direction="long",
        higher_trend="bullish",
        market_regime="HIGH_VOLATILITY",
    )
    assert not matches_elite_subprofile_h(
        setup_type="MAIN_SIGNAL",
        score=95,
        direction="long",
        higher_trend="bullish",
        market_regime="HIGH_VOLATILITY",
    )
    assert not matches_elite_subprofile_h(
        setup_type="SECONDARY_SIGNAL",
        score=89,
        direction="long",
        higher_trend="bullish",
        market_regime="HIGH_VOLATILITY",
    )
    assert not matches_elite_subprofile_h(
        setup_type="SECONDARY_SIGNAL",
        score=95,
        direction="long",
        higher_trend="bearish",
        market_regime="HIGH_VOLATILITY",
    )
    assert not matches_elite_subprofile_h(
        setup_type="SECONDARY_SIGNAL",
        score=95,
        direction="long",
        higher_trend="bullish",
        market_regime="TRENDING",
    )


def test_decision_trace_includes_profile_g_and_h_tokens_when_matched() -> None:
    evaluation = DummyEvaluation(setup_score=95)

    result = apply_elite_subprofile_dev_tag(
        evaluation,
        setup_type="SECONDARY_SIGNAL",
        direction="long",
        higher_trend="bullish",
        session="OVERLAP",
        market_regime="HIGH_VOLATILITY",
        trade_location="near_resistance",
    )

    assert result.matched_profiles == ("G", "H")
    assert "elite_subprofile_g=true" in evaluation.decision_trace
    assert "elite_subprofile_h=true" in evaluation.decision_trace


def test_decision_trace_only_adds_matching_profile_token() -> None:
    evaluation = DummyEvaluation(setup_score=95)

    result = apply_elite_subprofile_dev_tag(
        evaluation,
        setup_type="SECONDARY_SIGNAL",
        direction="long",
        higher_trend="bullish",
        session="LONDON",
        market_regime="HIGH_VOLATILITY",
        trade_location="near_support",
    )

    assert result.matched_profiles == ("H",)
    assert "elite_subprofile_g=true" not in evaluation.decision_trace
    assert "elite_subprofile_h=true" in evaluation.decision_trace


def test_decision_trace_not_modified_when_not_matched() -> None:
    evaluation = DummyEvaluation(setup_score=95)

    result = apply_elite_subprofile_dev_tag(
        evaluation,
        setup_type="SECONDARY_SIGNAL",
        direction="long",
        higher_trend="bearish",
        session="OVERLAP",
        market_regime="HIGH_VOLATILITY",
        trade_location="near_resistance",
    )

    assert result.matched is False
    assert evaluation.decision_trace == []


def test_default_env_disabled_and_configurable(monkeypatch) -> None:
    monkeypatch.delenv("ELITE_SUBPROFILE_DEV_NOTE_ENABLED", raising=False)
    assert Settings().elite_subprofile_dev_note_enabled is False

    monkeypatch.setenv("ELITE_SUBPROFILE_DEV_NOTE_ENABLED", "true")
    assert Settings().elite_subprofile_dev_note_enabled is True


def test_dev_note_format_is_private_observability_text() -> None:
    message = format_elite_subprofile_dev_note(
        symbol="btcusdt",
        profiles=("G", "H"),
        direction="long",
        score=95,
        session="OVERLAP",
        market_regime="HIGH_VOLATILITY",
        trade_location="near_resistance",
        setup_type="SECONDARY_SIGNAL",
    )

    assert "🔥 ELITE SUBPROFILE G/H" in message
    assert "BTCUSDT LONG" in message
    assert "Score: 90+" in message
    assert "Session: OVERLAP" in message
    assert "Regime: HIGH_VOLATILITY" in message
    assert "Location: near_resistance" in message
    assert "Setup: SECONDARY_SIGNAL" in message


def test_subprofile_helper_does_not_touch_public_sending() -> None:
    source = inspect.getsource(elite_subprofile_dev_tag)

    assert "send_public" not in source
    assert "telegram_public" not in source
