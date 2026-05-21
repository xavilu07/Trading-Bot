from __future__ import annotations

from trading_signals.agents.agent_models import AgentVote


def vote_skeptic(
    *,
    evaluation,
    setup_context: dict[str, object] | None = None,
    performance_gate: dict[str, object] | None = None,
) -> AgentVote:
    setup_context = setup_context or {}
    performance_gate = performance_gate or {}
    failed = [str(item) for item in getattr(evaluation, "failed_filters", []) or []]
    rejection_reasons = [str(item) for item in getattr(evaluation, "rejection_reasons", []) or []]
    warnings = [str(item) for item in setup_context.get("avoidance_warnings", []) or []]
    trace = [str(item) for item in getattr(evaluation, "decision_trace", []) or []]
    penalties = [item for item in trace if item.startswith("penalties=")]

    risks = []
    risks.extend(rejection_reasons[:5])
    risks.extend(warnings[:5])
    if penalties and penalties[0] != "penalties=none":
        risks.append(penalties[0])
    if performance_gate.get("would_block") is True:
        risks.append("historical gate would block")

    score = 70.0 - min(55.0, len(set(failed + rejection_reasons + warnings)) * 8.0)
    if performance_gate.get("would_block") is True:
        score -= 15
    score = max(0.0, score)

    if score < 40:
        action = "WOULD_BLOCK"
    elif risks:
        action = "CAUTION"
    else:
        action = "ALLOW"
    confidence = "HIGH" if len(risks) >= 4 else "MEDIUM" if risks else "LOW"
    return AgentVote("skeptic_agent", action, confidence, score, ["skeptic review completed"], risks)
