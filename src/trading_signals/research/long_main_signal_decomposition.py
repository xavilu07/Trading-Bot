from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


SURVIVOR_MIN_TRADES = 20


def analyze_long_main_signal_decomposition(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    all_trades = load_canonical_closed_trades(data_path)
    rows = [
        row
        for row in all_trades
        if str(row.get("direction") or "").lower() == "long"
        and str(row.get("setup_type") or "").upper() == "MAIN_SIGNAL"
    ]
    metrics = _metrics(rows)
    breakdowns = {
        "symbol": _group_summary(rows, "symbol"),
        "session": _group_summary(rows, "session"),
        "market_regime": _group_summary(rows, "market_regime"),
        "score_bucket": _group_summary(rows, "score_bucket"),
        "entry_context": _group_summary(rows, "entry_context"),
        "reason": _reason_summary(rows),
        "liquidity_context": _group_summary(rows, "liquidity_context"),
        "trend_alignment": _group_summary(rows, "trend_alignment"),
    }
    groups = _flatten_groups(breakdowns)
    worst = _rank_worst(groups)
    best = _rank_best(groups)
    survivors = _candidate_survivors(groups)
    answers = _answers(metrics=metrics, worst=worst, best=best, survivors=survivors)
    return {
        "scope": "LONG_MAIN_SIGNAL_DECOMPOSITION",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "filter": {"direction": "LONG", "setup_type": "MAIN_SIGNAL"},
        "metrics": metrics,
        "classification": classify_group(metrics),
        "breakdowns": breakdowns,
        "worst_groups": worst,
        "best_groups": best,
        "candidate_long_survivors": survivors,
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


def write_long_main_signal_decomposition_report(result: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "long_main_signal_decomposition.md"
    path.write_text(format_long_main_signal_decomposition_markdown(result), encoding="utf-8")
    return path


def format_long_main_signal_decomposition_markdown(result: dict[str, Any]) -> str:
    answers = result.get("answers", {})
    lines = [
        "# LONG_MAIN_SIGNAL_DECOMPOSITION",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        "Filter: `direction=LONG`, `setup_type=MAIN_SIGNAL`",
        f"Classification: {result.get('classification')}",
        "",
        "## Executive Summary",
        "",
        f"- LONG MAIN_SIGNAL: {_metrics_inline(result.get('metrics', {}))}",
        f"- If kept only best LONG MAIN_SIGNAL subsets, would LONG become profitable? {answers.get('best_subset_profitability', '')}",
        f"- Dimensions explaining most losses: {answers.get('loss_drivers', '')}",
        f"- Viable LONG MAIN_SIGNAL subset worth shadow-tracking: {answers.get('viable_shadow_subset', '')}",
        f"- Next subset to investigate: {answers.get('next_subset_to_investigate', '')}",
        f"- Recommended action: {result.get('recommended_action')}",
        "",
        "## Worst LONG MAIN_SIGNAL Groups",
        "",
        *_rank_table(result.get("worst_groups", [])),
        "",
        "## Best LONG MAIN_SIGNAL Groups",
        "",
        *_rank_table(result.get("best_groups", [])),
        "",
        "## Candidate LONG Survivors",
        "",
        "Criteria: minimum 20 trades, PF > 1.10, positive Total R.",
        "",
        *_rank_table(result.get("candidate_long_survivors", [])),
        "",
        "## Breakdowns",
        "",
    ]
    for title, key in (
        ("By Symbol", "symbol"),
        ("By Session", "session"),
        ("By Market Regime", "market_regime"),
        ("By Score Bucket", "score_bucket"),
        ("By Entry Context", "entry_context"),
        ("By Warning / Rejection / Penalty Reason", "reason"),
        ("By Liquidity Context", "liquidity_context"),
        ("By Trend Alignment", "trend_alignment"),
    ):
        lines.extend([f"### {title}", "", *_group_table(result.get("breakdowns", {}).get(key, {}), title), ""])
    return "\n".join(lines).rstrip() + "\n"


def _answers(
    *,
    metrics: dict[str, Any],
    worst: list[dict[str, Any]],
    best: list[dict[str, Any]],
    survivors: list[dict[str, Any]],
) -> dict[str, str]:
    if survivors:
        best_subset_profitability = f"Yes, {len(survivors)} subgroup(s) satisfy survivor criteria."
        viable_shadow_subset = _describe_group(survivors[0])
        recommended_action = "candidate for shadow promotion"
    elif best:
        best_subset_profitability = "Not proven. Some subgroups are profitable, but none meet the minimum 20-trade survivor threshold."
        viable_shadow_subset = f"Potential watchlist only: {_describe_group(best[0])}"
        recommended_action = "continue monitoring"
    else:
        best_subset_profitability = "No. No profitable LONG MAIN_SIGNAL subgroup was found."
        viable_shadow_subset = "none"
        recommended_action = "no action"
    if worst:
        loss_drivers = ", ".join(_describe_group(row) for row in worst[:5])
        next_subset = _describe_group(worst[0])
        if classify_group(metrics) == "TOXIC":
            recommended_action = "candidate for future filter"
    else:
        loss_drivers = "none"
        next_subset = viable_shadow_subset
    return {
        "best_subset_profitability": best_subset_profitability,
        "loss_drivers": loss_drivers,
        "viable_shadow_subset": viable_shadow_subset,
        "next_subset_to_investigate": next_subset,
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
            float(row["metrics"].get("total_r", 0.0)),
            _pf_float(row["metrics"].get("profit_factor")),
            float(row["metrics"].get("avg_r", 0.0)),
        ),
    )[:20]


def _rank_best(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    promising = [row for row in groups if row.get("classification") == "PROMISING" and int(row.get("metrics", {}).get("trades", 0) or 0) > 0]
    return sorted(
        promising,
        key=lambda row: (
            float(row["metrics"].get("total_r", 0.0)),
            _pf_float(row["metrics"].get("profit_factor")),
            float(row["metrics"].get("avg_r", 0.0)),
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
            float(row["metrics"].get("total_r", 0.0)),
            _pf_float(row["metrics"].get("profit_factor")),
            float(row["metrics"].get("avg_r", 0.0)),
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
    if field == "liquidity_context":
        return _liquidity_context(row)
    if field == "trend_alignment":
        return _trend_alignment(row)
    return str(row.get(field) or "UNKNOWN")


def _liquidity_context(row: dict[str, Any]) -> str:
    sweep = str(row.get("liquidity_sweep") or "").strip()
    if sweep:
        return f"sweep:{sweep}"
    location = str(row.get("trade_location") or "").strip()
    if location and location.upper() != "UNKNOWN":
        return f"location:{location}"
    liquidity_reasons = sorted(reason for reason in _tokens(row.get("rejection_reasons")) | _tokens(row.get("warnings")) | _tokens(row.get("penalties")) if "liquidity" in reason.lower())
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
    if entry == higher == "bullish":
        return "aligned_bullish"
    if entry == higher:
        return f"aligned_{entry}"
    if higher == "bearish" and entry == "bullish":
        return "against_htf_bearish"
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
