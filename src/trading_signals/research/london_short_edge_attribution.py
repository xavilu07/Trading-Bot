from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


CLOSED_STATUSES = {"tp2_hit", "tp_hit", "sl_hit", "expired", "breakeven", "closed", "win", "loss"}
WIN_STATUSES = {"tp2_hit", "tp_hit", "win"}
BLOCKED_STATUSES = {"rejected", "no_trade", "blocked"}
RANGE_PENALTY = "market_structure_range_penalty"
SECONDARY_FAILED = "secondary_setup_requirements_failed"
BODY_RATIO_FAILED = "body_ratio_below_threshold"

CSV_FIELDS = [
    "generated_at",
    "analysis_type",
    "feature",
    "value",
    "sample_size",
    "closed_trades",
    "allowed_count",
    "blocked_count",
    "wins",
    "losses",
    "winrate",
    "total_r",
    "avg_r",
    "profit_factor",
    "confidence",
    "driver_score",
    "interpretation",
]

FEATURES = (
    "setup_type",
    "entry_context",
    "market_regime",
    "trade_location",
    "score_bucket",
    "trend_alignment",
    "volume_bucket",
    "body_bucket",
    "rr_bucket",
    "has_penalties",
    "has_range_penalty",
    "has_secondary_setup_requirements_failed",
    "has_body_ratio_below_threshold",
    "penalty",
    "rejection_reason",
)

COMPARISONS = {
    "MAIN_SIGNAL vs SECONDARY_SIGNAL": ("setup_type", ("MAIN_SIGNAL", "SECONDARY_SIGNAL")),
    "PULLBACK vs BREAKOUT": ("entry_context", ("PULLBACK", "BREAKOUT")),
    "RANGING vs TRENDING vs HIGH_VOLATILITY": ("market_regime", ("RANGING", "TRENDING", "HIGH_VOLATILITY")),
    "score 70-79 vs 80-89 vs 90+": ("score_bucket", ("70-79", "80-89", "90+")),
    "with range penalty vs without range penalty": ("has_range_penalty", ("true", "false")),
}


def load_london_short_research_rows(data_path: Path, reports_path: Path | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(_load_trade_csvs(data_path))
    rows.extend(_load_signal_activity(data_path / "bot_activity" / "signals_log.jsonl"))
    if reports_path is not None:
        rows.extend(_load_meta_dataset(reports_path / "meta_dataset.csv"))
    normalized = [_normalize_row(row) for row in rows]
    return [
        row
        for row in normalized
        if row is not None and row["session"] == "LONDON" and row["direction"] == "short"
    ]


def analyze_london_short_edge_attribution(rows: list[dict[str, Any]], *, min_trades: int = 5) -> dict[str, Any]:
    normalized = [_normalize_row(row) for row in rows]
    london_short = [
        row
        for row in normalized
        if row is not None and row["session"] == "LONDON" and row["direction"] == "short"
    ]
    closed = [row for row in london_short if row["result_r"] is not None]
    winners = [row for row in closed if float(row["result_r"]) > 0]
    losers = [row for row in closed if float(row["result_r"]) < 0]
    attribution_rows = _build_attribution_rows(london_short, min_trades=min_trades)
    comparison_rows = _build_comparison_rows(london_short, min_trades=min_trades)
    positive = [
        row for row in attribution_rows
        if row["analysis_type"] == "driver" and row["interpretation"] == "positive_driver"
    ][:10]
    negative = [
        row for row in attribution_rows
        if row["analysis_type"] == "driver" and row["interpretation"] == "negative_driver"
    ][:10]
    recommended_rules = _recommended_rules(positive, negative, min_trades=min_trades)
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "rows_analyzed": len(london_short),
        "closed_trades": len(closed),
        "allowed_rows": len([row for row in london_short if row["allowed"]]),
        "blocked_rows": len([row for row in london_short if row["blocked"]]),
        "winners": len(winners),
        "losers": len(losers),
        "overall_metrics": _metrics(closed),
        "winner_profile": _profile(winners),
        "loser_profile": _profile(losers),
        "allowed_profile": _profile([row for row in london_short if row["allowed"]]),
        "blocked_profile": _profile([row for row in london_short if row["blocked"]]),
        "top_positive_drivers": positive,
        "top_negative_drivers": negative,
        "comparison_rows": comparison_rows,
        "attribution_rows": attribution_rows,
        "recommended_rules": recommended_rules,
        "what_not_to_change": _what_not_to_change(attribution_rows),
        "confidence": _confidence(len(closed)),
        "sample_size": len(london_short),
    }


def write_london_short_edge_reports(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "london_short_edge_attribution.json"
    csv_path = reports_path / "london_short_edge_attribution.csv"
    summary_path = reports_path / "london_short_edge_attribution_summary.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_csv(csv_path, result.get("attribution_rows", []) + result.get("comparison_rows", []), result.get("generated_at"))
    summary_path.write_text(format_london_short_edge_attribution(result), encoding="utf-8")
    return {"json_path": json_path, "csv_path": csv_path, "summary_path": summary_path}


def format_london_short_edge_attribution(result: dict[str, Any]) -> str:
    metrics = result.get("overall_metrics", {})
    return (
        "# London Short Edge Attribution\n\n"
        f"- Generated at: {result.get('generated_at')}\n"
        f"- Sample size: {result.get('sample_size', 0)}\n"
        f"- Closed trades: {result.get('closed_trades', 0)}\n"
        f"- Allowed / blocked rows: {result.get('allowed_rows', 0)} / {result.get('blocked_rows', 0)}\n"
        f"- WR: {metrics.get('winrate', 0)}%\n"
        f"- Total R: {metrics.get('total_r', 0)}\n"
        f"- Avg R: {metrics.get('avg_r', 0)}\n"
        f"- PF: {_pf(metrics.get('profit_factor'))}\n"
        f"- Confidence: {result.get('confidence', 'LOW')}\n\n"
        "## Top Positive Drivers\n\n"
        f"{_format_rows(result.get('top_positive_drivers'))}\n\n"
        "## Top Negative Drivers\n\n"
        f"{_format_rows(result.get('top_negative_drivers'))}\n\n"
        "## Recommended Rules\n\n"
        f"{_format_list(result.get('recommended_rules'))}\n\n"
        "## What NOT To Change\n\n"
        f"{_format_list(result.get('what_not_to_change'))}\n"
    )


def _build_attribution_rows(rows: list[dict[str, Any]], *, min_trades: int) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for feature in FEATURES:
            for value in _feature_values(row, feature):
                grouped[(feature, value)].append(row)
    output = []
    for (feature, value), items in grouped.items():
        output.append(_analysis_row("driver", feature, value, items, min_trades=min_trades))
    return sorted(output, key=lambda row: (float(row["driver_score"]), int(row["closed_trades"])), reverse=True)


def _build_comparison_rows(rows: list[dict[str, Any]], *, min_trades: int) -> list[dict[str, Any]]:
    output = []
    for label, (feature, values) in COMPARISONS.items():
        for value in values:
            items = [row for row in rows if str(row.get(feature)) == value]
            output.append(_analysis_row("comparison", label, value, items, min_trades=min_trades))
    return output


def _analysis_row(
    analysis_type: str,
    feature: str,
    value: str,
    rows: list[dict[str, Any]],
    *,
    min_trades: int,
) -> dict[str, Any]:
    closed = [row for row in rows if row["result_r"] is not None]
    metrics = _metrics(closed)
    driver_score = _driver_score(metrics, min_trades=min_trades)
    interpretation = _interpretation(metrics, min_trades=min_trades)
    return {
        "analysis_type": analysis_type,
        "feature": feature,
        "value": value,
        "sample_size": len(rows),
        "closed_trades": metrics["trades"],
        "allowed_count": len([row for row in rows if row["allowed"]]),
        "blocked_count": len([row for row in rows if row["blocked"]]),
        "wins": metrics["wins"],
        "losses": metrics["losses"],
        "winrate": metrics["winrate"],
        "total_r": metrics["total_r"],
        "avg_r": metrics["avg_r"],
        "profit_factor": metrics["profit_factor"],
        "confidence": _confidence(int(metrics["trades"])),
        "driver_score": driver_score,
        "interpretation": interpretation,
    }


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(row["result_r"]) for row in rows if row.get("result_r") is not None]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    gross_profit = sum(max(0.0, value) for value in values)
    gross_loss = abs(sum(min(0.0, value) for value in values))
    return {
        "trades": len(values),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": round(len(wins) / len(values) * 100, 2) if values else 0.0,
        "total_r": round(sum(values), 4),
        "avg_r": round(sum(values) / len(values), 4) if values else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else (None if gross_profit > 0 else 0.0),
    }


def _driver_score(metrics: dict[str, Any], *, min_trades: int) -> float:
    trades = int(metrics["trades"])
    if trades < min_trades:
        return 0.0
    pf = metrics["profit_factor"]
    pf_component = 3.0 if pf is None and float(metrics["total_r"]) > 0 else min(float(pf or 0.0), 3.0)
    return round(float(metrics["avg_r"]) + (float(metrics["winrate"]) / 100.0) + pf_component + min(trades / 30.0, 1.0), 4)


def _interpretation(metrics: dict[str, Any], *, min_trades: int) -> str:
    trades = int(metrics["trades"])
    if trades < min_trades:
        return "insufficient_sample"
    pf = metrics["profit_factor"]
    avg_r = float(metrics["avg_r"])
    winrate = float(metrics["winrate"])
    if avg_r > 0 and winrate >= 50 and (pf is None or float(pf) >= 1.2):
        return "positive_driver"
    if avg_r < 0 and (winrate < 45 or (pf is not None and float(pf) < 1.0)):
        return "negative_driver"
    return "mixed_or_neutral"


def _feature_values(row: dict[str, Any], feature: str) -> list[str]:
    if feature == "score_bucket":
        return [_score_bucket(row.get("score"))]
    if feature == "trend_alignment":
        return [_trend_alignment(row)]
    if feature == "volume_bucket":
        return [_ratio_bucket(row.get("volume_ratio"), high=1.2, low=0.8, labels=("volume_high", "volume_mid", "volume_low"))]
    if feature == "body_bucket":
        return [_ratio_bucket(row.get("body_ratio"), high=0.5, low=0.35, labels=("body_strong", "body_valid", "body_weak"))]
    if feature == "rr_bucket":
        return [_rr_bucket(row.get("risk_reward"))]
    if feature == "has_penalties":
        return ["true" if row["penalties"] else "false"]
    if feature == "has_range_penalty":
        return ["true" if RANGE_PENALTY in row["all_tokens"] else "false"]
    if feature == "has_secondary_setup_requirements_failed":
        return ["true" if SECONDARY_FAILED in row["all_tokens"] else "false"]
    if feature == "has_body_ratio_below_threshold":
        return ["true" if BODY_RATIO_FAILED in row["all_tokens"] else "false"]
    if feature == "penalty":
        return sorted(row["penalties"]) or ["none"]
    if feature == "rejection_reason":
        return sorted(row["rejection_reasons"]) or ["none"]
    value = str(row.get(feature) or "UNKNOWN").strip()
    return [value if value else "UNKNOWN"]


def _profile(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "setup_type": dict(Counter(str(row.get("setup_type")) for row in rows).most_common(10)),
        "entry_context": dict(Counter(str(row.get("entry_context")) for row in rows).most_common(10)),
        "market_regime": dict(Counter(str(row.get("market_regime")) for row in rows).most_common(10)),
        "trade_location": dict(Counter(str(row.get("trade_location")) for row in rows).most_common(10)),
        "score_bucket": dict(Counter(_score_bucket(row.get("score")) for row in rows).most_common(10)),
        "penalties": dict(Counter(token for row in rows for token in row["penalties"]).most_common(10)),
        "rejection_reasons": dict(Counter(token for row in rows for token in row["rejection_reasons"]).most_common(10)),
    }


def _recommended_rules(positive: list[dict[str, Any]], negative: list[dict[str, Any]], *, min_trades: int) -> list[str]:
    rules = []
    for row in positive[:5]:
        rules.append(
            f"observe_allow_candidate: {row['feature']}={row['value']} "
            f"(n={row['closed_trades']}, WR={row['winrate']}%, AvgR={row['avg_r']}, PF={_pf(row['profit_factor'])})"
        )
    for row in negative[:5]:
        rules.append(
            f"avoid_or_keep_private: {row['feature']}={row['value']} "
            f"(n={row['closed_trades']}, WR={row['winrate']}%, AvgR={row['avg_r']}, PF={_pf(row['profit_factor'])})"
        )
    if not rules:
        rules.append(f"collect_more_london_short_samples_before_policy_change_min_trades_{min_trades}")
    return rules


def _what_not_to_change(rows: list[dict[str, Any]]) -> list[str]:
    range_row = next((row for row in rows if row["feature"] == "has_range_penalty" and row["value"] == "true"), None)
    output = [
        "do_not_enable_all_shorts_globally",
        "do_not_change_public_policy_from_london_short_edge_without_context_filter",
    ]
    if not range_row or range_row["interpretation"] != "negative_driver":
        output.append("do_not_assume_market_structure_range_penalty_is_the_root_cause")
    if range_row and range_row["interpretation"] == "negative_driver":
        output.append("do_not_relax_market_structure_range_penalty_without_a_specific_positive_subcontext")
    return output


def _load_trade_csvs(data_path: Path) -> list[dict[str, Any]]:
    paths = []
    paper_path = data_path / "paper_trading"
    if paper_path.exists():
        paths.extend(path for path in paper_path.glob("*.csv") if path.is_file())
    live_path = data_path / "live_trading" / "trades.csv"
    if live_path.exists():
        paths.append(live_path)
    rows = []
    for path in sorted(paths):
        for row in _read_csv(path):
            status = str(row.get("status") or row.get("outcome") or "").strip().lower()
            result_r = _float(row.get("result_r") or row.get("r_result") or row.get("realized_r"))
            if result_r is None:
                continue
            if status and status not in CLOSED_STATUSES and not row.get("closed_at"):
                continue
            rows.append({**row, "result_r": result_r, "source": f"trade:{path.name}", "allowed": True})
    return rows


def _load_signal_activity(path: Path, *, max_lines: int = 10000) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    rows = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle.readlines()[-max_lines:]:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append({**item, "source": "signals_log"})
    return rows


def _load_meta_dataset(path: Path) -> list[dict[str, Any]]:
    rows = []
    for row in _read_csv(path):
        result_r = _float(row.get("result_r"))
        label = str(row.get("label") or "").strip()
        if result_r is None and label in {"0", "1"}:
            result_r = 1.0 if label == "1" else -1.0
        rows.append({**row, "result_r": result_r, "source": "meta_dataset"})
    return rows


def _normalize_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    raw_summary = row.get("raw_summary") if isinstance(row.get("raw_summary"), dict) else {}
    penalties = _tokens(row.get("penalties") or raw_summary.get("penalties"))
    penalties |= _trace_penalty_tokens(row.get("entry_reasons") or row.get("reasons") or raw_summary.get("entry_reasons"))
    rejection_reasons = _tokens(
        row.get("rejection_reasons")
        or row.get("conditions_failed")
        or row.get("entry_or_rejection_reason")
        or raw_summary.get("rejection_reasons")
    )
    warnings = _tokens(row.get("warnings") or row.get("avoidance_warnings"))
    result_r = _float(row.get("result_r") or row.get("r_result") or row.get("realized_r"))
    status = str(row.get("status") or row.get("outcome") or "").strip().lower()
    all_tokens = penalties | rejection_reasons | warnings
    direction = _norm_lower(row.get("direction") or raw_summary.get("direction"))
    session = _norm_upper(row.get("session") or raw_summary.get("session"))
    if direction != "short" or session != "LONDON":
        return None
    return {
        **row,
        "direction": direction,
        "session": session,
        "setup_type": _norm_upper(row.get("setup_type") or raw_summary.get("setup_type") or "UNKNOWN"),
        "entry_context": _norm_upper(row.get("entry_context") or raw_summary.get("entry_context") or "UNKNOWN"),
        "market_regime": _norm_upper(row.get("market_regime") or raw_summary.get("market_regime") or "UNKNOWN"),
        "trade_location": str(row.get("trade_location") or raw_summary.get("trade_location") or "UNKNOWN").strip() or "UNKNOWN",
        "score": _float(row.get("score") or row.get("setup_score")),
        "body_ratio": _float(row.get("body_ratio")),
        "volume_ratio": _float(row.get("volume_ratio") or row.get("volume_ratio_vs_average_20")),
        "risk_reward": _float(row.get("risk_reward") or row.get("risk_reward_tp2") or row.get("rr")),
        "trend_entry": _norm_lower(row.get("trend_entry") or row.get("trend_1h")),
        "trend_higher": _norm_lower(row.get("trend_higher") or row.get("trend_4h") or row.get("trend_higher_timeframe")),
        "result_r": result_r,
        "status": status,
        "allowed": _allowed(row, status, result_r),
        "blocked": _blocked(row, status, result_r),
        "penalties": penalties,
        "rejection_reasons": rejection_reasons,
        "warnings": warnings,
        "all_tokens": all_tokens,
    }


def _allowed(row: dict[str, Any], status: str, result_r: float | None) -> bool:
    if result_r is not None:
        return True
    if str(row.get("public_published", "")).lower() == "true":
        return True
    return status in {"sent", "paper", "experimental"}


def _blocked(row: dict[str, Any], status: str, result_r: float | None) -> bool:
    if result_r is not None and status in CLOSED_STATUSES:
        return False
    if status in BLOCKED_STATUSES:
        return True
    return bool(row.get("rejection_reasons") or row.get("conditions_failed")) and status not in {"sent", "paper"}


def _score_bucket(score: object) -> str:
    value = _float(score)
    if value is None:
        return "UNKNOWN"
    if value < 70:
        return "<70"
    if value < 80:
        return "70-79"
    if value < 90:
        return "80-89"
    return "90+"


def _trend_alignment(row: dict[str, Any]) -> str:
    entry = str(row.get("trend_entry") or "").lower()
    higher = str(row.get("trend_higher") or "").lower()
    if not entry or not higher or "unknown" in {entry, higher}:
        return "UNKNOWN"
    return "aligned" if entry == higher else "misaligned"


def _ratio_bucket(value: object, *, high: float, low: float, labels: tuple[str, str, str]) -> str:
    number = _float(value)
    if number is None:
        return "UNKNOWN"
    if number >= high:
        return labels[0]
    if number >= low:
        return labels[1]
    return labels[2]


def _rr_bucket(value: object) -> str:
    number = _float(value)
    if number is None:
        return "UNKNOWN"
    if number >= 2:
        return "rr_2_plus"
    if number >= 1.5:
        return "rr_1_5_to_2"
    return "rr_below_1_5"


def _write_csv(path: Path, rows: list[dict[str, Any]], generated_at: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS} | {"generated_at": generated_at or ""})


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except csv.Error:
        return []


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
    tokens: set[str] = set()
    items = _trace_items(value)
    for item in items:
        text = str(item).strip()
        if text.startswith("penalties="):
            tokens |= _tokens(text.split("=", 1)[1])
        elif RANGE_PENALTY in text or "distance_to_liquidity_penalty" in text or "timeframe_alignment_penalty" in text:
            tokens |= _tokens(text)
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


def _format_rows(rows: object) -> str:
    if not isinstance(rows, list) or not rows:
        return "- sin datos"
    return "\n".join(
        f"- {row.get('feature')}={row.get('value')} | n={row.get('closed_trades')} | "
        f"WR={row.get('winrate')}% | TotalR={row.get('total_r')} | AvgR={row.get('avg_r')} | PF={_pf(row.get('profit_factor'))}"
        for row in rows[:8]
        if isinstance(row, dict)
    )


def _format_list(items: object) -> str:
    if not isinstance(items, list) or not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def _confidence(sample_size: int) -> str:
    if sample_size >= 30:
        return "HIGH"
    if sample_size >= 10:
        return "MEDIUM"
    return "LOW"


def _pf(value: object) -> object:
    return "inf" if value is None else value


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _norm_upper(value: object) -> str:
    return str(value or "UNKNOWN").strip().upper()


def _norm_lower(value: object) -> str:
    return str(value or "unknown").strip().lower()
