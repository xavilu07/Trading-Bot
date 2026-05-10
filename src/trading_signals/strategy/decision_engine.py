from __future__ import annotations

from trading_signals.domain.entities.signal_decision import SignalDecision
from trading_signals.strategy.signal_decision_adapter import (
    signal_decision_from_modules,
    signal_decision_from_strategy_evaluation,
)


SHADOW_MODULES = {"trend", "momentum", "liquidity", "market_regime", "risk"}


def evaluate_parallel_decision(module_results: dict[str, dict[str, object]]) -> dict[str, object]:
    scores = [float(result.get("score", 0.0)) for result in module_results.values()]
    total_score = round(sum(scores) / len(scores), 2) if scores else 0.0
    rejection_reasons = [
        str(result.get("reason", "unknown"))
        for result in module_results.values()
        if result.get("ok") is not True
    ]
    signal_details = module_results.get("signal_builder", {}).get("details", {})
    final_direction = "no_trade"
    if isinstance(signal_details, dict):
        final_direction = str(signal_details.get("direction", "no_trade"))
    if final_direction in {"long", "short"} and not rejection_reasons:
        decision = "SEND"
    elif final_direction in {"long", "short"}:
        decision = "PAPER_ONLY"
    else:
        decision = "REJECT"
    shadow = evaluate_shadow_decision(module_results)
    return {
        "ok": decision == "SEND",
        "score": total_score,
        "reason": "parallel_decision_diagnostic",
        "details": {
            "total_score": total_score,
            "final_direction": final_direction,
            "decision": decision,
            "rejection_reasons": rejection_reasons,
            **shadow,
        },
    }


def evaluate_shadow_decision(module_results: dict[str, dict[str, object]]) -> dict[str, object]:
    shadow_results = {
        name: result
        for name, result in module_results.items()
        if name in SHADOW_MODULES and not _is_missing_risk_plan(name, result)
    }
    scores = [float(result.get("score", 0.0)) for result in shadow_results.values()]
    shadow_score = round(sum(scores) / len(scores), 2) if scores else 0.0
    trend_ok = bool(module_results.get("trend", {}).get("ok"))
    momentum_ok = bool(module_results.get("momentum", {}).get("ok"))
    liquidity_ok = bool(module_results.get("liquidity", {}).get("ok"))
    shadow_rejection_reasons = [
        str(result.get("reason", "unknown"))
        for name, result in shadow_results.items()
        if result.get("ok") is not True
    ]
    direction = _shadow_direction(module_results)
    if shadow_score >= 80 and trend_ok and momentum_ok and liquidity_ok:
        shadow_decision = "SEND"
    elif shadow_score >= 65 and trend_ok and momentum_ok:
        shadow_decision = "PAPER_ONLY"
    else:
        shadow_decision = "REJECT"
    if shadow_decision == "REJECT":
        if shadow_score < 65:
            shadow_rejection_reasons.append("shadow_score_below_paper_threshold")
        if not trend_ok:
            shadow_rejection_reasons.append("shadow_trend_failed")
        if not momentum_ok:
            shadow_rejection_reasons.append("shadow_momentum_failed")
    if shadow_decision != "SEND" and shadow_score < 80:
        shadow_rejection_reasons.append("shadow_score_below_send_threshold")
    if shadow_decision == "PAPER_ONLY" and not liquidity_ok:
        shadow_rejection_reasons.append("shadow_liquidity_failed")
    return {
        "shadow_decision": shadow_decision,
        "shadow_score": shadow_score,
        "shadow_direction": direction,
        "shadow_rejection_reasons": list(dict.fromkeys(shadow_rejection_reasons)),
    }


def _is_missing_risk_plan(name: str, result: dict[str, object]) -> bool:
    return name == "risk" and result.get("reason") == "risk_plan_missing"


def _shadow_direction(module_results: dict[str, dict[str, object]]) -> str:
    momentum_details = module_results.get("momentum", {}).get("details", {})
    if isinstance(momentum_details, dict) and momentum_details.get("direction") in {"long", "short"}:
        return str(momentum_details["direction"])
    trend_details = module_results.get("trend", {}).get("details", {})
    if isinstance(trend_details, dict):
        trend = trend_details.get("trend_entry")
        if trend == "bullish":
            return "long"
        if trend == "bearish":
            return "short"
    return "no_trade"


def build_signal_decision_from_modules(
    *,
    symbol: str,
    module_results: dict[str, dict[str, object]],
    entry_price: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    source_engine: str = "parallel_decision_engine",
) -> SignalDecision:
    return signal_decision_from_modules(
        symbol=symbol,
        module_results=module_results,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        source_engine=source_engine,
    )


def build_signal_decision_from_strategy_evaluation(
    *,
    evaluation,
    risk_plan=None,
    setup_type: str = "UNKNOWN",
    warnings: list[str] | None = None,
    source_engine: str = "liquidity_sweep_mtf_v1",
) -> SignalDecision:
    return signal_decision_from_strategy_evaluation(
        evaluation=evaluation,
        risk_plan=risk_plan,
        setup_type=setup_type,
        warnings=warnings,
        source_engine=source_engine,
    )
