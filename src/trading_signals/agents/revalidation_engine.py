from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.agents.research_memory import load_research_memory, save_research_memory
from trading_signals.agents.strategy_knowledge_base import (
    load_strategy_knowledge_base,
    normalize_conditions,
    save_strategy_knowledge_base,
)
from trading_signals.agents.qic_runtime import atomic_write_json, atomic_write_text


def run_revalidation_engine(
    *,
    knowledge_base_path: Path = Path("data") / "qic" / "strategy_knowledge_base.json",
    research_memory_path: Path = Path("data") / "qic" / "research_memory.json",
    reports_root: Path = Path("reports"),
    output_path: Path = Path("reports") / "qic",
    min_new_trades: int = 50,
    degradation_pf_drop_pct: float = 15.0,
) -> dict[str, Any]:
    kb = load_strategy_knowledge_base(knowledge_base_path)
    memory = load_research_memory(research_memory_path)
    simulator_rows = _load_simulator_rows(reports_root / "strategy_simulator")
    results = []
    for item in (kb.get("items") or {}).values():
        if not isinstance(item, dict):
            continue
        result = revalidate_edge(
            item,
            simulator_rows=simulator_rows,
            min_new_trades=min_new_trades,
            degradation_pf_drop_pct=degradation_pf_drop_pct,
        )
        results.append(result)
        _update_memory_revalidation(memory, item, result)
        _update_knowledge_item(item, result)
    save_research_memory(memory, research_memory_path)
    save_strategy_knowledge_base(kb, knowledge_base_path)
    report = {
        "status": "ok",
        "results": results,
        "summary": _summary(results),
    }
    write_revalidation_reports(report, output_path=output_path)
    return report


def revalidate_edge(
    item: dict[str, Any],
    *,
    simulator_rows: list[dict[str, Any]],
    min_new_trades: int = 50,
    degradation_pf_drop_pct: float = 15.0,
) -> dict[str, Any]:
    conditions = item.get("rule_conditions") or []
    current = _find_current_metrics(conditions, simulator_rows)
    previous_pf = _float(item.get("last_expected_pf"))
    previous_total_r = _float(item.get("last_expected_total_r"))
    previous_evidence = _float(
        item.get("last_revalidated_evidence")
        if item.get("last_revalidated_evidence") is not None
        else item.get("last_evidence")
    )
    if current is None:
        return {
            "knowledge_item_id": item.get("id"),
            "conditions": normalize_conditions(conditions),
            "result": "insufficient_new_data",
            "reason": "current_metrics_not_found",
            "previous_pf": previous_pf,
            "current_pf": None,
        }
    current_evidence = _float(current.get("evidence") or current.get("remaining_closed") or current.get("trades_remaining"))
    new_trades = current_evidence - previous_evidence
    current_pf = _float(current.get("profit_factor") or current.get("expected_pf") or current.get("pf"))
    current_total_r = _float(current.get("total_r") or current.get("expected_total_r"))
    if new_trades < min_new_trades:
        result = "insufficient_new_data"
        reason = "not_enough_new_trades"
    elif current_pf < 1.0:
        result = "edge_invalidated"
        reason = "pf_below_one"
    elif previous_pf > 0 and ((previous_pf - current_pf) / previous_pf * 100.0) > degradation_pf_drop_pct:
        result = "edge_degraded"
        reason = "pf_drop_exceeds_threshold"
    elif current_pf >= previous_pf and current_total_r >= previous_total_r:
        result = "edge_improved"
        reason = "pf_and_total_r_improved"
    else:
        result = "edge_still_valid"
        reason = "metrics_remain_positive"
    return {
        "knowledge_item_id": item.get("id"),
        "conditions": normalize_conditions(conditions),
        "result": result,
        "reason": reason,
        "previous_pf": previous_pf,
        "current_pf": current_pf,
        "previous_total_r": previous_total_r,
        "current_total_r": current_total_r,
        "previous_evidence": previous_evidence,
        "current_evidence": current_evidence,
        "new_trades": new_trades,
    }


def write_revalidation_reports(report: dict[str, Any], *, output_path: Path = Path("reports") / "qic") -> dict[str, Path]:
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "revalidation.json"
    md_path = output_path / "revalidation.md"
    atomic_write_json(json_path, report)
    atomic_write_text(md_path, _markdown(report))
    return {"json": json_path, "markdown": md_path}


def _load_simulator_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for filename in ("single_filters.json", "double_filters.json", "triple_filters.json", "best_configs.json", "recommendations.json"):
        file_path = path / filename
        if not file_path.exists():
            continue
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        rows.extend(_extract_rows(raw))
    return rows


def _extract_rows(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if not isinstance(raw, dict):
        return []
    # "simulations" is the key run_strategy_simulator actually writes for single_filters.json,
    # double_filters.json and triple_filters.json. It was missing here, so those three files —
    # the only place single-condition edges are reported — were silently parsed as empty and
    # every KB edge fell back to whatever happened to appear in best_configs/recommendations.
    for key in ("results", "simulations", "recommendations", "best_configs", "single_filters", "double_filters", "triple_filters", "configs"):
        value = raw.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return [raw] if raw.get("conditions") else []


def _find_current_metrics(conditions: Any, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    target = normalize_conditions(conditions)
    for row in rows:
        row_conditions = row.get("conditions") or row.get("rule_conditions") or row.get("filters") or row.get("condition")
        if normalize_conditions(row_conditions) == target:
            return row
    return None


def _update_knowledge_item(item: dict[str, Any], result: dict[str, Any]) -> None:
    """Write the revalidation verdict back onto the knowledge base item.

    The verdict used to reach only reports/qic/revalidation.*, which nothing
    downstream reads. The proposal pipeline reads the KB item, so it kept quoting
    `last_expected_pf` from the day the edge was discovered: on 2026-08-20 it
    proposed implementing edge_fc1437682982 at its original in-sample PF 2.6415
    over 20 trades, in the same cycle that revalidation scored it PF 0.919 over
    1003 trades and returned `edge_invalidated`.

    The measured numbers are kept in their own `last_revalidated_*` fields rather
    than overwriting `last_expected_pf`, which the proposal pipeline owns and
    means something different (a simulator projection, not a measurement).
    """
    item["last_revalidation_result"] = result
    item["last_revalidated_at"] = _now()
    verdict = str(result.get("result") or "")
    if verdict == "insufficient_new_data":
        # No fresh measurement; leave the stored measurement as it stands.
        return
    for field, key in (
        ("last_revalidated_pf", "current_pf"),
        ("last_revalidated_total_r", "current_total_r"),
        ("last_revalidated_evidence", "current_evidence"),
    ):
        value = result.get(key)
        if value is not None:
            item[field] = value
    if verdict == "edge_invalidated":
        item["status"] = "retired"
    elif verdict == "edge_degraded":
        item["status"] = "needs_revalidation"


def _update_memory_revalidation(memory: dict[str, Any], item: dict[str, Any], result: dict[str, Any]) -> None:
    target_conditions = normalize_conditions(item.get("rule_conditions") or [])
    experiments = memory.setdefault("experiments", {})
    for experiment in experiments.values():
        if normalize_conditions(experiment.get("normalized_conditions") or []) != target_conditions:
            continue
        experiment["last_revalidation_result"] = result
        if result["result"] == "edge_degraded":
            experiment["current_status"] = "degraded"
        elif result["result"] == "edge_invalidated":
            experiment["current_status"] = "retired"
        elif result["result"] in {"edge_improved", "edge_still_valid"} and int(experiment.get("times_seen", 0)) >= 3:
            experiment["current_status"] = "candidate"


def _summary(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        key = str(result.get("result") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _markdown(report: dict[str, Any]) -> str:
    lines = ["# QIC Revalidation", ""]
    lines.append(f"Results: {len(report.get('results') or [])}")
    lines.append("")
    for key, value in (report.get("summary") or {}).items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("| knowledge_item_id | result | previous_pf | current_pf | new_trades | reason |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for item in report.get("results") or []:
        lines.append(
            f"| {_md(item.get('knowledge_item_id'))} | {_md(item.get('result'))} | {_md(item.get('previous_pf'))} | "
            f"{_md(item.get('current_pf'))} | {_md(item.get('new_trades'))} | {_md(item.get('reason'))} |"
        )
    return "\n".join(lines) + "\n"


def _float(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _md(value: Any) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, sort_keys=True)
    return str(value).replace("|", "\\|")


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()
