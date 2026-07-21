from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

from trading_signals.agents.agent_activity import record_agent_execution
from trading_signals.agents.qic_runtime import utc_now
from trading_signals.agents.qic_models import DebateIntervention
from trading_signals.agents.risk_agent import classify_trade_reduction_risk
from trading_signals.agents.research_agent import load_research_reports


def run_debate_engine(
    *,
    reports_root: Path = Path("reports"),
    activity_path: Path = Path("data") / "qic" / "agent_activity.json",
    enabled_agents: list[str] | None = None,
) -> dict[str, Any]:
    enabled = set(enabled_agents or ("research_director", "strategy_director", "risk_director", "simulation_director"))
    reports = load_research_reports(reports_root)
    interventions: list[DebateIntervention] = []
    research = _run_or_skip("research_director", enabled, lambda: research_director_opinion(reports), activity_path, inputs=len(reports))
    interventions.append(research)
    strategy = _run_or_skip("strategy_director", enabled, lambda: strategy_director_opinion(research), activity_path, inputs=research.evidence)
    interventions.append(strategy)
    risk = _run_or_skip("risk_director", enabled, lambda: risk_director_opinion(strategy, reports), activity_path, inputs=len(strategy.data.get("rule_candidates", [])))
    interventions.append(risk)
    simulation = _run_or_skip("simulation_director", enabled, lambda: simulation_director_opinion(strategy, reports), activity_path, inputs=len(strategy.data.get("rule_candidates", [])))
    interventions.append(simulation)
    interventions.append(
        _run_or_skip(
            "research_director",
            enabled,
            lambda: research_response_opinion(research, risk, simulation),
            activity_path,
            inputs=3,
        )
    )
    return {
        "pipeline": ["Research", "Strategy", "Risk", "Simulation", "Research", "CIO"],
        "interventions": [item.to_dict() for item in interventions],
        "reports_loaded": {
            key: sorted(value.keys()) if isinstance(value, dict) else []
            for key, value in reports.items()
        },
        "enabled_agents": sorted(enabled),
    }


def _run_or_skip(
    agent: str,
    enabled: set[str],
    operation: Any,
    activity_path: Path,
    *,
    inputs: int,
) -> DebateIntervention:
    if agent in enabled:
        return _recorded_opinion(agent, operation, activity_path, inputs=inputs)
    return DebateIntervention(
        agent=agent,
        role=agent.replace("_", " ").title(),
        stage="disabled",
        content="Agent disabled by QIC_ENABLED_AGENTS.",
        confidence="LOW",
        evidence=0,
        risk_level="LOW",
        data={"disabled": True},
    )


def _recorded_opinion(
    agent: str,
    operation: Any,
    activity_path: Path,
    *,
    inputs: int,
) -> DebateIntervention:
    started_at = utc_now()
    started = perf_counter()
    try:
        result = operation()
    except Exception:
        record_agent_execution(
            agent,
            started_at=started_at,
            status="failed",
            duration_ms=(perf_counter() - started) * 1000,
            inputs_processed=inputs,
            path=activity_path,
        )
        raise
    record_agent_execution(
        agent,
        started_at=started_at,
        status="completed",
        duration_ms=(perf_counter() - started) * 1000,
        inputs_processed=inputs,
        outputs_generated=1,
        supported=0 if result.risk_level in {"HIGH", "EXTREME"} else 1,
        opposed=1 if result.risk_level in {"HIGH", "EXTREME"} else 0,
        proposals_generated=len(result.data.get("rule_candidates", [])) if agent == "strategy_director" else 0,
        proposals_blocked=len(result.data.get("risks", [])) if agent == "risk_director" else 0,
        simulations_run=len(result.data.get("top_simulations", [])) if agent == "simulation_director" else 0,
        path=activity_path,
    )
    return result


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
    simulations = sorted(simulations, key=lambda item: float(item.get("composite_score") or 0), reverse=True)
    best = simulations[0] if simulations else {}
    return DebateIntervention(
        agent="simulation_director",
        role="Simulation Director",
        stage="simulation",
        content="Validated available candidates with Strategy Simulator outputs only.",
        confidence=str(best.get("confidence") or "LOW").upper(),
        evidence=int(best.get("remaining_closed") or best.get("evidence") or 0),
        risk_level="LOW",
        data={"best_simulation": best, "top_simulations": simulations[:50]},
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
    baseline = simulator.get("overview", {}).get("baseline", {}) if isinstance(simulator.get("overview"), dict) else {}
    simulations = []
    for section, source, complexity in (
        ("single_filters", "single_filter", 1),
        ("double_filters", "double_filter", 2),
        ("best_configs", "best_config", 2),
    ):
        key = "configs" if section == "best_configs" else "simulations"
        for item in simulator.get(section, {}).get(key, [])[:100]:
            if isinstance(item, dict):
                simulations.append(_normalize_simulation_candidate(item, baseline, source=source, complexity=complexity))
    for item in simulator.get("recommendations", {}).get("recommendations", [])[:100]:
        if not isinstance(item, dict) or str(item.get("action")) == "Insufficient data":
            continue
        simulations.append(
            _normalize_simulation_candidate(
                {
                    "simulation_type": "recommendation",
                    "conditions": item.get("conditions") or [],
                    "trades_eliminated": item.get("trades_lost", 0),
                    "remaining_closed": item.get("evidence", 0),
                    "profit_factor": item.get("expected_pf"),
                    "total_r": item.get("expected_total_r"),
                    "delta_total_r": item.get("expected_improvement", item.get("expected_total_r")),
                    "confidence": item.get("confidence", "LOW"),
                },
                baseline,
                source="recommendation",
                complexity=2,
            )
        )
    return [item for item in simulations if isinstance(item, dict)]


def _normalize_simulation_candidate(
    item: dict[str, Any],
    baseline: dict[str, Any],
    *,
    source: str,
    complexity: int,
) -> dict[str, Any]:
    candidate = dict(item)
    baseline_closed = _float_value(baseline.get("closed")) or (
        (_float_value(candidate.get("trades_eliminated")) or 0) + (_float_value(candidate.get("remaining_closed")) or 0)
    )
    trades_eliminated = _float_value(candidate.get("trades_eliminated")) or 0.0
    remaining_closed = _float_value(candidate.get("remaining_closed") or candidate.get("evidence")) or 0.0
    trade_reduction_pct = _float_value(candidate.get("trade_reduction_pct"))
    if trade_reduction_pct is None:
        trade_reduction_pct = round(trades_eliminated / baseline_closed * 100, 4) if baseline_closed else 0.0
    candidate["source"] = source
    candidate["complexity"] = complexity
    candidate["baseline_profit_factor"] = _float_value(baseline.get("profit_factor"))
    candidate["baseline_total_r"] = _float_value(baseline.get("total_r"))
    candidate["baseline_closed"] = int(baseline_closed)
    candidate["trade_reduction_pct"] = trade_reduction_pct
    candidate["remaining_closed"] = int(remaining_closed)
    candidate["composite_score"] = _composite_score(candidate, baseline, source=source, complexity=complexity)
    return candidate


def _composite_score(candidate: dict[str, Any], baseline: dict[str, Any], *, source: str, complexity: int) -> float:
    baseline_pf = _float_value(baseline.get("profit_factor")) or 0.0
    baseline_total_r = _float_value(baseline.get("total_r")) or 0.0
    baseline_closed = _float_value(baseline.get("closed")) or (
        (_float_value(candidate.get("trades_eliminated")) or 0) + (_float_value(candidate.get("remaining_closed")) or 0)
    )
    baseline_drawdown = _float_value(baseline.get("drawdown")) or 0.0
    profit_factor = _float_value(candidate.get("profit_factor")) or 0.0
    total_r = _float_value(candidate.get("total_r")) or 0.0
    remaining_closed = _float_value(candidate.get("remaining_closed")) or 0.0
    trade_reduction_pct = _float_value(candidate.get("trade_reduction_pct")) or 0.0
    delta_pf = _float_value(candidate.get("delta_pf"))
    if delta_pf is None:
        delta_pf = profit_factor - baseline_pf
    delta_total_r = _float_value(candidate.get("delta_total_r"))
    if delta_total_r is None:
        delta_total_r = total_r - baseline_total_r
    drawdown = _float_value(candidate.get("drawdown")) or baseline_drawdown
    drawdown_improvement = drawdown - baseline_drawdown
    retention = max(0.0, min(1.0, remaining_closed / baseline_closed)) if baseline_closed else 0.0
    evidence_score = min(1.0, remaining_closed / 200.0) if remaining_closed else 0.0
    total_scale = max(abs(baseline_total_r), 10.0)
    score = 0.0
    score += delta_pf * 18.0
    score += (delta_total_r / total_scale) * 14.0
    score += retention * 16.0
    score += evidence_score * 10.0
    score += min(max(drawdown_improvement, -10.0), 10.0)
    if trade_reduction_pct <= 40:
        score += 8.0
    elif trade_reduction_pct <= 60:
        score += 2.0
    else:
        score -= (trade_reduction_pct - 60.0) * 1.5
    if source == "single_filter":
        score += 4.0
    elif complexity >= 3:
        score -= 4.0
    if profit_factor < 1.05 or total_r <= 0 or remaining_closed < 200:
        score -= 25.0
    return round(score, 4)


def _float_value(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


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
