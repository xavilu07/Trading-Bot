from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


TARGET_TOKEN = "distance_to_liquidity_penalty"
SURVIVOR_MIN_TRADES = 10
TOXIC_MIN_TRADES = 10
CRITICAL_MIN_TRADES = 30


TOXIC_COMBINATION_RULES: tuple[tuple[str, tuple[str, ...], Callable[[dict[str, Any]], bool]], ...] = (
    (
        "distance_to_liquidity_penalty + MAIN_SIGNAL",
        (TARGET_TOKEN, "MAIN_SIGNAL"),
        lambda row: _has_distance_penalty(row) and _setup_type(row) == "MAIN_SIGNAL",
    ),
    (
        "distance_to_liquidity_penalty + LONG",
        (TARGET_TOKEN, "LONG"),
        lambda row: _has_distance_penalty(row) and _direction(row) == "long",
    ),
    (
        "distance_to_liquidity_penalty + bullish_sweep",
        (TARGET_TOKEN, "bullish_sweep"),
        lambda row: _has_distance_penalty(row) and _is_bullish_sweep(row),
    ),
    (
        "distance_to_liquidity_penalty + against_htf",
        (TARGET_TOKEN, "against_htf"),
        lambda row: _has_distance_penalty(row) and _is_against_htf(row),
    ),
    (
        "distance_to_liquidity_penalty + HIGH_VOLATILITY",
        (TARGET_TOKEN, "HIGH_VOLATILITY"),
        lambda row: _has_distance_penalty(row) and _market_regime(row) == "HIGH_VOLATILITY",
    ),
    (
        "distance_to_liquidity_penalty + RANGING",
        (TARGET_TOKEN, "RANGING"),
        lambda row: _has_distance_penalty(row) and _market_regime(row) == "RANGING",
    ),
    (
        "distance_to_liquidity_penalty + NEW_YORK",
        (TARGET_TOKEN, "NEW_YORK"),
        lambda row: _has_distance_penalty(row) and _session(row) == "NEW_YORK",
    ),
    (
        "distance_to_liquidity_penalty + OVERLAP",
        (TARGET_TOKEN, "OVERLAP"),
        lambda row: _has_distance_penalty(row) and _session(row) == "OVERLAP",
    ),
)


def analyze_distance_to_liquidity_root_cause(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    all_trades = load_canonical_closed_trades(data_path)
    target_rows = [row for row in all_trades if _has_distance_penalty(row)]
    after_existing_blocks = [row for row in all_trades if not _is_existing_production_block_context(row)]
    target_after_existing_blocks = [row for row in after_existing_blocks if _has_distance_penalty(row)]
    breakdowns = _build_breakdowns(target_rows)
    groups = _flatten_groups(breakdowns)
    toxic_combinations = _toxic_combination_counterfactuals(all_trades)
    survivors = _rank_survivors(groups)
    toxic_subgroups = _rank_toxic(groups)
    counterfactuals = _counterfactuals(all_trades=all_trades, after_existing_blocks=after_existing_blocks)
    answers = _answers(
        metrics=_metrics(target_rows),
        metrics_after_existing_blocks=_metrics(target_after_existing_blocks),
        survivors=survivors,
        toxic_combinations=toxic_combinations,
        counterfactuals=counterfactuals,
    )
    return {
        "scope": "DISTANCE_TO_LIQUIDITY_ROOT_CAUSE_ANALYSIS",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "method": (
            "Analyze canonical closed trades tagged with distance_to_liquidity_penalty, "
            "including counterfactual removal before and after already-blocked bullish_sweep and against_htf+BREAKOUT contexts."
        ),
        "target_token": TARGET_TOKEN,
        "baseline_metrics": _metrics(all_trades),
        "distance_to_liquidity_penalty_metrics": _metrics(target_rows),
        "distance_to_liquidity_penalty_after_existing_blocks_metrics": _metrics(target_after_existing_blocks),
        "classification": classify_distance_to_liquidity_component(_metrics(target_rows)),
        "breakdowns": breakdowns,
        "toxic_subgroups": toxic_subgroups,
        "toxic_combinations": toxic_combinations,
        "survivors": survivors,
        "counterfactuals": counterfactuals,
        "answers": answers,
        "recommended_action": answers["recommended_action"],
    }


def write_distance_to_liquidity_root_cause_reports(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    markdown_path = reports_path / "distance_to_liquidity_root_cause_analysis.md"
    json_path = reports_path / "distance_to_liquidity_root_cause_analysis.json"
    markdown_path.write_text(format_distance_to_liquidity_root_cause_markdown(result), encoding="utf-8")
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return {"markdown": markdown_path, "json": json_path}


def format_distance_to_liquidity_root_cause_markdown(result: dict[str, Any]) -> str:
    answers = result.get("answers", {})
    breakdowns = result.get("breakdowns", {})
    lines = [
        "# DISTANCE_TO_LIQUIDITY_ROOT_CAUSE_ANALYSIS",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        f"Method: {result.get('method')}",
        f"Classification: {result.get('classification')}",
        f"Recommended action: {result.get('recommended_action')}",
        "",
        "## Executive Summary",
        "",
        f"- Baseline: {_metrics_inline(result.get('baseline_metrics', {}))}",
        f"- distance_to_liquidity_penalty: {_metrics_inline(result.get('distance_to_liquidity_penalty_metrics', {}))}",
        f"- After existing blocks: {_metrics_inline(result.get('distance_to_liquidity_penalty_after_existing_blocks_metrics', {}))}",
        f"- Is liquidity distance itself toxic? {answers.get('liquidity_distance_itself_toxic', 'UNKNOWN')}",
        f"- Toxicity remains after existing blocks? {answers.get('toxicity_remains_after_existing_blocks', 'UNKNOWN')}",
        f"- Root cause or correlated? {answers.get('root_cause_or_correlated', 'UNKNOWN')}",
        f"- Blocking improves PF? {answers.get('blocking_improves_pf', 'UNKNOWN')}",
        f"- Partial better than full block? {answers.get('partial_rule_better_than_full_block', 'UNKNOWN')}",
        "",
        "## Baseline",
        "",
        *_single_metrics_table(result.get("distance_to_liquidity_penalty_metrics", {})),
        "",
        "## Breakdowns",
        "",
    ]
    for title, key in (
        ("By Symbol", "symbol"),
        ("By Session", "session"),
        ("By Market Regime", "market_regime"),
        ("By Direction", "direction"),
        ("By Setup Type", "setup_type"),
        ("By Score Bucket", "score_bucket"),
        ("By Liquidity Sweep", "liquidity_sweep"),
        ("By Trade Location", "trade_location"),
        ("By Trend Alignment", "trend_alignment"),
        ("By HTF Alignment", "htf_alignment"),
    ):
        lines.extend([f"### {title}", "", *_group_table(breakdowns.get(key, {}), title), ""])
    lines.extend(
        [
            "## Toxic Combinations",
            "",
            "Tested fixed combinations requested for distance_to_liquidity_penalty.",
            "",
            *_combination_table(result.get("toxic_combinations", [])),
            "",
            "## Survivors",
            "",
            "Criteria: minimum 10 trades, PF > 1.1, TotalR > 0.",
            "",
            *_rank_table(result.get("survivors", [])),
            "",
            "## Toxic Subgroups",
            "",
            *_rank_table(result.get("toxic_subgroups", [])),
            "",
            "## Counterfactuals",
            "",
            *_counterfactual_table(result.get("counterfactuals", {})),
            "",
            "## Answers",
            "",
        ]
    )
    for question, answer in answers.items():
        if question == "recommended_action":
            continue
        lines.append(f"- {question}: {answer}")
    lines.extend(["", "## Recommended Action", "", str(result.get("recommended_action", "KEEP"))])
    return "\n".join(lines).rstrip() + "\n"


def classify_distance_to_liquidity_component(metrics: dict[str, Any]) -> str:
    trades = int(metrics.get("trades", 0) or 0)
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    pf = _pf_float(metrics.get("profit_factor"))
    if total_r >= 0 or pf >= 1:
        return "NOISE"
    if trades >= CRITICAL_MIN_TRADES and total_r <= -5 and pf < 0.85:
        return "CRITICAL"
    if trades >= TOXIC_MIN_TRADES and pf < 1:
        return "IMPORTANT"
    if trades >= 3:
        return "WATCH"
    return "NOISE"


def classify_combination(payload: dict[str, Any]) -> str:
    removed = int(payload.get("removed_trades", 0) or 0)
    r_improvement = float(payload.get("r_improvement", 0.0) or 0.0)
    pf_improvement = float(payload.get("pf_improvement", 0.0) or 0.0)
    removed_pf = _pf_float(payload.get("removed_metrics", {}).get("profit_factor"))
    profitable_lost = int(payload.get("profitable_trades_lost", 0) or 0)
    losing_removed = int(payload.get("losing_trades_removed", 0) or 0)
    if removed >= CRITICAL_MIN_TRADES and r_improvement >= 5 and pf_improvement >= 0.10 and removed_pf < 0.85:
        return "CRITICAL"
    if removed >= TOXIC_MIN_TRADES and r_improvement > 0 and losing_removed >= profitable_lost and removed_pf < 1:
        return "IMPORTANT"
    if removed >= 5:
        return "WATCH"
    return "NOISE"


def _build_breakdowns(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "symbol": _group_summary(rows, "symbol"),
        "session": _group_summary(rows, "session"),
        "market_regime": _group_summary(rows, "market_regime"),
        "direction": _group_summary(rows, "direction"),
        "setup_type": _group_summary(rows, "setup_type"),
        "score_bucket": _group_summary(rows, "score_bucket"),
        "liquidity_sweep": _group_summary(rows, "liquidity_sweep"),
        "trade_location": _group_summary(rows, "trade_location"),
        "trend_alignment": _group_summary(rows, "trend_alignment"),
        "htf_alignment": _group_summary(rows, "htf_alignment"),
    }


def _toxic_combination_counterfactuals(all_trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current = _metrics(all_trades)
    results: list[dict[str, Any]] = []
    for name, factors, predicate in TOXIC_COMBINATION_RULES:
        removed = [row for row in all_trades if predicate(row)]
        without = [row for row in all_trades if not predicate(row)]
        without_metrics = _metrics(without)
        removed_metrics = _metrics(removed)
        payload = {
            "name": name,
            "factors": list(factors),
            "removed_trades": len(removed),
            "removed_metrics": removed_metrics,
            "pf_before": current["profit_factor"],
            "pf_after": without_metrics["profit_factor"],
            "total_r_before": current["total_r"],
            "total_r_after": without_metrics["total_r"],
            "pf_improvement": _round(_pf_float(without_metrics["profit_factor"]) - _pf_float(current["profit_factor"])),
            "r_improvement": _round(float(without_metrics["total_r"]) - float(current["total_r"])),
            "profitable_trades_lost": int(removed_metrics.get("wins", 0) or 0),
            "losing_trades_removed": int(removed_metrics.get("losses", 0) or 0),
        }
        payload["classification"] = classify_combination(payload)
        results.append(payload)
    return sorted(
        results,
        key=lambda row: (
            float(row.get("r_improvement", 0.0) or 0.0),
            float(row.get("pf_improvement", 0.0) or 0.0),
            -int(row.get("profitable_trades_lost", 0) or 0),
            int(row.get("removed_trades", 0) or 0),
        ),
        reverse=True,
    )


def _counterfactuals(*, all_trades: list[dict[str, Any]], after_existing_blocks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "without_distance_to_liquidity_penalty": _remove_payload(all_trades, _has_distance_penalty),
        "without_existing_production_blocks": _remove_payload(all_trades, _is_existing_production_block_context),
        "without_distance_to_liquidity_penalty_after_existing_blocks": _remove_payload(after_existing_blocks, _has_distance_penalty),
    }


def _remove_payload(rows: list[dict[str, Any]], predicate: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
    current = _metrics(rows)
    removed = [row for row in rows if predicate(row)]
    without = [row for row in rows if not predicate(row)]
    without_metrics = _metrics(without)
    return {
        "removed_trades": len(removed),
        "removed_metrics": _metrics(removed),
        "current_metrics": current,
        "without_metrics": without_metrics,
        "pf_before": current["profit_factor"],
        "pf_after": without_metrics["profit_factor"],
        "total_r_before": current["total_r"],
        "total_r_after": without_metrics["total_r"],
        "pf_improvement": _round(_pf_float(without_metrics["profit_factor"]) - _pf_float(current["profit_factor"])),
        "r_improvement": _round(float(without_metrics["total_r"]) - float(current["total_r"])),
        "winrate_delta": _round(float(without_metrics.get("winrate", 0.0) or 0.0) - float(current.get("winrate", 0.0) or 0.0)),
    }


def _answers(
    *,
    metrics: dict[str, Any],
    metrics_after_existing_blocks: dict[str, Any],
    survivors: list[dict[str, Any]],
    toxic_combinations: list[dict[str, Any]],
    counterfactuals: dict[str, Any],
) -> dict[str, str]:
    classification = classify_distance_to_liquidity_component(metrics)
    after_classification = classify_distance_to_liquidity_component(metrics_after_existing_blocks)
    globally_toxic = classification in {"CRITICAL", "IMPORTANT"}
    remains_toxic = after_classification in {"CRITICAL", "IMPORTANT"}
    full_cf = counterfactuals.get("without_distance_to_liquidity_penalty", {})
    post_blocks_cf = counterfactuals.get("without_distance_to_liquidity_penalty_after_existing_blocks", {})
    blocking_pf_improves = float(full_cf.get("pf_improvement", 0.0) or 0.0) > 0
    post_blocks_improves = float(post_blocks_cf.get("pf_improvement", 0.0) or 0.0) > 0
    best_combo = next((row for row in toxic_combinations if row.get("classification") in {"CRITICAL", "IMPORTANT"}), None)
    if not globally_toxic:
        action = "KEEP"
    elif remains_toxic and survivors and best_combo:
        action = "REDEFINE_ENTRY"
    elif remains_toxic and best_combo:
        action = "PARTIAL_BLOCK"
    elif globally_toxic and not remains_toxic:
        action = "SHADOW_BLOCK"
    elif globally_toxic and not survivors:
        action = "FULL_BLOCK"
    else:
        action = "PARTIAL_BLOCK"
    return {
        "liquidity_distance_itself_toxic": "YES" if globally_toxic else "NO",
        "toxicity_remains_after_existing_blocks": "YES" if remains_toxic else "NO",
        "root_cause_or_correlated": _root_cause_or_correlated(globally_toxic, remains_toxic, survivors, toxic_combinations),
        "blocking_improves_pf": "YES" if blocking_pf_improves else "NO",
        "blocking_improves_pf_after_existing_blocks": "YES" if post_blocks_improves else "NO",
        "partial_rule_better_than_full_block": "YES" if survivors and best_combo else "NO",
        "best_partial_rule": _describe_combination(best_combo),
        "best_survivor": _describe_group(survivors[0]) if survivors else "none",
        "recommended_action": action,
    }


def _root_cause_or_correlated(
    globally_toxic: bool,
    remains_toxic: bool,
    survivors: list[dict[str, Any]],
    toxic_combinations: list[dict[str, Any]],
) -> str:
    if not globally_toxic:
        return "not_toxic"
    if not remains_toxic:
        return "correlated_with_existing_blocked_contexts"
    if survivors:
        return "mixed_signal_symptom_requires_entry_redefinition"
    if any(row.get("classification") in {"CRITICAL", "IMPORTANT"} for row in toxic_combinations):
        return "root_cause_candidate"
    return "correlated_but_unresolved"


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
            and _pf_float(metrics.get("profit_factor")) < 1
            and float(metrics.get("total_r", 0.0) or 0.0) < 0
        ):
            toxic.append(row)
    return sorted(toxic, key=lambda row: (float(row["metrics"].get("total_r", 0.0)), _pf_float(row["metrics"].get("profit_factor"))))[:30]


def _rank_survivors(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    survivors = []
    for row in groups:
        metrics = row.get("metrics", {})
        if (
            int(metrics.get("trades", 0) or 0) >= SURVIVOR_MIN_TRADES
            and _pf_float(metrics.get("profit_factor")) > 1.10
            and float(metrics.get("total_r", 0.0) or 0.0) > 0
        ):
            survivors.append(row)
    return sorted(survivors, key=lambda row: (float(row["metrics"].get("total_r", 0.0)), _pf_float(row["metrics"].get("profit_factor"))), reverse=True)


def _group_summary(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[_field_value(row, field)].append(row)
    return _summaries(groups)


def _summaries(groups: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    result = {}
    for key, items in sorted(groups.items()):
        metrics = _metrics(items)
        result[key] = {"metrics": metrics, "classification": classify_distance_to_liquidity_component(metrics)}
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
    if field == "session":
        return _session(row)
    return str(row.get(field) or "UNKNOWN").strip() or "UNKNOWN"


def _has_distance_penalty(row: dict[str, Any]) -> bool:
    return TARGET_TOKEN in _all_tokens(row)


def _is_existing_production_block_context(row: dict[str, Any]) -> bool:
    return _is_bullish_sweep(row) or _is_against_htf_breakout(row)


def _is_against_htf_breakout(row: dict[str, Any]) -> bool:
    return _is_against_htf(row) and _entry_context(row) == "BREAKOUT"


def _is_bullish_sweep(row: dict[str, Any]) -> bool:
    return _liquidity_sweep(row) == "bullish_sweep" or _liquidity_context(row).lower() == "sweep:bullish_sweep"


def _is_against_htf(row: dict[str, Any]) -> bool:
    return "against_htf" in _all_tokens(row) or _htf_alignment(row) == "against_htf"


def _setup_type(row: dict[str, Any]) -> str:
    return str(row.get("setup_type") or "UNKNOWN").strip().upper()


def _direction(row: dict[str, Any]) -> str:
    return str(row.get("direction") or "unknown").strip().lower()


def _market_regime(row: dict[str, Any]) -> str:
    return str(row.get("market_regime") or "UNKNOWN").strip().upper()


def _session(row: dict[str, Any]) -> str:
    return str(row.get("session") or "UNKNOWN").strip().upper()


def _entry_context(row: dict[str, Any]) -> str:
    return str(row.get("entry_context") or "UNKNOWN").strip().upper()


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


def _describe_combination(row: dict[str, Any] | None) -> str:
    if not row:
        return "none"
    metrics = row.get("removed_metrics", {})
    return (
        f"{row.get('name')} (removed={row.get('removed_trades', 0)}, PF={metrics.get('profit_factor', 0)}, "
        f"TotalR={metrics.get('total_r', 0)}, R improvement={row.get('r_improvement', 0)}, "
        f"class={row.get('classification', 'NOISE')})"
    )


def _metrics_inline(metrics: object) -> str:
    if not isinstance(metrics, dict):
        metrics = {}
    return (
        f"trades={metrics.get('trades', 0)}, WR={metrics.get('winrate', 0)}%, "
        f"PF={metrics.get('profit_factor', 0)}, TotalR={metrics.get('total_r', 0)}, AvgR={metrics.get('avg_r', 0)}"
    )


def _single_metrics_table(metrics: object) -> list[str]:
    payload = metrics if isinstance(metrics, dict) else {}
    return [
        "| Trades | Wins | Losses | WR | PF | Total R | Avg R |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        (
            f"| {payload.get('trades', 0)} | {payload.get('wins', 0)} | {payload.get('losses', 0)} | "
            f"{payload.get('winrate', 0)}% | {payload.get('profit_factor', 0)} | "
            f"{payload.get('total_r', 0)} | {payload.get('avg_r', 0)} |"
        ),
    ]


def _group_table(payload: object, label: str) -> list[str]:
    lines = [f"| {label} | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |", "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    if not isinstance(payload, dict) or not payload:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |")
        return lines
    ranked = sorted(payload.items(), key=lambda item: (float(item[1].get("metrics", {}).get("total_r", 0.0)), _pf_float(item[1].get("metrics", {}).get("profit_factor"))))
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


def _combination_table(rows: object) -> list[str]:
    lines = [
        "| Rule | Removed | Removed PF | Removed TotalR | PF After | TotalR After | PF Improvement | R Improvement | Profitable Lost | Losing Removed | Classification |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    if not isinstance(rows, list) or not rows:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |")
        return lines
    for row in rows:
        removed = row.get("removed_metrics", {}) if isinstance(row, dict) else {}
        lines.append(
            f"| {row.get('name', '')} | {row.get('removed_trades', 0)} | {removed.get('profit_factor', 0)} | "
            f"{removed.get('total_r', 0)} | {row.get('pf_after', 0)} | {row.get('total_r_after', 0)} | "
            f"{row.get('pf_improvement', 0)} | {row.get('r_improvement', 0)} | {row.get('profitable_trades_lost', 0)} | "
            f"{row.get('losing_trades_removed', 0)} | {row.get('classification', 'NOISE')} |"
        )
    return lines


def _counterfactual_table(payload: object) -> list[str]:
    lines = [
        "| Scenario | Removed | PF Before | PF After | TotalR Before | TotalR After | PF Improvement | R Improvement | WR Delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    if not isinstance(payload, dict) or not payload:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |")
        return lines
    for scenario, item in payload.items():
        if not isinstance(item, dict):
            continue
        lines.append(
            f"| {scenario} | {item.get('removed_trades', 0)} | {item.get('pf_before', 0)} | {item.get('pf_after', 0)} | "
            f"{item.get('total_r_before', 0)} | {item.get('total_r_after', 0)} | {item.get('pf_improvement', 0)} | "
            f"{item.get('r_improvement', 0)} | {item.get('winrate_delta', 0)} |"
        )
    return lines
