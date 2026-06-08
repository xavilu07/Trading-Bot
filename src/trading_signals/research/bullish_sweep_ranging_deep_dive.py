from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


TARGET_REGIME = "RANGING"
MIN_SUBGROUP_TRADES = 3
MIN_CRITICAL_TRADES = 10


def analyze_bullish_sweep_ranging_deep_dive(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    all_trades = load_canonical_closed_trades(data_path)
    rows = [row for row in all_trades if _is_bullish_sweep(row) and _market_regime(row) == TARGET_REGIME]
    metrics = _metrics(rows)
    breakdowns = {
        "symbol": _group_summary(rows, "symbol"),
        "session": _group_summary(rows, "session"),
        "direction": _group_summary(rows, "direction"),
        "setup_type": _group_summary(rows, "setup_type"),
        "entry_context": _group_summary(rows, "entry_context"),
        "liquidity_context": _group_summary(rows, "liquidity_context"),
        "trend_alignment": _group_summary(rows, "trend_alignment"),
        "htf_alignment": _group_summary(rows, "htf_alignment"),
        "score_bucket": _group_summary(rows, "score_bucket"),
        "warning": _token_summary(rows, "warnings", "avoidance_warnings"),
        "penalty": _token_summary(rows, "penalties"),
        "rejection_reason": _token_summary(rows, "rejection_reasons"),
    }
    toxic = _rank_toxic(_flatten_groups(breakdowns))
    survivors = _rank_survivors(_flatten_groups(breakdowns))
    counterfactual = _counterfactual_remove_bullish_sweep_ranging(all_trades)
    answers = _answers(metrics=metrics, toxic=toxic, survivors=survivors, counterfactual=counterfactual)
    return {
        "scope": "BULLISH_SWEEP_RANGING_DEEP_DIVE",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "method": "Analyze canonical closed trades where bullish_sweep is present and market_regime=RANGING.",
        "baseline_metrics": _metrics(all_trades),
        "metrics": metrics,
        "classification": classify_loss_component(metrics),
        "breakdowns": breakdowns,
        "toxic_subgroups": toxic,
        "survivors": survivors,
        "counterfactual_removal": counterfactual,
        "answers": answers,
        "recommended_action": answers["recommended_action"],
    }


def write_bullish_sweep_ranging_deep_dive_report(result: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "bullish_sweep_ranging_deep_dive.md"
    path.write_text(format_bullish_sweep_ranging_deep_dive_markdown(result), encoding="utf-8")
    return path


def format_bullish_sweep_ranging_deep_dive_markdown(result: dict[str, Any]) -> str:
    answers = result.get("answers", {})
    breakdowns = result.get("breakdowns", {})
    counterfactual = result.get("counterfactual_removal", {})
    lines = [
        "# BULLISH_SWEEP_RANGING_DEEP_DIVE",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        f"Method: {result.get('method')}",
        f"Classification: {result.get('classification')}",
        "",
        "## Executive Summary",
        "",
        f"- Current baseline: {_metrics_inline(result.get('baseline_metrics', {}))}",
        f"- Bullish sweep + RANGING: {_metrics_inline(result.get('metrics', {}))}",
        f"- Is bullish_sweep + ranging globally toxic? {answers.get('globally_toxic', '')}",
        f"- Main loss subgroup: {answers.get('main_loss_subgroup', '')}",
        f"- Survivor subgroup: {answers.get('survivor_subgroup', '')}",
        f"- Material PF improvement if removed? {answers.get('material_pf_improvement', '')}",
        f"- Future shadow filter evidence: {answers.get('future_shadow_filter_evidence', '')}",
        "",
        "## Toxic Bullish Sweep Ranging Subgroups",
        "",
        "Criteria: minimum 3 trades, negative Total R, PF < 1.",
        "",
        *_rank_table(result.get("toxic_subgroups", [])),
        "",
        "## Survivors",
        "",
        "Criteria: minimum 3 trades, PF > 1.1, positive Total R.",
        "",
        *_rank_table(result.get("survivors", [])),
        "",
        "## Counterfactual Removal",
        "",
        f"- PF current: {counterfactual.get('current_metrics', {}).get('profit_factor', 0)}",
        f"- PF without bullish_sweep_ranging: {counterfactual.get('without_bullish_sweep_ranging_metrics', {}).get('profit_factor', 0)}",
        f"- TotalR current: {counterfactual.get('current_metrics', {}).get('total_r', 0)}",
        f"- TotalR without bullish_sweep_ranging: {counterfactual.get('without_bullish_sweep_ranging_metrics', {}).get('total_r', 0)}",
        f"- Winrate delta: {counterfactual.get('winrate_delta', 0)}",
        f"- Trades removed: {counterfactual.get('trades_removed', 0)}",
        "",
        "## Breakdowns",
        "",
    ]
    for title, key in (
        ("By Symbol", "symbol"),
        ("By Session", "session"),
        ("By Direction", "direction"),
        ("By Setup Type", "setup_type"),
        ("By Entry Context", "entry_context"),
        ("By Liquidity Context", "liquidity_context"),
        ("By Trend Alignment", "trend_alignment"),
        ("By HTF Alignment", "htf_alignment"),
        ("By Score Bucket", "score_bucket"),
        ("By Warning", "warning"),
        ("By Penalty", "penalty"),
        ("By Rejection Reason", "rejection_reason"),
    ):
        lines.extend([f"### {title}", "", *_group_table(breakdowns.get(key, {}), title), ""])
    lines.extend(
        [
            "## Recommended Action",
            "",
            result.get("recommended_action", "KEEP"),
        ]
    )
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
    if trades >= 2:
        return "WATCH"
    return "NOISE"


def _answers(
    *,
    metrics: dict[str, Any],
    toxic: list[dict[str, Any]],
    survivors: list[dict[str, Any]],
    counterfactual: dict[str, Any],
) -> dict[str, str]:
    classification = classify_loss_component(metrics)
    globally_toxic = classification in {"CRITICAL", "IMPORTANT"}
    main_loss = _describe_group(toxic[0]) if toxic else "none"
    survivor = _describe_group(survivors[0]) if survivors else "none"
    current_pf = _pf_float(counterfactual.get("current_metrics", {}).get("profit_factor"))
    without_pf = _pf_float(counterfactual.get("without_bullish_sweep_ranging_metrics", {}).get("profit_factor"))
    material_pf = without_pf - current_pf >= 0.10
    if not globally_toxic:
        action = "KEEP"
    elif survivors:
        action = "PARTIAL_BLOCK"
    elif classification == "CRITICAL" and material_pf:
        action = "FULL_BLOCK"
    elif material_pf:
        action = "SHADOW_BLOCK"
    else:
        action = "PARTIAL_BLOCK"
    return {
        "globally_toxic": "YES" if globally_toxic else "NO",
        "main_loss_subgroup": main_loss,
        "survivor_subgroup": survivor,
        "material_pf_improvement": "YES" if material_pf else "NO",
        "future_shadow_filter_evidence": "YES" if globally_toxic else "NO",
        "recommended_action": action,
    }


def _counterfactual_remove_bullish_sweep_ranging(all_trades: list[dict[str, Any]]) -> dict[str, Any]:
    removed = [row for row in all_trades if _is_bullish_sweep(row) and _market_regime(row) == TARGET_REGIME]
    without = [row for row in all_trades if not (_is_bullish_sweep(row) and _market_regime(row) == TARGET_REGIME)]
    current = _metrics(all_trades)
    without_metrics = _metrics(without)
    return {
        "current_metrics": current,
        "without_bullish_sweep_ranging_metrics": without_metrics,
        "removed_metrics": _metrics(removed),
        "trades_removed": len(removed),
        "winrate_delta": _round(float(without_metrics.get("winrate", 0.0) or 0.0) - float(current.get("winrate", 0.0) or 0.0)),
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


def _rank_toxic(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    toxic = []
    for row in groups:
        metrics = row.get("metrics", {})
        if (
            int(metrics.get("trades", 0) or 0) >= MIN_SUBGROUP_TRADES
            and float(metrics.get("total_r", 0.0) or 0.0) < 0
            and _pf_float(metrics.get("profit_factor")) < 1.0
        ):
            toxic.append(row)
    return sorted(toxic, key=lambda row: (_pf_float(row["metrics"].get("profit_factor")), float(row["metrics"].get("total_r", 0.0))))[:30]


def _rank_survivors(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    survivors = []
    for row in groups:
        metrics = row.get("metrics", {})
        if (
            int(metrics.get("trades", 0) or 0) >= MIN_SUBGROUP_TRADES
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
    if field == "score_bucket":
        return _score_bucket(row.get("score"))
    if field == "liquidity_context":
        return _liquidity_context(row)
    if field == "trend_alignment":
        return _trend_alignment(row)
    if field == "htf_alignment":
        return _htf_alignment(row)
    return str(row.get(field) or "UNKNOWN")


def _market_regime(row: dict[str, Any]) -> str:
    return str(row.get("market_regime") or "UNKNOWN").upper()


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
