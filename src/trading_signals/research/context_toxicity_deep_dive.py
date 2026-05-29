from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


TARGET_CONTEXTS = {
    "entry_context=CHOPPY_RANGE": lambda row: row["entry_context"] == "CHOPPY_RANGE",
    "market_regime=HIGH_VOLATILITY": lambda row: row["market_regime"] == "HIGH_VOLATILITY",
    "setup_type=UNKNOWN": lambda row: row["setup_type"] == "UNKNOWN",
    "session=UNKNOWN": lambda row: row["session"] == "UNKNOWN",
    "trade_location=UNKNOWN": lambda row: row["trade_location"] == "UNKNOWN",
}

SEGMENTS = {
    "GLOBAL": lambda row: True,
    "LONDON_ONLY": lambda row: row["session"] == "LONDON",
    "SHORT_ONLY": lambda row: row["direction"] == "short",
    "LONG_ONLY": lambda row: row["direction"] == "long",
    "HIGH_VOLATILITY_LONG": lambda row: row["market_regime"] == "HIGH_VOLATILITY" and row["direction"] == "long",
    "HIGH_VOLATILITY_SHORT": lambda row: row["market_regime"] == "HIGH_VOLATILITY" and row["direction"] == "short",
    "CHOPPY_RANGE_SHORT": lambda row: row["entry_context"] == "CHOPPY_RANGE" and row["direction"] == "short",
    "CHOPPY_RANGE_LONG": lambda row: row["entry_context"] == "CHOPPY_RANGE" and row["direction"] == "long",
}

DRILLDOWN_FIELDS = (
    "direction",
    "session",
    "setup_type",
    "entry_context",
    "market_regime",
    "trade_location",
    "score_bucket",
    "volume_bucket",
    "body_ratio_bucket",
    "rr_bucket",
    "trend_alignment",
    "opened_hour_utc",
    "symbol",
    "penalty",
    "rejection_reason",
)

CSV_FIELDS = [
    "generated_at",
    "segment",
    "target_context",
    "feature",
    "value",
    "sample_size",
    "total_r",
    "profit_factor",
    "winrate",
    "avg_r",
    "max_drawdown",
    "confidence",
    "rolling_last_10_r",
    "rolling_last_20_r",
    "rolling_last_30_r",
    "degradation",
    "toxicity_score",
    "opportunity_score",
    "classification",
]


def load_context_toxicity_records(data_path: Path, reports_path: Path) -> list[dict[str, Any]]:
    return [row for row in (_normalize(row) for row in load_canonical_closed_trades(data_path)) if row is not None]


def analyze_context_toxicity(records: list[dict[str, Any]], *, min_trades: int = 5) -> dict[str, Any]:
    normalized = [row for row in (_normalize(row) for row in records) if row is not None and row.get("result_r") is not None]
    rows = _build_rows(normalized, min_trades=min_trades)
    confirmed = [row for row in rows if row["classification"] == "CONFIRMED_TOXIC"]
    hidden = [row for row in rows if row["classification"] == "HIDDEN_EDGE"]
    unstable = [row for row in rows if row["classification"] == "UNSTABLE"]
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "records_analyzed": len(normalized),
        "min_trades": min_trades,
        "global_performance": _metrics(normalized),
        "segment_performance": _segment_performance(normalized),
        "analysis_rows": rows,
        "confirmed_toxic_contexts": confirmed,
        "unstable_contexts": unstable,
        "hidden_edge_contexts": hidden,
        "recommended_keep_blocked": _recommended_keep_blocked(confirmed),
        "recommended_watchlist": _recommended_watchlist(unstable),
        "recommended_candidate_relaxations": _recommended_candidate_relaxations(hidden),
        "what_not_to_change": _what_not_to_change(rows),
    }


def write_context_toxicity_reports(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "context_toxicity_deep_dive.json"
    csv_path = reports_path / "context_toxicity_deep_dive.csv"
    summary_path = reports_path / "context_toxicity_deep_dive_summary.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_csv(csv_path, result.get("analysis_rows", []), result.get("generated_at"))
    summary_path.write_text(format_context_toxicity_summary(result), encoding="utf-8")
    return {"json_path": json_path, "csv_path": csv_path, "summary_path": summary_path}


def format_context_toxicity_summary(result: dict[str, Any]) -> str:
    global_metrics = result.get("global_performance", {})
    return (
        "# Context Toxicity Deep Dive\n\n"
        f"- Generated at: {result.get('generated_at')}\n"
        f"- Records analyzed: {result.get('records_analyzed', 0)}\n"
        f"- Min trades: {result.get('min_trades', 0)}\n"
        f"- Global WR: {global_metrics.get('winrate', 0)}%\n"
        f"- Global Total R: {global_metrics.get('total_r', 0)}\n"
        f"- Global PF: {_pf(global_metrics.get('profit_factor'))}\n\n"
        "## Confirmed Toxic Contexts\n\n"
        f"{_format_rows(result.get('confirmed_toxic_contexts'))}\n\n"
        "## Hidden Edge Contexts\n\n"
        f"{_format_rows(result.get('hidden_edge_contexts'))}\n\n"
        "## Unstable Contexts\n\n"
        f"{_format_rows(result.get('unstable_contexts'))}\n\n"
        "## Recommended Keep Blocked\n\n"
        f"{_format_list(result.get('recommended_keep_blocked'))}\n\n"
        "## Watchlist\n\n"
        f"{_format_list(result.get('recommended_watchlist'))}\n\n"
        "## Candidate Relaxations\n\n"
        f"{_format_list(result.get('recommended_candidate_relaxations'))}\n\n"
        "## What NOT To Change\n\n"
        f"{_format_list(result.get('what_not_to_change'))}\n"
    )


def _build_rows(records: list[dict[str, Any]], *, min_trades: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for segment_name, segment_predicate in SEGMENTS.items():
        segment_rows = [row for row in records if segment_predicate(row)]
        if segment_rows:
            rows.append(_analysis_row(segment_name, "SEGMENT", "segment", segment_name, segment_rows, min_trades=min_trades))
        for target_name, target_predicate in TARGET_CONTEXTS.items():
            target_rows = [row for row in segment_rows if target_predicate(row)]
            if not target_rows:
                continue
            rows.append(_analysis_row(segment_name, target_name, "target_context", target_name, target_rows, min_trades=min_trades))
            for field in DRILLDOWN_FIELDS:
                grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
                for row in target_rows:
                    for value in _field_values(row, field):
                        grouped[value].append(row)
                for value, items in grouped.items():
                    rows.append(_analysis_row(segment_name, target_name, field, value, items, min_trades=min_trades))
    return sorted(rows, key=lambda row: (float(row["toxicity_score"]), -float(row["opportunity_score"]), int(row["sample_size"])), reverse=True)


def _analysis_row(
    segment: str,
    target_context: str,
    feature: str,
    value: str,
    records: list[dict[str, Any]],
    *,
    min_trades: int,
) -> dict[str, Any]:
    metrics = _metrics(records)
    rolling = _rolling_metrics(records)
    degradation = _degradation(metrics, rolling)
    toxicity = _toxicity_score(metrics, degradation, min_trades=min_trades)
    opportunity = _opportunity_score(metrics, degradation, min_trades=min_trades)
    classification = _classification(
        segment=segment,
        target_context=target_context,
        feature=feature,
        value=value,
        metrics=metrics,
        toxicity_score=toxicity,
        opportunity_score=opportunity,
        min_trades=min_trades,
    )
    return {
        "segment": segment,
        "target_context": target_context,
        "feature": feature,
        "value": value,
        "sample_size": metrics["sample_size"],
        "total_r": metrics["total_r"],
        "profit_factor": metrics["profit_factor"],
        "winrate": metrics["winrate"],
        "avg_r": metrics["avg_r"],
        "max_drawdown": metrics["max_drawdown"],
        "confidence": _confidence(int(metrics["sample_size"])),
        "rolling_last_10_r": rolling["last_10_total_r"],
        "rolling_last_20_r": rolling["last_20_total_r"],
        "rolling_last_30_r": rolling["last_30_total_r"],
        "degradation": degradation,
        "toxicity_score": toxicity,
        "opportunity_score": opportunity,
        "classification": classification,
    }


def _classification(
    *,
    segment: str,
    target_context: str,
    feature: str,
    value: str,
    metrics: dict[str, Any],
    toxicity_score: float,
    opportunity_score: float,
    min_trades: int,
) -> str:
    sample = int(metrics["sample_size"])
    avg_r = float(metrics["avg_r"])
    pf = metrics["profit_factor"]
    winrate = float(metrics["winrate"])
    if sample < min_trades:
        return "UNSTABLE"
    if segment == "HIGH_VOLATILITY_LONG" and avg_r < 0 and (pf is not None and float(pf) < 1.0):
        return "CONFIRMED_TOXIC"
    if toxicity_score >= 65 and avg_r < 0 and (winrate < 45 or (pf is not None and float(pf) < 1.0)):
        return "CONFIRMED_TOXIC"
    if segment in {"HIGH_VOLATILITY_SHORT", "CHOPPY_RANGE_SHORT"} and opportunity_score >= 65:
        if _has_london_or_volume_edge(feature, value, target_context):
            return "HIDDEN_EDGE"
    if opportunity_score >= 75 and avg_r > 0 and winrate >= 50:
        return "HIDDEN_EDGE"
    return "UNSTABLE"


def _has_london_or_volume_edge(feature: str, value: str, target_context: str) -> bool:
    return (
        feature == "session" and value == "LONDON"
    ) or (
        feature == "volume_bucket" and value == "volume_high"
    ) or "LONDON" in target_context


def _metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(row["result_r"]) for row in records if row.get("result_r") is not None]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    gross_profit = sum(max(0.0, value) for value in values)
    gross_loss = abs(sum(min(0.0, value) for value in values))
    max_drawdown, current_drawdown = _drawdowns(values)
    return {
        "sample_size": len(values),
        "wins": len(wins),
        "losses": len(losses),
        "total_r": round(sum(values), 4),
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else (None if gross_profit > 0 else 0.0),
        "winrate": round(len(wins) / len(values) * 100, 2) if values else 0.0,
        "avg_r": round(sum(values) / len(values), 4) if values else 0.0,
        "max_drawdown": round(max_drawdown, 4),
        "current_drawdown": round(current_drawdown, 4),
    }


def _rolling_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(records, key=lambda row: str(row.get("timestamp") or ""))
    values = [float(row["result_r"]) for row in ordered if row.get("result_r") is not None]
    return {
        "last_10_total_r": round(sum(values[-10:]), 4) if values else 0.0,
        "last_20_total_r": round(sum(values[-20:]), 4) if values else 0.0,
        "last_30_total_r": round(sum(values[-30:]), 4) if values else 0.0,
        "last_10_avg_r": round(sum(values[-10:]) / len(values[-10:]), 4) if values[-10:] else 0.0,
    }


def _degradation(metrics: dict[str, Any], rolling: dict[str, Any]) -> float:
    avg_r = float(metrics["avg_r"])
    last_10_avg = float(rolling["last_10_avg_r"])
    return round(avg_r - last_10_avg, 4)


def _toxicity_score(metrics: dict[str, Any], degradation: float, *, min_trades: int) -> float:
    sample = int(metrics["sample_size"])
    if sample == 0:
        return 0.0
    pf = metrics["profit_factor"]
    score = 0.0
    if float(metrics["avg_r"]) < 0:
        score += min(35.0, abs(float(metrics["avg_r"])) * 40.0)
    if float(metrics["total_r"]) < 0:
        score += min(25.0, abs(float(metrics["total_r"])) * 4.0)
    if pf is not None and float(pf) < 1.0:
        score += (1.0 - float(pf)) * 25.0
    if float(metrics["winrate"]) < 40:
        score += (40.0 - float(metrics["winrate"])) * 0.5
    if degradation > 0:
        score += min(15.0, degradation * 20.0)
    if sample < min_trades:
        score *= 0.5
    return round(min(100.0, score), 4)


def _opportunity_score(metrics: dict[str, Any], degradation: float, *, min_trades: int) -> float:
    sample = int(metrics["sample_size"])
    if sample == 0:
        return 0.0
    pf = metrics["profit_factor"]
    score = 0.0
    if float(metrics["avg_r"]) > 0:
        score += min(35.0, float(metrics["avg_r"]) * 40.0)
    if float(metrics["total_r"]) > 0:
        score += min(25.0, float(metrics["total_r"]) * 4.0)
    if pf is None:
        score += 25.0
    elif float(pf) > 1.2:
        score += min(25.0, (float(pf) - 1.0) * 20.0)
    if float(metrics["winrate"]) > 50:
        score += min(15.0, (float(metrics["winrate"]) - 50.0) * 0.5)
    if degradation < 0:
        score += min(10.0, abs(degradation) * 15.0)
    if sample < min_trades:
        score *= 0.5
    return round(min(100.0, score), 4)


def _segment_performance(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {name: _metrics([row for row in records if predicate(row)]) for name, predicate in SEGMENTS.items()}


def _field_values(row: dict[str, Any], field: str) -> list[str]:
    if field == "score_bucket":
        return [_score_bucket(row.get("score"))]
    if field == "volume_bucket":
        return [_ratio_bucket(row.get("volume_ratio"), low=0.8, high=1.2, labels=("volume_low", "volume_mid", "volume_high"))]
    if field == "body_ratio_bucket":
        return [_ratio_bucket(row.get("body_ratio"), low=0.35, high=0.5, labels=("body_weak", "body_valid", "body_strong"))]
    if field == "rr_bucket":
        return [_rr_bucket(row.get("risk_reward") or row.get("risk_reward_tp2") or row.get("rr"))]
    if field == "trend_alignment":
        return [_trend_alignment(row)]
    if field == "penalty":
        return sorted(row["penalties"]) or ["none"]
    if field == "rejection_reason":
        return sorted(row["rejection_reasons"]) or ["none"]
    return [str(row.get(field) or "UNKNOWN")]


def _normalize(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    result_r = _float(row.get("result_r") or row.get("r_result") or row.get("realized_r"))
    if result_r is None:
        return None
    raw_reasons = row.get("entry_reasons") or row.get("reasons")
    penalties = _tokens(row.get("penalties")) | _trace_penalty_tokens(raw_reasons)
    rejection_reasons = _tokens(row.get("rejection_reasons") or row.get("conditions_failed") or row.get("entry_or_rejection_reason"))
    return {
        **row,
        "result_r": result_r,
        "symbol": str(row.get("symbol") or "UNKNOWN").upper(),
        "direction": str(row.get("direction") or "unknown").lower(),
        "session": str(row.get("session") or "UNKNOWN").upper(),
        "setup_type": str(row.get("setup_type") or "UNKNOWN").upper(),
        "entry_context": str(row.get("entry_context") or "UNKNOWN").upper(),
        "market_regime": str(row.get("market_regime") or "UNKNOWN").upper(),
        "trade_location": str(row.get("trade_location") or "UNKNOWN"),
        "score": _float(row.get("score") or row.get("setup_score") or row.get("setup_score_final")),
        "volume_ratio": _float(row.get("volume_ratio") or row.get("volume_ratio_vs_average_20")),
        "body_ratio": _float(row.get("body_ratio")),
        "risk_reward": _float(row.get("risk_reward") or row.get("risk_reward_tp2") or row.get("rr")),
        "trend_entry": str(row.get("trend_entry") or row.get("trend_1h") or "").lower(),
        "trend_higher": str(row.get("trend_higher") or row.get("trend_4h") or row.get("trend_higher_timeframe") or "").lower(),
        "opened_hour_utc": str(row.get("opened_hour_utc") or _hour(row.get("opened_at") or row.get("timestamp"))),
        "penalties": penalties,
        "rejection_reasons": rejection_reasons,
    }


def _recommended_keep_blocked(rows: list[dict[str, Any]]) -> list[str]:
    ordered = sorted(rows, key=_recommendation_priority)
    return [
        f"{row['segment']} | {row['target_context']} | {row['feature']}={row['value']} | "
        f"n={row['sample_size']} | AvgR={row['avg_r']} | PF={_pf(row['profit_factor'])}"
        for row in ordered[:10]
    ] or ["no_confirmed_toxic_context_with_current_sample"]


def _recommended_watchlist(rows: list[dict[str, Any]]) -> list[str]:
    ordered = sorted(rows, key=_recommendation_priority)
    return [
        f"{row['segment']} | {row['target_context']} | {row['feature']}={row['value']} | "
        f"n={row['sample_size']} | toxicity={row['toxicity_score']} | opportunity={row['opportunity_score']}"
        for row in ordered[:10]
    ] or ["no_unstable_contexts"]


def _recommended_candidate_relaxations(rows: list[dict[str, Any]]) -> list[str]:
    ordered = sorted(rows, key=_recommendation_priority)
    return [
        f"{row['segment']} | {row['target_context']} | {row['feature']}={row['value']} | "
        f"n={row['sample_size']} | AvgR={row['avg_r']} | PF={_pf(row['profit_factor'])}"
        for row in ordered[:10]
    ] or ["no_candidate_relaxation_detected"]


def _recommendation_priority(row: dict[str, Any]) -> tuple[int, int, float, float]:
    feature_priority = 0 if row.get("feature") == "segment" else 1
    target_priority = 0 if row.get("target_context") == "SEGMENT" else 1
    return (
        feature_priority,
        target_priority,
        -float(row.get("toxicity_score") or 0),
        -float(row.get("opportunity_score") or 0),
    )


def _what_not_to_change(rows: list[dict[str, Any]]) -> list[str]:
    output = [
        "do_not_relax_unknown_contexts_globally",
        "do_not_relax_choppy_range_or_high_volatility_without_direction_session_volume_filters",
        "do_not_change_public_policy_from_low_confidence_samples",
    ]
    high_vol_long = next((row for row in rows if row["segment"] == "HIGH_VOLATILITY_LONG" and row["feature"] == "segment"), None)
    if high_vol_long and high_vol_long["classification"] == "CONFIRMED_TOXIC":
        output.append("do_not_enable_high_volatility_long_publicly")
    return output


def _write_csv(path: Path, rows: list[dict[str, Any]], generated_at: str | None) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS} | {"generated_at": generated_at or ""})


def _max_drawdown(values: list[float]) -> float:
    return _drawdowns(values)[0]


def _drawdowns(values: list[float]) -> tuple[float, float]:
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        max_dd = min(max_dd, cumulative - peak)
    return max_dd, cumulative - peak


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


def _ratio_bucket(value: object, *, low: float, high: float, labels: tuple[str, str, str]) -> str:
    number = _float(value)
    if number is None:
        return "UNKNOWN"
    if number < low:
        return labels[0]
    if number < high:
        return labels[1]
    return labels[2]


def _rr_bucket(value: object) -> str:
    number = _float(value)
    if number is None:
        return "UNKNOWN"
    if number < 1.5:
        return "rr_below_1_5"
    if number < 2:
        return "rr_1_5_to_2"
    return "rr_2_plus"


def _trend_alignment(row: dict[str, Any]) -> str:
    entry = str(row.get("trend_entry") or "").lower()
    higher = str(row.get("trend_higher") or "").lower()
    if not entry or not higher or "unknown" in {entry, higher}:
        return "UNKNOWN"
    return "aligned" if entry == higher else "misaligned"


def _hour(value: object) -> str:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return "UNKNOWN"
    return str(parsed.astimezone(UTC).hour)


def _tokens(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, set):
        return {str(item).strip().lower() for item in value if str(item).strip()}
    if isinstance(value, list):
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


def _trace_penalty_tokens(value: object) -> set[str]:
    tokens = set()
    for item in _trace_items(value):
        text = str(item)
        if text.startswith("penalties="):
            tokens |= _tokens(text.split("=", 1)[1])
    return tokens


def _trace_items(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    text = str(value).strip()
    if not text:
        return []
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        decoded = None
    if isinstance(decoded, list):
        return [str(item) for item in decoded]
    return [text]


def _confidence(sample_size: int) -> str:
    if sample_size >= 30:
        return "HIGH"
    if sample_size >= 10:
        return "MEDIUM"
    return "LOW"


def _pf(value: object) -> object:
    return "inf" if value is None else value


def _format_rows(rows: object) -> str:
    if not isinstance(rows, list) or not rows:
        return "- none"
    return "\n".join(
        f"- {row.get('segment')} | {row.get('target_context')} | {row.get('feature')}={row.get('value')} | "
        f"n={row.get('sample_size')} | WR={row.get('winrate')}% | TotalR={row.get('total_r')} | "
        f"AvgR={row.get('avg_r')} | PF={_pf(row.get('profit_factor'))}"
        for row in rows[:10]
        if isinstance(row, dict)
    )


def _format_list(items: object) -> str:
    if not isinstance(items, list) or not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
