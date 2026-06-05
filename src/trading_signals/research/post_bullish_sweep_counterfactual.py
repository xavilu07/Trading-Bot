from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


MIN_IMPORTANT_TRADES = 10
MIN_CRITICAL_TRADES = 20


def analyze_post_bullish_sweep_counterfactual(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    all_trades = load_canonical_closed_trades(data_path)
    bullish_sweep_trades = [row for row in all_trades if _is_bullish_sweep(row)]
    remaining = [row for row in all_trades if not _is_bullish_sweep(row)]
    current_metrics = _metrics(all_trades)
    removed_metrics = _metrics(bullish_sweep_trades)
    remaining_metrics = _metrics(remaining)
    breakdowns = {
        "symbol": _group_summary(remaining, "symbol"),
        "session": _group_summary(remaining, "session"),
        "market_regime": _group_summary(remaining, "market_regime"),
        "setup_type": _group_summary(remaining, "setup_type"),
        "score_bucket": _group_summary(remaining, "score_bucket"),
        "warning": _token_summary(remaining, "warnings", "avoidance_warnings"),
        "penalty": _token_summary(remaining, "penalties"),
        "rejection_reason": _token_summary(remaining, "rejection_reasons"),
        "liquidity_context": _group_summary(remaining, "liquidity_context"),
        "trend_alignment": _group_summary(remaining, "trend_alignment"),
        "long_subset": _subset_summary(remaining, direction="long"),
        "short_subset": _subset_summary(remaining, direction="short"),
    }
    enemy_ranking = _rank_new_enemies(_flatten_groups(breakdowns))
    answers = _answers(
        current_metrics=current_metrics,
        remaining_metrics=remaining_metrics,
        removed_metrics=removed_metrics,
        enemy_ranking=enemy_ranking,
    )
    return {
        "scope": "POST_BULLISH_SWEEP_COUNTERFACTUAL_ANALYSIS",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "current_metrics": current_metrics,
        "removed_bullish_sweep_metrics": removed_metrics,
        "post_bullish_sweep_metrics": remaining_metrics,
        "removed_trades": len(bullish_sweep_trades),
        "remaining_trades": len(remaining),
        "breakdowns": breakdowns,
        "new_enemy_ranking": enemy_ranking,
        "answers": answers,
        "next_investigation_recommendation": answers["next_investigation_recommendation"],
    }


def write_post_bullish_sweep_counterfactual_report(result: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "post_bullish_sweep_counterfactual.md"
    path.write_text(format_post_bullish_sweep_counterfactual_markdown(result), encoding="utf-8")
    return path


def format_post_bullish_sweep_counterfactual_markdown(result: dict[str, Any]) -> str:
    answers = result.get("answers", {})
    breakdowns = result.get("breakdowns", {})
    lines = [
        "# POST_BULLISH_SWEEP_COUNTERFACTUAL_ANALYSIS",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        "Method: removed all trades where `liquidity_context=sweep:bullish_sweep` or `liquidity_sweep=bullish_sweep`.",
        "",
        "## Executive Summary",
        "",
        f"- Current system: {_metrics_inline(result.get('current_metrics', {}))}",
        f"- Removed bullish_sweep only: {_metrics_inline(result.get('removed_bullish_sweep_metrics', {}))}",
        f"- System without bullish_sweep: {_metrics_inline(result.get('post_bullish_sweep_metrics', {}))}",
        f"- Is system profitable after removing bullish_sweep? {answers.get('system_profitable_after_removal', '')}",
        f"- Largest loss contributor: {answers.get('largest_loss_contributor', '')}",
        f"- Second largest loss contributor: {answers.get('second_largest_loss_contributor', '')}",
        f"- Third largest loss contributor: {answers.get('third_largest_loss_contributor', '')}",
        f"- Remaining component with enough sample size: {answers.get('component_with_sample_size', '')}",
        f"- Probably noise: {answers.get('probably_noise', '')}",
        "",
        "## New Enemy Ranking",
        "",
        *_rank_table(result.get("new_enemy_ranking", [])),
        "",
        "## Worst Symbols",
        "",
        *_group_table(breakdowns.get("symbol", {}), "Symbol"),
        "",
        "## Worst Sessions",
        "",
        *_group_table(breakdowns.get("session", {}), "Session"),
        "",
        "## Worst Market Regimes",
        "",
        *_group_table(breakdowns.get("market_regime", {}), "Market Regime"),
        "",
        "## Worst Setup Types",
        "",
        *_group_table(breakdowns.get("setup_type", {}), "Setup Type"),
        "",
        "## Worst Score Buckets",
        "",
        *_group_table(breakdowns.get("score_bucket", {}), "Score Bucket"),
        "",
        "## Worst Warnings",
        "",
        *_group_table(breakdowns.get("warning", {}), "Warning"),
        "",
        "## Worst Penalties",
        "",
        *_group_table(breakdowns.get("penalty", {}), "Penalty"),
        "",
        "## Worst Rejection Reasons",
        "",
        *_group_table(breakdowns.get("rejection_reason", {}), "Rejection Reason"),
        "",
        "## Worst Liquidity Contexts Excluding Bullish Sweep",
        "",
        *_group_table(breakdowns.get("liquidity_context", {}), "Liquidity Context"),
        "",
        "## Worst Trend Alignment Groups",
        "",
        *_group_table(breakdowns.get("trend_alignment", {}), "Trend Alignment"),
        "",
        "## Worst LONG Subsets",
        "",
        *_group_table(breakdowns.get("long_subset", {}), "LONG Subset"),
        "",
        "## Worst SHORT Subsets",
        "",
        *_group_table(breakdowns.get("short_subset", {}), "SHORT Subset"),
        "",
        "## Next Investigation Recommendation",
        "",
        answers.get("next_investigation_recommendation", "continue monitoring"),
    ]
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
    current_metrics: dict[str, Any],
    remaining_metrics: dict[str, Any],
    removed_metrics: dict[str, Any],
    enemy_ranking: list[dict[str, Any]],
) -> dict[str, str]:
    top = enemy_ranking[:3]
    largest = _describe_group(top[0]) if len(top) >= 1 else "none"
    second = _describe_group(top[1]) if len(top) >= 2 else "none"
    third = _describe_group(top[2]) if len(top) >= 3 else "none"
    enough_sample = next((row for row in enemy_ranking if row.get("classification") in {"CRITICAL", "IMPORTANT"}), None)
    noise = next((row for row in enemy_ranking if row.get("classification") == "NOISE"), None)
    system_profitable = (
        float(remaining_metrics.get("total_r", 0.0) or 0.0) > 0
        and _pf_float(remaining_metrics.get("profit_factor")) > 1.0
    )
    if enough_sample:
        next_investigation = f"Deep dive `{enough_sample.get('dimension')}={enough_sample.get('value')}`."
    else:
        next_investigation = "Continue monitoring; no remaining negative component has enough sample size."
    return {
        "system_profitable_after_removal": "YES" if system_profitable else "NO",
        "largest_loss_contributor": largest,
        "second_largest_loss_contributor": second,
        "third_largest_loss_contributor": third,
        "component_with_sample_size": _describe_group(enough_sample) if enough_sample else "none",
        "probably_noise": _describe_group(noise) if noise else "none",
        "next_investigation_recommendation": next_investigation,
        "current_vs_post_delta": (
            f"PF {current_metrics.get('profit_factor')} -> {remaining_metrics.get('profit_factor')}; "
            f"TotalR {current_metrics.get('total_r')} -> {remaining_metrics.get('total_r')}; "
            f"removed TotalR {removed_metrics.get('total_r')}"
        ),
    }


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


def _rank_new_enemies(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    loss_groups = [
        row
        for row in groups
        if float(row.get("metrics", {}).get("total_r", 0.0) or 0.0) < 0
        and int(row.get("metrics", {}).get("trades", 0) or 0) > 0
    ]
    return sorted(
        loss_groups,
        key=lambda row: (
            float(row["metrics"].get("total_r", 0.0)),
            _pf_float(row["metrics"].get("profit_factor")),
            -int(row["metrics"].get("trades", 0) or 0),
        ),
    )[:30]


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


def _subset_summary(rows: list[dict[str, Any]], *, direction: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if str(row.get("direction") or "").lower() != direction:
            continue
        groups[_subset_key(row)].append(row)
    return _summaries(groups)


def _summaries(groups: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    result = {}
    for key, items in sorted(groups.items()):
        metrics = _metrics(items)
        result[key] = {"metrics": metrics, "classification": classify_loss_component(metrics)}
    return result


def _field_value(row: dict[str, Any], field: str) -> str:
    if field == "score_bucket":
        return _score_bucket(row.get("score"))
    if field == "liquidity_context":
        return _liquidity_context(row)
    if field == "trend_alignment":
        return _trend_alignment(row)
    return str(row.get(field) or "UNKNOWN")


def _subset_key(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("direction") or "unknown").upper(),
            str(row.get("setup_type") or "UNKNOWN").upper(),
            str(row.get("session") or "UNKNOWN").upper(),
            str(row.get("market_regime") or "UNKNOWN").upper(),
            str(row.get("entry_context") or "UNKNOWN").upper(),
            str(row.get("trade_location") or "UNKNOWN"),
        ]
    )


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
