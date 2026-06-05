from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


MIN_SUBGROUP_TRADES = 10
MIN_CRITICAL_TRADES = 20


DIMENSIONS = (
    "symbol",
    "session",
    "direction",
    "setup_type",
    "entry_context",
    "liquidity_context",
    "warning",
    "penalty",
    "rejection_reason",
    "trend_alignment",
    "htf_alignment",
)


def analyze_score_80_89_regime_decomposition(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    all_trades = load_canonical_closed_trades(data_path)
    bucket_rows = [row for row in all_trades if not _is_bullish_sweep(row) and _in_score_bucket_80_89(row.get("score"))]
    trending_rows = [row for row in bucket_rows if _market_regime(row) == "TRENDING"]
    ranging_rows = [row for row in bucket_rows if _market_regime(row) == "RANGING"]
    trending_breakdowns = _build_breakdowns(trending_rows)
    ranging_breakdowns = _build_breakdowns(ranging_rows)
    regime_difference = _regime_difference_analysis(trending_breakdowns, ranging_breakdowns)
    toxic_trending = _toxic_trending_subgroups(trending_breakdowns)
    safe_ranging = _safe_ranging_survivors(ranging_breakdowns)
    counterfactual = _remove_group_counterfactual(bucket_rows, toxic_trending[0] if toxic_trending else None)
    answers = _answers(
        trending_metrics=_metrics(trending_rows),
        ranging_metrics=_metrics(ranging_rows),
        toxic_trending=toxic_trending,
        safe_ranging=safe_ranging,
        regime_difference=regime_difference,
        counterfactual=counterfactual,
    )
    return {
        "scope": "SCORE_80_89_REGIME_DECOMPOSITION",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "method": "Exclude bullish_sweep first, then compare score 80-89 TRENDING vs RANGING.",
        "metrics": {
            "all_score_80_89": _metrics(bucket_rows),
            "trending": _metrics(trending_rows),
            "ranging": _metrics(ranging_rows),
        },
        "classification": {
            "trending": classify_loss_component(_metrics(trending_rows)),
            "ranging": classify_loss_component(_metrics(ranging_rows)),
        },
        "breakdowns": {
            "trending": trending_breakdowns,
            "ranging": ranging_breakdowns,
        },
        "regime_difference_analysis": regime_difference,
        "toxic_trending_subgroups": toxic_trending,
        "safe_ranging_survivors": safe_ranging,
        "top_trending_subgroup_counterfactual": counterfactual,
        "answers": answers,
        "next_recommended_investigation": answers["next_recommended_investigation"],
    }


def write_score_80_89_regime_decomposition_report(result: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "score_80_89_regime_decomposition.md"
    path.write_text(format_score_80_89_regime_decomposition_markdown(result), encoding="utf-8")
    return path


def format_score_80_89_regime_decomposition_markdown(result: dict[str, Any]) -> str:
    answers = result.get("answers", {})
    metrics = result.get("metrics", {})
    counterfactual = result.get("top_trending_subgroup_counterfactual", {})
    lines = [
        "# SCORE_80_89_REGIME_DECOMPOSITION",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        f"Method: {result.get('method')}",
        "",
        "## Executive Summary",
        "",
        f"- Score 80-89 total: {_metrics_inline(metrics.get('all_score_80_89', {}))}",
        f"- TRENDING: {_metrics_inline(metrics.get('trending', {}))}",
        f"- RANGING: {_metrics_inline(metrics.get('ranging', {}))}",
        f"- Why does TRENDING lose money? {answers.get('why_trending_loses', '')}",
        f"- Why does RANGING survive? {answers.get('why_ranging_survives', '')}",
        f"- Main difference subgroup: {answers.get('main_difference_subgroup', '')}",
        f"- PF if worst TRENDING subgroup removed: {counterfactual.get('remaining_metrics', {}).get('profit_factor', 0)}",
        f"- Future shadow filter evidence: {answers.get('future_shadow_filter_evidence', '')}",
        "",
        "## Regime Difference Analysis",
        "",
        *_difference_table(result.get("regime_difference_analysis", {})),
        "",
        "## Toxic TRENDING Subgroups",
        "",
        "Criteria: minimum 10 trades, negative Total R, PF < 1.",
        "",
        *_rank_table(result.get("toxic_trending_subgroups", [])),
        "",
        "## Safe RANGING Survivors",
        "",
        "Criteria: minimum 10 trades, PF > 1.1, positive Total R.",
        "",
        *_rank_table(result.get("safe_ranging_survivors", [])),
        "",
        "## Top TRENDING Subgroup Removal Counterfactual",
        "",
        f"- Removed subgroup: {counterfactual.get('removed_group', 'none')}",
        f"- Removed metrics: {_metrics_inline(counterfactual.get('removed_metrics', {}))}",
        f"- Remaining metrics: {_metrics_inline(counterfactual.get('remaining_metrics', {}))}",
        "",
        "## TRENDING Breakdowns",
        "",
    ]
    for title, key in _dimension_titles():
        lines.extend([f"### {title}", "", *_group_table(result.get("breakdowns", {}).get("trending", {}).get(key, {}), title), ""])
    lines.extend(["## RANGING Breakdowns", ""])
    for title, key in _dimension_titles():
        lines.extend([f"### {title}", "", *_group_table(result.get("breakdowns", {}).get("ranging", {}).get(key, {}), title), ""])
    lines.extend(["## Next Recommended Investigation", "", answers.get("next_recommended_investigation", "continue monitoring")])
    return "\n".join(lines).rstrip() + "\n"


def classify_loss_component(metrics: dict[str, Any]) -> str:
    trades = int(metrics.get("trades", 0) or 0)
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    pf = _pf_float(metrics.get("profit_factor"))
    if total_r >= 0 or pf >= 1:
        return "NOISE"
    if trades >= MIN_CRITICAL_TRADES and total_r <= -5:
        return "CRITICAL"
    if trades >= MIN_SUBGROUP_TRADES:
        return "IMPORTANT"
    if trades >= 3:
        return "WATCH"
    return "NOISE"


def _build_breakdowns(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "symbol": _group_summary(rows, "symbol"),
        "session": _group_summary(rows, "session"),
        "direction": _group_summary(rows, "direction"),
        "setup_type": _group_summary(rows, "setup_type"),
        "entry_context": _group_summary(rows, "entry_context"),
        "liquidity_context": _group_summary(rows, "liquidity_context"),
        "warning": _token_summary(rows, "warnings", "avoidance_warnings"),
        "penalty": _token_summary(rows, "penalties"),
        "rejection_reason": _token_summary(rows, "rejection_reasons"),
        "trend_alignment": _group_summary(rows, "trend_alignment"),
        "htf_alignment": _group_summary(rows, "htf_alignment"),
    }


def _regime_difference_analysis(
    trending: dict[str, dict[str, dict[str, Any]]],
    ranging: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for dimension in DIMENSIONS:
        trending_groups = trending.get(dimension, {})
        ranging_groups = ranging.get(dimension, {})
        result[dimension] = {
            "biggest_winner_trending": _best_group(dimension, trending_groups),
            "biggest_loser_trending": _worst_group(dimension, trending_groups),
            "biggest_winner_ranging": _best_group(dimension, ranging_groups),
            "biggest_loser_ranging": _worst_group(dimension, ranging_groups),
            "largest_total_r_gap": _largest_gap(dimension, trending_groups, ranging_groups),
        }
    return result


def _toxic_trending_subgroups(breakdowns: dict[str, dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    for dimension, groups in breakdowns.items():
        for value, payload in groups.items():
            metrics = payload.get("metrics", {})
            if (
                int(metrics.get("trades", 0) or 0) >= MIN_SUBGROUP_TRADES
                and float(metrics.get("total_r", 0.0) or 0.0) < 0
                and _pf_float(metrics.get("profit_factor")) < 1.0
            ):
                rows.append({"dimension": dimension, "value": value, "metrics": metrics, "classification": classify_loss_component(metrics)})
    return sorted(rows, key=lambda row: (_pf_float(row["metrics"].get("profit_factor")), float(row["metrics"].get("total_r", 0.0))))[:30]


def _safe_ranging_survivors(breakdowns: dict[str, dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    for dimension, groups in breakdowns.items():
        for value, payload in groups.items():
            metrics = payload.get("metrics", {})
            if (
                int(metrics.get("trades", 0) or 0) >= MIN_SUBGROUP_TRADES
                and _pf_float(metrics.get("profit_factor")) > 1.10
                and float(metrics.get("total_r", 0.0) or 0.0) > 0
            ):
                rows.append({"dimension": dimension, "value": value, "metrics": metrics, "classification": "NOISE"})
    return sorted(rows, key=lambda row: (float(row["metrics"].get("total_r", 0.0)), _pf_float(row["metrics"].get("profit_factor"))), reverse=True)[:30]


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


def _answers(
    *,
    trending_metrics: dict[str, Any],
    ranging_metrics: dict[str, Any],
    toxic_trending: list[dict[str, Any]],
    safe_ranging: list[dict[str, Any]],
    regime_difference: dict[str, dict[str, Any]],
    counterfactual: dict[str, Any],
) -> dict[str, str]:
    worst = toxic_trending[0] if toxic_trending else None
    safe = safe_ranging[0] if safe_ranging else None
    gap = _top_gap(regime_difference)
    evidence = "YES" if worst and int(worst.get("metrics", {}).get("trades", 0) or 0) >= MIN_SUBGROUP_TRADES else "NO"
    if worst:
        next_investigation = f"Deep dive `{worst.get('dimension')}={worst.get('value')}` inside score 80-89 TRENDING."
    elif gap:
        next_investigation = f"Deep dive regime gap `{gap.get('dimension')}={gap.get('value')}`."
    else:
        next_investigation = "Continue monitoring; no robust regime-specific subgroup found."
    return {
        "why_trending_loses": _describe_group(worst) if worst else f"TRENDING metrics are {_metrics_inline(trending_metrics)} with no 10-trade toxic subgroup.",
        "why_ranging_survives": _describe_group(safe) if safe else f"RANGING metrics are {_metrics_inline(ranging_metrics)} but no survivor met 10-trade criteria.",
        "main_difference_subgroup": _describe_gap(gap),
        "pf_after_subgroup_removed": str(counterfactual.get("remaining_metrics", {}).get("profit_factor", 0)),
        "future_shadow_filter_evidence": evidence,
        "next_recommended_investigation": next_investigation,
    }


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


def _best_group(dimension: str, groups: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not groups:
        return _empty_group(dimension)
    value, payload = max(groups.items(), key=lambda item: float(item[1].get("metrics", {}).get("total_r", 0.0)))
    return {"dimension": dimension, "value": value, "metrics": payload.get("metrics", {}), "classification": payload.get("classification", "NOISE")}


def _worst_group(dimension: str, groups: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not groups:
        return _empty_group(dimension)
    value, payload = min(groups.items(), key=lambda item: float(item[1].get("metrics", {}).get("total_r", 0.0)))
    return {"dimension": dimension, "value": value, "metrics": payload.get("metrics", {}), "classification": payload.get("classification", "NOISE")}


def _largest_gap(dimension: str, trending: dict[str, dict[str, Any]], ranging: dict[str, dict[str, Any]]) -> dict[str, Any]:
    values = sorted(set(trending) | set(ranging))
    if not values:
        return _empty_gap(dimension)
    gaps = []
    for value in values:
        trend_r = float(trending.get(value, {}).get("metrics", {}).get("total_r", 0.0) or 0.0)
        range_r = float(ranging.get(value, {}).get("metrics", {}).get("total_r", 0.0) or 0.0)
        gaps.append({"dimension": dimension, "value": value, "trending_total_r": trend_r, "ranging_total_r": range_r, "gap": _round(range_r - trend_r)})
    return max(gaps, key=lambda row: abs(float(row.get("gap", 0.0))))


def _top_gap(regime_difference: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    gaps = [payload.get("largest_total_r_gap", {}) for payload in regime_difference.values()]
    gaps = [gap for gap in gaps if gap and gap.get("value") != "none"]
    if not gaps:
        return None
    return max(gaps, key=lambda row: abs(float(row.get("gap", 0.0) or 0.0)))


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


def _field_value(row: dict[str, Any], field: str) -> str:
    if field == "liquidity_context":
        return _liquidity_context(row)
    if field == "trend_alignment":
        return _trend_alignment(row)
    if field == "htf_alignment":
        return _htf_alignment(row)
    return str(row.get(field) or "UNKNOWN")


def _market_regime(row: dict[str, Any]) -> str:
    return str(row.get("market_regime") or "UNKNOWN").upper()


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


def _empty_group(dimension: str) -> dict[str, Any]:
    return {"dimension": dimension, "value": "none", "metrics": _metrics([]), "classification": "NOISE"}


def _empty_gap(dimension: str) -> dict[str, Any]:
    return {"dimension": dimension, "value": "none", "trending_total_r": 0.0, "ranging_total_r": 0.0, "gap": 0.0}


def _describe_group(row: dict[str, Any] | None) -> str:
    if not row:
        return "none"
    metrics = row.get("metrics", {})
    return (
        f"{row.get('dimension')}={row.get('value')} "
        f"(trades={metrics.get('trades', 0)}, PF={metrics.get('profit_factor', 0)}, "
        f"TotalR={metrics.get('total_r', 0)}, class={row.get('classification', 'NOISE')})"
    )


def _describe_gap(row: dict[str, Any] | None) -> str:
    if not row:
        return "none"
    return (
        f"{row.get('dimension')}={row.get('value')} "
        f"(TRENDING TotalR={row.get('trending_total_r', 0)}, RANGING TotalR={row.get('ranging_total_r', 0)}, "
        f"gap={row.get('gap', 0)})"
    )


def _metrics_inline(metrics: object) -> str:
    if not isinstance(metrics, dict):
        metrics = {}
    return (
        f"trades={metrics.get('trades', 0)}, WR={metrics.get('winrate', 0)}%, "
        f"PF={metrics.get('profit_factor', 0)}, TotalR={metrics.get('total_r', 0)}, AvgR={metrics.get('avg_r', 0)}"
    )


def _dimension_titles() -> tuple[tuple[str, str], ...]:
    return (
        ("By Symbol", "symbol"),
        ("By Session", "session"),
        ("By Direction", "direction"),
        ("By Setup Type", "setup_type"),
        ("By Entry Context", "entry_context"),
        ("By Liquidity Context", "liquidity_context"),
        ("By Warning", "warning"),
        ("By Penalty", "penalty"),
        ("By Rejection Reason", "rejection_reason"),
        ("By Trend Alignment", "trend_alignment"),
        ("By HTF Alignment", "htf_alignment"),
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


def _difference_table(payload: object) -> list[str]:
    lines = [
        "| Dimension | Winner TRENDING | Loser TRENDING | Winner RANGING | Loser RANGING | Largest Gap |",
        "|---|---|---|---|---|---|",
    ]
    if not isinstance(payload, dict) or not payload:
        lines.append("| none | none | none | none | none | none |")
        return lines
    for dimension, item in payload.items():
        lines.append(
            f"| {dimension} | {_short_group(item.get('biggest_winner_trending'))} | {_short_group(item.get('biggest_loser_trending'))} | "
            f"{_short_group(item.get('biggest_winner_ranging'))} | {_short_group(item.get('biggest_loser_ranging'))} | "
            f"{_describe_gap(item.get('largest_total_r_gap'))} |"
        )
    return lines


def _short_group(row: object) -> str:
    if not isinstance(row, dict):
        return "none"
    metrics = row.get("metrics", {})
    return f"{row.get('value', 'none')} TotalR={metrics.get('total_r', 0)} PF={metrics.get('profit_factor', 0)}"
