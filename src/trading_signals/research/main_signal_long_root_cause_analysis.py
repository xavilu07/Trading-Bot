from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


TOXIC_MIN_TRADES = 10
SURVIVOR_MIN_TRADES = 10
TINY_SURVIVOR_MIN_TRADES = 5
CRITICAL_MIN_TRADES = 30


ROOT_CAUSE_RULES: tuple[tuple[str, tuple[str, ...], Callable[[dict[str, Any]], bool]], ...] = (
    ("MAIN_SIGNAL LONG + bullish_sweep", ("bullish_sweep",), lambda row: _is_main_long(row) and _is_bullish_sweep(row)),
    ("MAIN_SIGNAL LONG + against_htf", ("against_htf",), lambda row: _is_main_long(row) and _is_against_htf(row)),
    ("MAIN_SIGNAL LONG + near_support", ("near_support",), lambda row: _is_main_long(row) and _is_near_support(row)),
    ("MAIN_SIGNAL LONG + HIGH_VOLATILITY", ("HIGH_VOLATILITY",), lambda row: _is_main_long(row) and _market_regime(row) == "HIGH_VOLATILITY"),
    ("MAIN_SIGNAL LONG + RANGING", ("RANGING",), lambda row: _is_main_long(row) and _market_regime(row) == "RANGING"),
    ("MAIN_SIGNAL LONG + BREAKOUT", ("BREAKOUT",), lambda row: _is_main_long(row) and _entry_context(row) == "BREAKOUT"),
    (
        "MAIN_SIGNAL LONG + bullish_sweep + against_htf",
        ("bullish_sweep", "against_htf"),
        lambda row: _is_main_long(row) and _is_bullish_sweep(row) and _is_against_htf(row),
    ),
    (
        "MAIN_SIGNAL LONG + bullish_sweep + near_support",
        ("bullish_sweep", "near_support"),
        lambda row: _is_main_long(row) and _is_bullish_sweep(row) and _is_near_support(row),
    ),
    (
        "MAIN_SIGNAL LONG + against_htf + near_support",
        ("against_htf", "near_support"),
        lambda row: _is_main_long(row) and _is_against_htf(row) and _is_near_support(row),
    ),
    (
        "MAIN_SIGNAL LONG + HIGH_VOLATILITY + near_support",
        ("HIGH_VOLATILITY", "near_support"),
        lambda row: _is_main_long(row) and _market_regime(row) == "HIGH_VOLATILITY" and _is_near_support(row),
    ),
    ("MAIN_SIGNAL LONG + score_bucket 60-69", ("score_bucket 60-69",), lambda row: _is_main_long(row) and _score_bucket(row.get("score")) == "60-69"),
    ("MAIN_SIGNAL LONG + score_bucket 70-79", ("score_bucket 70-79",), lambda row: _is_main_long(row) and _score_bucket(row.get("score")) == "70-79"),
    ("MAIN_SIGNAL LONG + score_bucket 90+", ("score_bucket 90+",), lambda row: _is_main_long(row) and _score_bucket(row.get("score")) == "90+"),
    (
        "MAIN_SIGNAL LONG + distance_to_liquidity_penalty",
        ("distance_to_liquidity_penalty",),
        lambda row: _is_main_long(row) and _has_token(row, "distance_to_liquidity_penalty"),
    ),
    (
        "MAIN_SIGNAL LONG + directional_confluence_failed",
        ("directional_confluence_failed",),
        lambda row: _is_main_long(row) and _has_token(row, "directional_confluence_failed"),
    ),
    (
        "MAIN_SIGNAL LONG + body_ratio_below_threshold",
        ("body_ratio_below_threshold",),
        lambda row: _is_main_long(row) and _has_token(row, "body_ratio_below_threshold"),
    ),
    (
        "MAIN_SIGNAL LONG + timeframe_alignment_penalty",
        ("timeframe_alignment_penalty",),
        lambda row: _is_main_long(row) and _has_token(row, "timeframe_alignment_penalty"),
    ),
)


def analyze_main_signal_long_root_cause(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    all_trades = load_canonical_closed_trades(data_path)
    main_long = [row for row in all_trades if _is_main_long(row)]
    main_short = [row for row in all_trades if _is_main_short(row)]
    secondary_long = [row for row in all_trades if _is_secondary_long(row)]
    non_main_long = [row for row in all_trades if not _is_main_long(row)]
    existing_blocked_main_long = [row for row in main_long if _is_existing_production_block_context(row)]
    remaining_main_long = [row for row in main_long if not _is_existing_production_block_context(row)]

    breakdowns = _build_breakdowns(main_long)
    groups = _flatten_groups(breakdowns)
    toxic_single_factors = _rank_toxic(groups)
    survivor_longs = _rank_survivors(groups, min_trades=SURVIVOR_MIN_TRADES, min_pf=1.10)
    tiny_promising_longs = _rank_survivors(groups, min_trades=TINY_SURVIVOR_MIN_TRADES, max_trades=9, min_pf=1.30)
    root_causes = _root_cause_counterfactuals(all_trades)
    toxic_root_causes = [row for row in root_causes if _is_toxic_root_cause(row)]
    single_root_causes = [row for row in toxic_root_causes if len(row.get("factors", [])) == 1]
    multi_root_causes = [row for row in toxic_root_causes if len(row.get("factors", [])) > 1]

    counterfactuals = _counterfactuals(
        all_trades=all_trades,
        main_long=main_long,
        existing_blocked_main_long=existing_blocked_main_long,
        remaining_main_long=remaining_main_long,
        worst_single=single_root_causes[0] if single_root_causes else None,
        worst_multi=multi_root_causes[0] if multi_root_causes else None,
    )
    comparisons = _comparisons(
        main_long=main_long,
        main_short=main_short,
        secondary_long=secondary_long,
        non_main_long=non_main_long,
    )
    answers = _answers(
        main_long_metrics=_metrics(main_long),
        existing_blocked_metrics=_metrics(existing_blocked_main_long),
        remaining_metrics=_metrics(remaining_main_long),
        toxic_single_factors=toxic_single_factors,
        survivor_longs=survivor_longs,
        tiny_promising_longs=tiny_promising_longs,
        root_causes=root_causes,
        single_root_causes=single_root_causes,
        multi_root_causes=multi_root_causes,
        counterfactuals=counterfactuals,
    )

    return {
        "scope": "MAIN_SIGNAL_LONG_ROOT_CAUSE_ANALYSIS",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "method": (
            "Analyze canonical closed trades where setup_type=MAIN_SIGNAL and direction=long, "
            "then discount already blocked bullish_sweep and against_htf+BREAKOUT contexts."
        ),
        "baseline_metrics": _metrics(all_trades),
        "main_signal_long_baseline": _metrics(main_long),
        "comparisons": comparisons,
        "existing_production_blocks": {
            "rules": ["bullish_sweep", "against_htf + BREAKOUT"],
            "covered_metrics": _metrics(existing_blocked_main_long),
            "remaining_after_existing_blocks": _metrics(remaining_main_long),
            "toxicity_covered_r": _round(-float(_metrics(existing_blocked_main_long).get("total_r", 0.0) or 0.0))
            if float(_metrics(existing_blocked_main_long).get("total_r", 0.0) or 0.0) < 0
            else 0.0,
            "remaining_toxic_r": _round(-float(_metrics(remaining_main_long).get("total_r", 0.0) or 0.0))
            if float(_metrics(remaining_main_long).get("total_r", 0.0) or 0.0) < 0
            else 0.0,
        },
        "classification": classify_main_signal_long_root_cause(_metrics(main_long)),
        "breakdowns": breakdowns,
        "toxic_single_factor_clusters": toxic_single_factors,
        "tested_root_causes": root_causes,
        "toxic_root_causes": toxic_root_causes,
        "survivor_longs": survivor_longs,
        "tiny_promising_longs": tiny_promising_longs,
        "counterfactuals": counterfactuals,
        "answers": answers,
        "recommended_action": answers["recommended_action"],
    }


def write_main_signal_long_root_cause_reports(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    markdown_path = reports_path / "main_signal_long_root_cause_analysis.md"
    json_path = reports_path / "main_signal_long_root_cause_analysis.json"
    markdown_path.write_text(format_main_signal_long_root_cause_markdown(result), encoding="utf-8")
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return {"markdown": markdown_path, "json": json_path}


def format_main_signal_long_root_cause_markdown(result: dict[str, Any]) -> str:
    answers = result.get("answers", {})
    existing = result.get("existing_production_blocks", {})
    counterfactuals = result.get("counterfactuals", {})
    lines = [
        "# MAIN_SIGNAL_LONG_ROOT_CAUSE_ANALYSIS",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        f"Method: {result.get('method')}",
        f"Classification: {result.get('classification')}",
        f"Recommended action: {result.get('recommended_action')}",
        "",
        "## Executive Summary",
        "",
        f"- Global baseline: {_metrics_inline(result.get('baseline_metrics', {}))}",
        f"- MAIN_SIGNAL LONG baseline: {_metrics_inline(result.get('main_signal_long_baseline', {}))}",
        f"- Existing blocks covered: {_metrics_inline(existing.get('covered_metrics', {}))}",
        f"- Remaining after existing blocks: {_metrics_inline(existing.get('remaining_after_existing_blocks', {}))}",
        f"- Toxicity already covered R: {existing.get('toxicity_covered_r', 0)}",
        f"- Remaining toxic R: {existing.get('remaining_toxic_r', 0)}",
        f"- Is MAIN_SIGNAL LONG globally toxic? {answers.get('globally_toxic', 'UNKNOWN')}",
        f"- Still toxic after existing blocks? {answers.get('still_toxic_after_existing_blocks', 'UNKNOWN')}",
        f"- Next best non-overlapping root cause: {answers.get('next_best_non_overlapping_root_cause', 'none')}",
        f"- Smallest high-impact rule: {answers.get('smallest_rule_least_collateral', 'none')}",
        f"- Dominant issue: {answers.get('dominant_issue', 'unknown')}",
        "",
        "## MAIN_SIGNAL LONG Baseline",
        "",
        *_single_metrics_table(result.get("main_signal_long_baseline", {})),
        "",
        "## Comparisons",
        "",
        *_comparison_table(result.get("comparisons", {})),
        "",
        "## Toxic Root Causes",
        "",
        "Criteria: minimum 10 closed trades, PF < 0.85, TotalR < 0. Ranked by R improvement, damage and collateral.",
        "",
        *_root_cause_table(result.get("toxic_root_causes", [])),
        "",
        "## Toxic Single-Factor Clusters",
        "",
        *_rank_table(result.get("toxic_single_factor_clusters", [])),
        "",
        "## Survivor Longs",
        "",
        "Criteria: minimum 10 closed trades, PF > 1.1 and TotalR > 0.",
        "",
        *_rank_table(result.get("survivor_longs", [])),
        "",
        "## Tiny But Promising Longs",
        "",
        "Criteria: 5-9 closed trades, PF > 1.3 and TotalR > 0.",
        "",
        *_rank_table(result.get("tiny_promising_longs", [])),
        "",
        "## Counterfactuals",
        "",
        *_counterfactual_table(counterfactuals),
        "",
        "## Tested Root Cause Rules",
        "",
        *_root_cause_table(result.get("tested_root_causes", [])),
        "",
        "## Answers",
        "",
    ]
    for question, answer in answers.items():
        if question == "recommended_action":
            continue
        lines.append(f"- {question}: {answer}")
    lines.extend(
        [
            "",
            "## Breakdowns",
            "",
        ]
    )
    for title, key in (
        ("By Symbol", "symbol"),
        ("By Session", "session"),
        ("By Market Regime", "market_regime"),
        ("By Entry Context", "entry_context"),
        ("By Liquidity Sweep", "liquidity_sweep"),
        ("By Trade Location", "trade_location"),
        ("By Trend Alignment", "trend_alignment"),
        ("By HTF Alignment", "htf_alignment"),
        ("By Score Bucket", "score_bucket"),
        ("By Warning", "warning"),
        ("By Penalty", "penalty"),
        ("By Failed Filter", "failed_filter"),
        ("By Rejection Reason", "rejection_reason"),
        ("By Condition Failed", "condition_failed"),
        ("By Volume Ratio Bucket", "volume_ratio_bucket"),
        ("By Body Ratio Bucket", "body_ratio_bucket"),
        ("By Distance To Liquidity Bucket", "distance_to_liquidity_bucket"),
        ("By RR Bucket", "rr_bucket"),
    ):
        lines.extend([f"### {title}", "", *_group_table(result.get("breakdowns", {}).get(key, {}), title), ""])
    lines.extend(["## Recommended Action", "", str(result.get("recommended_action", "KEEP"))])
    return "\n".join(lines).rstrip() + "\n"


def classify_main_signal_long_root_cause(metrics: dict[str, Any]) -> str:
    trades = int(metrics.get("trades", 0) or 0)
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    pf = _pf_float(metrics.get("profit_factor"))
    if total_r >= 0 or pf >= 1:
        return "NOISE"
    if trades >= CRITICAL_MIN_TRADES and total_r <= -10 and pf < 0.85:
        return "CRITICAL"
    if trades >= TOXIC_MIN_TRADES and pf < 1:
        return "IMPORTANT"
    if trades >= 3:
        return "WATCH"
    return "NOISE"


def classify_root_cause(payload: dict[str, Any]) -> str:
    removed = int(payload.get("removed_trades", 0) or 0)
    r_improvement = float(payload.get("r_improvement", 0.0) or 0.0)
    pf_improvement = float(payload.get("pf_improvement", 0.0) or 0.0)
    profitable_lost = int(payload.get("profitable_trades_lost", 0) or 0)
    losing_removed = int(payload.get("losing_trades_removed", 0) or 0)
    removed_pf = _pf_float(payload.get("removed_metrics", {}).get("profit_factor"))
    if removed >= 30 and r_improvement >= 10 and pf_improvement >= 0.10 and losing_removed > profitable_lost and removed_pf < 0.85:
        return "CRITICAL"
    if removed >= TOXIC_MIN_TRADES and r_improvement > 0 and losing_removed >= profitable_lost and removed_pf < 1:
        return "IMPORTANT"
    if removed >= TINY_SURVIVOR_MIN_TRADES:
        return "WATCH"
    return "NOISE"


def _build_breakdowns(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "symbol": _group_summary(rows, "symbol"),
        "session": _group_summary(rows, "session"),
        "market_regime": _group_summary(rows, "market_regime"),
        "entry_context": _group_summary(rows, "entry_context"),
        "liquidity_sweep": _group_summary(rows, "liquidity_sweep"),
        "trade_location": _group_summary(rows, "trade_location"),
        "trend_alignment": _group_summary(rows, "trend_alignment"),
        "htf_alignment": _group_summary(rows, "htf_alignment"),
        "score_bucket": _group_summary(rows, "score_bucket"),
        "volume_ratio_bucket": _group_summary(rows, "volume_ratio_bucket"),
        "body_ratio_bucket": _group_summary(rows, "body_ratio_bucket"),
        "distance_to_liquidity_bucket": _group_summary(rows, "distance_to_liquidity_bucket"),
        "rr_bucket": _group_summary(rows, "rr_bucket"),
        "warning": _token_summary(rows, "warnings", "avoidance_warnings"),
        "penalty": _token_summary(rows, "penalties"),
        "failed_filter": _token_summary(rows, "failed_filters"),
        "rejection_reason": _token_summary(rows, "rejection_reasons"),
        "condition_failed": _token_summary(rows, "conditions_failed"),
    }


def _comparisons(
    *,
    main_long: list[dict[str, Any]],
    main_short: list[dict[str, Any]],
    secondary_long: list[dict[str, Any]],
    non_main_long: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "MAIN_SIGNAL_LONG": _comparison_payload(main_long),
        "MAIN_SIGNAL_SHORT": _comparison_payload(main_short),
        "SECONDARY_SIGNAL_LONG": _comparison_payload(secondary_long),
        "NON_MAIN_SIGNAL_LONG": _comparison_payload(non_main_long),
    }


def _comparison_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "metrics": _metrics(rows),
        "top_symbol": _top_distribution(rows, "symbol"),
        "top_session": _top_distribution(rows, "session"),
        "top_regime": _top_distribution(rows, "market_regime"),
        "top_entry_context": _top_distribution(rows, "entry_context"),
        "top_liquidity": _top_distribution(rows, "liquidity_sweep"),
        "top_htf": _top_distribution(rows, "htf_alignment"),
    }


def _root_cause_counterfactuals(all_trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current = _metrics(all_trades)
    results: list[dict[str, Any]] = []
    for name, factors, predicate in ROOT_CAUSE_RULES:
        removed = [row for row in all_trades if predicate(row)]
        without = [row for row in all_trades if not predicate(row)]
        without_metrics = _metrics(without)
        removed_metrics = _metrics(removed)
        payload = {
            "name": name,
            "factors": list(factors),
            "removed_trades": len(removed),
            "pf_before": current["profit_factor"],
            "pf_after": without_metrics["profit_factor"],
            "total_r_before": current["total_r"],
            "total_r_after": without_metrics["total_r"],
            "r_improvement": _round(float(without_metrics["total_r"]) - float(current["total_r"])),
            "pf_improvement": _round(_pf_float(without_metrics["profit_factor"]) - _pf_float(current["profit_factor"])),
            "profitable_trades_lost": int(removed_metrics.get("wins", 0) or 0),
            "losing_trades_removed": int(removed_metrics.get("losses", 0) or 0),
            "removed_metrics": removed_metrics,
        }
        payload["classification"] = classify_root_cause(payload)
        results.append(payload)
    return sorted(
        results,
        key=lambda row: (
            float(row.get("r_improvement", 0.0) or 0.0),
            -int(row.get("profitable_trades_lost", 0) or 0),
            float(row.get("pf_improvement", 0.0) or 0.0),
            int(row.get("removed_trades", 0) or 0),
        ),
        reverse=True,
    )


def _is_toxic_root_cause(row: dict[str, Any]) -> bool:
    metrics = row.get("removed_metrics", {})
    return (
        int(metrics.get("trades", 0) or 0) >= TOXIC_MIN_TRADES
        and _pf_float(metrics.get("profit_factor")) < 0.85
        and float(metrics.get("total_r", 0.0) or 0.0) < 0
    )


def _counterfactuals(
    *,
    all_trades: list[dict[str, Any]],
    main_long: list[dict[str, Any]],
    existing_blocked_main_long: list[dict[str, Any]],
    remaining_main_long: list[dict[str, Any]],
    worst_single: dict[str, Any] | None,
    worst_multi: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "current_global": _metrics(all_trades),
        "without_all_main_signal_long": _remove_payload(all_trades, _is_main_long),
        "without_worst_single_root_cause": _named_remove_payload(all_trades, worst_single),
        "without_worst_multi_factor_root_cause": _named_remove_payload(all_trades, worst_multi),
        "without_bullish_sweep_already_blocked_contexts": _remove_payload(all_trades, _is_bullish_sweep),
        "without_against_htf_breakout_already_blocked_contexts": _remove_payload(all_trades, _is_against_htf_breakout),
        "without_existing_production_blocks": _remove_payload(all_trades, _is_existing_production_block_context),
        "without_remaining_toxic_main_signal_long_after_existing_blocks": _remove_specific_payload(all_trades, remaining_main_long),
        "main_signal_long_existing_block_overlap": {
            "covered_metrics": _metrics(existing_blocked_main_long),
            "remaining_metrics": _metrics(remaining_main_long),
            "covered_share_pct": _round(len(existing_blocked_main_long) / len(main_long) * 100) if main_long else 0.0,
        },
    }


def _remove_payload(all_trades: list[dict[str, Any]], predicate: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
    current = _metrics(all_trades)
    removed = [row for row in all_trades if predicate(row)]
    without = [row for row in all_trades if not predicate(row)]
    without_metrics = _metrics(without)
    return {
        "removed_trades": len(removed),
        "removed_metrics": _metrics(removed),
        "without_metrics": without_metrics,
        "pf_before": current["profit_factor"],
        "pf_after": without_metrics["profit_factor"],
        "total_r_before": current["total_r"],
        "total_r_after": without_metrics["total_r"],
        "winrate_delta": _round(float(without_metrics.get("winrate", 0.0) or 0.0) - float(current.get("winrate", 0.0) or 0.0)),
        "r_improvement": _round(float(without_metrics["total_r"]) - float(current["total_r"])),
    }


def _remove_specific_payload(all_trades: list[dict[str, Any]], removed_rows: list[dict[str, Any]]) -> dict[str, Any]:
    ids = {id(row) for row in removed_rows}
    return _remove_payload(all_trades, lambda row: id(row) in ids)


def _named_remove_payload(all_trades: list[dict[str, Any]], root_cause: dict[str, Any] | None) -> dict[str, Any]:
    if not root_cause:
        return {"name": "none", **_remove_specific_payload(all_trades, [])}
    name = str(root_cause.get("name") or "unknown")
    predicate = next((predicate for candidate_name, _factors, predicate in ROOT_CAUSE_RULES if candidate_name == name), None)
    if predicate is None:
        return {"name": name, **_remove_specific_payload(all_trades, [])}
    return {"name": name, **_remove_payload(all_trades, predicate)}


def _answers(
    *,
    main_long_metrics: dict[str, Any],
    existing_blocked_metrics: dict[str, Any],
    remaining_metrics: dict[str, Any],
    toxic_single_factors: list[dict[str, Any]],
    survivor_longs: list[dict[str, Any]],
    tiny_promising_longs: list[dict[str, Any]],
    root_causes: list[dict[str, Any]],
    single_root_causes: list[dict[str, Any]],
    multi_root_causes: list[dict[str, Any]],
    counterfactuals: dict[str, Any],
) -> dict[str, str]:
    globally_toxic = classify_main_signal_long_root_cause(main_long_metrics) in {"CRITICAL", "IMPORTANT"}
    remaining_class = classify_main_signal_long_root_cause(remaining_metrics)
    still_toxic = remaining_class in {"CRITICAL", "IMPORTANT"}
    next_non_overlapping = _best_non_overlapping_root_cause(root_causes)
    smallest_rule = _smallest_high_impact_rule(root_causes)
    existing_total = float(existing_blocked_metrics.get("total_r", 0.0) or 0.0)
    main_total = float(main_long_metrics.get("total_r", 0.0) or 0.0)
    covered_text = _coverage_text(main_total, existing_total)
    issue = _dominant_issue(toxic_single_factors, root_causes)
    recommended_action = _recommended_action(
        globally_toxic=globally_toxic,
        still_toxic=still_toxic,
        survivor_longs=survivor_longs,
        tiny_promising_longs=tiny_promising_longs,
        next_non_overlapping=next_non_overlapping,
        counterfactuals=counterfactuals,
    )
    return {
        "toxicity_already_covered_by_existing_blocks": covered_text,
        "remaining_toxicity_after_existing_blocks": _metrics_inline(remaining_metrics),
        "next_best_non_overlapping_root_cause": _describe_root_cause(next_non_overlapping),
        "globally_toxic": "YES" if globally_toxic else "NO",
        "still_toxic_after_existing_blocks": "YES" if still_toxic else "NO",
        "block_redefine_or_keep": _block_redefine_or_keep(recommended_action),
        "smallest_rule_least_collateral": _describe_root_cause(smallest_rule),
        "dominant_issue": issue,
        "best_single_root_cause": _describe_root_cause(single_root_causes[0] if single_root_causes else None),
        "best_multi_factor_root_cause": _describe_root_cause(multi_root_causes[0] if multi_root_causes else None),
        "best_survivor": _describe_group(survivor_longs[0]) if survivor_longs else "none",
        "tiny_promising_survivor": _describe_group(tiny_promising_longs[0]) if tiny_promising_longs else "none",
        "recommended_action": recommended_action,
    }


def _recommended_action(
    *,
    globally_toxic: bool,
    still_toxic: bool,
    survivor_longs: list[dict[str, Any]],
    tiny_promising_longs: list[dict[str, Any]],
    next_non_overlapping: dict[str, Any] | None,
    counterfactuals: dict[str, Any],
) -> str:
    if not globally_toxic:
        return "KEEP"
    if still_toxic and next_non_overlapping:
        if survivor_longs or tiny_promising_longs:
            return "REDEFINE_MAIN_SIGNAL_LONG"
        return "PARTIAL_BLOCK"
    without_all = counterfactuals.get("without_all_main_signal_long", {})
    if float(without_all.get("r_improvement", 0.0) or 0.0) > 10 and not survivor_longs:
        return "FULL_BLOCK"
    if survivor_longs:
        return "REDEFINE_MAIN_SIGNAL_LONG"
    return "SHADOW_BLOCK"


def _block_redefine_or_keep(action: str) -> str:
    if action == "FULL_BLOCK":
        return "FULL_BLOCK"
    if action in {"PARTIAL_BLOCK", "SHADOW_BLOCK"}:
        return "PARTIAL_BLOCK"
    if action == "REDEFINE_MAIN_SIGNAL_LONG":
        return "REDEFINE_MAIN_SIGNAL_LONG"
    return "KEEP"


def _best_non_overlapping_root_cause(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [
        row
        for row in rows
        if _is_toxic_root_cause(row)
        and "bullish_sweep" not in set(row.get("factors", []))
        and not {"against_htf", "BREAKOUT"}.issubset(set(row.get("factors", [])))
        and float(row.get("r_improvement", 0.0) or 0.0) > 0
    ]
    ranked = sorted(
        candidates,
        key=lambda row: (
            float(row.get("r_improvement", 0.0) or 0.0),
            _actionable_specificity(row),
            -int(row.get("profitable_trades_lost", 0) or 0),
            float(row.get("pf_improvement", 0.0) or 0.0),
        ),
        reverse=True,
    )
    return ranked[0] if ranked else None


def _smallest_high_impact_rule(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [
        row
        for row in rows
        if _is_toxic_root_cause(row)
        and float(row.get("r_improvement", 0.0) or 0.0) > 0
        and int(row.get("losing_trades_removed", 0) or 0) >= int(row.get("profitable_trades_lost", 0) or 0)
    ]
    return sorted(candidates, key=lambda row: (int(row.get("removed_trades", 0) or 0), -float(row.get("r_improvement", 0.0) or 0.0)))[0] if candidates else None


def _actionable_specificity(row: dict[str, Any]) -> int:
    factors = set(row.get("factors", []))
    broad = {"score_bucket 60-69", "score_bucket 70-79", "score_bucket 90+", "HIGH_VOLATILITY", "RANGING"}
    if factors & {"distance_to_liquidity_penalty", "directional_confluence_failed", "body_ratio_below_threshold", "timeframe_alignment_penalty"}:
        return 3
    if factors & {"against_htf", "near_support", "BREAKOUT"}:
        return 2
    if factors - broad:
        return 1
    return 0


def _coverage_text(main_total: float, covered_total: float) -> str:
    if main_total >= 0:
        return "MAIN_SIGNAL_LONG is not net-negative in this dataset."
    covered_r = abs(min(covered_total, 0.0))
    total_loss = abs(main_total)
    pct = _round(covered_r / total_loss * 100) if total_loss else 0.0
    return f"{covered_r}R covered by existing blocks ({pct}% of MAIN_SIGNAL_LONG net loss)."


def _dominant_issue(toxic_single_factors: list[dict[str, Any]], root_causes: list[dict[str, Any]]) -> str:
    names = " ".join(str(row.get("name") or row.get("dimension") or "") for row in root_causes[:5] + toxic_single_factors[:5]).lower()
    if "bullish_sweep" in names:
        return "liquidity_sweep"
    if "against_htf" in names or "htf" in names:
        return "HTF mismatch"
    if "near_support" in names:
        return "trade_location"
    if "high_volatility" in names or "ranging" in names:
        return "regime"
    if "score_bucket" in names:
        return "score"
    if "distance_to_liquidity" in names:
        return "liquidity_distance"
    return "unknown"


def _flatten_groups(breakdowns: dict[str, dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dimension, groups in breakdowns.items():
        for value, payload in groups.items():
            rows.append(
                {
                    "dimension": dimension,
                    "value": value,
                    "metrics": payload.get("metrics", {}),
                    "classification": payload.get("classification", "NOISE"),
                }
            )
    return rows


def _rank_toxic(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    toxic = []
    for row in groups:
        metrics = row.get("metrics", {})
        if (
            int(metrics.get("trades", 0) or 0) >= TOXIC_MIN_TRADES
            and _pf_float(metrics.get("profit_factor")) < 0.85
            and float(metrics.get("total_r", 0.0) or 0.0) < 0
        ):
            toxic.append(row)
    return sorted(
        toxic,
        key=lambda row: (
            float(row["metrics"].get("total_r", 0.0)),
            _pf_float(row["metrics"].get("profit_factor")),
            -int(row["metrics"].get("trades", 0) or 0),
        ),
    )[:40]


def _rank_survivors(groups: list[dict[str, Any]], *, min_trades: int, min_pf: float, max_trades: int | None = None) -> list[dict[str, Any]]:
    survivors = []
    for row in groups:
        metrics = row.get("metrics", {})
        trades = int(metrics.get("trades", 0) or 0)
        if max_trades is not None and trades > max_trades:
            continue
        if trades >= min_trades and _pf_float(metrics.get("profit_factor")) > min_pf and float(metrics.get("total_r", 0.0) or 0.0) > 0:
            survivors.append(row)
    return sorted(survivors, key=lambda row: (float(row["metrics"].get("total_r", 0.0)), _pf_float(row["metrics"].get("profit_factor"))), reverse=True)


def _group_summary(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[_field_value(row, field)].append(row)
    return _summaries(groups)


def _token_summary(rows: list[dict[str, Any]], *fields: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        values: set[str] = set()
        for field in fields:
            values |= _tokens(row.get(field))
        if not values:
            groups["none"].append(row)
            continue
        for value in sorted(values):
            groups[value].append(row)
    return _summaries(groups)


def _summaries(groups: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    result = {}
    for key, items in sorted(groups.items()):
        metrics = _metrics(items)
        result[key] = {"metrics": metrics, "classification": classify_main_signal_long_root_cause(metrics)}
    return result


def _field_value(row: dict[str, Any], field: str) -> str:
    if field == "score_bucket":
        return _score_bucket(row.get("score"))
    if field == "liquidity_sweep":
        return _liquidity_sweep(row)
    if field == "trend_alignment":
        return _trend_alignment(row)
    if field == "htf_alignment":
        return _htf_alignment(row)
    if field == "direction":
        return _direction(row)
    if field == "setup_type":
        return _setup_type(row)
    if field == "market_regime":
        return _market_regime(row)
    if field == "entry_context":
        return _entry_context(row)
    if field == "volume_ratio_bucket":
        return _ratio_bucket(row.get("volume_ratio"), high=1.2, low=0.8, labels=("volume_high", "volume_mid", "volume_low"))
    if field == "body_ratio_bucket":
        return _ratio_bucket(row.get("body_ratio"), high=0.5, low=0.35, labels=("body_strong", "body_valid", "body_weak"))
    if field == "distance_to_liquidity_bucket":
        return _distance_to_liquidity_bucket(row)
    if field == "rr_bucket":
        return _rr_bucket(row.get("risk_reward"))
    return str(row.get(field) or "UNKNOWN").strip() or "UNKNOWN"


def _is_main_long(row: dict[str, Any]) -> bool:
    return _setup_type(row) == "MAIN_SIGNAL" and _direction(row) == "long"


def _is_main_short(row: dict[str, Any]) -> bool:
    return _setup_type(row) == "MAIN_SIGNAL" and _direction(row) == "short"


def _is_secondary_long(row: dict[str, Any]) -> bool:
    return _setup_type(row) == "SECONDARY_SIGNAL" and _direction(row) == "long"


def _setup_type(row: dict[str, Any]) -> str:
    return str(row.get("setup_type") or "UNKNOWN").strip().upper()


def _direction(row: dict[str, Any]) -> str:
    return str(row.get("direction") or "unknown").strip().lower()


def _market_regime(row: dict[str, Any]) -> str:
    return str(row.get("market_regime") or "UNKNOWN").strip().upper()


def _entry_context(row: dict[str, Any]) -> str:
    return str(row.get("entry_context") or "UNKNOWN").strip().upper()


def _is_existing_production_block_context(row: dict[str, Any]) -> bool:
    return _is_bullish_sweep(row) or _is_against_htf_breakout(row)


def _is_against_htf_breakout(row: dict[str, Any]) -> bool:
    return _is_against_htf(row) and _entry_context(row) == "BREAKOUT"


def _is_bullish_sweep(row: dict[str, Any]) -> bool:
    return _liquidity_sweep(row) == "bullish_sweep" or _liquidity_context(row).lower() == "sweep:bullish_sweep"


def _is_near_support(row: dict[str, Any]) -> bool:
    return str(row.get("trade_location") or "").strip() == "near_support" or _liquidity_context(row).lower() == "location:near_support"


def _is_against_htf(row: dict[str, Any]) -> bool:
    return "against_htf" in _all_tokens(row) or _htf_alignment(row) == "against_htf"


def _has_token(row: dict[str, Any], token: str) -> bool:
    return token.lower() in _all_tokens(row)


def _all_tokens(row: dict[str, Any]) -> set[str]:
    return (
        _tokens(row.get("warnings"))
        | _tokens(row.get("avoidance_warnings"))
        | _tokens(row.get("penalties"))
        | _tokens(row.get("rejection_reasons"))
        | _tokens(row.get("conditions_failed"))
        | _tokens(row.get("failed_filters"))
        | _tokens(row.get("entry_or_rejection_reason"))
        | _tokens(row.get("reasons"))
    )


def _liquidity_sweep(row: dict[str, Any]) -> str:
    sweep = str(row.get("liquidity_sweep") or "").strip()
    if sweep:
        return sweep
    context = _liquidity_context(row).lower()
    if context.startswith("sweep:"):
        return context.split(":", 1)[1]
    return "none"


def _liquidity_context(row: dict[str, Any]) -> str:
    explicit = str(row.get("liquidity_context") or "").strip()
    if explicit:
        return explicit
    sweep = str(row.get("liquidity_sweep") or "").strip()
    if sweep:
        return f"sweep:{sweep}"
    location = str(row.get("trade_location") or "").strip()
    if location and location.upper() != "UNKNOWN":
        return f"location:{location}"
    liquidity_reasons = sorted(reason for reason in _all_tokens(row) if "liquidity" in reason)
    if liquidity_reasons:
        return f"reason:{liquidity_reasons[0]}"
    return "UNKNOWN"


def _trend_alignment(row: dict[str, Any]) -> str:
    explicit = str(row.get("timeframe_alignment") or "").strip().lower()
    if explicit:
        return explicit
    entry = str(row.get("trend_entry") or row.get("trend_1h") or "").strip().lower()
    higher = str(row.get("trend_higher") or row.get("trend_4h") or row.get("trend_higher_timeframe") or "").strip().lower()
    if not entry or not higher:
        return "UNKNOWN"
    if entry == higher:
        return f"aligned_{entry}"
    return f"mixed_{entry}_vs_{higher}"


def _htf_alignment(row: dict[str, Any]) -> str:
    explicit = str(row.get("htf_alignment") or "").strip().lower()
    if explicit:
        return explicit
    direction = _direction(row)
    higher = str(row.get("trend_higher") or row.get("trend_4h") or row.get("trend_higher_timeframe") or "").strip().lower()
    if not direction or not higher:
        return "UNKNOWN"
    if direction == "long" and higher == "bearish":
        return "against_htf"
    if direction == "short" and higher == "bullish":
        return "against_htf"
    if direction == "long" and higher == "bullish":
        return "aligned_with_htf"
    if direction == "short" and higher == "bearish":
        return "aligned_with_htf"
    return f"htf_{higher}"


def _score_bucket(value: object) -> str:
    score = _float(value)
    if score is None:
        return "UNKNOWN"
    if score < 60:
        return "<60"
    if score < 70:
        return "60-69"
    if score < 80:
        return "70-79"
    if score < 90:
        return "80-89"
    return "90+"


def _ratio_bucket(value: object, *, high: float, low: float, labels: tuple[str, str, str]) -> str:
    number = _float(value)
    if number is None:
        return "UNKNOWN"
    if number >= high:
        return labels[0]
    if number >= low:
        return labels[1]
    return labels[2]


def _rr_bucket(value: object) -> str:
    number = _float(value)
    if number is None:
        return "UNKNOWN"
    if number >= 2:
        return "rr_2_plus"
    if number >= 1.5:
        return "rr_1_5_to_2"
    return "rr_below_1_5"


def _distance_to_liquidity_bucket(row: dict[str, Any]) -> str:
    number = _float(
        row.get("distance_to_liquidity_atr")
        or row.get("nearest_distance_to_liquidity_atr")
        or row.get("directional_distance_to_liquidity_atr")
    )
    if number is None:
        return "UNKNOWN"
    if number <= 1.0:
        return "distance_close"
    if number <= 2.5:
        return "distance_valid"
    return "distance_far"


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [_float(row.get("result_r")) for row in rows]
    values = [value for value in values if value is not None]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "trades": len(values),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": _round(len(wins) / len(values) * 100) if values else 0.0,
        "profit_factor": _profit_factor(gross_profit, gross_loss),
        "total_r": _round(sum(values)),
        "avg_r": _round(sum(values) / len(values)) if values else 0.0,
    }


def _profit_factor(gross_profit: float, gross_loss: float) -> float | str:
    if gross_loss > 0:
        return _round(gross_profit / gross_loss)
    if gross_profit > 0:
        return "inf"
    return 0.0


def _tokens(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, set, tuple)):
        return {str(item).strip().lower() for item in value if str(item).strip()}
    text = str(value).strip()
    if not text:
        return set()
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        decoded = None
    if isinstance(decoded, list):
        return {str(item).strip().lower() for item in decoded if str(item).strip()}
    return {item.strip().lower() for item in text.replace("|", ",").replace(";", ",").split(",") if item.strip()}


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float) -> float:
    rounded = round(value, 4)
    return 0.0 if rounded == 0 else rounded


def _pf_float(value: object) -> float:
    if value == "inf":
        return 999.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _describe_group(row: dict[str, Any] | None) -> str:
    if not row:
        return "none"
    metrics = row.get("metrics", {})
    return (
        f"{row.get('dimension')}={row.get('value')} "
        f"(trades={metrics.get('trades', 0)}, PF={metrics.get('profit_factor', 0)}, "
        f"TotalR={metrics.get('total_r', 0)}, class={row.get('classification', 'NOISE')})"
    )


def _describe_root_cause(row: dict[str, Any] | None) -> str:
    if not row:
        return "none"
    metrics = row.get("removed_metrics", {})
    return (
        f"{row.get('name')} (removed={row.get('removed_trades', 0)}, "
        f"PF={metrics.get('profit_factor', 0)}, TotalR={metrics.get('total_r', 0)}, "
        f"R improvement={row.get('r_improvement', 0)}, class={row.get('classification', 'NOISE')})"
    )


def _metrics_inline(metrics: object) -> str:
    if not isinstance(metrics, dict):
        metrics = {}
    return (
        f"trades={metrics.get('trades', 0)}, WR={metrics.get('winrate', 0)}%, "
        f"PF={metrics.get('profit_factor', 0)}, TotalR={metrics.get('total_r', 0)}, AvgR={metrics.get('avg_r', 0)}"
    )


def _single_metrics_table(metrics: object) -> list[str]:
    return [
        "| Trades | Wins | Losses | WR | PF | Total R | Avg R |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        (
            f"| {metrics.get('trades', 0) if isinstance(metrics, dict) else 0} | "
            f"{metrics.get('wins', 0) if isinstance(metrics, dict) else 0} | "
            f"{metrics.get('losses', 0) if isinstance(metrics, dict) else 0} | "
            f"{metrics.get('winrate', 0) if isinstance(metrics, dict) else 0}% | "
            f"{metrics.get('profit_factor', 0) if isinstance(metrics, dict) else 0} | "
            f"{metrics.get('total_r', 0) if isinstance(metrics, dict) else 0} | "
            f"{metrics.get('avg_r', 0) if isinstance(metrics, dict) else 0} |"
        ),
    ]


def _group_table(payload: object, label: str) -> list[str]:
    lines = [f"| {label} | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |", "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    if not isinstance(payload, dict) or not payload:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |")
        return lines
    ranked = sorted(
        payload.items(),
        key=lambda item: (
            float(item[1].get("metrics", {}).get("total_r", 0.0)),
            _pf_float(item[1].get("metrics", {}).get("profit_factor")),
            -int(item[1].get("metrics", {}).get("trades", 0) or 0),
        ),
    )
    for key, value in ranked[:30]:
        metrics = value.get("metrics", {}) if isinstance(value, dict) else {}
        lines.append(
            f"| {key} | {metrics.get('trades', 0)} | {metrics.get('wins', 0)} | {metrics.get('losses', 0)} | "
            f"{metrics.get('winrate', 0)}% | {metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | "
            f"{metrics.get('avg_r', 0)} | {value.get('classification', 'NOISE') if isinstance(value, dict) else 'NOISE'} |"
        )
    return lines


def _rank_table(rows: object) -> list[str]:
    lines = ["| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    if not isinstance(rows, list) or not rows:
        lines.append("| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |")
        return lines
    for row in rows[:30]:
        metrics = row.get("metrics", {}) if isinstance(row, dict) else {}
        lines.append(
            f"| {row.get('dimension', '')} | {row.get('value', '')} | {metrics.get('trades', 0)} | "
            f"{metrics.get('wins', 0)} | {metrics.get('losses', 0)} | {metrics.get('winrate', 0)}% | "
            f"{metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} | "
            f"{row.get('classification', 'NOISE')} |"
        )
    return lines


def _root_cause_table(rows: object) -> list[str]:
    lines = [
        "| Rule | Factors | Removed | Removed PF | Removed TotalR | PF After | TotalR After | R Improvement | Profitable Lost | Losing Removed | Classification |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    if not isinstance(rows, list) or not rows:
        lines.append("| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |")
        return lines
    for row in rows:
        removed = row.get("removed_metrics", {}) if isinstance(row, dict) else {}
        lines.append(
            f"| {row.get('name', '')} | {', '.join(row.get('factors', []))} | {row.get('removed_trades', 0)} | "
            f"{removed.get('profit_factor', 0)} | {removed.get('total_r', 0)} | {row.get('pf_after', 0)} | "
            f"{row.get('total_r_after', 0)} | {row.get('r_improvement', 0)} | {row.get('profitable_trades_lost', 0)} | "
            f"{row.get('losing_trades_removed', 0)} | {row.get('classification', 'NOISE')} |"
        )
    return lines


def _comparison_table(payload: object) -> list[str]:
    lines = [
        "| Group | Trades | Wins | Losses | WR | PF | Total R | Avg R | Top Symbol | Top Session | Top Regime | Top Entry | Top Liquidity | Top HTF |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|---|",
    ]
    if not isinstance(payload, dict) or not payload:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | none | none | none | none | none | none |")
        return lines
    for group, item in payload.items():
        metrics = item.get("metrics", {}) if isinstance(item, dict) else {}
        lines.append(
            f"| {group} | {metrics.get('trades', 0)} | {metrics.get('wins', 0)} | {metrics.get('losses', 0)} | "
            f"{metrics.get('winrate', 0)}% | {metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | "
            f"{metrics.get('avg_r', 0)} | {item.get('top_symbol', 'none')} | {item.get('top_session', 'none')} | "
            f"{item.get('top_regime', 'none')} | {item.get('top_entry_context', 'none')} | {item.get('top_liquidity', 'none')} | "
            f"{item.get('top_htf', 'none')} |"
        )
    return lines


def _counterfactual_table(payload: object) -> list[str]:
    lines = [
        "| Scenario | Removed | PF Before | PF After | TotalR Before | TotalR After | R Improvement | WR Delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    if not isinstance(payload, dict) or not payload:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 |")
        return lines
    for scenario, item in payload.items():
        if not isinstance(item, dict) or "pf_after" not in item:
            continue
        name = item.get("name") or scenario
        lines.append(
            f"| {name} | {item.get('removed_trades', 0)} | {item.get('pf_before', 0)} | {item.get('pf_after', 0)} | "
            f"{item.get('total_r_before', 0)} | {item.get('total_r_after', 0)} | {item.get('r_improvement', 0)} | "
            f"{item.get('winrate_delta', 0)} |"
        )
    return lines


def _top_distribution(rows: list[dict[str, Any]], field: str) -> str:
    if not rows:
        return "none"
    groups: dict[str, int] = defaultdict(int)
    for row in rows:
        groups[_field_value(row, field)] += 1
    key, count = max(groups.items(), key=lambda item: item[1])
    return f"{key} ({_round(count / len(rows) * 100)}%)"
