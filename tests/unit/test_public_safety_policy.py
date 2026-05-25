from __future__ import annotations

from trading_signals.application.policies.public_safety_policy import evaluate_public_safety_policy


def signal(direction: str = "long"):
    return type("Signal", (), {"decision": direction})()


def evaluation(setup_type: str = "MAIN_SIGNAL"):
    return type("Evaluation", (), {"setup_type": setup_type, "passed_filters": [], "decision_trace": []})()


def base_context(**overrides):
    context = {
        "market_regime": "TRENDING",
        "entry_context": "BREAKOUT",
        "trade_location": "mid_range",
        "setup_type": "MAIN_SIGNAL",
        "warnings": [],
        "avoidance_warnings": [],
        "penalties": [],
    }
    context.update(overrides)
    return context


def assert_blocks(reason: str, *, context: dict | None = None, direction: str = "long", public_block_reason: str | None = None) -> None:
    result = evaluate_public_safety_policy(
        signal=signal(direction),
        evaluation_or_decision=evaluation(),
        setup_context=context or base_context(),
        public_block_reason=public_block_reason,
    )
    assert result["public_allowed"] is False
    assert reason in result["block_reasons"]
    assert result["policy_version"] == "v1"


def test_policy_version_present_and_clean_signal_allowed() -> None:
    result = evaluate_public_safety_policy(
        signal=signal("long"),
        evaluation_or_decision=evaluation(),
        setup_context=base_context(),
    )

    assert result == {
        "public_allowed": True,
        "block_reasons": [],
        "warnings": [],
        "policy_version": "v1",
    }


def test_policy_blocks_each_core_rule() -> None:
    assert_blocks("kill_switch_active", public_block_reason="kill_switch:daily_loss_limit")
    assert_blocks("meta_decision_reject", context=base_context(meta_decision={"meta_decision": "REJECT"}))
    assert_blocks("capital_preservation_mode", context=base_context(meta_decision={"capital_preservation_mode": True}))
    assert_blocks("trade_quality_trash", context=base_context(trade_quality={"trade_quality_grade": "TRASH"}))
    assert_blocks("market_regime_ranging", context=base_context(market_regime="RANGING"))
    assert_blocks("entry_context_choppy_range", context=base_context(entry_context="CHOPPY_RANGE"))
    assert_blocks("trade_location_premium_zone", context=base_context(trade_location="premium_zone"))
    assert_blocks("setup_type_secondary_signal", context=base_context(setup_type="SECONDARY_SIGNAL"))
    assert_blocks("short_without_high_historical_edge", direction="short")
    assert_blocks("against_htf", context=base_context(avoidance_warnings=["against_htf"]))
    assert_blocks("low_volume", context=base_context(avoidance_warnings=["low_volume"]))
    assert_blocks("dirty_sideways_market", context=base_context(avoidance_warnings=["dirty_sideways_market"]))


def test_policy_allows_short_with_high_historical_edge() -> None:
    result = evaluate_public_safety_policy(
        signal=signal("short"),
        evaluation_or_decision=evaluation(),
        setup_context=base_context(historical_edge={"historical_confidence": "HIGH"}),
    )

    assert result["public_allowed"] is True


def test_policy_collects_multiple_block_reasons() -> None:
    result = evaluate_public_safety_policy(
        signal=signal("short"),
        evaluation_or_decision=evaluation(),
        setup_context=base_context(
            market_regime="RANGING",
            entry_context="CHOPPY_RANGE",
            trade_location="premium_zone",
            avoidance_warnings=["against_htf", "low_volume"],
        ),
        public_block_reason="kill_switch:daily_loss_limit",
    )

    assert result["public_allowed"] is False
    assert "kill_switch_active" in result["block_reasons"]
    assert "market_regime_ranging" in result["block_reasons"]
    assert "entry_context_choppy_range" in result["block_reasons"]
    assert "trade_location_premium_zone" in result["block_reasons"]
    assert "short_without_high_historical_edge" in result["block_reasons"]
    assert "against_htf" in result["block_reasons"]
    assert "low_volume" in result["block_reasons"]
