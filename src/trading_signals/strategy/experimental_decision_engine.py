from __future__ import annotations


def evaluate_experimental_decision(module_results: dict[str, dict[str, object]]) -> dict[str, object]:
    momentum = module_results.get("momentum", {})
    trend = module_results.get("trend", {})
    liquidity = module_results.get("liquidity", {})
    strategy_gate = module_results.get("strategy_gate", {})
    decision_engine = module_results.get("decision_engine", {})
    signal_builder = module_results.get("signal_builder", {})

    gate_details = strategy_gate.get("details", {}) if isinstance(strategy_gate.get("details"), dict) else {}
    decision_details = decision_engine.get("details", {}) if isinstance(decision_engine.get("details"), dict) else {}
    signal_details = signal_builder.get("details", {}) if isinstance(signal_builder.get("details"), dict) else {}

    score = float(strategy_gate.get("score") or decision_details.get("total_score") or 0.0)
    direction = str(
        gate_details.get("suggested_direction")
        or signal_details.get("direction")
        or decision_details.get("final_direction")
        or "no_trade"
    )
    checks = {
        "score": score >= 80,
        "momentum": momentum.get("ok") is True,
        "trend": trend.get("ok") is True,
        "liquidity": liquidity.get("ok") is True,
        "direction": direction == "short",
    }
    failed = [name for name, passed in checks.items() if not passed]
    would_send = not failed
    original_block = gate_details.get("condition_failed") or signal_builder.get("reason") or "none"
    reason = (
        "experimental_accepts_short_only_without_primary_sweep"
        if would_send
        else "experimental_rejects_" + "|".join(failed)
    )
    return {
        "ok": would_send,
        "score": score,
        "reason": reason,
        "details": {
            "experimental_decision": "SEND" if would_send else "REJECT",
            "experimental_reason": reason,
            "would_send_signal": would_send,
            "direction": direction,
            "score": score,
            "original_blocking_filter": original_block,
            "checks": checks,
        },
    }
