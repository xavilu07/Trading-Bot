from __future__ import annotations

from trading_signals.strategy.decision_engine import evaluate_parallel_decision


def module(ok: bool, score: float, reason: str, details: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "ok": ok,
        "score": score,
        "reason": reason,
        "details": details or {},
    }


def test_decision_engine_sends_when_all_modules_ok_and_signal_direction_exists() -> None:
    result = evaluate_parallel_decision(
        {
            "trend": module(True, 100, "trend_aligned"),
            "risk": module(True, 100, "risk_reward_valid"),
            "signal_builder": module(True, 80, "signal_candidate_ready", {"direction": "long"}),
        }
    )

    assert result["ok"] is True
    assert result["details"]["decision"] == "SEND"
    assert result["details"]["final_direction"] == "long"
    assert result["details"]["rejection_reasons"] == []


def test_decision_engine_marks_signal_as_paper_only_when_parallel_modules_fail() -> None:
    result = evaluate_parallel_decision(
        {
            "trend": module(False, 50, "trend_timeframe_mismatch"),
            "risk": module(True, 100, "risk_reward_valid"),
            "signal_builder": module(True, 80, "signal_candidate_ready", {"direction": "short"}),
        }
    )

    assert result["ok"] is False
    assert result["details"]["decision"] == "PAPER_ONLY"
    assert result["details"]["rejection_reasons"] == ["trend_timeframe_mismatch"]


def test_decision_engine_rejects_without_signal_direction() -> None:
    result = evaluate_parallel_decision(
        {
            "trend": module(True, 100, "trend_aligned"),
            "signal_builder": module(False, 0, "signal_not_ready", {"direction": "no_trade"}),
        }
    )

    assert result["ok"] is False
    assert result["details"]["decision"] == "REJECT"


def test_shadow_decision_sends_from_modules_without_legacy_signal_builder() -> None:
    result = evaluate_parallel_decision(
        {
            "trend": module(True, 100, "trend_aligned", {"trend_entry": "bullish"}),
            "momentum": module(True, 85, "momentum_confirmed", {"direction": "long"}),
            "liquidity": module(True, 80, "liquidity_distance_ok"),
            "market_regime": module(True, 80, "market_regime_trending"),
            "risk": module(False, 0, "risk_plan_missing"),
            "signal_builder": module(False, 0, "signal_not_ready", {"direction": "no_trade"}),
        }
    )

    assert result["details"]["decision"] == "REJECT"
    assert result["details"]["shadow_decision"] == "SEND"
    assert result["details"]["shadow_score"] == 86.25
    assert result["details"]["shadow_direction"] == "long"
    assert "risk_plan_missing" not in result["details"]["shadow_rejection_reasons"]


def test_shadow_decision_marks_paper_only_when_score_is_good_but_liquidity_fails() -> None:
    result = evaluate_parallel_decision(
        {
            "trend": module(True, 100, "trend_aligned", {"trend_entry": "bearish"}),
            "momentum": module(True, 80, "momentum_confirmed", {"direction": "short"}),
            "liquidity": module(False, 40, "liquidity_too_far"),
            "market_regime": module(True, 70, "market_regime_high_volatility"),
            "risk": module(False, 0, "risk_plan_missing"),
        }
    )

    assert result["details"]["shadow_decision"] == "PAPER_ONLY"
    assert result["details"]["shadow_direction"] == "short"
    assert "liquidity_too_far" in result["details"]["shadow_rejection_reasons"]
    assert "shadow_liquidity_failed" in result["details"]["shadow_rejection_reasons"]


def test_shadow_decision_rejects_when_momentum_fails() -> None:
    result = evaluate_parallel_decision(
        {
            "trend": module(True, 100, "trend_aligned", {"trend_entry": "bullish"}),
            "momentum": module(False, 25, "body_ratio_below_threshold", {"direction": "long"}),
            "liquidity": module(True, 80, "liquidity_distance_ok"),
            "market_regime": module(True, 70, "market_regime_high_volatility"),
        }
    )

    assert result["details"]["shadow_decision"] == "REJECT"
    assert "body_ratio_below_threshold" in result["details"]["shadow_rejection_reasons"]
    assert "shadow_momentum_failed" in result["details"]["shadow_rejection_reasons"]
