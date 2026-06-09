from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


TOXIC_MIN_TRADES = 10
SURVIVOR_MIN_TRADES = 10
CRITICAL_MIN_TRADES = 30


PARTIAL_BLOCKS: tuple[tuple[str, Callable[[dict[str, Any]], bool]], ...] = (
    ("MAIN_SIGNAL + bullish_sweep", lambda row: _is_main_signal(row) and _is_bullish_sweep(row)),
    ("MAIN_SIGNAL + against_htf", lambda row: _is_main_signal(row) and _is_against_htf(row)),
    ("MAIN_SIGNAL + long", lambda row: _is_main_signal(row) and _direction(row) == "long"),
    ("MAIN_SIGNAL + near_support", lambda row: _is_main_signal(row) and _is_near_support(row)),
    ("MAIN_SIGNAL + aligned_bearish", lambda row: _is_main_signal(row) and _trend_alignment(row) == "aligned_bearish"),
    ("MAIN_SIGNAL + HIGH_VOLATILITY", lambda row: _is_main_signal(row) and _market_regime(row) == "HIGH_VOLATILITY"),
    ("MAIN_SIGNAL + BREAKOUT", lambda row: _is_main_signal(row) and _entry_context(row) == "BREAKOUT"),
    ("MAIN_SIGNAL + score_bucket 80-89", lambda row: _is_main_signal(row) and _score_bucket(row.get("score")) == "80-89"),
    ("MAIN_SIGNAL + distance_to_liquidity_penalty", lambda row: _is_main_signal(row) and _has_token(row, "distance_to_liquidity_penalty")),
    ("MAIN_SIGNAL + directional_confluence_failed", lambda row: _is_main_signal(row) and _has_token(row, "directional_confluence_failed")),
    ("MAIN_SIGNAL + dirty_sideways_market", lambda row: _is_main_signal(row) and _has_token(row, "dirty_sideways_market")),
    ("MAIN_SIGNAL + choppy_range", lambda row: _is_main_signal(row) and _entry_context(row) == "CHOPPY_RANGE"),
)


def analyze_main_signal_deep_dive(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    all_trades = load_canonical_closed_trades(data_path)
    main_rows = [row for row in all_trades if _is_main_signal(row)]
    secondary_rows = [row for row in all_trades if _setup_type(row) == "SECONDARY_SIGNAL"]
    metrics = _metrics(main_rows)
    breakdowns = {
        "symbol": _group_summary(main_rows, "symbol"),
        "session": _group_summary(main_rows, "session"),
        "direction": _group_summary(main_rows, "direction"),
        "market_regime": _group_summary(main_rows, "market_regime"),
        "entry_context": _group_summary(main_rows, "entry_context"),
        "liquidity_context": _group_summary(main_rows, "liquidity_context"),
        "trade_location": _group_summary(main_rows, "trade_location"),
        "trend_alignment": _group_summary(main_rows, "trend_alignment"),
        "htf_alignment": _group_summary(main_rows, "htf_alignment"),
        "score_bucket": _group_summary(main_rows, "score_bucket"),
        "warning": _token_summary(main_rows, "warnings", "avoidance_warnings"),
        "penalty": _token_summary(main_rows, "penalties"),
        "rejection_reason": _token_summary(main_rows, "rejection_reasons"),
        "condition_failed": _token_summary(main_rows, "conditions_failed"),
    }
    groups = _flatten_groups(breakdowns)
    toxic = _rank_toxic(groups)
    survivors = _rank_survivors(groups)
    comparison = _main_vs_secondary_comparison(main_rows, secondary_rows)
    counterfactual = _counterfactual_remove_main_signal(all_trades)
    partial_blocks = _partial_block_counterfactuals(all_trades)
    answers = _answers(
        main_metrics=metrics,
        secondary_metrics=_metrics(secondary_rows),
        toxic=toxic,
        survivors=survivors,
        counterfactual=counterfactual,
        partial_blocks=partial_blocks,
    )
    return {
        "scope": "MAIN_SIGNAL_DEEP_DIVE",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "method": "Analyze canonical closed trades where setup_type=MAIN_SIGNAL.",
        "baseline_metrics": _metrics(all_trades),
        "main_signal_metrics": metrics,
        "secondary_signal_metrics": _metrics(secondary_rows),
        "classification": classify_main_signal(metrics),
        "breakdowns": breakdowns,
        "toxic_subgroups": toxic,
        "survivors": survivors,
        "main_vs_secondary_comparison": comparison,
        "counterfactual_removal": counterfactual,
        "counterfactual_partial_blocks": partial_blocks,
        "answers": answers,
        "recommended_action": answers["recommended_action"],
    }


def write_main_signal_deep_dive_report(result: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "main_signal_deep_dive.md"
    path.write_text(format_main_signal_deep_dive_markdown(result), encoding="utf-8")
    return path


def format_main_signal_deep_dive_markdown(result: dict[str, Any]) -> str:
    answers = result.get("answers", {})
    counterfactual = result.get("counterfactual_removal", {})
    breakdowns = result.get("breakdowns", {})
    lines = [
        "# MAIN_SIGNAL_DEEP_DIVE",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        f"Method: {result.get('method')}",
        f"Classification: {result.get('classification')}",
        "",
        "## Executive Summary",
        "",
        f"- Baseline: {_metrics_inline(result.get('baseline_metrics', {}))}",
        f"- MAIN_SIGNAL: {_metrics_inline(result.get('main_signal_metrics', {}))}",
        f"- SECONDARY_SIGNAL: {_metrics_inline(result.get('secondary_signal_metrics', {}))}",
        f"- Is MAIN_SIGNAL globally toxic? {answers.get('globally_toxic', '')}",
        f"- Is MAIN_SIGNAL worse than SECONDARY_SIGNAL? {answers.get('worse_than_secondary', '')}",
        f"- Biggest damage subgroup: {answers.get('main_loss_subgroup', '')}",
        f"- Best survivor: {answers.get('survivor_subgroup', '')}",
        f"- Material PF improvement if removed? {answers.get('material_pf_improvement', '')}",
        f"- Structural strategy issue evidence: {answers.get('structural_strategy_issue', '')}",
        f"- Recommended action: {result.get('recommended_action', 'KEEP')}",
        "",
        "## MAIN_SIGNAL Toxic Subgroups",
        "",
        "Criteria: minimum 10 trades, PF < 1, TotalR < 0. Ranked by TotalR then PF.",
        "",
        *_rank_table(result.get("toxic_subgroups", [])),
        "",
        "## MAIN_SIGNAL Survivors",
        "",
        "Criteria: minimum 10 trades, PF > 1.1, TotalR > 0.",
        "",
        *_rank_table(result.get("survivors", [])),
        "",
        "## MAIN_SIGNAL vs SECONDARY_SIGNAL Comparison",
        "",
        *_comparison_table(result.get("main_vs_secondary_comparison", {})),
        "",
        "## Counterfactual Removal",
        "",
        f"- PF current: {counterfactual.get('current_metrics', {}).get('profit_factor', 0)}",
        f"- PF without MAIN_SIGNAL: {counterfactual.get('without_main_signal_metrics', {}).get('profit_factor', 0)}",
        f"- TotalR current: {counterfactual.get('current_metrics', {}).get('total_r', 0)}",
        f"- TotalR without MAIN_SIGNAL: {counterfactual.get('without_main_signal_metrics', {}).get('total_r', 0)}",
        f"- Winrate delta: {counterfactual.get('winrate_delta', 0)}",
        f"- Trades removed: {counterfactual.get('trades_removed', 0)}",
        "",
        "## Counterfactual Partial Blocks",
        "",
        *_partial_block_table(result.get("counterfactual_partial_blocks", [])),
        "",
        "## Breakdowns",
        "",
    ]
    for title, key in (
        ("By Symbol", "symbol"),
        ("By Session", "session"),
        ("By Direction", "direction"),
        ("By Market Regime", "market_regime"),
        ("By Entry Context", "entry_context"),
        ("By Liquidity Context", "liquidity_context"),
        ("By Trade Location", "trade_location"),
        ("By Trend Alignment", "trend_alignment"),
        ("By HTF Alignment", "htf_alignment"),
        ("By Score Bucket", "score_bucket"),
        ("By Warning", "warning"),
        ("By Penalty", "penalty"),
        ("By Rejection Reason", "rejection_reason"),
        ("By Conditions Failed", "condition_failed"),
    ):
        lines.extend([f"### {title}", "", *_group_table(breakdowns.get(key, {}), title), ""])
    lines.extend(["## Recommended Action", "", result.get("recommended_action", "KEEP")])
    return "\n".join(lines).rstrip() + "\n"


def classify_main_signal(metrics: dict[str, Any]) -> str:
    trades = int(metrics.get("trades", 0) or 0)
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    pf = _pf_float(metrics.get("profit_factor"))
    if total_r >= 0 or pf >= 1:
        return "NOISE"
    if trades >= CRITICAL_MIN_TRADES and total_r <= -10:
        return "CRITICAL"
    if trades >= TOXIC_MIN_TRADES:
        return "IMPORTANT"
    if trades >= 3:
        return "WATCH"
    return "NOISE"


def classify_partial_block(payload: dict[str, Any]) -> str:
    removed = int(payload.get("removed_trades", 0) or 0)
    r_improvement = float(payload.get("r_improvement", 0.0) or 0.0)
    pf_improvement = float(payload.get("pf_improvement", 0.0) or 0.0)
    profitable_lost = int(payload.get("profitable_trades_lost", 0) or 0)
    losing_removed = int(payload.get("losing_trades_removed", 0) or 0)
    if removed >= 30 and r_improvement >= 10 and pf_improvement >= 0.10 and losing_removed > profitable_lost:
        return "DEPLOY_CANDIDATE"
    if removed >= 10 and r_improvement > 0 and losing_removed >= profitable_lost:
        return "SHADOW_TEST"
    if removed >= 5:
        return "WATCH"
    return "REJECT"


def _answers(
    *,
    main_metrics: dict[str, Any],
    secondary_metrics: dict[str, Any],
    toxic: list[dict[str, Any]],
    survivors: list[dict[str, Any]],
    counterfactual: dict[str, Any],
    partial_blocks: list[dict[str, Any]],
) -> dict[str, str]:
    classification = classify_main_signal(main_metrics)
    globally_toxic = classification in {"CRITICAL", "IMPORTANT"}
    main_pf = _pf_float(main_metrics.get("profit_factor"))
    secondary_pf = _pf_float(secondary_metrics.get("profit_factor"))
    main_total_r = float(main_metrics.get("total_r", 0.0) or 0.0)
    secondary_total_r = float(secondary_metrics.get("total_r", 0.0) or 0.0)
    worse_than_secondary = main_pf < secondary_pf and main_total_r < secondary_total_r
    current_pf = _pf_float(counterfactual.get("current_metrics", {}).get("profit_factor"))
    without_pf = _pf_float(counterfactual.get("without_main_signal_metrics", {}).get("profit_factor"))
    material_pf = without_pf - current_pf >= 0.10
    deploy_candidates = [row for row in partial_blocks if row.get("classification") == "DEPLOY_CANDIDATE"]
    shadow_candidates = [row for row in partial_blocks if row.get("classification") == "SHADOW_TEST"]
    if not globally_toxic:
        action = "KEEP"
    elif deploy_candidates:
        action = "PARTIAL_BLOCK"
    elif survivors and shadow_candidates:
        action = "REDEFINE_MAIN_SIGNAL"
    elif material_pf and not survivors:
        action = "FULL_BLOCK"
    elif shadow_candidates:
        action = "SHADOW_BLOCK"
    else:
        action = "PARTIAL_BLOCK"
    structural = "YES" if globally_toxic and worse_than_secondary and (bool(survivors) or bool(deploy_candidates or shadow_candidates)) else "NO"
    return {
        "globally_toxic": "YES" if globally_toxic else "NO",
        "worse_than_secondary": "YES" if worse_than_secondary else "NO",
        "main_loss_subgroup": _describe_group(toxic[0]) if toxic else "none",
        "survivor_subgroup": _describe_group(survivors[0]) if survivors else "none",
        "material_pf_improvement": "YES" if material_pf else "NO",
        "structural_strategy_issue": structural,
        "recommended_action": action,
    }


def _main_vs_secondary_comparison(main_rows: list[dict[str, Any]], secondary_rows: list[dict[str, Any]]) -> dict[str, Any]:
    main_groups = _flatten_groups(
        {
            "session": _group_summary(main_rows, "session"),
            "direction": _group_summary(main_rows, "direction"),
            "market_regime": _group_summary(main_rows, "market_regime"),
            "entry_context": _group_summary(main_rows, "entry_context"),
            "liquidity_context": _group_summary(main_rows, "liquidity_context"),
        }
    )
    secondary_groups = _flatten_groups(
        {
            "session": _group_summary(secondary_rows, "session"),
            "direction": _group_summary(secondary_rows, "direction"),
            "market_regime": _group_summary(secondary_rows, "market_regime"),
            "entry_context": _group_summary(secondary_rows, "entry_context"),
            "liquidity_context": _group_summary(secondary_rows, "liquidity_context"),
        }
    )
    return {
        "MAIN_SIGNAL": {
            "metrics": _metrics(main_rows),
            "best_contexts": _rank_survivors(main_groups)[:5],
            "worst_contexts": _rank_toxic(main_groups)[:5],
        },
        "SECONDARY_SIGNAL": {
            "metrics": _metrics(secondary_rows),
            "best_contexts": _rank_survivors(secondary_groups)[:5],
            "worst_contexts": _rank_toxic(secondary_groups)[:5],
        },
    }


def _counterfactual_remove_main_signal(all_trades: list[dict[str, Any]]) -> dict[str, Any]:
    removed = [row for row in all_trades if _is_main_signal(row)]
    without = [row for row in all_trades if not _is_main_signal(row)]
    current = _metrics(all_trades)
    without_metrics = _metrics(without)
    return {
        "current_metrics": current,
        "without_main_signal_metrics": without_metrics,
        "removed_metrics": _metrics(removed),
        "trades_removed": len(removed),
        "winrate_delta": _round(float(without_metrics.get("winrate", 0.0) or 0.0) - float(current.get("winrate", 0.0) or 0.0)),
    }


def _partial_block_counterfactuals(all_trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current = _metrics(all_trades)
    results = []
    for name, predicate in PARTIAL_BLOCKS:
        removed = [row for row in all_trades if predicate(row)]
        without = [row for row in all_trades if not predicate(row)]
        without_metrics = _metrics(without)
        removed_metrics = _metrics(removed)
        payload = {
            "name": name,
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
        payload["classification"] = classify_partial_block(payload)
        results.append(payload)
    return sorted(results, key=lambda row: (float(row["r_improvement"]), float(row["pf_improvement"]), int(row["removed_trades"])), reverse=True)


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
        result[key] = {"metrics": metrics, "classification": classify_main_signal(metrics)}
    return result


def _field_value(row: dict[str, Any], field: str) -> str:
    if field == "score_bucket":
        return _score_bucket(row.get("score"))
    if field == "liquidity_context":
        return _liquidity_context(row)
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
    return str(row.get(field) or "UNKNOWN")


def _is_main_signal(row: dict[str, Any]) -> bool:
    return _setup_type(row) == "MAIN_SIGNAL"


def _setup_type(row: dict[str, Any]) -> str:
    return str(row.get("setup_type") or "UNKNOWN").strip().upper()


def _direction(row: dict[str, Any]) -> str:
    return str(row.get("direction") or "unknown").strip().lower()


def _market_regime(row: dict[str, Any]) -> str:
    return str(row.get("market_regime") or "UNKNOWN").strip().upper()


def _entry_context(row: dict[str, Any]) -> str:
    return str(row.get("entry_context") or "UNKNOWN").strip().upper()


def _is_bullish_sweep(row: dict[str, Any]) -> bool:
    return _liquidity_context(row) == "sweep:bullish_sweep"


def _is_near_support(row: dict[str, Any]) -> bool:
    return str(row.get("trade_location") or "").strip() == "near_support" or _liquidity_context(row) == "location:near_support"


def _is_against_htf(row: dict[str, Any]) -> bool:
    return "against_htf" in _all_tokens(row) or _htf_alignment(row) == "against_htf"


def _has_token(row: dict[str, Any], token: str) -> bool:
    return token in _all_tokens(row)


def _all_tokens(row: dict[str, Any]) -> set[str]:
    return (
        _tokens(row.get("warnings"))
        | _tokens(row.get("avoidance_warnings"))
        | _tokens(row.get("penalties"))
        | _tokens(row.get("rejection_reasons"))
        | _tokens(row.get("conditions_failed"))
    )


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
    liquidity_reasons = sorted(
        reason
        for reason in _tokens(row.get("rejection_reasons")) | _tokens(row.get("warnings")) | _tokens(row.get("penalties"))
        if "liquidity" in reason.lower()
    )
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
        return {str(item).strip() for item in value if str(item).strip()}
    text = str(value).strip()
    if not text:
        return set()
    return {item.strip() for item in text.replace("|", ",").replace(";", ",").split(",") if item.strip()}


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


def _metrics_inline(metrics: object) -> str:
    if not isinstance(metrics, dict):
        metrics = {}
    return (
        f"trades={metrics.get('trades', 0)}, WR={metrics.get('winrate', 0)}%, "
        f"PF={metrics.get('profit_factor', 0)}, TotalR={metrics.get('total_r', 0)}, AvgR={metrics.get('avg_r', 0)}"
    )


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


def _comparison_table(payload: object) -> list[str]:
    lines = ["| Setup | Trades | Wins | Losses | WR | PF | Total R | Avg R | Best Context | Worst Context |", "|---|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    if not isinstance(payload, dict) or not payload:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | none | none |")
        return lines
    for setup in ("MAIN_SIGNAL", "SECONDARY_SIGNAL"):
        item = payload.get(setup, {})
        metrics = item.get("metrics", {}) if isinstance(item, dict) else {}
        best = _describe_group(item.get("best_contexts", [None])[0]) if item.get("best_contexts") else "none"
        worst = _describe_group(item.get("worst_contexts", [None])[0]) if item.get("worst_contexts") else "none"
        lines.append(
            f"| {setup} | {metrics.get('trades', 0)} | {metrics.get('wins', 0)} | {metrics.get('losses', 0)} | "
            f"{metrics.get('winrate', 0)}% | {metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | "
            f"{metrics.get('avg_r', 0)} | {best} | {worst} |"
        )
    return lines


def _partial_block_table(rows: object) -> list[str]:
    lines = [
        "| Rule | Removed | PF Before | PF After | TotalR Before | TotalR After | R Improvement | Profitable Lost | Losing Removed | Classification |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    if not isinstance(rows, list) or not rows:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | REJECT |")
        return lines
    for row in rows:
        lines.append(
            f"| {row.get('name')} | {row.get('removed_trades', 0)} | {row.get('pf_before', 0)} | "
            f"{row.get('pf_after', 0)} | {row.get('total_r_before', 0)} | {row.get('total_r_after', 0)} | "
            f"{row.get('r_improvement', 0)} | {row.get('profitable_trades_lost', 0)} | "
            f"{row.get('losing_trades_removed', 0)} | {row.get('classification', 'REJECT')} |"
        )
    return lines
