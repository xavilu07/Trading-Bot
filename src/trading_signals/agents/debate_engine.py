from __future__ import annotations

from pathlib import Path
from typing import Any

from trading_signals.agents.qic_models import DebateIntervention
from trading_signals.agents.risk_agent import classify_trade_reduction_risk
from trading_signals.agents.research_agent import load_research_reports


def run_debate_engine(*, reports_root: Path = Path("reports")) -> dict[str, Any]:
    reports = load_research_reports(reports_root)
    interventions: list[DebateIntervention] = []
    research = research_director_opinion(reports)
    interventions.append(research)
    strategy = strategy_director_opinion(research)
    interventions.append(strategy)
    risk = risk_director_opinion(strategy, reports)
    interventions.append(risk)
    simulation = simulation_director_opinion(strategy, reports)
    interventions.append(simulation)
    interventions.append(research_response_opinion(research, risk, simulation))
    return {
        "pipeline": ["Research", "Strategy", "Risk", "Simulation", "Research", "CIO"],
        "interventions": [item.to_dict() for item in interventions],
        "reports_loaded": {
            key: sorted(value.keys()) if isinstance(value, dict) else []
            for key, value in reports.items()
        },
    }


def research_director_opinion(reports: dict[str, Any]) -> DebateIntervention:
    quant = reports.get("quant_research", {})
    historical = reports.get("historical_intelligence", {})
    simulator = reports.get("strategy_simulator", {})
    patterns = []
    patterns.extend(_top_labels(quant.get("feature_importance", {}).get("features", []), key="feature"))
    patterns.extend(_top_labels(historical.get("negative_edges", {}).get("edges", []), key="label"))
    patterns.extend(_top_conditions(simulator.get("single_filters", {}).get("simulations", [])))
    evidence = max([_max_evidence(patterns), 0])
    return DebateIntervention(
        agent="research_director",
        role="Research Director",
        stage="research",
        content="Detected research patterns; not recommending implementation yet.",
        confidence=_confidence(evidence),
        evidence=evidence,
        risk_level="LOW",
        data={"patterns": patterns[:15]},
    )


def strategy_director_opinion(research: DebateIntervention) -> DebateIntervention:
    patterns = list(research.data.get("patterns", []))
    candidates = []
    for pattern in patterns[:10]:
        if not _actionable_pattern(pattern):
            continue
        candidates.append(
            {
                "rule_candidate": f"Review context: {pattern.get('label') or pattern.get('feature') or pattern.get('condition')}",
                "source_pattern": pattern,
            }
        )
    return DebateIntervention(
        agent="strategy_director",
        role="Strategy Director",
        stage="strategy",
        content="Converted research patterns into possible strategy rules for debate.",
        confidence=research.confidence,
        evidence=research.evidence,
        risk_level="MEDIUM",
        data={"rule_candidates": candidates},
    )


def _actionable_pattern(pattern: dict[str, Any]) -> bool:
    if pattern.get("condition") or pattern.get("conditions"):
        return True
    if pattern.get("context"):
        return True
    return pattern.get("profit_factor") is not None and pattern.get("total_r") is not None


def risk_director_opinion(strategy: DebateIntervention, reports: dict[str, Any]) -> DebateIntervention:
    candidates = list(strategy.data.get("rule_candidates", []))
    baseline_closed = _baseline_closed(reports)
    risks = []
    for candidate in candidates:
        source = candidate.get("source_pattern") or {}
        trades_lost = int(float(source.get("trades_eliminated") or source.get("closed") or source.get("trades") or 0))
        reduction = classify_trade_reduction_risk(trades_lost, baseline_closed)
        if reduction["risk_level"] != "LOW":
            risks.append(
                {
                    "candidate": candidate.get("rule_candidate"),
                    "risk": reduction["risk"],
                    "risk_level": reduction["risk_level"],
                    "trades_lost": trades_lost,
                    "baseline_trades": baseline_closed,
                    "trade_reduction_pct": reduction["trade_reduction_pct"],
                }
            )
        elif trades_lost < 20:
            risks.append({"candidate": candidate.get("rule_candidate"), "risk": "low_sample_overfitting", "trades_lost": trades_lost})
    for simulation in _simulator_candidates(reports)[:25]:
        trades_lost = int(float(simulation.get("trades_eliminated") or 0))
        reduction = classify_trade_reduction_risk(trades_lost, baseline_closed)
        if reduction["risk_level"] == "LOW":
            continue
        risks.append(
            {
                "candidate": ", ".join(str(item) for item in simulation.get("conditions") or []) or "simulated candidate",
                "risk": reduction["risk"],
                "risk_level": reduction["risk_level"],
                "trades_lost": trades_lost,
                "baseline_trades": baseline_closed,
                "trade_reduction_pct": reduction["trade_reduction_pct"],
            }
        )
    risk_level = _max_risk_level(str(item.get("risk_level") or "MEDIUM") for item in risks) if risks else "LOW"
    return DebateIntervention(
        agent="risk_director",
        role="Risk Director",
        stage="risk",
        content="Attempted to reject weak or overfit rule candidates.",
        confidence="HIGH" if risks else "MEDIUM",
        evidence=baseline_closed,
        risk_level=risk_level,
        data={"risks": risks, "baseline_closed": baseline_closed},
    )


def simulation_director_opinion(strategy: DebateIntervention, reports: dict[str, Any]) -> DebateIntervention:
    simulations = _simulator_candidates(reports)
    simulations = sorted(simulations, key=lambda item: (float(item.get("delta_total_r") or item.get("total_r") or 0), float(item.get("profit_factor") or 0)), reverse=True)
    best = simulations[0] if simulations else {}
    return DebateIntervention(
        agent="simulation_director",
        role="Simulation Director",
        stage="simulation",
        content="Validated available candidates with Strategy Simulator outputs only.",
        confidence=str(best.get("confidence") or "LOW").upper(),
        evidence=int(best.get("remaining_closed") or best.get("evidence") or 0),
        risk_level="LOW",
        data={"best_simulation": best, "top_simulations": simulations[:10]},
    )


def research_response_opinion(
    research: DebateIntervention,
    risk: DebateIntervention,
    simulation: DebateIntervention,
) -> DebateIntervention:
    risks = risk.data.get("risks", [])
    best = simulation.data.get("best_simulation", {})
    content = "Research response: evidence remains observational; CIO should require manual approval."
    if risks:
        content = "Research response: risk objections noted; prefer shadow validation before production."
    return DebateIntervention(
        agent="research_director",
        role="Research Director",
        stage="research_response",
        content=content,
        confidence=simulation.confidence if best else research.confidence,
        evidence=max(research.evidence, simulation.evidence),
        risk_level=risk.risk_level,
        data={"risk_objections": risks, "best_simulation": best},
    )


def _top_labels(rows: Any, *, key: str) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    output = []
    for row in rows[:10]:
        if isinstance(row, dict):
            output.append({"label": row.get(key) or row.get("label") or row.get("value"), "evidence": row.get("closed") or row.get("evidence") or row.get("evidence_count") or 0, **row})
    return output


def _top_conditions(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    output = []
    for row in rows[:10]:
        if isinstance(row, dict):
            output.append({"condition": row.get("conditions"), "evidence": row.get("remaining_closed") or 0, **row})
    return output


def _simulator_candidates(reports: dict[str, Any]) -> list[dict[str, Any]]:
    simulator = reports.get("strategy_simulator", {})
    simulations = []
    for section in ("single_filters", "double_filters", "triple_filters", "best_configs"):
        key = "configs" if section == "best_configs" else "simulations"
        simulations.extend(simulator.get(section, {}).get(key, [])[:10])
    for item in simulator.get("recommendations", {}).get("recommendations", [])[:10]:
        if not isinstance(item, dict) or str(item.get("action")) == "Insufficient data":
            continue
        simulations.append(
            {
                "simulation_type": "recommendation",
                "conditions": item.get("conditions") or [],
                "trades_eliminated": item.get("trades_lost", 0),
                "remaining_closed": item.get("evidence", 0),
                "profit_factor": item.get("expected_pf"),
                "total_r": item.get("expected_total_r"),
                "delta_total_r": item.get("expected_improvement", item.get("expected_total_r")),
                "confidence": item.get("confidence", "LOW"),
            }
        )
    return [item for item in simulations if isinstance(item, dict)]


def _baseline_closed(reports: dict[str, Any]) -> int:
    try:
        return int(
            float(
                reports.get("strategy_simulator", {})
                .get("overview", {})
                .get("baseline", {})
                .get("closed", 0)
                or 0
            )
        )
    except (TypeError, ValueError):
        return 0


def _max_risk_level(levels: Any) -> str:
    ranks = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "EXTREME": 3}
    max_level = "LOW"
    for level in levels:
        normalized = str(level).upper()
        if ranks.get(normalized, 0) > ranks[max_level]:
            max_level = normalized
    return max_level


def _max_evidence(items: list[dict[str, Any]]) -> int:
    values = []
    for item in items:
        try:
            values.append(int(float(item.get("evidence") or 0)))
        except (TypeError, ValueError):
            pass
    return max(values) if values else 0


def _confidence(evidence: int) -> str:
    if evidence >= 80:
        return "HIGH"
    if evidence >= 30:
        return "MEDIUM"
    return "LOW"
