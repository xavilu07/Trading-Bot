from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


FEATURE_FIELDS = (
    "symbol",
    "direction",
    "setup_type",
    "market_regime",
    "session",
    "entry_context",
    "trade_location",
    "liquidity_context",
    "trend_alignment",
    "htf_alignment",
    "score_bucket",
    "warning",
    "penalty",
    "rejection_reason",
)
MIN_IMPACT_TRADES = 5


def analyze_winner_dna(*, data_path: Path, now: datetime | None = None, min_trades: int = MIN_IMPACT_TRADES) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    trades = load_canonical_closed_trades(data_path)
    baseline = _metrics(trades)
    winners = [row for row in trades if _is_win(row)]
    losers = [row for row in trades if _is_loss(row)]
    feature_groups = _feature_groups(trades)
    positive = _rank_predictors(feature_groups, baseline_winrate=float(baseline["winrate"]), positive=True, min_trades=min_trades)
    negative = _rank_predictors(feature_groups, baseline_winrate=float(baseline["winrate"]), positive=False, min_trades=min_trades)
    counterfactual = _counterfactuals(trades, feature_groups, min_trades=min_trades)
    variable_impact = _variable_impact(feature_groups, baseline_winrate=float(baseline["winrate"]), min_trades=min_trades)
    return {
        "scope": "WINNER_DNA_ANALYSIS",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "baseline_metrics": baseline,
        "winner_profile": _profile(winners, trades),
        "loser_profile": _profile(losers, trades),
        "top_positive_predictors": positive,
        "top_negative_predictors": negative,
        "counterfactual_uplift": counterfactual,
        "variable_impact_ranking": variable_impact,
        "final_recommendation": _recommendation(positive, negative, variable_impact),
    }


def write_winner_dna_report(result: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "winner_dna_analysis.md"
    path.write_text(format_winner_dna_markdown(result), encoding="utf-8")
    return path


def format_winner_dna_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# WINNER_DNA_ANALYSIS",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        "",
        "## Executive Summary",
        "",
        f"- Baseline: {_metrics_inline(result.get('baseline_metrics', {}))}",
        f"- Recommendation: {result.get('final_recommendation', '')}",
        "",
        "## Winner Profile",
        "",
        *_profile_table(result.get("winner_profile", {})),
        "",
        "## Loser Profile",
        "",
        *_profile_table(result.get("loser_profile", {})),
        "",
        "## Top Positive Predictors",
        "",
        *_predictor_table(result.get("top_positive_predictors", [])),
        "",
        "## Top Negative Predictors",
        "",
        *_predictor_table(result.get("top_negative_predictors", [])),
        "",
        "## Counterfactual Uplift",
        "",
        *_counterfactual_table(result.get("counterfactual_uplift", [])),
        "",
        "## Variable Impact Ranking",
        "",
        *_variable_table(result.get("variable_impact_ranking", [])),
        "",
        "## Final Recommendation",
        "",
        "Variables con mayor probabilidad incremental de éxito:",
    ]
    positives = result.get("top_positive_predictors", [])
    if isinstance(positives, list) and positives:
        for row in positives[:5]:
            lines.append(
                f"- {row.get('dimension')}={row.get('value')} "
                f"(WR {row.get('winrate')}%, uplift {row.get('winrate_uplift')} pp, "
                f"PF {row.get('profit_factor')}, TotalR {row.get('total_r')})"
            )
    else:
        lines.append("- Datos insuficientes para aislar predictores positivos robustos.")
    lines.extend(
        [
            "",
            "Variables que más reducen probabilidad de éxito:",
        ]
    )
    negatives = result.get("top_negative_predictors", [])
    if isinstance(negatives, list) and negatives:
        for row in negatives[:5]:
            lines.append(
                f"- {row.get('dimension')}={row.get('value')} "
                f"(WR {row.get('winrate')}%, uplift {row.get('winrate_uplift')} pp, "
                f"PF {row.get('profit_factor')}, TotalR {row.get('total_r')})"
            )
    else:
        lines.append("- Datos insuficientes para aislar predictores negativos robustos.")
    return "\n".join(lines).rstrip() + "\n"


def _profile(rows: list[dict[str, Any]], all_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    profile: dict[str, list[dict[str, Any]]] = {}
    total = len(rows)
    all_counts = _profile_counts(all_rows)
    counts = _profile_counts(rows)
    for dimension, values in counts.items():
        items = []
        for value, count in values.items():
            all_count = all_counts.get(dimension, {}).get(value, 0)
            items.append(
                {
                    "dimension": dimension,
                    "value": value,
                    "count": count,
                    "share": _round(count / total * 100) if total else 0.0,
                    "dataset_share": _round(all_count / len(all_rows) * 100) if all_rows else 0.0,
                    "overrepresentation": _round((count / total * 100 if total else 0.0) - (all_count / len(all_rows) * 100 if all_rows else 0.0)),
                }
            )
        profile[dimension] = sorted(items, key=lambda row: (float(row["overrepresentation"]), int(row["count"])), reverse=True)[:5]
    return profile


def _profile_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        for dimension, value in _features(row):
            counts[dimension][value] += 1
    return {dimension: dict(values) for dimension, values in counts.items()}


def _feature_groups(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for feature in _features(row):
            groups[feature].append(row)
    return groups


def _rank_predictors(
    groups: dict[tuple[str, str], list[dict[str, Any]]],
    *,
    baseline_winrate: float,
    positive: bool,
    min_trades: int,
) -> list[dict[str, Any]]:
    ranked = []
    for (dimension, value), rows in groups.items():
        metrics = _metrics(rows)
        if metrics["trades"] < min_trades:
            continue
        uplift = _round(float(metrics["winrate"]) - baseline_winrate)
        pf = _pf_float(metrics["profit_factor"])
        total_r = float(metrics["total_r"])
        if positive and uplift > 0 and pf > 1 and total_r > 0:
            ranked.append(_predictor_payload(dimension, value, metrics, uplift))
        if not positive and uplift < 0 and (pf < 1 or total_r < 0):
            ranked.append(_predictor_payload(dimension, value, metrics, uplift))
    if positive:
        return sorted(ranked, key=lambda row: (float(row["winrate_uplift"]), float(row["total_r"]), _pf_float(row["profit_factor"])), reverse=True)[:30]
    return sorted(ranked, key=lambda row: (float(row["winrate_uplift"]), float(row["total_r"]), _pf_float(row["profit_factor"])))[:30]


def _predictor_payload(dimension: str, value: str, metrics: dict[str, Any], uplift: float) -> dict[str, Any]:
    return {
        "dimension": dimension,
        "value": value,
        "trades": metrics["trades"],
        "wins": metrics["wins"],
        "losses": metrics["losses"],
        "winrate": metrics["winrate"],
        "winrate_uplift": uplift,
        "profit_factor": metrics["profit_factor"],
        "total_r": metrics["total_r"],
        "avg_r": metrics["avg_r"],
    }


def _counterfactuals(
    rows: list[dict[str, Any]],
    groups: dict[tuple[str, str], list[dict[str, Any]]],
    *,
    min_trades: int,
) -> list[dict[str, Any]]:
    current = _metrics(rows)
    output = []
    for (dimension, value), group_rows in groups.items():
        if len(group_rows) < min_trades:
            continue
        without = [row for row in rows if (dimension, value) not in set(_features(row))]
        without_metrics = _metrics(without)
        output.append(
            {
                "dimension": dimension,
                "value": value,
                "removed_trades": len(group_rows),
                "pf_before": current["profit_factor"],
                "pf_after": without_metrics["profit_factor"],
                "total_r_before": current["total_r"],
                "total_r_after": without_metrics["total_r"],
                "winrate_before": current["winrate"],
                "winrate_after": without_metrics["winrate"],
                "pf_uplift": _round(_pf_float(without_metrics["profit_factor"]) - _pf_float(current["profit_factor"])),
                "total_r_uplift": _round(float(without_metrics["total_r"]) - float(current["total_r"])),
                "winrate_uplift": _round(float(without_metrics["winrate"]) - float(current["winrate"])),
            }
        )
    return sorted(output, key=lambda row: (float(row["total_r_uplift"]), float(row["pf_uplift"]), float(row["winrate_uplift"])), reverse=True)[:30]


def _variable_impact(
    groups: dict[tuple[str, str], list[dict[str, Any]]],
    *,
    baseline_winrate: float,
    min_trades: int,
) -> list[dict[str, Any]]:
    by_dimension: dict[str, list[float]] = defaultdict(list)
    by_dimension_trades: dict[str, int] = defaultdict(int)
    for (dimension, _value), rows in groups.items():
        metrics = _metrics(rows)
        if metrics["trades"] < min_trades:
            continue
        by_dimension[dimension].append(abs(float(metrics["winrate"]) - baseline_winrate))
        by_dimension_trades[dimension] += int(metrics["trades"])
    output = []
    for dimension, impacts in by_dimension.items():
        output.append(
            {
                "dimension": dimension,
                "groups": len(impacts),
                "covered_trades": by_dimension_trades[dimension],
                "avg_abs_winrate_impact": _round(sum(impacts) / len(impacts)) if impacts else 0.0,
                "max_abs_winrate_impact": _round(max(impacts)) if impacts else 0.0,
            }
        )
    return sorted(output, key=lambda row: (float(row["avg_abs_winrate_impact"]), float(row["max_abs_winrate_impact"])), reverse=True)


def _recommendation(positive: list[dict[str, Any]], negative: list[dict[str, Any]], variable_impact: list[dict[str, Any]]) -> str:
    if not positive and not negative:
        return "Datos insuficientes para aislar DNA ganador/perdedor. Seguir acumulando muestra canónica."
    text = []
    if positive:
        text.append(f"Priorizar observación de {positive[0]['dimension']}={positive[0]['value']}.")
    if negative:
        text.append(f"Tratar {negative[0]['dimension']}={negative[0]['value']} como principal fuente de deterioro a investigar.")
    if variable_impact:
        text.append(f"La dimensión con mayor impacto medio es {variable_impact[0]['dimension']}.")
    return " ".join(text)


def _features(row: dict[str, Any]) -> list[tuple[str, str]]:
    features: list[tuple[str, str]] = []
    for field in ("symbol", "direction", "setup_type", "market_regime", "session", "entry_context", "trade_location"):
        features.append((field, str(row.get(field) or "UNKNOWN")))
    features.extend(
        [
            ("liquidity_context", _liquidity_context(row)),
            ("trend_alignment", _trend_alignment(row)),
            ("htf_alignment", _htf_alignment(row)),
            ("score_bucket", _score_bucket(row.get("score"))),
        ]
    )
    for token in sorted(_tokens(row.get("warnings")) | _tokens(row.get("avoidance_warnings"))):
        features.append(("warning", token))
    for token in sorted(_tokens(row.get("penalties"))):
        features.append(("penalty", token))
    for token in sorted(_tokens(row.get("rejection_reasons"))):
        features.append(("rejection_reason", token))
    return features


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


def _is_win(row: dict[str, Any]) -> bool:
    value = _float(row.get("result_r"))
    return value is not None and value > 0


def _is_loss(row: dict[str, Any]) -> bool:
    value = _float(row.get("result_r"))
    return value is not None and value < 0


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


def _tokens(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, set, tuple)):
        return {str(item).strip() for item in value if str(item).strip()}
    text = str(value).strip()
    if not text:
        return set()
    return {item.strip() for item in text.replace("|", ",").replace(";", ",").split(",") if item.strip()}


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


def _profile_table(profile: object) -> list[str]:
    lines = ["| Dimension | Value | Count | Share | Dataset Share | Overrepresentation |", "|---|---|---:|---:|---:|---:|"]
    if not isinstance(profile, dict) or not profile:
        lines.append("| none | none | 0 | 0 | 0 | 0 |")
        return lines
    rows = [item for values in profile.values() for item in values]
    for row in sorted(rows, key=lambda item: (float(item.get("overrepresentation", 0)), int(item.get("count", 0))), reverse=True)[:30]:
        lines.append(
            f"| {row.get('dimension')} | {row.get('value')} | {row.get('count', 0)} | {row.get('share', 0)}% | "
            f"{row.get('dataset_share', 0)}% | {row.get('overrepresentation', 0)} |"
        )
    return lines


def _predictor_table(rows: object) -> list[str]:
    lines = ["| Dimension | Value | Trades | WR | Uplift pp | PF | Total R | Avg R |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    if not isinstance(rows, list) or not rows:
        lines.append("| none | none | 0 | 0 | 0 | 0 | 0 | 0 |")
        return lines
    for row in rows[:30]:
        lines.append(
            f"| {row.get('dimension')} | {row.get('value')} | {row.get('trades', 0)} | {row.get('winrate', 0)}% | "
            f"{row.get('winrate_uplift', 0)} | {row.get('profit_factor', 0)} | {row.get('total_r', 0)} | {row.get('avg_r', 0)} |"
        )
    return lines


def _counterfactual_table(rows: object) -> list[str]:
    lines = [
        "| Dimension | Value | Removed | PF Before | PF After | TotalR Before | TotalR After | TotalR Uplift | WR Uplift |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    if not isinstance(rows, list) or not rows:
        lines.append("| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 |")
        return lines
    for row in rows[:30]:
        lines.append(
            f"| {row.get('dimension')} | {row.get('value')} | {row.get('removed_trades', 0)} | "
            f"{row.get('pf_before', 0)} | {row.get('pf_after', 0)} | {row.get('total_r_before', 0)} | "
            f"{row.get('total_r_after', 0)} | {row.get('total_r_uplift', 0)} | {row.get('winrate_uplift', 0)} |"
        )
    return lines


def _variable_table(rows: object) -> list[str]:
    lines = ["| Dimension | Groups | Covered Trades | Avg Abs WR Impact | Max Abs WR Impact |", "|---|---:|---:|---:|---:|"]
    if not isinstance(rows, list) or not rows:
        lines.append("| none | 0 | 0 | 0 | 0 |")
        return lines
    for row in rows:
        lines.append(
            f"| {row.get('dimension')} | {row.get('groups', 0)} | {row.get('covered_trades', 0)} | "
            f"{row.get('avg_abs_winrate_impact', 0)} | {row.get('max_abs_winrate_impact', 0)} |"
        )
    return lines
