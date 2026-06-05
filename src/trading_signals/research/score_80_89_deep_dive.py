from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


SURVIVOR_MIN_TRADES = 10
MIN_IMPORTANT_TRADES = 10
MIN_CRITICAL_TRADES = 20


def analyze_score_80_89_deep_dive(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    all_trades = load_canonical_closed_trades(data_path)
    post_bullish_sweep = [row for row in all_trades if not _is_bullish_sweep(row)]
    rows = [row for row in post_bullish_sweep if _in_score_bucket_80_89(row.get("score"))]
    metrics = _metrics(rows)
    breakdowns = {
        "symbol": _group_summary(rows, "symbol"),
        "session": _group_summary(rows, "session"),
        "market_regime": _group_summary(rows, "market_regime"),
        "setup_type": _group_summary(rows, "setup_type"),
        "direction": _group_summary(rows, "direction"),
        "entry_context": _group_summary(rows, "entry_context"),
        "liquidity_context": _group_summary(rows, "liquidity_context"),
        "warning": _token_summary(rows, "warnings", "avoidance_warnings"),
        "penalty": _token_summary(rows, "penalties"),
        "rejection_reason": _token_summary(rows, "rejection_reasons"),
        "trend_alignment": _group_summary(rows, "trend_alignment"),
        "htf_alignment": _group_summary(rows, "htf_alignment"),
    }
    groups = _flatten_groups(breakdowns)
    toxic_subgroups = _rank_toxic(groups)
    survivors = _rank_survivors(groups)
    counterfactual = _remove_group_counterfactual(rows, toxic_subgroups[0] if toxic_subgroups else None)
    answers = _answers(metrics=metrics, toxic_subgroups=toxic_subgroups, survivors=survivors, counterfactual=counterfactual)
    return {
        "scope": "SCORE_80_89_DEEP_DIVE",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "method": "Exclude bullish_sweep first, then analyze trades with 80 <= score < 90.",
        "input_trades": len(all_trades),
        "post_bullish_sweep_trades": len(post_bullish_sweep),
        "metrics": metrics,
        "classification": classify_loss_component(metrics),
        "breakdowns": breakdowns,
        "toxic_subgroups": toxic_subgroups,
        "survivors_inside_80_89": survivors,
        "top_subgroup_counterfactual": counterfactual,
        "answers": answers,
        "recommended_action": answers["recommended_action"],
    }


def write_score_80_89_deep_dive_report(result: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "score_80_89_deep_dive.md"
    path.write_text(format_score_80_89_deep_dive_markdown(result), encoding="utf-8")
    return path


def format_score_80_89_deep_dive_markdown(result: dict[str, Any]) -> str:
    answers = result.get("answers", {})
    breakdowns = result.get("breakdowns", {})
    counterfactual = result.get("top_subgroup_counterfactual", {})
    lines = [
        "# SCORE_80_89_DEEP_DIVE",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        f"Method: {result.get('method')}",
        f"Classification: {result.get('classification')}",
        "",
        "## Executive Summary",
        "",
        f"- Score 80-89: {_metrics_inline(result.get('metrics', {}))}",
        f"- Is entire 80-89 bucket bad? {answers.get('entire_bucket_bad', '')}",
        f"- Main loss subgroup: {answers.get('main_loss_subgroup', '')}",
        f"- PF if main subgroup removed: {counterfactual.get('remaining_metrics', {}).get('profit_factor', 0)}",
        f"- Safe survivor worth keeping: {answers.get('safe_survivor', '')}",
        f"- Recommended action: {result.get('recommended_action')}",
        "",
        "## Toxic Subgroups",
        "",
        *_rank_table(result.get("toxic_subgroups", [])),
        "",
        "## Survivors Inside 80-89",
        "",
        "Criteria: minimum 10 trades, PF > 1.10, positive Total R.",
        "",
        *_rank_table(result.get("survivors_inside_80_89", [])),
        "",
        "## Top Subgroup Removal Counterfactual",
        "",
        f"- Removed subgroup: {counterfactual.get('removed_group', 'none')}",
        f"- Removed metrics: {_metrics_inline(counterfactual.get('removed_metrics', {}))}",
        f"- Remaining metrics: {_metrics_inline(counterfactual.get('remaining_metrics', {}))}",
        "",
        "## Breakdowns",
        "",
    ]
    for title, key in (
        ("By Symbol", "symbol"),
        ("By Session", "session"),
        ("By Market Regime", "market_regime"),
        ("By Setup Type", "setup_type"),
        ("By Direction", "direction"),
        ("By Entry Context", "entry_context"),
        ("By Liquidity Context", "liquidity_context"),
        ("By Warning", "warning"),
        ("By Penalty", "penalty"),
        ("By Rejection Reason", "rejection_reason"),
        ("By Trend Alignment", "trend_alignment"),
        ("By HTF Alignment", "htf_alignment"),
    ):
        lines.extend([f"### {title}", "", *_group_table(breakdowns.get(key, {}), title), ""])
    lines.extend(["## Counterfactual Recommendation", "", answers.get("counterfactual_recommendation", "continue monitoring")])
    return "\n".join(lines).rstrip() + "\n"


def classify_loss_component(metrics: dict[str, Any]) -> str:
    trades = int(metrics.get("trades", 0) or 0)
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    pf = _pf_float(metrics.get("profit_factor"))
    if total_r >= 0 or pf >= 1:
        return "NOISE"
    if trades >= MIN_CRITICAL_TRADES and total_r <= -5:
        return "CRITICAL"
    if trades >= MIN_IMPORTANT_TRADES:
        return "IMPORTANT"
    if trades >= 3:
        return "WATCH"
    return "NOISE"


def _answers(
    *,
    metrics: dict[str, Any],
    toxic_subgroups: list[dict[str, Any]],
    survivors: list[dict[str, Any]],
    counterfactual: dict[str, Any],
) -> dict[str, str]:
    bucket_bad = float(metrics.get("total_r", 0.0) or 0.0) < 0 and _pf_float(metrics.get("profit_factor")) < 1.0
    main_loss = _describe_group(toxic_subgroups[0]) if toxic_subgroups else "none"
    safe_survivor = _describe_group(survivors[0]) if survivors else "none"
    classification = classify_loss_component(metrics)
    remaining_metrics = counterfactual.get("remaining_metrics", {})
    improves_after_partial = _pf_float(remaining_metrics.get("profit_factor")) > _pf_float(metrics.get("profit_factor"))
    if not bucket_bad:
        action = "KEEP"
        recommendation = "Keep score 80-89 active; current evidence is not negative."
    elif survivors:
        action = "PARTIAL_BLOCK"
        recommendation = f"Investigate partial block on `{main_loss}` while preserving survivor `{safe_survivor}`."
    elif classification == "CRITICAL" and not survivors:
        action = "FULL_BLOCK"
        recommendation = "Shadow-test full block of score 80-89; no survivor met sample and PF criteria."
    elif improves_after_partial:
        action = "PARTIAL_BLOCK"
        recommendation = f"Shadow-test partial block on `{main_loss}`."
    else:
        action = "PARTIAL_BLOCK"
        recommendation = "Continue with targeted subgroup investigation before any full block."
    return {
        "entire_bucket_bad": "YES" if bucket_bad else "NO",
        "main_loss_subgroup": main_loss,
        "safe_survivor": safe_survivor,
        "recommended_action": action,
        "counterfactual_recommendation": recommendation,
    }


def _remove_group_counterfactual(rows: list[dict[str, Any]], group: dict[str, Any] | None) -> dict[str, Any]:
    if not group:
        return {"removed_group": "none", "removed_metrics": _metrics([]), "remaining_metrics": _metrics(rows)}
    dimension = str(group.get("dimension") or "")
    value = str(group.get("value") or "")
    removed = [row for row in rows if _belongs_to_group(row, dimension, value)]
    remaining = [row for row in rows if not _belongs_to_group(row, dimension, value)]
    return {
        "removed_group": f"{dimension}={value}",
        "removed_metrics": _metrics(removed),
        "remaining_metrics": _metrics(remaining),
    }


def _belongs_to_group(row: dict[str, Any], dimension: str, value: str) -> bool:
    if dimension in {"warning", "penalty", "rejection_reason"}:
        fields = {
            "warning": ("warnings", "avoidance_warnings"),
            "penalty": ("penalties",),
            "rejection_reason": ("rejection_reasons",),
        }[dimension]
        tokens: set[str] = set()
        for field in fields:
            tokens |= _tokens(row.get(field))
        return value in tokens or (value == "none" and not tokens)
    return _field_value(row, dimension) == value


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
    toxic = [
        row
        for row in groups
        if float(row.get("metrics", {}).get("total_r", 0.0) or 0.0) < 0
        and int(row.get("metrics", {}).get("trades", 0) or 0) > 0
    ]
    return sorted(
        toxic,
        key=lambda row: (
            float(row["metrics"].get("total_r", 0.0)),
            _pf_float(row["metrics"].get("profit_factor")),
            -int(row["metrics"].get("trades", 0) or 0),
        ),
    )[:30]


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
    return sorted(
        survivors,
        key=lambda row: (
            float(row["metrics"].get("total_r", 0.0)),
            _pf_float(row["metrics"].get("profit_factor")),
            -int(row["metrics"].get("trades", 0) or 0),
        ),
        reverse=True,
    )


def _group_summary(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[_field_value(row, field)].append(row)
    return _summaries(groups)


def _token_summary(rows: list[dict[str, Any]], *fields: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        tokens: set[str] = set()
        for field in fields:
            tokens |= _tokens(row.get(field))
        if not tokens:
            groups["none"].append(row)
            continue
        for token in sorted(tokens):
            groups[token].append(row)
    return _summaries(groups)


def _summaries(groups: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    result = {}
    for key, items in sorted(groups.items()):
        metrics = _metrics(items)
        result[key] = {"metrics": metrics, "classification": classify_loss_component(metrics)}
    return result


def _field_value(row: dict[str, Any], field: str) -> str:
    if field == "liquidity_context":
        return _liquidity_context(row)
    if field == "trend_alignment":
        return _trend_alignment(row)
    if field == "htf_alignment":
        return _htf_alignment(row)
    return str(row.get(field) or "UNKNOWN")


def _in_score_bucket_80_89(value: object) -> bool:
    score = _float(value)
    return score is not None and 80 <= score < 90


def _is_bullish_sweep(row: dict[str, Any]) -> bool:
    return _liquidity_context(row) == "sweep:bullish_sweep"


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
    direction = str(row.get("direction") or "").strip().lower()
    higher = str(row.get("trend_higher") or row.get("trend_4h") or row.get("trend_higher_timeframe") or "").strip().lower()
    if not direction or not higher:
        return "UNKNOWN"
    if direction == "long" and higher == "bullish":
        return "aligned_with_htf"
    if direction == "short" and higher == "bearish":
        return "aligned_with_htf"
    if direction == "long" and higher == "bearish":
        return "against_htf"
    if direction == "short" and higher == "bullish":
        return "against_htf"
    return f"htf_{higher}"


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
        "winrate": round(len(wins) / len(values) * 100, 2) if values else 0.0,
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
