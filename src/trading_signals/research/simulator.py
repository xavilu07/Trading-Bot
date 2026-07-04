from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Any

from trading_signals.research.dataset import load_research_dataset
from trading_signals.research.statistics import compute_metrics, confidence_level, normalize_group_value, rounded, to_float


SAFE_CATEGORICAL_FEATURES = (
    "symbol",
    "direction",
    "setup",
    "setup_type",
    "strategy",
    "session",
    "utc_hour",
    "opened_weekday",
    "market_regime",
    "location",
    "trade_location",
    "entry_zone",
    "entry_context",
    "score_bucket",
    "rr_bucket",
    "volume_ratio_bucket",
    "rsi_bucket",
    "bos",
    "break_of_structure",
    "liquidity_sweep",
    "liquidity_distance_bucket",
    "htf_alignment",
    "ltf_alignment",
    "trend_1h",
    "trend_4h",
    "paper_level",
    "rr_valid",
    "late_entry_from_bos",
)

SAFE_NUMERIC_THRESHOLDS = {
    "score": (("<", 60), ("<", 70), ("<", 80), (">=", 70), (">=", 80), (">=", 90)),
    "rr": (("<", 1.5), ("<", 2), (">=", 2), (">=", 3)),
    "volume_ratio": (("<", 0.8), ("<", 1.0), (">=", 1.2), (">=", 1.8)),
    "rsi": (("<", 35), ("<", 45), (">=", 55), (">=", 65)),
    "liquidity_distance": (("<", 1), (">=", 2), (">=", 4)),
}

BANNED_FILTER_FEATURES = {
    "outcome",
    "status",
    "result_r",
    "mfe_r",
    "mae_r",
    "closed_at",
    "updated_at",
    "candles_held",
    "holding_candles",
    "holding_hours",
    "holding_candles_bucket",
}

REPORTS = (
    "overview",
    "single_filters",
    "double_filters",
    "triple_filters",
    "best_configs",
    "worst_configs",
    "recommendations",
)


def run_strategy_simulator(
    *,
    data_path: Path = Path("data"),
    reports_path: Path = Path("reports") / "strategy_simulator",
    min_evidence: int = 20,
    max_conditions: int = 60,
) -> dict[str, Any]:
    dataset = load_research_dataset(data_path)
    rows = dataset["rows"]
    baseline = compute_metrics(rows)
    conditions = build_filter_conditions(rows, min_evidence=min_evidence, max_conditions=max_conditions)
    single = run_exclusion_simulations(rows, baseline, conditions, size=1, min_evidence=min_evidence)
    double = run_exclusion_simulations(rows, baseline, conditions, size=2, min_evidence=min_evidence)
    triple = run_exclusion_simulations(rows, baseline, conditions, size=3, min_evidence=min_evidence)
    best_configs = run_keep_configurations(rows, baseline, conditions, min_evidence=min_evidence)
    all_filters = [*single, *double, *triple]
    worst_configs = sorted(all_filters, key=lambda item: (item["delta_total_r"], item["delta_pf"]))[:100]
    recommendations = build_simulator_recommendations(single, double, triple, best_configs)
    reports = {
        "overview": {
            "source": dataset["source"],
            "baseline": baseline,
            "eligible_conditions": conditions,
            "pre_trade_only": True,
            "excluded_filter_features": sorted(BANNED_FILTER_FEATURES),
        },
        "single_filters": {"simulations": single},
        "double_filters": {"simulations": double},
        "triple_filters": {"simulations": triple},
        "best_configs": {"configs": best_configs},
        "worst_configs": {"configs": worst_configs},
        "recommendations": {"recommendations": recommendations},
    }
    paths = write_reports(reports_path, reports)
    return {
        "reports_path": str(reports_path),
        "overview": reports["overview"],
        "paths": {name: {kind: str(path) for kind, path in report_paths.items()} for name, report_paths in paths.items()},
    }


def build_filter_conditions(
    rows: list[dict[str, Any]],
    *,
    min_evidence: int = 20,
    max_conditions: int = 60,
) -> list[dict[str, Any]]:
    conditions: list[dict[str, Any]] = []
    for feature in SAFE_CATEGORICAL_FEATURES:
        if feature in BANNED_FILTER_FEATURES:
            continue
        counts: dict[str, int] = {}
        for row in rows:
            if to_float(row.get("result_r")) is None:
                continue
            value = normalize_group_value(row.get(feature))
            if value == "UNKNOWN":
                continue
            counts[value] = counts.get(value, 0) + 1
        for value, evidence in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:8]:
            if evidence >= min_evidence:
                conditions.append(
                    {
                        "feature": feature,
                        "operator": "==",
                        "value": value,
                        "evidence": evidence,
                        "label": f"exclude {feature}={value}",
                    }
                )
    for feature, thresholds in SAFE_NUMERIC_THRESHOLDS.items():
        if feature in BANNED_FILTER_FEATURES:
            continue
        for operator, threshold in thresholds:
            evidence = sum(
                1
                for row in rows
                if to_float(row.get("result_r")) is not None
                and _compare(to_float(row.get(feature)), operator, threshold)
            )
            if evidence >= min_evidence:
                conditions.append(
                    {
                        "feature": feature,
                        "operator": operator,
                        "value": threshold,
                        "evidence": evidence,
                        "label": f"exclude {feature}{operator}{threshold}",
                    }
                )
    return sorted(conditions, key=lambda item: item["evidence"], reverse=True)[:max_conditions]


def run_exclusion_simulations(
    rows: list[dict[str, Any]],
    baseline: dict[str, Any],
    conditions: list[dict[str, Any]],
    *,
    size: int,
    min_evidence: int,
) -> list[dict[str, Any]]:
    simulations = []
    for condition_group in combinations(conditions, size):
        result = simulate_exclusion(rows, baseline, list(condition_group))
        if result["remaining_closed"] < min_evidence or result["removed_closed"] < min_evidence:
            continue
        simulations.append(result)
    return sorted(simulations, key=lambda item: (item["delta_pf"], item["delta_total_r"]), reverse=True)[:250]


def run_keep_configurations(
    rows: list[dict[str, Any]],
    baseline: dict[str, Any],
    conditions: list[dict[str, Any]],
    *,
    min_evidence: int,
) -> list[dict[str, Any]]:
    configs = []
    keep_conditions = [condition for condition in conditions if condition["operator"] in {"==", ">="}]
    for size in (2, 3):
        for condition_group in combinations(keep_conditions, size):
            result = simulate_keep_only(rows, baseline, list(condition_group))
            if result["remaining_closed"] < min_evidence:
                continue
            configs.append(result)
    return sorted(configs, key=lambda item: (item["profit_factor"], item["total_r"], item["remaining_closed"]), reverse=True)[:250]


def simulate_exclusion(rows: list[dict[str, Any]], baseline: dict[str, Any], conditions: list[dict[str, Any]]) -> dict[str, Any]:
    removed = [row for row in rows if any(matches_condition(row, condition) for condition in conditions)]
    remaining = [row for row in rows if row not in removed]
    metrics = compute_metrics(remaining)
    removed_metrics = compute_metrics(removed)
    return _simulation_result(
        simulation_type="exclude",
        baseline=baseline,
        conditions=conditions,
        metrics=metrics,
        removed_metrics=removed_metrics,
    )


def simulate_keep_only(rows: list[dict[str, Any]], baseline: dict[str, Any], conditions: list[dict[str, Any]]) -> dict[str, Any]:
    remaining = [row for row in rows if all(matches_condition(row, condition) for condition in conditions)]
    removed = [row for row in rows if row not in remaining]
    metrics = compute_metrics(remaining)
    removed_metrics = compute_metrics(removed)
    return _simulation_result(
        simulation_type="keep_only",
        baseline=baseline,
        conditions=conditions,
        metrics=metrics,
        removed_metrics=removed_metrics,
    )


def matches_condition(row: dict[str, Any], condition: dict[str, Any]) -> bool:
    feature = condition["feature"]
    if feature in BANNED_FILTER_FEATURES:
        return False
    operator = condition["operator"]
    expected = condition["value"]
    if operator == "==":
        return normalize_group_value(row.get(feature)) == str(expected)
    return _compare(to_float(row.get(feature)), operator, float(expected))


def build_simulator_recommendations(
    single: list[dict[str, Any]],
    double: list[dict[str, Any]],
    triple: list[dict[str, Any]],
    best_configs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates = sorted([*single, *double, *triple], key=lambda item: (item["delta_pf"], item["delta_total_r"]), reverse=True)
    recommendations = []
    for item in candidates[:20]:
        if item["delta_pf"] <= 0 and item["delta_total_r"] <= 0:
            continue
        recommendations.append(
            {
                "action": "Simulate filter before production",
                "conditions": item["conditions"],
                "expected_pf": item["profit_factor"],
                "expected_total_r": item["total_r"],
                "trades_lost": item["trades_eliminated"],
                "confidence": item["confidence"],
                "evidence": item["remaining_closed"],
                "expected_improvement": item["delta_total_r"],
            }
        )
    for item in best_configs[:10]:
        recommendations.append(
            {
                "action": "Prioritize configuration in shadow",
                "conditions": item["conditions"],
                "expected_pf": item["profit_factor"],
                "expected_total_r": item["total_r"],
                "trades_lost": item["trades_eliminated"],
                "confidence": item["confidence"],
                "evidence": item["remaining_closed"],
                "expected_improvement": item["delta_total_r"],
            }
        )
    if not recommendations:
        recommendations.append(
            {
                "action": "Insufficient data",
                "conditions": [],
                "expected_pf": 0.0,
                "expected_total_r": 0.0,
                "trades_lost": 0,
                "confidence": "LOW",
                "evidence": 0,
                "expected_improvement": 0.0,
            }
        )
    return recommendations[:50]


def write_reports(reports_path: Path, reports: dict[str, Any]) -> dict[str, dict[str, Path]]:
    reports_path.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name in REPORTS:
        payload = reports[name]
        json_path = reports_path / f"{name}.json"
        md_path = reports_path / f"{name}.md"
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text(to_markdown(name, payload), encoding="utf-8")
        paths[name] = {"json": json_path, "markdown": md_path}
    return paths


def to_markdown(name: str, payload: dict[str, Any]) -> str:
    lines = [f"# {name.replace('_', ' ').title()}", ""]
    if name == "overview":
        lines.extend(_key_values(payload.get("baseline", {})))
        lines.append("")
        lines.append("## Eligible Conditions")
        lines.extend(_table(payload.get("eligible_conditions", [])[:100]))
    elif "simulations" in payload:
        lines.extend(_table(payload["simulations"]))
    elif "configs" in payload:
        lines.extend(_table(payload["configs"]))
    elif "recommendations" in payload:
        lines.extend(_table(payload["recommendations"]))
    else:
        lines.append(json.dumps(payload, indent=2, sort_keys=True))
    return "\n".join(lines) + "\n"


def _simulation_result(
    *,
    simulation_type: str,
    baseline: dict[str, Any],
    conditions: list[dict[str, Any]],
    metrics: dict[str, Any],
    removed_metrics: dict[str, Any],
) -> dict[str, Any]:
    remaining_closed = metrics["closed"]
    removed_closed = removed_metrics["closed"]
    baseline_closed = baseline["closed"] or 1
    return {
        "simulation_type": simulation_type,
        "conditions": [condition["label"] for condition in conditions],
        "condition_details": conditions,
        "trades_remaining": metrics["trades"],
        "trades_eliminated": removed_metrics["trades"],
        "remaining_closed": remaining_closed,
        "removed_closed": removed_closed,
        "winrate": metrics["winrate"],
        "profit_factor": metrics["profit_factor"],
        "total_r": metrics["total_r"],
        "expectancy": metrics["expectancy"],
        "avg_r": metrics["avg_r"],
        "average_win": metrics["average_win"],
        "average_loss": metrics["average_loss"],
        "drawdown": metrics["drawdown"],
        "trade_reduction_pct": rounded(removed_closed / baseline_closed * 100),
        "delta_pf": rounded(metrics["profit_factor"] - baseline["profit_factor"]),
        "delta_wr": rounded(metrics["winrate"] - baseline["winrate"]),
        "delta_total_r": rounded(metrics["total_r"] - baseline["total_r"]),
        "confidence": confidence_level(remaining_closed),
        "evidence": remaining_closed,
        "removed_metrics": removed_metrics,
    }


def _compare(value: float | None, operator: str, expected: float) -> bool:
    if value is None:
        return False
    if operator == "<":
        return value < expected
    if operator == "<=":
        return value <= expected
    if operator == ">":
        return value > expected
    if operator == ">=":
        return value >= expected
    return False


def _key_values(payload: dict[str, Any]) -> list[str]:
    return [f"- {key}: {value}" for key, value in payload.items()]


def _table(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["No data."]
    columns = _columns(rows)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows[:100]:
        lines.append("| " + " | ".join(_md(row.get(column, "")) for column in columns) + " |")
    return lines


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    preferred = [
        "conditions",
        "action",
        "expected_pf",
        "expected_total_r",
        "trades_lost",
        "trades_remaining",
        "trades_eliminated",
        "remaining_closed",
        "removed_closed",
        "winrate",
        "profit_factor",
        "total_r",
        "expectancy",
        "drawdown",
        "trade_reduction_pct",
        "delta_pf",
        "delta_wr",
        "delta_total_r",
        "confidence",
        "evidence",
        "label",
        "feature",
        "operator",
        "value",
    ]
    available = {key for row in rows for key in row}
    return [key for key in preferred if key in available][:10]


def _md(value: Any) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, sort_keys=True)
    return str(value).replace("|", "\\|")
