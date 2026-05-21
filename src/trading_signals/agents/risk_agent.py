from __future__ import annotations

from trading_signals.agents.agent_models import AgentVote


def vote_risk(
    *,
    risk_plan=None,
    setup_context: dict[str, object] | None = None,
    warnings: list[str] | None = None,
) -> AgentVote:
    setup_context = setup_context or {}
    warnings = list(warnings or setup_context.get("avoidance_warnings", []) or [])
    reasons: list[str] = []
    risks: list[str] = []
    score = 70.0

    rr = getattr(risk_plan, "risk_reward", None)
    if rr is None:
        rr = setup_context.get("risk_reward") or setup_context.get("rr")
    try:
        rr_float = float(rr) if rr is not None else None
    except (TypeError, ValueError):
        rr_float = None

    rr_valid = setup_context.get("rr_valid")
    if rr_valid is True or (rr_float is not None and rr_float >= 1.5):
        reasons.append("risk reward valid")
        score += 15
    elif rr_valid is False or rr_float is not None:
        risks.append("risk reward weak")
        score -= 25
    else:
        risks.append("risk plan missing")
        score -= 10

    if getattr(risk_plan, "stop_loss", None) is not None and getattr(risk_plan, "take_profit", None) is not None:
        reasons.append("stop loss and take profit available")
    if warnings:
        risks.extend(str(item) for item in warnings[:5])
        score -= min(25, len(warnings) * 5)

    if score < 45:
        action = "WOULD_BLOCK"
    elif risks:
        action = "CAUTION"
    elif score >= 85:
        action = "PRIORITIZE"
    else:
        action = "ALLOW"

    confidence = "HIGH" if rr_float is not None or rr_valid is not None else "MEDIUM" if risk_plan is not None else "LOW"
    return AgentVote("risk_agent", action, confidence, score, reasons or ["risk context observable"], risks)
