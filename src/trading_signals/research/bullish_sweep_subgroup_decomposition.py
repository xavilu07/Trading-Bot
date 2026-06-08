from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


MIN_TOXIC_TRADES = 5
MIN_SURVIVOR_TRADES = 5


def analyze_bullish_sweep_subgroup_decomposition(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    all_trades = load_canonical_closed_trades(data_path)
    bullish_rows = [row for row in all_trades if _is_bullish_sweep(row)]
    metrics = _metrics(bullish_rows)
    breakdowns = {
        "symbol": _group_summary(bullish_rows, "symbol"),
        "session": _group_summary(bullish_rows, "session"),
        "direction": _group_summary(bullish_rows, "direction"),
        "setup_type": _group_summary(bullish_rows, "setup_type"),
        "score_bucket": _group_summary(bullish_rows, "score_bucket"),
        "market_regime": _group_summary(bullish_rows, "market_regime"),
        "liquidity_context": _group_summary(bullish_rows, "liquidity_context"),
        "trend_alignment": _group_summary(bullish_rows, "trend_alignment"),
        "htf_alignment": _group_summary(bullish_rows, "htf_alignment"),
        "entry_context": _group_summary(bullish_rows, "entry_context"),
    }
    groups = _flatten_groups(breakdowns)
    toxic = _rank_toxic(groups)
    survivors = _rank_survivors(groups)
    counterfactuals = _counterfactuals_by_subgroup(bullish_rows, groups)
    impact_ranking = _rank_impact(counterfactuals)
    recommendation = _recommendation(metrics=metrics, toxic=toxic, survivors=survivors, impact=impact_ranking)
    return {
        "scope": "BULLISH_SWEEP_SUBGROUP_DECOMPOSITION",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "metrics": metrics,
        "classification": _classify(metrics),
        "breakdowns": breakdowns,
        "toxic_subgroups": toxic,
        "profitable_survivors": survivors,
        "counterfactual_removal_by_subgroup": counterfactuals,
        "impact_ranking": impact_ranking,
        "recommended_action": recommendation,
    }


def write_bullish_sweep_subgroup_decomposition_report(result: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "bullish_sweep_subgroup_decomposition.md"
    path.write_text(format_bullish_sweep_subgroup_decomposition_markdown(result), encoding="utf-8")
    return path


def format_bullish_sweep_subgroup_decomposition_markdown(result: dict[str, Any]) -> str:
    breakdowns = result.get("breakdowns", {})
    lines = [
        "# BULLISH_SWEEP_SUBGROUP_DECOMPOSITION",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        "Scope: trades where `liquidity_context=sweep:bullish_sweep` or `liquidity_sweep=bullish_sweep`.",
        f"Classification: {result.get('classification')}",
        f"Recommended action: {result.get('recommended_action')}",
        "",
        "## Summary",
        "",
        f"- Bullish sweep: {_metrics_inline(result.get('metrics', {}))}",
        f"- Toxic subgroups: {len(result.get('toxic_subgroups', []))}",
        f"- Profitable survivors: {len(result.get('profitable_survivors', []))}",
        "",
        "## Toxic Subgroups",
        "",
        *_rank_table(result.get("toxic_subgroups", [])),
        "",
        "## Profitable Survivors",
        "",
        *_rank_table(result.get("profitable_survivors", [])),
        "",
        "## Counterfactual Removal By Subgroup",
        "",
        *_counterfactual_table(result.get("counterfactual_removal_by_subgroup", [])),
        "",
        "## Impact Ranking",
        "",
        *_counterfactual_table(result.get("impact_ranking", [])),
        "",
        "## Breakdowns",
        "",
    ]
    for title, key in (
        ("By Symbol", "symbol"),
        ("By Session", "session"),
        ("By Direction", "direction"),
        ("By Setup Type", "setup_type"),
        ("By Score Bucket", "score_bucket"),
        ("By Market Regime", "market_regime"),
        ("By Liquidity Context", "liquidity_context"),
        ("By Trend Alignment", "trend_alignment"),
        ("By HTF Alignment", "htf_alignment"),
        ("By Entry Context", "entry_context"),
    ):
        lines.extend([f"### {title}", "", *_group_table(breakdowns.get(key, {}), title), ""])
    return "\n".join(lines).rstrip() + "\n"


def _recommendation(
    *,
    metrics: dict[str, Any],
    toxic: list[dict[str, Any]],
    survivors: list[dict[str, Any]],
    impact: list[dict[str, Any]],
) -> str:
    classification = _classify(metrics)
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    if classification == "PROMISING":
        return "RECLASSIFY"
    if survivors and toxic:
        return "PARTIAL_BLOCK"
    if survivors and not toxic:
        return "INVESTIGATE_SURVIVOR"
    if classification == "TOXIC" and total_r < 0 and not survivors:
        return "KEEP_FULL_BLOCK"
    if impact and float(impact[0].get("r_improvement", 0.0) or 0.0) > 0:
        return "PARTIAL_BLOCK"
    return "KEEP_FULL_BLOCK"


def _classify(metrics: dict[str, Any]) -> str:
    trades = int(metrics.get("trades", 0) or 0)
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    pf = _pf_float(metrics.get("profit_factor"))
    winrate = float(metrics.get("winrate", 0.0) or 0.0)
    if trades == 0:
        return "NEUTRAL"
    if total_r < 0 and pf < 1:
        return "TOXIC"
    if total_r > 0 and pf > 1.1 and winrate >= 40:
        return "PROMISING"
    return "NEUTRAL"


def _flatten_groups(breakdowns: dict[str, dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dimension, groups in breakdowns.items():
        for value, payload in groups.items():
            rows.append(
                {
                    "dimension": dimension,
                    "value": value,
                    "metrics": payload.get("metrics", {}),
                    "classification": payload.get("classification", "NEUTRAL"),
                }
            )
    return rows


def _rank_toxic(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    toxic = []
    for row in groups:
        metrics = row.get("metrics", {})
        if (
            int(metrics.get("trades", 0) or 0) >= MIN_TOXIC_TRADES
            and float(metrics.get("total_r", 0.0) or 0.0) < 0
            and _pf_float(metrics.get("profit_factor")) < 1
        ):
            toxic.append(row)
    return sorted(toxic, key=lambda row: (_pf_float(row["metrics"].get("profit_factor")), float(row["metrics"].get("total_r", 0.0))))[:30]


def _rank_survivors(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    survivors = []
    for row in groups:
        metrics = row.get("metrics", {})
        if (
            int(metrics.get("trades", 0) or 0) >= MIN_SURVIVOR_TRADES
            and float(metrics.get("total_r", 0.0) or 0.0) > 0
            and _pf_float(metrics.get("profit_factor")) > 1.1
        ):
            survivors.append(row)
    return sorted(survivors, key=lambda row: (float(row["metrics"].get("total_r", 0.0)), _pf_float(row["metrics"].get("profit_factor"))), reverse=True)[:30]


def _counterfactuals_by_subgroup(rows: list[dict[str, Any]], groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current = _metrics(rows)
    results = []
    for group in groups:
        dimension = str(group.get("dimension") or "")
        value = str(group.get("value") or "")
        removed = [row for row in rows if _belongs_to_group(row, dimension, value)]
        if not removed:
            continue
        remaining = [row for row in rows if not _belongs_to_group(row, dimension, value)]
        remaining_metrics = _metrics(remaining)
        removed_metrics = _metrics(removed)
        results.append(
            {
                "dimension": dimension,
                "value": value,
                "removed_metrics": removed_metrics,
                "remaining_metrics": remaining_metrics,
                "trades_removed": removed_metrics["trades"],
                "pf_before": current["profit_factor"],
                "pf_after": remaining_metrics["profit_factor"],
                "total_r_before": current["total_r"],
                "total_r_after": remaining_metrics["total_r"],
                "r_improvement": _round(float(remaining_metrics["total_r"]) - float(current["total_r"])),
                "pf_improvement": _round(_pf_float(remaining_metrics["profit_factor"]) - _pf_float(current["profit_factor"])),
            }
        )
    return sorted(results, key=lambda row: (float(row["r_improvement"]), float(row["pf_improvement"]), int(row["trades_removed"])), reverse=True)


def _rank_impact(counterfactuals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        counterfactuals,
        key=lambda row: (float(row.get("r_improvement", 0.0) or 0.0), float(row.get("pf_improvement", 0.0) or 0.0), int(row.get("trades_removed", 0) or 0)),
        reverse=True,
    )[:30]


def _belongs_to_group(row: dict[str, Any], dimension: str, value: str) -> bool:
    return _field_value(row, dimension) == value


def _group_summary(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[_field_value(row, field)].append(row)
    return {key: {"metrics": _metrics(items), "classification": _classify(_metrics(items))} for key, items in sorted(groups.items())}


def _field_value(row: dict[str, Any], field: str) -> str:
    if field == "score_bucket":
        return _score_bucket(row.get("score"))
    if field == "liquidity_context":
        return _liquidity_context(row)
    if field == "trend_alignment":
        return _trend_alignment(row)
    if field == "htf_alignment":
        return _htf_alignment(row)
    return str(row.get(field) or "UNKNOWN")


def _is_bullish_sweep(row: dict[str, Any]) -> bool:
    return _liquidity_context(row) == "sweep:bullish_sweep"


def _liquidity_context(row: dict[str, Any]) -> str:
    explicit = str(row.get("liquidity_context") or "").strip()
    if explicit:
        return explicit
    sweep = str(row.get("liquidity_sweep") or "").strip()
    if sweep:
        return f"sweep:{sweep}"
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
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NEUTRAL |")
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
            f"{metrics.get('avg_r', 0)} | {value.get('classification', 'NEUTRAL') if isinstance(value, dict) else 'NEUTRAL'} |"
        )
    return lines


def _rank_table(rows: object) -> list[str]:
    lines = ["| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    if not isinstance(rows, list) or not rows:
        lines.append("| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NEUTRAL |")
        return lines
    for row in rows[:30]:
        metrics = row.get("metrics", {}) if isinstance(row, dict) else {}
        lines.append(
            f"| {row.get('dimension', '')} | {row.get('value', '')} | {metrics.get('trades', 0)} | "
            f"{metrics.get('wins', 0)} | {metrics.get('losses', 0)} | {metrics.get('winrate', 0)}% | "
            f"{metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} | "
            f"{row.get('classification', 'NEUTRAL')} |"
        )
    return lines


def _counterfactual_table(rows: object) -> list[str]:
    lines = [
        "| Dimension | Value | Removed Trades | PF Before | PF After | TotalR Before | TotalR After | R Improvement | PF Improvement |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    if not isinstance(rows, list) or not rows:
        lines.append("| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 |")
        return lines
    for row in rows[:30]:
        lines.append(
            f"| {row.get('dimension', '')} | {row.get('value', '')} | {row.get('trades_removed', 0)} | "
            f"{row.get('pf_before', 0)} | {row.get('pf_after', 0)} | {row.get('total_r_before', 0)} | "
            f"{row.get('total_r_after', 0)} | {row.get('r_improvement', 0)} | {row.get('pf_improvement', 0)} |"
        )
    return lines
