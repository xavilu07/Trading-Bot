from __future__ import annotations

import itertools
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


MIN_CLUSTER_TRADES = 10
MULTI_FACTOR_FIELDS = (
    "setup_type",
    "trade_location",
    "market_regime",
    "score_bucket",
    "trend_alignment",
    "htf_alignment",
    "liquidity_sweep",
)


def analyze_winner_dna_2_super_survivor(*, data_path: Path, now: datetime | None = None, min_trades: int = MIN_CLUSTER_TRADES) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    all_trades = load_canonical_closed_trades(data_path)
    eligible = [row for row in all_trades if not _is_existing_production_block_context(row)]
    breakdowns = _build_breakdowns(eligible)
    single_clusters = _flatten_groups(breakdowns)
    super_survivors = _rank_super_survivors(single_clusters, min_trades=min_trades)
    multi_factor_dna = _multi_factor_dna(eligible, min_trades=min_trades)
    what_if = _what_if_analysis(eligible, super_survivors)
    answers = _answers(
        baseline=_metrics(eligible),
        super_survivors=super_survivors,
        multi_factor_dna=multi_factor_dna,
        what_if=what_if,
    )
    return {
        "scope": "WINNER_DNA_2_0_SUPER_SURVIVOR_ANALYSIS",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "method": "Analyze canonical closed trades after excluding existing production blocks: bullish_sweep and against_htf+BREAKOUT.",
        "excluded_production_blocks": ["bullish_sweep", "against_htf+BREAKOUT"],
        "baseline_after_production_blocks": _metrics(eligible),
        "excluded_metrics": _metrics([row for row in all_trades if _is_existing_production_block_context(row)]),
        "classification": classify_survivor_set(_metrics(eligible)),
        "breakdowns": breakdowns,
        "super_survivors": super_survivors,
        "multi_factor_dna_top_20": multi_factor_dna[:20],
        "what_if_analysis": what_if,
        "answers": answers,
        "recommended_action": answers["recommended_action"],
    }


def write_winner_dna_2_super_survivor_reports(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    markdown_path = reports_path / "winner_dna_2_super_survivor_analysis.md"
    json_path = reports_path / "winner_dna_2_super_survivor_analysis.json"
    markdown_path.write_text(format_winner_dna_2_super_survivor_markdown(result), encoding="utf-8")
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return {"markdown": markdown_path, "json": json_path}


def format_winner_dna_2_super_survivor_markdown(result: dict[str, Any]) -> str:
    answers = result.get("answers", {})
    breakdowns = result.get("breakdowns", {})
    what_if = result.get("what_if_analysis", {})
    lines = [
        "# WINNER_DNA_2_0_SUPER_SURVIVOR_ANALYSIS",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        f"Method: {result.get('method')}",
        f"Classification: {result.get('classification')}",
        f"Recommended action: {result.get('recommended_action')}",
        "",
        "## Executive Summary",
        "",
        f"- Baseline after production blocks: {_metrics_inline(result.get('baseline_after_production_blocks', {}))}",
        f"- Excluded production blocks: {_metrics_inline(result.get('excluded_metrics', {}))}",
        f"- Strongest trading DNA: {answers.get('strongest_trading_dna', 'none')}",
        f"- Repeated winner factors: {answers.get('repeated_winner_factors', 'none')}",
        f"- Most profitable factor: {answers.get('most_profitable_factor', 'none')}",
        f"- SECONDARY_SIGNAL superior? {answers.get('secondary_signal_superior', 'UNKNOWN')}",
        f"- near_resistance edge? {answers.get('near_resistance_edge', 'UNKNOWN')}",
        f"- score 90+ confirmed edge? {answers.get('score_90_plus_confirmed_edge', 'UNKNOWN')}",
        "",
        "## Baseline",
        "",
        *_single_metrics_table(result.get("baseline_after_production_blocks", {})),
        "",
        "## Super Survivors",
        "",
        "Criteria: minimum 10 trades. Ranked by PF, TotalR, stability score and sample size.",
        "",
        *_survivor_table(result.get("super_survivors", [])),
        "",
        "## Multi-factor DNA Top 20",
        "",
        *_multi_factor_table(result.get("multi_factor_dna_top_20", [])),
        "",
        "## What If Analysis",
        "",
        *_what_if_table(what_if),
        "",
        "## Survivor Discovery Breakdowns",
        "",
    ]
    for title, key in (
        ("By Symbol", "symbol"),
        ("By Session", "session"),
        ("By Direction", "direction"),
        ("By Setup Type", "setup_type"),
        ("By Market Regime", "market_regime"),
        ("By Trade Location", "trade_location"),
        ("By Liquidity Sweep", "liquidity_sweep"),
        ("By Trend Alignment", "trend_alignment"),
        ("By HTF Alignment", "htf_alignment"),
        ("By Score Bucket", "score_bucket"),
        ("By Entry Context", "entry_context"),
        ("By Warnings", "warning"),
        ("By Penalties", "penalty"),
    ):
        lines.extend([f"### {title}", "", *_group_table(breakdowns.get(key, {}), title), ""])
    lines.extend(["## Answers", ""])
    for question, answer in answers.items():
        if question == "recommended_action":
            continue
        lines.append(f"- {question}: {answer}")
    lines.extend(["", "## Recommended Action", "", str(result.get("recommended_action", "KEEP_CURRENT"))])
    return "\n".join(lines).rstrip() + "\n"


def classify_survivor_set(metrics: dict[str, Any]) -> str:
    pf = _pf_float(metrics.get("profit_factor"))
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    trades = int(metrics.get("trades", 0) or 0)
    if trades < MIN_CLUSTER_TRADES or total_r <= 0 or pf <= 1:
        return "NO_EDGE"
    if pf > 1.8:
        return "ELITE"
    if pf > 1.4:
        return "STRONG"
    if pf > 1.2:
        return "PROMISING"
    return "NO_EDGE"


def _build_breakdowns(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "symbol": _group_summary(rows, "symbol"),
        "session": _group_summary(rows, "session"),
        "direction": _group_summary(rows, "direction"),
        "setup_type": _group_summary(rows, "setup_type"),
        "market_regime": _group_summary(rows, "market_regime"),
        "trade_location": _group_summary(rows, "trade_location"),
        "liquidity_sweep": _group_summary(rows, "liquidity_sweep"),
        "trend_alignment": _group_summary(rows, "trend_alignment"),
        "htf_alignment": _group_summary(rows, "htf_alignment"),
        "score_bucket": _group_summary(rows, "score_bucket"),
        "entry_context": _group_summary(rows, "entry_context"),
        "warning": _token_summary(rows, "warnings", "avoidance_warnings"),
        "penalty": _token_summary(rows, "penalties"),
    }


def _rank_super_survivors(groups: list[dict[str, Any]], *, min_trades: int) -> list[dict[str, Any]]:
    survivors = []
    for row in groups:
        metrics = row.get("metrics", {})
        if (
            int(metrics.get("trades", 0) or 0) >= min_trades
            and _pf_float(metrics.get("profit_factor")) > 1.20
            and float(metrics.get("total_r", 0.0) or 0.0) > 0
        ):
            row = {**row}
            row["survivor_classification"] = classify_survivor_set(metrics)
            row["stability_score"] = _stability_score(metrics)
            survivors.append(row)
    return sorted(
        survivors,
        key=lambda row: (
            _pf_float(row["metrics"].get("profit_factor")),
            float(row["metrics"].get("total_r", 0.0)),
            float(row.get("stability_score", 0.0)),
            int(row["metrics"].get("trades", 0) or 0),
        ),
        reverse=True,
    )


def _multi_factor_dna(rows: list[dict[str, Any]], *, min_trades: int) -> list[dict[str, Any]]:
    groups: dict[tuple[tuple[str, str], ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        values = {field: _field_value(row, field) for field in MULTI_FACTOR_FIELDS}
        for size in (2, 3):
            for combo in itertools.combinations(MULTI_FACTOR_FIELDS, size):
                key = tuple((field, values[field]) for field in combo)
                if any(value == "UNKNOWN" for _field, value in key):
                    continue
                groups[key].append(row)
    output = []
    for key, group_rows in groups.items():
        metrics = _metrics(group_rows)
        if metrics["trades"] < min_trades or _pf_float(metrics["profit_factor"]) <= 1.20 or float(metrics["total_r"]) <= 0:
            continue
        output.append(
            {
                "combination": " + ".join(f"{field}={value}" for field, value in key),
                "factors": [{"dimension": field, "value": value} for field, value in key],
                "metrics": metrics,
                "classification": classify_survivor_set(metrics),
                "stability_score": _stability_score(metrics),
            }
        )
    return sorted(
        output,
        key=lambda row: (
            _pf_float(row["metrics"].get("profit_factor")),
            float(row["metrics"].get("total_r", 0.0)),
            float(row.get("stability_score", 0.0)),
            int(row["metrics"].get("trades", 0) or 0),
        ),
        reverse=True,
    )


def _what_if_analysis(rows: list[dict[str, Any]], super_survivors: list[dict[str, Any]]) -> dict[str, Any]:
    elite_groups = [row for row in super_survivors if row.get("survivor_classification") == "ELITE"]
    elite_strong_groups = [row for row in super_survivors if row.get("survivor_classification") in {"ELITE", "STRONG"}]
    top_contexts_count = max(1, int(len(super_survivors) * 0.2)) if super_survivors else 0
    top_20_groups = super_survivors[:top_contexts_count]
    return {
        "only_elite": _metrics(_rows_matching_any_group(rows, elite_groups)),
        "only_elite_and_strong": _metrics(_rows_matching_any_group(rows, elite_strong_groups)),
        "only_top_20_percent_contexts": _metrics(_rows_matching_any_group(rows, top_20_groups)),
    }


def _answers(
    *,
    baseline: dict[str, Any],
    super_survivors: list[dict[str, Any]],
    multi_factor_dna: list[dict[str, Any]],
    what_if: dict[str, Any],
) -> dict[str, str]:
    strongest = multi_factor_dna[0] if multi_factor_dna else (super_survivors[0] if super_survivors else None)
    repeated = _repeated_factors(super_survivors[:20], multi_factor_dna[:20])
    secondary = _find_group(super_survivors, "setup_type", "SECONDARY_SIGNAL")
    near_resistance = _find_group(super_survivors, "trade_location", "near_resistance")
    score_90 = _find_group(super_survivors, "score_bucket", "90+")
    elite_metrics = what_if.get("only_elite", {})
    elite_strong_metrics = what_if.get("only_elite_and_strong", {})
    if _pf_float(elite_metrics.get("profit_factor")) > 1.8 and int(elite_metrics.get("trades", 0) or 0) >= MIN_CLUSTER_TRADES:
        action = "BUILD_ELITE_PROFILE"
    elif _pf_float(elite_strong_metrics.get("profit_factor")) > 1.4 and int(elite_strong_metrics.get("trades", 0) or 0) >= MIN_CLUSTER_TRADES:
        action = "PRIORITIZE_ELITE_CONTEXTS"
    elif super_survivors:
        action = "CREATE_ELITE_SHADOW_MODE"
    else:
        action = "KEEP_CURRENT"
    return {
        "strongest_trading_dna": _describe_survivor(strongest),
        "repeated_winner_factors": ", ".join(repeated[:8]) if repeated else "none",
        "most_profitable_factor": _describe_survivor(super_survivors[0] if super_survivors else None),
        "secondary_signal_superior": _edge_answer(secondary),
        "near_resistance_edge": _edge_answer(near_resistance),
        "score_90_plus_confirmed_edge": _edge_answer(score_90),
        "elite_version_of_bot": _elite_profile_text(super_survivors, multi_factor_dna),
        "baseline_after_blocks": _metrics_inline(baseline),
        "recommended_action": action,
    }


def _rows_matching_any_group(rows: list[dict[str, Any]], groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not groups:
        return []
    output = []
    seen: set[int] = set()
    for row in rows:
        for group in groups:
            if _row_matches_group(row, group):
                row_id = id(row)
                if row_id not in seen:
                    output.append(row)
                    seen.add(row_id)
                break
    return output


def _row_matches_group(row: dict[str, Any], group: dict[str, Any]) -> bool:
    if "dimension" in group:
        return _field_value(row, str(group.get("dimension"))) == str(group.get("value"))
    factors = group.get("factors", [])
    if not isinstance(factors, list):
        return False
    return all(_field_value(row, str(item.get("dimension"))) == str(item.get("value")) for item in factors if isinstance(item, dict))


def _flatten_groups(breakdowns: dict[str, dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dimension, groups in breakdowns.items():
        for value, payload in groups.items():
            rows.append(
                {
                    "dimension": dimension,
                    "value": value,
                    "metrics": payload.get("metrics", {}),
                    "classification": payload.get("classification", "NO_EDGE"),
                }
            )
    return rows


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
        result[key] = {
            "metrics": metrics,
            "classification": classify_survivor_set(metrics),
            "stability_score": _stability_score(metrics),
        }
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
        return _direction(row).upper()
    if field == "setup_type":
        return _setup_type(row)
    if field == "market_regime":
        return _market_regime(row)
    if field == "session":
        return _session(row)
    if field == "entry_context":
        return _entry_context(row)
    return str(row.get(field) or "UNKNOWN").strip() or "UNKNOWN"


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


def _stability_score(metrics: dict[str, Any]) -> float:
    trades = int(metrics.get("trades", 0) or 0)
    pf = min(_pf_float(metrics.get("profit_factor")), 5.0)
    winrate = float(metrics.get("winrate", 0.0) or 0.0)
    avg_r = float(metrics.get("avg_r", 0.0) or 0.0)
    sample_factor = min(trades / 50, 1.0)
    score = (pf / 5 * 40) + (winrate / 100 * 35) + (max(avg_r, 0) * 15) + (sample_factor * 10)
    return _round(min(score, 100.0))


def _find_group(groups: list[dict[str, Any]], dimension: str, value: str) -> dict[str, Any] | None:
    return next((row for row in groups if row.get("dimension") == dimension and row.get("value") == value), None)


def _repeated_factors(super_survivors: list[dict[str, Any]], multi_factor_dna: list[dict[str, Any]]) -> list[str]:
    counts: dict[str, int] = defaultdict(int)
    for row in super_survivors:
        counts[f"{row.get('dimension')}={row.get('value')}"] += 1
    for row in multi_factor_dna:
        for factor in row.get("factors", []):
            if isinstance(factor, dict):
                counts[f"{factor.get('dimension')}={factor.get('value')}"] += 1
    return [key for key, _count in sorted(counts.items(), key=lambda item: item[1], reverse=True)]


def _edge_answer(row: dict[str, Any] | None) -> str:
    if not row:
        return "NO"
    metrics = row.get("metrics", {})
    return f"YES ({_metrics_inline(metrics)}, class={row.get('survivor_classification') or row.get('classification')})"


def _elite_profile_text(super_survivors: list[dict[str, Any]], multi_factor_dna: list[dict[str, Any]]) -> str:
    if multi_factor_dna:
        return f"Prioritize {multi_factor_dna[0].get('combination')} with {_metrics_inline(multi_factor_dna[0].get('metrics', {}))}."
    if super_survivors:
        return f"Prioritize {super_survivors[0].get('dimension')}={super_survivors[0].get('value')} with {_metrics_inline(super_survivors[0].get('metrics', {}))}."
    return "No elite profile is statistically visible yet."


def _describe_survivor(row: dict[str, Any] | None) -> str:
    if not row:
        return "none"
    if "combination" in row:
        return f"{row.get('combination')} ({_metrics_inline(row.get('metrics', {}))}, class={row.get('classification')})"
    return f"{row.get('dimension')}={row.get('value')} ({_metrics_inline(row.get('metrics', {}))}, class={row.get('survivor_classification')})"


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
    lines = [f"| {label} | Trades | Wins | Losses | WR | PF | Total R | Avg R | Class | Stability |", "|---|---:|---:|---:|---:|---:|---:|---:|---|---:|"]
    if not isinstance(payload, dict) or not payload:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_EDGE | 0 |")
        return lines
    ranked = sorted(
        payload.items(),
        key=lambda item: (
            _pf_float(item[1].get("metrics", {}).get("profit_factor")),
            float(item[1].get("metrics", {}).get("total_r", 0.0)),
            float(item[1].get("stability_score", 0.0)),
        ),
        reverse=True,
    )
    for key, value in ranked[:30]:
        metrics = value.get("metrics", {}) if isinstance(value, dict) else {}
        lines.append(
            f"| {key} | {metrics.get('trades', 0)} | {metrics.get('wins', 0)} | {metrics.get('losses', 0)} | "
            f"{metrics.get('winrate', 0)}% | {metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | "
            f"{metrics.get('avg_r', 0)} | {value.get('classification', 'NO_EDGE') if isinstance(value, dict) else 'NO_EDGE'} | "
            f"{value.get('stability_score', 0) if isinstance(value, dict) else 0} |"
        )
    return lines


def _survivor_table(rows: object) -> list[str]:
    lines = [
        "| Dimension | Value | Trades | WR | PF | Total R | Avg R | Class | Stability |",
        "|---|---|---:|---:|---:|---:|---:|---|---:|",
    ]
    if not isinstance(rows, list) or not rows:
        lines.append("| none | none | 0 | 0 | 0 | 0 | 0 | NO_EDGE | 0 |")
        return lines
    for row in rows[:40]:
        metrics = row.get("metrics", {}) if isinstance(row, dict) else {}
        lines.append(
            f"| {row.get('dimension', '')} | {row.get('value', '')} | {metrics.get('trades', 0)} | "
            f"{metrics.get('winrate', 0)}% | {metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | "
            f"{metrics.get('avg_r', 0)} | {row.get('survivor_classification', 'NO_EDGE')} | {row.get('stability_score', 0)} |"
        )
    return lines


def _multi_factor_table(rows: object) -> list[str]:
    lines = [
        "| Combination | Trades | WR | PF | Total R | Avg R | Class | Stability |",
        "|---|---:|---:|---:|---:|---:|---|---:|",
    ]
    if not isinstance(rows, list) or not rows:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | NO_EDGE | 0 |")
        return lines
    for row in rows[:20]:
        metrics = row.get("metrics", {}) if isinstance(row, dict) else {}
        lines.append(
            f"| {row.get('combination', '')} | {metrics.get('trades', 0)} | {metrics.get('winrate', 0)}% | "
            f"{metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} | "
            f"{row.get('classification', 'NO_EDGE')} | {row.get('stability_score', 0)} |"
        )
    return lines


def _what_if_table(payload: object) -> list[str]:
    lines = ["| Scenario | Trades | WR | PF | Total R | Avg R |", "|---|---:|---:|---:|---:|---:|"]
    if not isinstance(payload, dict) or not payload:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 |")
        return lines
    for scenario, metrics in payload.items():
        if not isinstance(metrics, dict):
            continue
        lines.append(
            f"| {scenario} | {metrics.get('trades', 0)} | {metrics.get('winrate', 0)}% | "
            f"{metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} |"
        )
    return lines
