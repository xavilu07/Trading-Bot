from __future__ import annotations

from trading_signals.application.policies.public_canary_policy import PublicShortCanaryConfig, evaluate_public_short_canary


def signal(direction: str = "short"):
    return type("Signal", (), {"decision": direction, "symbol": "BTCUSDT"})()


def evaluation(score: float = 70, setup_type: str = "MAIN_SIGNAL"):
    return type("Evaluation", (), {"total_score": score, "setup_score": score, "setup_type": setup_type})()


def context(**overrides):
    data = {"session": "LONDON", "entry_context": "PULLBACK", "setup_type": "MAIN_SIGNAL"}
    data.update(overrides)
    return data


def test_canary_disabled_blocks_without_changing_default() -> None:
    result = evaluate_public_short_canary(
        signal=signal("short"),
        evaluation_or_decision=evaluation(90),
        setup_context=context(),
        config=PublicShortCanaryConfig(enabled=False),
    )

    assert result["public_canary_match"] is False
    assert result["public_canary_reason"] == "canary_disabled"


def test_canary_enabled_allows_exact_london_short_pullback_main_score() -> None:
    result = evaluate_public_short_canary(
        signal=signal("short"),
        evaluation_or_decision=evaluation(90),
        setup_context=context(),
        config=PublicShortCanaryConfig(enabled=True),
    )

    assert result["public_canary_match"] is True
    assert result["public_canary_decision"] == "allow"


def test_canary_blocks_non_london() -> None:
    result = evaluate_public_short_canary(
        signal=signal("short"),
        evaluation_or_decision=evaluation(90),
        setup_context=context(session="NEW_YORK"),
        config=PublicShortCanaryConfig(enabled=True),
    )

    assert result["public_canary_match"] is False
    assert "canary_session_mismatch" in result["public_canary_reason"]


def test_canary_blocks_score_below_minimum() -> None:
    result = evaluate_public_short_canary(
        signal=signal("short"),
        evaluation_or_decision=evaluation(69),
        setup_context=context(),
        config=PublicShortCanaryConfig(enabled=True),
    )

    assert result["public_canary_match"] is False
    assert "canary_score_mismatch" in result["public_canary_reason"]


def test_canary_blocks_different_setup() -> None:
    result = evaluate_public_short_canary(
        signal=signal("short"),
        evaluation_or_decision=evaluation(90, "SECONDARY_SIGNAL"),
        setup_context=context(setup_type="SECONDARY_SIGNAL"),
        config=PublicShortCanaryConfig(enabled=True),
    )

    assert result["public_canary_match"] is False
    assert "canary_setup_type_mismatch" in result["public_canary_reason"]


def test_canary_does_not_match_long() -> None:
    result = evaluate_public_short_canary(
        signal=signal("long"),
        evaluation_or_decision=evaluation(90),
        setup_context=context(),
        config=PublicShortCanaryConfig(enabled=True),
    )

    assert result["public_canary_match"] is False
    assert "canary_direction_mismatch" in result["public_canary_reason"]
