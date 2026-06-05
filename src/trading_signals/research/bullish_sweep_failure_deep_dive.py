from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


SURVIVOR_MIN_TRADES = 20


def analyze_bullish_sweep_failure_deep_dive(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    all_trades = load_canonical_closed_trades(data_path)
    rows = [row for row in all_trades if _liquidity_context(row) == "sweep:bullish_sweep"]
    metrics = _metrics(rows)
    breakdowns = {
        "symbol": _group_summary(rows, "symbol"),
        "session": _group_summary(rows, "session"),
        "market_regime": _group_summary(rows, "market_regime"),
        "score_bucket": _group_summary(rows, "score_bucket"),
        "setup_type": _group_summary(rows, "setup_type"),
        "entry_context": _group_summary(rows, "entry_context"),
        "trend_alignment": _group_summary(rows, "trend_alignment"),
        "reason": _reason_summary(rows),
        "direction": _group_summary(rows, "direction"),
        "htf_alignment": _group_summary(rows, "htf_alignment"),
    }
    groups = _flatten_groups(breakdowns)
    worst = _rank_worst(groups)
    best = _rank_best(groups)
    survivors = _candidate_survivors(groups)
    answers = _answers(metrics=metrics, breakdowns=breakdowns, worst=worst, best=best, survivors=survivors)
    return {
        "scope": "BULLISH_SWEEP_FAILURE_DEEP_DIVE",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "filter": {"liquidity_context": "sweep:bullish_sweep"},
        "metrics": metrics,
        "classification": classify_group(metrics),
        "breakdowns": breakdowns,
        "worst_groups": worst,
        "best_groups": best,
        "bullish_sweep_survivors": survivors,
        "answers": answers,
        "recommended_action": answers["recommended_action"],
    }


def classify_group(metrics: dict[str, Any]) -> str:
    trades = int(metrics.get("trades", 0) or 0)
    if trades < 2:
        return "NEUTRAL"
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    pf = _pf_float(metrics.get("profit_factor"))
    winrate = float(metrics.get("winrate", 0.0) or 0.0)
    if total_r < 0 and pf < 1.0:
        return "TOXIC"
    if total_r > 0 and pf > 1.10 and winrate >= 40:
        return "PROMISING"
    return "NEUTRAL"


def write_bullish_sweep_failure_deep_dive_report(result: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "bullish_sweep_failure_deep_dive.md"
    path.write_text(format_bullish_sweep_failure_deep_dive_markdown(result), encoding="utf-8")
    return path


def format_bullish_sweep_failure_deep_dive_markdown(result: dict[str, Any]) -> str:
    answers = result.get("answers", {})
    lines = [
        "# BULLISH_SWEEP_FAILURE_DEEP_DIVE",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        "Filter: `liquidity_context=sweep:bullish_sweep`",
        f"Classification: {result.get('classification')}",
        "",
        "## Executive Summary",
        "",
        f"- Bullish sweep: {_metrics_inline(result.get('metrics', {}))}",
        f"- Is bullish_sweep globally broken? {answers.get('globally_broken', '')}",
        f"- Dimension explaining most losses: {answers.get('primary_loss_driver', '')}",
        f"- Symbols responsible for most damage: {answers.get('symbol_damage', '')}",
        f"- Sessions responsible for most damage: {answers.get('session_damage', '')}",
        f"- Does HTF alignment improve results? {answers.get('htf_alignment_effect', '')}",
        f"- Profitable bullish_sweep subsets worth shadow tracking: {answers.get('viable_shadow_subset', '')}",
        f"- Next investigation: {answers.get('next_investigation', '')}",
        f"- Recommended action: {result.get('recommended_action')}",
        "",
        "## Worst Bullish Sweep Groups",
        "",
        *_rank_table(result.get("worst_groups", [])),
        "",
        "## Best Bullish Sweep Groups",
        "",
        *_rank_table(result.get("best_groups", [])),
        "",
        "## Bullish Sweep Survivors",
        "",
        "Criteria: minimum 20 trades, PF > 1.10, positive Total R.",
        "",
        *_rank_table(result.get("bullish_sweep_survivors", [])),
        "",
        "## Breakdowns",
        "",
    ]
    for title, key in (
        ("By Symbol", "symbol"),
        ("By Session", "session"),
        ("By Market Regime", "market_regime"),
        ("By Score Bucket", "score_bucket"),
        ("By Setup Type", "setup_type"),
        ("By Entry Context", "entry_context"),
        ("By Trend Alignment", "trend_alignment"),
        ("By Warning / Rejection / Penalty Reason", "reason"),
        ("By Direction", "direction"),
        ("By HTF Alignment", "htf_alignment"),
    ):
        lines.extend([f"### {title}", "", *_group_table(result.get("breakdowns", {}).get(key, {}), title), ""])
    return "\n".join(lines).rstrip() + "\n"


def _answers(
    *,
    metrics: dict[str, Any],
    breakdowns: dict[str, dict[str, dict[str, Any]]],
    worst: list[dict[str, Any]],
    best: list[dict[str, Any]],
    survivors: list[dict[str, Any]],
) -> dict[str, str]:
    classification = classify_group(metrics)
    globally_broken = "Yes, global bullish_sweep is TOXIC." if classification == "TOXIC" else "No, global bullish_sweep is not classified as TOXIC."
    primary_loss_driver = _describe_group(worst[0]) if worst else "none"
    symbol_damage = _damage_summary(breakdowns.get("symbol", {}))
    session_damage = _damage_summary(breakdowns.get("session", {}))
    htf_alignment_effect = _alignment_effect(breakdowns.get("htf_alignment", {}))
    if survivors:
        viable_shadow_subset = _describe_group(survivors[0])
        recommended_action = "candidate for shadow promotion"
    elif best:
        viable_shadow_subset = f"Potential watchlist only: {_describe_group(best[0])}"
        recommended_action = "continue monitoring"
    else:
        viable_shadow_subset = "none"
        recommended_action = "no action"
    next_investigation = primary_loss_driver if worst else viable_shadow_subset
    if classification == "TOXIC":
        recommended_action = "candidate for future filter"
    return {
        "globally_broken": globally_broken,
        "primary_loss_driver": primary_loss_driver,
        "symbol_damage": symbol_damage,
        "session_damage": session_damage,
        "htf_alignment_effect": htf_alignment_effect,
        "viable_shadow_subset": viable_shadow_subset,
        "next_investigation": next_investigation,
        "recommended_action": recommended_action,
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
                    "classification": payload.get("classification", "NEUTRAL"),
                }
            )
    return rows


def _rank_worst(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    toxic = [row for row in groups if row.get("classification") == "TOXIC" and int(row.get("metrics", {}).get("trades", 0) or 0) > 0]
    return sorted(
        toxic,
        key=lambda row: (
            _pf_float(row["metrics"].get("profit_factor")),
            float(row["metrics"].get("total_r", 0.0)),
        ),
    )[:20]


def _rank_best(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    promising = [row for row in groups if row.get("classification") == "PROMISING" and int(row.get("metrics", {}).get("trades", 0) or 0) > 0]
    return sorted(
        promising,
        key=lambda row: (
            _pf_float(row["metrics"].get("profit_factor")),
            float(row["metrics"].get("total_r", 0.0)),
        ),
        reverse=True,
    )[:20]


def _candidate_survivors(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
            _pf_float(row["metrics"].get("profit_factor")),
            float(row["metrics"].get("total_r", 0.0)),
        ),
        reverse=True,
    )


def _group_summary(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[_field_value(row, field)].append(row)
    return {key: {"metrics": _metrics(items), "classification": classify_group(_metrics(items))} for key, items in sorted(groups.items())}


def _reason_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        reasons = sorted(set(_tokens(row.get("rejection_reasons")) | _tokens(row.get("warnings")) | _tokens(row.get("avoidance_warnings")) | _tokens(row.get("penalties"))))
        if not reasons:
            groups["none"].append(row)
            continue
        for reason in reasons:
            groups[reason].append(row)
    return {key: {"metrics": _metrics(items), "classification": classify_group(_metrics(items))} for key, items in sorted(groups.items())}


def _field_value(row: dict[str, Any], field: str) -> str:
    if field == "score_bucket":
        return _score_bucket(row.get("score"))
    if field == "trend_alignment":
        return _trend_alignment(row)
    if field == "htf_alignment":
        return _htf_alignment(row)
    return str(row.get(field) or "UNKNOWN")


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
        "total_r": round(sum(values), 4),
        "avg_r": round(sum(values) / len(values), 4) if values else 0.0,
    }


def _profit_factor(gross_profit: float, gross_loss: float) -> float | str:
    if gross_loss > 0:
        return round(gross_profit / gross_loss, 4)
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


def _damage_summary(groups: dict[str, dict[str, Any]]) -> str:
    toxic = [
        {"value": key, "metrics": payload.get("metrics", {})}
        for key, payload in groups.items()
        if isinstance(payload, dict)
        and float(payload.get("metrics", {}).get("total_r", 0.0) or 0.0) < 0
    ]
    if not toxic:
        return "none"
    ranked = sorted(toxic, key=lambda row: float(row["metrics"].get("total_r", 0.0)))[:5]
    return ", ".join(f"{row['value']} TotalR={row['metrics'].get('total_r', 0)} PF={row['metrics'].get('profit_factor', 0)}" for row in ranked)


def _alignment_effect(groups: dict[str, dict[str, Any]]) -> str:
    aligned = groups.get("aligned_with_htf", {}).get("metrics", {}) if isinstance(groups.get("aligned_with_htf"), dict) else {}
    against = groups.get("against_htf", {}).get("metrics", {}) if isinstance(groups.get("against_htf"), dict) else {}
    if not aligned and not against:
        return "insufficient HTF data"
    return (
        f"aligned_with_htf PF={aligned.get('profit_factor', 0)} TotalR={aligned.get('total_r', 0)}; "
        f"against_htf PF={against.get('profit_factor', 0)} TotalR={against.get('total_r', 0)}"
    )


def _describe_group(row: dict[str, Any]) -> str:
    metrics = row.get("metrics", {})
    return f"{row.get('dimension')}={row.get('value')} (trades={metrics.get('trades', 0)}, PF={metrics.get('profit_factor', 0)}, TotalR={metrics.get('total_r', 0)})"


def _metrics_inline(metrics: object) -> str:
    if not isinstance(metrics, dict):
        metrics = {}
    return f"trades={metrics.get('trades', 0)}, WR={metrics.get('winrate', 0)}%, PF={metrics.get('profit_factor', 0)}, TotalR={metrics.get('total_r', 0)}, AvgR={metrics.get('avg_r', 0)}"


def _group_table(payload: object, label: str) -> list[str]:
    lines = [f"| {label} | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |", "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    if not isinstance(payload, dict) or not payload:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NEUTRAL |")
        return lines
    for key, value in payload.items():
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
    for row in rows[:20]:
        metrics = row.get("metrics", {}) if isinstance(row, dict) else {}
        lines.append(
            f"| {row.get('dimension', '')} | {row.get('value', '')} | {metrics.get('trades', 0)} | "
            f"{metrics.get('wins', 0)} | {metrics.get('losses', 0)} | {metrics.get('winrate', 0)}% | "
            f"{metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} | {row.get('classification', 'NEUTRAL')} |"
        )
    return lines
