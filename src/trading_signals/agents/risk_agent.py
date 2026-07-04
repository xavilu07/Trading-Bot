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


def vote_committee_risk(proposal: dict[str, object]) -> dict[str, object]:
    trades_lost = _int(proposal.get("trades_lost"))
    baseline_trades = _int(proposal.get("baseline_trades"))
    evidence = _int(proposal.get("evidence"))
    expected_total_r = _float(proposal.get("expected_total_r"))
    risks: list[str] = []
    vote = "SUPPORT"
    risk_level = "LOW"

    reduction = classify_trade_reduction_risk(trades_lost, baseline_trades)
    proposal["baseline_trades"] = reduction["baseline_trades"]
    proposal["trade_reduction_pct"] = reduction["trade_reduction_pct"]
    if reduction["risk_level"] != "LOW":
        risks.append(str(reduction["risk"]))
        vote = "REJECT" if reduction["risk_level"] in {"HIGH", "EXTREME"} else "CAUTION"
        risk_level = str(reduction["risk_level"])

    if evidence < 20:
        risks.append("low_evidence")
        vote = "CAUTION"
        risk_level = _max_risk_level(risk_level, "MEDIUM")
    if not baseline_trades and trades_lost > max(50, evidence):
        risks.append("extreme_trade_reduction")
        vote = "REJECT"
        risk_level = _max_risk_level(risk_level, "HIGH")
    elif not baseline_trades and trades_lost > max(25, evidence * 0.5):
        risks.append("large_trade_reduction")
        vote = "CAUTION"
        risk_level = _max_risk_level(risk_level, "MEDIUM")
    if expected_total_r is not None and expected_total_r < 0:
        risks.append("negative_expected_total_r")
        vote = "REJECT"
        risk_level = _max_risk_level(risk_level, "HIGH")

    proposal["risk_level"] = risk_level
    proposal["risk_objections"] = risks
    return {
        "agent": "risk_agent",
        "vote": vote,
        "confidence": "HIGH" if risks else "MEDIUM",
        "reason": ", ".join(risks) if risks else "Risk profile acceptable for manual review.",
        "risks": risks,
    }


def classify_trade_reduction_risk(trades_lost: int, baseline_trades: int) -> dict[str, object]:
    pct = round((trades_lost / baseline_trades) * 100, 4) if baseline_trades > 0 else 0.0
    if pct > 60:
        risk_level = "EXTREME"
        risk = "extreme_trade_reduction"
    elif pct >= 40:
        risk_level = "HIGH"
        risk = "high_trade_reduction"
    elif pct >= 25:
        risk_level = "MEDIUM"
        risk = "medium_trade_reduction"
    else:
        risk_level = "LOW"
        risk = ""
    return {
        "baseline_trades": baseline_trades,
        "trades_lost": trades_lost,
        "trade_reduction_pct": pct,
        "risk_level": risk_level,
        "risk": risk,
    }


def _max_risk_level(left: str, right: str) -> str:
    ranks = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "EXTREME": 3}
    return left if ranks.get(left, 0) >= ranks.get(right, 0) else right


def _int(value: object) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: object) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
