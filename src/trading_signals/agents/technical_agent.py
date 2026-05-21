from __future__ import annotations

from trading_signals.agents.agent_models import AgentVote


def vote_technical(
    *,
    setup_context: dict[str, object] | None,
    evaluation,
    analysis=None,
) -> AgentVote:
    setup_context = setup_context or {}
    passed = set(getattr(evaluation, "passed_filters", []) or [])
    failed = set(getattr(evaluation, "failed_filters", []) or [])
    score = float(getattr(evaluation, "setup_score", 0.0) or 0.0)
    reasons: list[str] = []
    risks: list[str] = []

    if "primary_sweep_setup" in passed:
        reasons.append("primary sweep setup detected")
    if "secondary_setup" in passed:
        reasons.append("secondary setup detected")
    if "timeframe_alignment" in passed:
        reasons.append("timeframe aligned")
    if str(setup_context.get("entry_context", "")).upper() in {"BREAKOUT", "IMPULSE"}:
        reasons.append(f"entry context {setup_context.get('entry_context')}")
    if score >= 80:
        reasons.append("strong setup score")

    for item in ["body_ratio_below_threshold", "volatility_failed", "distance_to_liquidity_extreme"]:
        if item in failed:
            risks.append(item)
    if "timeframe_alignment_penalty" in failed:
        risks.append("timeframe alignment penalty")
    if str(setup_context.get("entry_context", "")).upper() == "CHOPPY_RANGE":
        risks.append("choppy range context")

    if risks and score < 65:
        action = "WOULD_BLOCK"
    elif risks:
        action = "CAUTION"
    elif score >= 80 and reasons:
        action = "PRIORITIZE"
    else:
        action = "ALLOW"

    confidence = "HIGH" if score >= 80 or len(risks) >= 2 else "MEDIUM" if reasons or risks else "LOW"
    return AgentVote("technical_agent", action, confidence, score, reasons or ["technical context acceptable"], risks)
