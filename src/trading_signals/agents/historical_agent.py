from __future__ import annotations

from trading_signals.agents.agent_models import AgentVote


def vote_historical(*, performance_gate: dict[str, object] | None) -> AgentVote:
    gate = performance_gate or {}
    action = str(gate.get("action") or "ALLOW").upper()
    if action not in {"ALLOW", "CAUTION", "WOULD_BLOCK", "PRIORITIZE"}:
        action = "ALLOW"
    confidence = str(gate.get("confidence") or "LOW").upper()
    if confidence not in {"LOW", "MEDIUM", "HIGH"}:
        confidence = "LOW"
    scores = gate.get("scores") if isinstance(gate.get("scores"), dict) else {}
    score_values = [float(value) for value in scores.values() if isinstance(value, (int, float))]
    score = sum(score_values) / len(score_values) if score_values else 50.0

    reasons = [str(item) for item in gate.get("reasons", []) or []]
    risks = [str(item) for item in gate.get("risks", []) or []]
    if gate.get("would_block") is True:
        action = "WOULD_BLOCK"
        risks.append("performance gate would block")
    if gate.get("would_prioritize") is True:
        action = "PRIORITIZE"
        reasons.append("performance gate would prioritize")

    return AgentVote("historical_agent", action, confidence, score, reasons or ["historical context neutral"], risks)
