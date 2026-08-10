from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


FUNNEL_COUNT_KEYS = [
    "raw_setups_evaluated",
    "candidates_created",
    "rejected_by_score",
    "rejected_by_quality_gates",
    "rejected_by_lifecycle_publishability",
    "observed_by_relaxation_shadow_v1",
    "v1_trades_created",
    "v1_skips_created",
    "candidates_reaching_publish_signal",
    "published_signals",
    "rejected_by_trading_paused",
]

REASON_STAGE_KEYS = [
    "score",
    "quality",
    "lifecycle_publishability",
    "relaxation_shadow_v1",
    "publishing",
]

SCORE_REJECTION_TOKENS = {
    "quality_score_failed",
    "setup_score_below_threshold",
    "score_below_threshold",
    "setup_score_failed",
    "paper_rejected_below_low",
}

QUALITY_REJECTION_TOKENS = {
    "secondary_setup_requirements_failed",
    "directional_confluence_failed",
    "market_structure_range",
    "market_structure_range_penalty",
    "distance_to_liquidity_failed",
    "distance_to_liquidity_extreme",
    "body_ratio_below_threshold",
    "timeframe_alignment_penalty",
    "timeframe_alignment_failed",
    "against_htf",
    "higher_timeframe_contradicts_long",
    "late_entry_filter",
    "pullback_bad_location",
    "risk_plan_failed",
}


def utc_now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def new_candidate_funnel_cycle(*, scan_run_id: str, started_at: str | None = None) -> dict[str, Any]:
    return {
        "scan_run_id": scan_run_id,
        "started_at": started_at or utc_now_iso(),
        "finished_at": None,
        "counts": {key: 0 for key in FUNNEL_COUNT_KEYS},
        "rejection_reasons": {key: {} for key in REASON_STAGE_KEYS},
    }


def increment_candidate_funnel(
    cycle: dict[str, Any],
    key: str,
    *,
    reason: str | None = None,
    reason_stage: str | None = None,
    amount: int = 1,
) -> None:
    if key not in FUNNEL_COUNT_KEYS:
        raise ValueError(f"Unknown candidate funnel counter: {key}")
    counts = cycle.setdefault("counts", {})
    counts[key] = int(counts.get(key, 0)) + amount
    if reason and reason_stage:
        add_candidate_funnel_reason(cycle, reason_stage, reason, amount=amount)


def add_candidate_funnel_reason(cycle: dict[str, Any], stage: str, reason: str, *, amount: int = 1) -> None:
    if stage not in REASON_STAGE_KEYS:
        raise ValueError(f"Unknown candidate funnel reason stage: {stage}")
    reasons = cycle.setdefault("rejection_reasons", {}).setdefault(stage, {})
    for token in split_reason_tokens(reason):
        reasons[token] = int(reasons.get(token, 0)) + amount


def split_reason_tokens(reason: str | None) -> list[str]:
    if not reason:
        return []
    tokens: list[str] = []
    for chunk in str(reason).replace(",", "|").split("|"):
        token = chunk.strip()
        if token:
            tokens.append(token)
    return tokens


def classify_rejection_stage(
    *,
    rejection_reasons: list[str] | tuple[str, ...] | None = None,
    failed_filters: list[str] | tuple[str, ...] | None = None,
) -> str:
    tokens = {
        token
        for item in [*(rejection_reasons or []), *(failed_filters or [])]
        for token in split_reason_tokens(str(item))
    }
    if tokens & SCORE_REJECTION_TOKENS:
        return "score"
    if tokens & QUALITY_REJECTION_TOKENS:
        return "quality"
    if tokens:
        return "quality"
    return "unknown"


def record_candidate_rejection(
    cycle: dict[str, Any],
    *,
    rejection_reasons: list[str] | tuple[str, ...] | None = None,
    failed_filters: list[str] | tuple[str, ...] | None = None,
    fallback_reason: str = "unknown",
) -> str:
    stage = classify_rejection_stage(rejection_reasons=rejection_reasons, failed_filters=failed_filters)
    reason = "|".join([*list(rejection_reasons or []), *list(failed_filters or [])]) or fallback_reason
    if stage == "score":
        increment_candidate_funnel(cycle, "rejected_by_score", reason=reason, reason_stage="score")
    else:
        increment_candidate_funnel(cycle, "rejected_by_quality_gates", reason=reason, reason_stage="quality")
    return stage


def record_relaxation_shadow_observation(cycle: dict[str, Any], observation: dict[str, Any] | None) -> None:
    if observation is None:
        return
    increment_candidate_funnel(cycle, "observed_by_relaxation_shadow_v1")
    reason = str(observation.get("skip_reason") or "")
    if bool(observation.get("trade_created")):
        increment_candidate_funnel(cycle, "v1_trades_created")
    else:
        increment_candidate_funnel(
            cycle,
            "v1_skips_created",
            reason=reason or "unknown_skip",
            reason_stage="relaxation_shadow_v1",
        )


def build_candidate_funnel_report(cycles: list[dict[str, Any]], *, rolling_window: int = 5) -> dict[str, Any]:
    normalized = [normalize_cycle(cycle) for cycle in cycles]
    latest = normalized[-1] if normalized else new_candidate_funnel_cycle(scan_run_id="none")
    rolling_cycles = normalized[-rolling_window:]
    rolling_counts = aggregate_counts(rolling_cycles)
    rolling_reasons = aggregate_reasons(rolling_cycles)
    top_stage = top_disappearance_stage(rolling_counts)
    conclusion = classify_candidate_funnel_conclusion(rolling_counts)
    return {
        "generated_at": utc_now_iso(),
        "rolling_window": rolling_window,
        "cycles_total": len(normalized),
        "latest_cycle": latest,
        "rolling_last_5_counts": rolling_counts,
        "top_disappearance_stage": top_stage,
        "top_rejection_reasons_per_stage": top_reasons_per_stage(rolling_reasons),
        "conclusion": conclusion,
    }


def normalize_cycle(cycle: dict[str, Any]) -> dict[str, Any]:
    counts = dict(cycle.get("counts", {}))
    reasons = dict(cycle.get("rejection_reasons", {}))
    return {
        "scan_run_id": cycle.get("scan_run_id", "unknown"),
        "started_at": cycle.get("started_at"),
        "finished_at": cycle.get("finished_at"),
        "counts": {key: int(counts.get(key, 0) or 0) for key in FUNNEL_COUNT_KEYS},
        "rejection_reasons": {
            stage: {str(reason): int(count or 0) for reason, count in dict(reasons.get(stage, {})).items()}
            for stage in REASON_STAGE_KEYS
        },
    }


def aggregate_counts(cycles: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for cycle in cycles:
        counter.update({key: int(cycle.get("counts", {}).get(key, 0) or 0) for key in FUNNEL_COUNT_KEYS})
    return {key: int(counter.get(key, 0)) for key in FUNNEL_COUNT_KEYS}


def aggregate_reasons(cycles: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    result: dict[str, Counter[str]] = {stage: Counter() for stage in REASON_STAGE_KEYS}
    for cycle in cycles:
        for stage in REASON_STAGE_KEYS:
            result[stage].update(dict(cycle.get("rejection_reasons", {}).get(stage, {})))
    return {stage: dict(counter) for stage, counter in result.items()}


def top_reasons_per_stage(reasons: dict[str, dict[str, int]], *, limit: int = 5) -> dict[str, list[dict[str, Any]]]:
    return {
        stage: [{"reason": reason, "count": count} for reason, count in Counter(items).most_common(limit)]
        for stage, items in reasons.items()
    }


def top_disappearance_stage(counts: dict[str, int]) -> dict[str, Any]:
    stage_counts = {
        "score_gate": int(counts.get("rejected_by_score", 0)),
        "quality_gate": int(counts.get("rejected_by_quality_gates", 0)),
        "lifecycle_publishability": int(counts.get("rejected_by_lifecycle_publishability", 0)),
        "v1_gap": max(
            0,
            int(counts.get("rejected_by_lifecycle_publishability", 0))
            - int(counts.get("observed_by_relaxation_shadow_v1", 0)),
        ),
        "publishing": max(
            0,
            int(counts.get("candidates_reaching_publish_signal", 0)) - int(counts.get("published_signals", 0)),
        ),
    }
    name, value = max(stage_counts.items(), key=lambda item: item[1])
    return {"stage": name if value > 0 else "none", "count": int(value), "stage_counts": stage_counts}


def classify_candidate_funnel_conclusion(counts: dict[str, int]) -> str:
    raw = int(counts.get("raw_setups_evaluated", 0))
    candidates = int(counts.get("candidates_created", 0))
    score = int(counts.get("rejected_by_score", 0))
    quality = int(counts.get("rejected_by_quality_gates", 0))
    lifecycle = int(counts.get("rejected_by_lifecycle_publishability", 0))
    v1_observed = int(counts.get("observed_by_relaxation_shadow_v1", 0))
    reaching_publish = int(counts.get("candidates_reaching_publish_signal", 0))
    published = int(counts.get("published_signals", 0))

    if raw == 0:
        return "no_raw_candidates"
    if score >= max(quality, lifecycle, 1):
        return "score_gate_bottleneck"
    if quality >= max(score, lifecycle, 1):
        return "quality_gate_bottleneck"
    if lifecycle > 0 and v1_observed == 0:
        return "v1_placement_still_too_late"
    if lifecycle >= max(score, quality, 1):
        return "lifecycle_publishability_bottleneck"
    if reaching_publish > 0 and published == 0:
        return "publishing_bottleneck"
    return "no_clear_bottleneck"


def load_candidate_funnel_state(data_path: Path) -> dict[str, Any]:
    state_file = data_path / "runtime" / "candidate_funnel_state.json"
    if not state_file.exists():
        return {"cycles": []}
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"cycles": []}
    cycles = data.get("cycles", [])
    return {"cycles": cycles if isinstance(cycles, list) else []}


def finalize_candidate_funnel_cycle(
    cycle: dict[str, Any],
    *,
    data_path: Path,
    reports_path: Path = Path("reports"),
    max_cycles: int = 50,
) -> dict[str, Any]:
    cycle["finished_at"] = cycle.get("finished_at") or utc_now_iso()
    state = load_candidate_funnel_state(data_path)
    cycles = [normalize_cycle(item) for item in state.get("cycles", [])]
    cycles.append(normalize_cycle(cycle))
    cycles = cycles[-max_cycles:]
    report = build_candidate_funnel_report(cycles)
    write_candidate_funnel_outputs(report, data_path=data_path, reports_path=reports_path, cycles=cycles)
    return report


def write_candidate_funnel_outputs(
    report: dict[str, Any],
    *,
    data_path: Path,
    reports_path: Path,
    cycles: list[dict[str, Any]] | None = None,
) -> dict[str, Path]:
    runtime_path = data_path / "runtime"
    runtime_path.mkdir(parents=True, exist_ok=True)
    reports_path.mkdir(parents=True, exist_ok=True)
    cycles_to_write = cycles if cycles is not None else [report.get("latest_cycle", {})]
    state_file = runtime_path / "candidate_funnel_state.json"
    audit_json = reports_path / "candidate_funnel_audit.json"
    audit_md = reports_path / "candidate_funnel_audit.md"
    state_file.write_text(
        json.dumps({"updated_at": report.get("generated_at"), "cycles": cycles_to_write}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    audit_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    audit_md.write_text(format_candidate_funnel_markdown(report), encoding="utf-8")
    return {"state": state_file, "audit_json": audit_json, "audit_md": audit_md}


def format_candidate_funnel_markdown(report: dict[str, Any]) -> str:
    latest_counts = report.get("latest_cycle", {}).get("counts", {})
    rolling_counts = report.get("rolling_last_5_counts", {})
    top_stage = report.get("top_disappearance_stage", {})
    reasons = report.get("top_rejection_reasons_per_stage", {})
    lines = [
        "# Candidate Funnel Audit",
        "",
        f"Generated at: {report.get('generated_at', '')}",
        f"Conclusion: {report.get('conclusion', 'unknown')}",
        f"Top disappearance stage: {top_stage.get('stage', 'none')} ({top_stage.get('count', 0)})",
        "",
        "## Latest Cycle Counts",
        "",
    ]
    lines.extend(_format_counts(latest_counts))
    lines.extend(["", "## Rolling Last 5 Cycles Counts", ""])
    lines.extend(_format_counts(rolling_counts))
    lines.extend(["", "## Top Rejection Reasons Per Stage", ""])
    for stage in REASON_STAGE_KEYS:
        items = reasons.get(stage, [])
        lines.append(f"### {stage}")
        if not items:
            lines.append("- none")
            continue
        for item in items:
            lines.append(f"- {item.get('reason')}: {item.get('count')}")
    lines.append("")
    return "\n".join(lines)


def _format_counts(counts: dict[str, Any]) -> list[str]:
    return [f"- {key}: {int(counts.get(key, 0) or 0)}" for key in FUNNEL_COUNT_KEYS]
