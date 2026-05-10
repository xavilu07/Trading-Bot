from __future__ import annotations

from trading_signals.strategy.experimental_decision_engine import evaluate_experimental_decision


def module(ok: bool, score: float, reason: str, details: dict[str, object] | None = None) -> dict[str, object]:
    return {"ok": ok, "score": score, "reason": reason, "details": details or {}}


def test_experimental_decision_accepts_high_score_short_without_primary_sweep() -> None:
    result = evaluate_experimental_decision(
        {
            "momentum": module(True, 90, "momentum_confirmed"),
            "trend": module(True, 100, "trend_aligned"),
            "liquidity": module(True, 60, "nearest_liquidity_ok"),
            "strategy_gate": module(
                False,
                82,
                "strategy_gate_blocked",
                {"suggested_direction": "short", "condition_failed": "short_primary_sweep"},
            ),
            "decision_engine": module(False, 80, "parallel_decision_diagnostic", {"final_direction": "no_trade"}),
            "signal_builder": module(False, 80, "signal_not_ready", {"direction": "no_trade"}),
        }
    )

    assert result["ok"] is True
    assert result["details"]["would_send_signal"] is True
    assert result["details"]["experimental_decision"] == "SEND"
    assert result["details"]["original_blocking_filter"] == "short_primary_sweep"


def test_experimental_decision_rejects_low_score_short() -> None:
    result = evaluate_experimental_decision(
        {
            "momentum": module(True, 90, "momentum_confirmed"),
            "trend": module(True, 100, "trend_aligned"),
            "liquidity": module(True, 60, "nearest_liquidity_ok"),
            "strategy_gate": module(False, 70, "strategy_gate_blocked", {"suggested_direction": "short"}),
        }
    )

    assert result["ok"] is False
    assert result["details"]["would_send_signal"] is False
    assert "score" in result["details"]["experimental_reason"]


def test_experimental_decision_rejects_long_even_with_high_score() -> None:
    result = evaluate_experimental_decision(
        {
            "momentum": module(True, 90, "momentum_confirmed"),
            "trend": module(True, 100, "trend_aligned"),
            "liquidity": module(True, 60, "nearest_liquidity_ok"),
            "strategy_gate": module(False, 100, "strategy_gate_blocked", {"suggested_direction": "long"}),
        }
    )

    assert result["ok"] is False
    assert result["details"]["would_send_signal"] is False
    assert "direction" in result["details"]["experimental_reason"]
