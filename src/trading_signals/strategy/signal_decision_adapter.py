from __future__ import annotations

from trading_signals.domain.entities.signal_decision import SignalDecision


"""Adapters between legacy strategy output and the normalized signal contract.

Current production flow:
- LiquiditySweepMTFV1 still returns StrategyEvaluation.
- StrategyEvaluation is persisted for audit/backward compatibility.
- run_market_scan adapts it to SignalDecision before publish/paper/live flows.
- decision_engine remains diagnostic only until explicitly activated.
"""


def signal_decision_from_modules(
    *,
    symbol: str,
    module_results: dict[str, dict[str, object]],
    entry_price: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    source_engine: str = "parallel_decision_engine",
) -> SignalDecision:
    decision_result = module_results.get("decision_engine", {})
    details = decision_result.get("details", {}) if isinstance(decision_result.get("details"), dict) else {}
    signal_details = module_results.get("signal_builder", {}).get("details", {})
    if not isinstance(signal_details, dict):
        signal_details = {}
    module_scores = {
        module: float(result.get("score", 0.0))
        for module, result in module_results.items()
        if module != "decision_engine"
    }
    passed_filters = list(signal_details.get("passed_filters", []) or [])
    failed_filters = list(signal_details.get("failed_filters", []) or [])
    return SignalDecision(
        symbol=symbol,
        direction=str(details.get("final_direction", signal_details.get("direction", "no_trade"))),
        decision=str(details.get("decision", "REJECT")),
        setup_type=str(signal_details.get("setup_type", "UNKNOWN")),
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        total_score=float(details.get("total_score", decision_result.get("score", 0.0)) or 0.0),
        module_scores=module_scores,
        rejection_reasons=[str(item) for item in details.get("rejection_reasons", []) or []],
        warnings=[],
        passed_filters=[str(item) for item in passed_filters],
        failed_filters=[str(item) for item in failed_filters],
        decision_trace=[],
        source_engine=source_engine,
    )


CORE_MODULAR_MODULES = {"trend", "momentum", "liquidity", "market_regime", "risk"}


def clean_modular_signal_decision(
    *,
    symbol: str,
    module_results: dict[str, dict[str, object]],
    entry_price: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    source_engine: str = "modular_decision_engine",
) -> SignalDecision:
    core_results = {
        name: result
        for name, result in module_results.items()
        if name in CORE_MODULAR_MODULES and not _is_non_blocking_missing_risk(name, result)
    }
    module_scores = {
        name: float(result.get("score", 0.0))
        for name, result in core_results.items()
    }
    total_score = round(sum(module_scores.values()) / len(module_scores), 2) if module_scores else 0.0
    trend_ok = bool(module_results.get("trend", {}).get("ok"))
    momentum_ok = bool(module_results.get("momentum", {}).get("ok"))
    liquidity_ok = bool(module_results.get("liquidity", {}).get("ok"))
    direction = _module_direction(module_results)

    rejection_reasons = [
        str(result.get("reason", "unknown"))
        for name, result in core_results.items()
        if result.get("ok") is not True
    ]
    if total_score >= 80 and trend_ok and momentum_ok and liquidity_ok:
        decision = "SEND"
    elif total_score >= 65 and trend_ok and momentum_ok:
        decision = "PAPER_ONLY"
    else:
        decision = "REJECT"

    if decision == "REJECT":
        if total_score < 65:
            rejection_reasons.append("modular_score_below_paper_threshold")
        if not trend_ok:
            rejection_reasons.append("modular_trend_failed")
        if not momentum_ok:
            rejection_reasons.append("modular_momentum_failed")
    if decision != "SEND" and total_score < 80:
        rejection_reasons.append("modular_score_below_send_threshold")
    if decision == "PAPER_ONLY" and not liquidity_ok:
        rejection_reasons.append("modular_liquidity_failed")

    return SignalDecision(
        symbol=symbol,
        direction=direction if decision in {"SEND", "PAPER_ONLY"} else "no_trade",
        decision=decision,
        setup_type="MODULAR_SIGNAL",
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        total_score=total_score,
        module_scores=module_scores,
        rejection_reasons=list(dict.fromkeys(rejection_reasons)),
        warnings=[],
        passed_filters=[
            name
            for name in ("trend", "momentum", "liquidity", "market_regime")
            if module_results.get(name, {}).get("ok") is True
        ],
        failed_filters=[
            name
            for name in ("trend", "momentum", "liquidity", "market_regime")
            if module_results.get(name, {}).get("ok") is not True
        ],
        decision_trace=[
            "clean_modular_engine",
            f"trend_ok={trend_ok}",
            f"momentum_ok={momentum_ok}",
            f"liquidity_ok={liquidity_ok}",
            f"total_score={total_score}",
        ],
        source_engine=source_engine,
    )


def _is_non_blocking_missing_risk(name: str, result: dict[str, object]) -> bool:
    return name == "risk" and result.get("reason") == "risk_plan_missing"


def _module_direction(module_results: dict[str, dict[str, object]]) -> str:
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


def signal_decision_from_strategy_evaluation(
    *,
    evaluation,
    risk_plan=None,
    setup_type: str = "UNKNOWN",
    warnings: list[str] | None = None,
    source_engine: str = "liquidity_sweep_mtf_v1",
) -> SignalDecision:
    direction = evaluation.decision if evaluation.decision in {"long", "short"} else "no_trade"
    decision = "SEND" if direction in {"long", "short"} and risk_plan is not None else "REJECT"
    return SignalDecision(
        symbol=evaluation.symbol,
        direction=direction,
        decision=decision,
        setup_type=setup_type,
        entry_price=getattr(risk_plan, "entry", None),
        stop_loss=getattr(risk_plan, "stop_loss", None),
        take_profit=getattr(risk_plan, "take_profit", None),
        total_score=float(evaluation.setup_score),
        module_scores={"strategy": float(evaluation.setup_score)},
        rejection_reasons=[str(item) for item in evaluation.rejection_reasons],
        warnings=warnings or [],
        passed_filters=[str(item) for item in getattr(evaluation, "passed_filters", [])],
        failed_filters=[str(item) for item in getattr(evaluation, "failed_filters", [])],
        decision_trace=[str(item) for item in getattr(evaluation, "decision_trace", [])],
        source_engine=source_engine,
    )
