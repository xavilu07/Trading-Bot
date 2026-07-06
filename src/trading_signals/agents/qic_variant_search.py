from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trading_signals.agents.risk_agent import classify_trade_reduction_risk
from trading_signals.research.dataset import load_research_dataset
from trading_signals.research.simulator import matches_condition, simulate_exclusion
from trading_signals.research.statistics import compute_metrics, confidence_level, rounded


DEFAULT_VARIANT_REPORTS_PATH = Path("reports") / "qic"


def run_qic_variant_search(
    proposal: dict[str, Any] | None,
    *,
    data_path: Path = Path("data"),
    reports_path: Path = DEFAULT_VARIANT_REPORTS_PATH,
    min_evidence: int = 20,
) -> dict[str, Any]:
    if not isinstance(proposal, dict) or proposal.get("action") != "REQUIRES_VARIANT_SEARCH":
        result = {
            "status": "skipped",
            "reason": "proposal_does_not_require_variant_search",
            "selected_variant": None,
            "variants": [],
        }
        write_variant_search_reports(result, reports_path)
        return result

    dataset = load_research_dataset(data_path)
    rows = list(dataset.get("rows") or [])
    baseline = compute_metrics(rows)
    original_conditions = _proposal_conditions(proposal)
    variants = evaluate_variants(
        rows,
        baseline,
        original_conditions,
        min_evidence=min_evidence,
    )
    valid = [item for item in variants if item.get("valid")]
    selected = _select_variant(valid)
    status = "variant_found" if selected else "no_valid_variant"
    result = {
        "status": status,
        "source": dataset.get("source"),
        "baseline": baseline,
        "original_proposal": {
            "id": proposal.get("id"),
            "title": proposal.get("title"),
            "action": proposal.get("action"),
            "risk_level": proposal.get("risk_level"),
            "trade_reduction_pct": proposal.get("trade_reduction_pct"),
            "conditions": proposal.get("context", {}).get("conditions", []),
        },
        "criteria": {
            "max_trade_reduction_pct": 60.0,
            "preferred_trade_reduction_pct": 40.0,
            "min_evidence": min_evidence,
            "min_removed_evidence": min_evidence,
            "min_profit_factor": 1.05,
            "requires_positive_total_r": True,
        },
        "selected_variant": selected,
        "variants": variants,
    }
    write_variant_search_reports(result, reports_path)
    return result


def evaluate_variants(
    rows: list[dict[str, Any]],
    baseline: dict[str, Any],
    original_conditions: list[dict[str, Any]],
    *,
    min_evidence: int = 20,
) -> list[dict[str, Any]]:
    candidates = generate_variant_conditions(original_conditions)
    evaluated = []
    seen: set[str] = set()
    for candidate in candidates:
        key = json.dumps(candidate, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        simulation = _simulate_variant(rows, baseline, candidate)
        invalid_reasons = _invalid_reasons(simulation, min_evidence=min_evidence)
        simulation["valid"] = not invalid_reasons
        simulation["invalid_reason"] = ", ".join(invalid_reasons)
        simulation["selection_score"] = _selection_score(simulation)
        evaluated.append(simulation)
    return sorted(
        evaluated,
        key=lambda item: (
            not bool(item.get("valid")),
            -float(item.get("profit_factor") or 0),
            -float(item.get("total_r") or 0),
            float(item.get("trade_reduction_pct") or 0),
            -int(item.get("remaining_closed") or 0),
        ),
    )


def generate_variant_conditions(original_conditions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [_normalize_condition(condition) for condition in original_conditions]
    normalized = [condition for condition in normalized if condition]
    variants: list[dict[str, Any]] = []

    for index, condition in enumerate(normalized):
        variants.append(
            {
                "variant_type": "drop_to_single_condition",
                "description": f"Use only {condition['label']}",
                "match_mode": "any",
                "conditions": [condition],
            }
        )
        for softened in _softened_condition(condition):
            variants.append(
                {
                    "variant_type": "soften_single_threshold",
                    "description": f"Use softened {softened['label']}",
                    "match_mode": "any",
                    "conditions": [softened],
                }
            )
        remaining = list(normalized)
        for softened in _softened_condition(condition):
            replacement = list(remaining)
            replacement[index] = softened
            variants.append(
                {
                    "variant_type": "soften_threshold_in_combo",
                    "description": f"Replace {condition['label']} with {softened['label']}",
                    "match_mode": "any",
                    "conditions": replacement,
                }
            )

    if len(normalized) >= 2:
        variants.append(
            {
                "variant_type": "conjunctive_filter",
                "description": "Require all original conditions before excluding",
                "match_mode": "all",
                "conditions": normalized,
            }
        )
    return variants


def apply_variant_to_proposal(
    proposal: dict[str, Any],
    variant_result: dict[str, Any],
) -> dict[str, Any]:
    selected = variant_result.get("selected_variant")
    updated = dict(proposal)
    if isinstance(selected, dict):
        updated.update(
            {
                "action": "PROPOSE_VARIANT",
                "title": f"CIO variant proposal: {', '.join(str(item) for item in selected.get('conditions', []))}",
                "hypothesis": "A less aggressive variant preserves more trades while improving baseline metrics.",
                "expected_pf": selected.get("profit_factor"),
                "expected_total_r": selected.get("total_r"),
                "trades_lost": selected.get("trades_eliminated"),
                "evidence": selected.get("remaining_closed"),
                "risk_level": selected.get("risk_level"),
                "trade_reduction_pct": selected.get("trade_reduction_pct"),
                "risk_objections": selected.get("risk_objections", []),
                "rationale": (
                    f"Selected QIC variant {selected.get('variant_type')} with PF {selected.get('profit_factor')} "
                    f"and TotalR {selected.get('total_r')}; trade reduction {selected.get('trade_reduction_pct')}%."
                ),
            }
        )
        context = dict(updated.get("context") or {})
        context.update(
            {
                "variant_search": {
                    "status": variant_result.get("status"),
                    "variant_type": selected.get("variant_type"),
                    "description": selected.get("description"),
                    "match_mode": selected.get("match_mode"),
                    "conditions": selected.get("conditions"),
                    "condition_details": selected.get("condition_details"),
                },
                "conditions": selected.get("conditions", []),
                "condition_details": selected.get("condition_details", []),
            }
        )
        updated["context"] = context
        return updated

    updated["action"] = "REQUIRES_MANUAL_RESEARCH"
    updated["hypothesis"] = "No statistically acceptable less-aggressive variant was found automatically."
    objections = list(updated.get("risk_objections") or [])
    if "no_profitable_variant_found" not in objections:
        objections.append("no_profitable_variant_found")
    updated["risk_objections"] = objections
    updated["rationale"] = "QIC variant search found no variant satisfying absolute PF, positive TotalR, reduction, and evidence criteria."
    return updated


def write_variant_search_reports(result: dict[str, Any], reports_path: Path = DEFAULT_VARIANT_REPORTS_PATH) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "variant_search.json"
    md_path = reports_path / "variant_search.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_variant_search_markdown(result), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def _proposal_conditions(proposal: dict[str, Any]) -> list[dict[str, Any]]:
    context = proposal.get("context") if isinstance(proposal.get("context"), dict) else {}
    details = context.get("condition_details") if isinstance(context, dict) else None
    if isinstance(details, list) and details:
        return [condition for condition in details if isinstance(condition, dict)]
    labels = context.get("conditions") if isinstance(context, dict) else []
    return [_parse_condition_label(str(label)) for label in labels or []]


def _normalize_condition(condition: dict[str, Any]) -> dict[str, Any]:
    feature = str(condition.get("feature") or "").strip()
    operator = str(condition.get("operator") or "").strip()
    value = condition.get("value")
    if not feature or not operator:
        return {}
    normalized = {
        "feature": feature,
        "operator": operator,
        "value": _numeric_or_text(value),
    }
    normalized["label"] = str(condition.get("label") or _condition_label(normalized))
    evidence = condition.get("evidence")
    if evidence is not None:
        normalized["evidence"] = evidence
    return normalized


def _softened_condition(condition: dict[str, Any]) -> list[dict[str, Any]]:
    feature = str(condition.get("feature"))
    operator = str(condition.get("operator"))
    value = _to_float(condition.get("value"))
    thresholds: list[float] = []
    if operator == ">=" and feature == "volume_ratio":
        thresholds = [threshold for threshold in (1.5, 1.8) if value is None or threshold > value]
    elif operator == ">=" and feature == "rsi":
        thresholds = [threshold for threshold in (60.0, 65.0) if value is None or threshold > value]
    softened = []
    for threshold in thresholds:
        next_condition = {
            "feature": feature,
            "operator": operator,
            "value": threshold,
        }
        next_condition["label"] = _condition_label(next_condition)
        softened.append(next_condition)
    if feature == "rsi" and operator == ">=":
        softened.append(
            {
                "feature": "rsi_bucket",
                "operator": "==",
                "value": "overbought",
                "label": "exclude rsi_bucket=overbought",
            }
        )
    return softened


def _simulate_variant(rows: list[dict[str, Any]], baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    conditions = list(candidate.get("conditions") or [])
    match_mode = str(candidate.get("match_mode") or "any")
    if match_mode == "all":
        result = _simulate_exclusion_all(rows, baseline, conditions)
    else:
        result = simulate_exclusion(rows, baseline, conditions)
    result.update(
        {
            "variant_type": candidate.get("variant_type"),
            "description": candidate.get("description"),
            "match_mode": match_mode,
        }
    )
    risk = classify_trade_reduction_risk(int(result.get("trades_eliminated") or 0), int(baseline.get("closed") or 0))
    result["risk_level"] = risk["risk_level"]
    result["risk_objections"] = [risk["risk"]] if risk["risk"] else []
    return result


def _simulate_exclusion_all(rows: list[dict[str, Any]], baseline: dict[str, Any], conditions: list[dict[str, Any]]) -> dict[str, Any]:
    removed = [row for row in rows if all(matches_condition(row, condition) for condition in conditions)]
    remaining = [row for row in rows if row not in removed]
    metrics = compute_metrics(remaining)
    removed_metrics = compute_metrics(removed)
    baseline_closed = baseline["closed"] or 1
    return {
        "simulation_type": "exclude",
        "conditions": [condition["label"] for condition in conditions],
        "condition_details": conditions,
        "trades_remaining": metrics["trades"],
        "trades_eliminated": removed_metrics["trades"],
        "remaining_closed": metrics["closed"],
        "removed_closed": removed_metrics["closed"],
        "winrate": metrics["winrate"],
        "profit_factor": metrics["profit_factor"],
        "total_r": metrics["total_r"],
        "expectancy": metrics["expectancy"],
        "avg_r": metrics["avg_r"],
        "average_win": metrics["average_win"],
        "average_loss": metrics["average_loss"],
        "drawdown": metrics["drawdown"],
        "trade_reduction_pct": rounded(removed_metrics["closed"] / baseline_closed * 100),
        "delta_pf": rounded(metrics["profit_factor"] - baseline["profit_factor"]),
        "delta_wr": rounded(metrics["winrate"] - baseline["winrate"]),
        "delta_total_r": rounded(metrics["total_r"] - baseline["total_r"]),
        "confidence": confidence_level(metrics["closed"]),
        "evidence": metrics["closed"],
        "removed_metrics": removed_metrics,
    }


def _invalid_reasons(simulation: dict[str, Any], *, min_evidence: int) -> list[str]:
    reasons = []
    if float(simulation.get("profit_factor") or 0) < 1.05:
        reasons.append("profit_factor_below_1_05")
    if float(simulation.get("total_r") or 0) <= 0:
        reasons.append("total_r_not_positive")
    if float(simulation.get("trade_reduction_pct") or 0) > 60.0:
        reasons.append("trade_reduction_above_60")
    if int(simulation.get("remaining_closed") or 0) < min_evidence:
        reasons.append("evidence_below_minimum")
    if int(simulation.get("removed_closed") or 0) < min_evidence:
        reasons.append("removed_evidence_below_minimum")
    return reasons


def _select_variant(valid_variants: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not valid_variants:
        return None
    return sorted(
        valid_variants,
        key=lambda item: (
            float(item.get("trade_reduction_pct") or 0) > 40.0,
            -float(item.get("profit_factor") or 0),
            -float(item.get("total_r") or 0),
            float(item.get("trade_reduction_pct") or 0),
            -int(item.get("remaining_closed") or 0),
            len(item.get("condition_details") or []),
        ),
    )[0]


def _selection_score(simulation: dict[str, Any]) -> float:
    reduction_penalty = float(simulation.get("trade_reduction_pct") or 0) / 100
    return rounded(float(simulation.get("delta_total_r") or 0) + float(simulation.get("delta_pf") or 0) - reduction_penalty)


def _parse_condition_label(label: str) -> dict[str, Any]:
    text = label.strip()
    if text.startswith("exclude "):
        text = text[len("exclude "):]
    for operator in (">=", "<=", "==", "<", ">"):
        if operator in text:
            feature, value = text.split(operator, 1)
            condition = {"feature": feature.strip(), "operator": operator, "value": _numeric_or_text(value.strip())}
            condition["label"] = _condition_label(condition)
            return condition
    return {}


def _condition_label(condition: dict[str, Any]) -> str:
    return f"exclude {condition['feature']}{condition['operator']}{condition['value']}"


def _numeric_or_text(value: Any) -> Any:
    numeric = _to_float(value)
    if numeric is None:
        return str(value)
    if numeric.is_integer():
        return int(numeric)
    return numeric


def _to_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _variant_search_markdown(result: dict[str, Any]) -> str:
    lines = ["# QIC Variant Search V1", ""]
    lines.append(f"- status: {result.get('status')}")
    if result.get("reason"):
        lines.append(f"- reason: {result.get('reason')}")
    selected = result.get("selected_variant")
    lines.append("")
    lines.append("## Selected Variant")
    if isinstance(selected, dict):
        lines.extend(_table([selected]))
    else:
        lines.append("No valid variant selected.")
    lines.append("")
    lines.append("## Candidate Variants")
    variants = result.get("variants") if isinstance(result.get("variants"), list) else []
    lines.extend(_table(variants[:25]))
    return "\n".join(lines) + "\n"


def _table(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["No data."]
    columns = [
        "variant_type",
        "conditions",
        "match_mode",
        "valid",
        "invalid_reason",
        "risk_level",
        "trade_reduction_pct",
        "profit_factor",
        "total_r",
        "remaining_closed",
        "trades_eliminated",
    ]
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(_md(row.get(column, "")) for column in columns) + " |")
    return lines


def _md(value: Any) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, sort_keys=True)
    return str(value).replace("|", "\\|")
