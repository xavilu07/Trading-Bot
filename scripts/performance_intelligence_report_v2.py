from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import TradeUniverse, load_trade_universe

CLOSED_STATUSES = {"expired", "sl_hit", "tp1_hit", "tp2_hit"}
OPEN_STATUSES = {"open", "pending"}
WIN_STATUSES = {"tp1_hit", "tp2_hit"}
LOSS_STATUSES = {"sl_hit"}

SINGLE_GROUPS = (
    "direction",
    "symbol",
    "setup_type",
    "paper_level",
    "score_exact",
    "score_bucket",
    "market_regime",
    "session",
    "entry_context",
    "trade_location",
    "opened_hour_utc",
    "opened_weekday",
    "rr_valid",
    "late_entry_from_bos",
    "trend_1h",
    "trend_4h",
    "break_of_structure",
    "liquidity_sweep",
    "directional_distance_to_liquidity_atr_bucket",
    "nearest_distance_to_liquidity_atr_bucket",
    "volume_ratio_bucket",
    "rsi_bucket",
)

COMBINED_GROUPS = (
    ("direction", "session"),
    ("direction", "market_regime"),
    ("direction", "entry_context"),
    ("direction", "setup_type"),
    ("symbol", "direction"),
    ("session", "entry_context"),
    ("market_regime", "entry_context"),
    ("direction", "market_regime", "entry_context"),
    ("setup_type", "market_regime"),
    ("score_bucket", "direction"),
    ("score_bucket", "session"),
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_path = Path(args.data_path)
    reports_path = Path(args.reports_path)
    result = generate_report(data_path=data_path, reports_path=reports_path)
    print(format_console_summary(result))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="performance-intelligence-report-v2")
    parser.add_argument("--data-path", default=os.getenv("DATA_STORAGE_PATH", "data"))
    parser.add_argument("--reports-path", default="reports")
    return parser.parse_args(argv)


def generate_report(*, data_path: Path, reports_path: Path) -> dict[str, Any]:
    trades_path = data_path / "paper_trading" / "trades.csv"
    rows = load_trade_universe(data_path, universe=TradeUniverse.ACCEPTED)
    normalized = [normalize_trade(row) for row in rows]
    closed = [row for row in normalized if row["is_closed"]]
    open_trades = [row for row in normalized if row["is_open"]]
    groups = build_group_analysis(closed)
    result = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": str(trades_path),
        "universe": TradeUniverse.ACCEPTED.value,
        "rows_loaded": len(rows),
        "closed_statuses": sorted(CLOSED_STATUSES),
        "open_statuses": sorted(OPEN_STATUSES),
        "closed_trades": len(closed),
        "open_trades": len(open_trades),
        "open_summary": summarize_open_trades(open_trades),
        "global_performance": metrics(closed),
        "status_distribution": dict(Counter(row["status"] for row in normalized)),
        "closed_status_distribution": dict(Counter(row["status"] for row in closed)),
        "groups": groups,
        "rankings": build_rankings(groups),
        "score_effectiveness": analyze_score_effectiveness(closed, groups),
        "expired_analysis": analyze_expired(closed, groups),
        "long_short_analysis": analyze_long_short(groups),
        "actionable_decisions": build_actionable_decisions(groups),
        "what_not_to_change_yet": build_what_not_to_change_yet(groups),
        "next_experiments": build_next_experiments(groups),
    }
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "performance_intelligence_report_v2.json"
    md_path = reports_path / "performance_intelligence_report_v2.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(format_markdown(result), encoding="utf-8")
    return result


def load_trade_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def normalize_trade(row: dict[str, Any]) -> dict[str, Any]:
    status = text(row.get("status")).lower() or "unknown"
    score = to_float(row.get("score"))
    opened_at = text(row.get("opened_at"))
    opened_hour = text(row.get("opened_hour_utc")) or parse_hour(opened_at)
    opened_weekday = text(row.get("opened_weekday")) or parse_weekday(opened_at)
    normalized = {
        **row,
        "status": status,
        "is_closed": status in CLOSED_STATUSES,
        "is_open": status in OPEN_STATUSES or (status not in CLOSED_STATUSES and not text(row.get("closed_at"))),
        "result_r": to_float(row.get("result_r")),
        "mfe_r": to_float(row.get("mfe_r")),
        "mae_r": to_float(row.get("mae_r")),
        "score": score,
        "score_exact": "UNKNOWN" if score is None else str(round(score, 4)).rstrip("0").rstrip("."),
        "score_bucket": score_bucket(score),
        "symbol": upper(row.get("symbol")),
        "direction": text(row.get("direction")).lower() or "unknown",
        "setup_type": upper(row.get("setup_type")),
        "paper_level": upper(row.get("paper_level")),
        "market_regime": upper(row.get("market_regime")),
        "session": upper(row.get("session")),
        "entry_context": upper(row.get("entry_context")),
        "trade_location": text(row.get("trade_location")) or "UNKNOWN",
        "opened_hour_utc": opened_hour,
        "opened_weekday": opened_weekday,
        "rr_valid": bool_text(row.get("rr_valid")),
        "late_entry_from_bos": bool_text(row.get("late_entry_from_bos")),
        "trend_1h": text(row.get("trend_1h")).lower() or "unknown",
        "trend_4h": text(row.get("trend_4h")).lower() or "unknown",
        "break_of_structure": text(row.get("break_of_structure")) or "UNKNOWN",
        "liquidity_sweep": text(row.get("liquidity_sweep")) or liquidity_from_reasons(row) or "none",
        "directional_distance_to_liquidity_atr": to_float(row.get("directional_distance_to_liquidity_atr")),
        "nearest_distance_to_liquidity_atr": to_float(row.get("nearest_distance_to_liquidity_atr")),
        "volume_ratio": to_float(row.get("volume_ratio")),
        "rsi": to_float(row.get("rsi")),
        "directional_distance_to_liquidity_atr_bucket": distance_bucket(to_float(row.get("directional_distance_to_liquidity_atr"))),
        "nearest_distance_to_liquidity_atr_bucket": distance_bucket(to_float(row.get("nearest_distance_to_liquidity_atr"))),
        "volume_ratio_bucket": volume_bucket(to_float(row.get("volume_ratio"))),
        "rsi_bucket": rsi_bucket(to_float(row.get("rsi"))),
    }
    return normalized


def build_group_analysis(closed: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "single": build_group_rows(closed, [(field,) for field in SINGLE_GROUPS]),
        "combined": build_group_rows(closed, COMBINED_GROUPS),
    }


def build_group_rows(closed: list[dict[str, Any]], definitions: tuple[tuple[str, ...], ...]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in closed:
        for definition in definitions:
            dimension = " + ".join(definition)
            value = " + ".join(str(row.get(field) or "UNKNOWN") for field in definition)
            grouped[(dimension, value)].append(row)
    rows = []
    for (dimension, value), items in grouped.items():
        rows.append({"dimension": dimension, "value": value, **metrics(items)})
    return sorted(rows, key=lambda item: (item["dimension"], -item["n"], item["value"]))


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [row["result_r"] for row in rows if row.get("result_r") is not None]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    neutral = [value for value in values if value == 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    expired = [row for row in rows if row.get("status") == "expired" and row.get("result_r") is not None]
    mfe_values = [row["mfe_r"] for row in rows if row.get("mfe_r") is not None]
    mae_values = [row["mae_r"] for row in rows if row.get("mae_r") is not None]
    return {
        "n": len(values),
        "totalR": round(sum(values), 4),
        "avgR": round(sum(values) / len(values), 4) if values else 0.0,
        "winrate": round(len(wins) / len(values) * 100, 4) if values else 0.0,
        "profit_factor": profit_factor(gross_win, gross_loss),
        "wins": len(wins),
        "losses": len(losses),
        "neutral": len(neutral),
        "expired_count": len(expired),
        "expired_totalR": round(sum(float(row["result_r"]) for row in expired), 4),
        "tp2_count": sum(1 for row in rows if row.get("status") == "tp2_hit"),
        "sl_count": sum(1 for row in rows if row.get("status") == "sl_hit"),
        "avg_mfe_r": round(sum(mfe_values) / len(mfe_values), 4) if mfe_values else None,
        "avg_mae_r": round(sum(mae_values) / len(mae_values), 4) if mae_values else None,
        "confidence": confidence(len(values)),
        "decision_hint": decision_hint(len(values), profit_factor(gross_win, gross_loss), sum(values), sum(values) / len(values) if values else 0.0),
    }


def profit_factor(gross_win: float, gross_loss: float) -> float | str:
    if gross_loss > 0:
        return round(gross_win / gross_loss, 4)
    if gross_win > 0:
        return "inf"
    return 0.0


def confidence(n: int) -> str:
    if n >= 30:
        return "HIGH"
    if n >= 15:
        return "MEDIUM"
    return "LOW"


def decision_hint(n: int, pf: float | str, total_r: float, avg_r: float) -> str:
    pf_value = pf_sort(pf)
    if n < 15:
        return "INSUFFICIENT_DATA"
    if n >= 30 and pf_value >= 1.3 and total_r > 0:
        return "PRIORITIZE"
    if n >= 15 and avg_r > 0:
        return "WATCH"
    if n >= 30 and pf_value < 0.85 and total_r < 0:
        return "AVOID"
    return "WATCH"


def build_rankings(groups: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    all_rows = groups["single"] + groups["combined"]
    evaluable = [row for row in all_rows if row["n"] >= 15]
    high_confidence = [row for row in all_rows if row["n"] >= 30]
    return {
        "best_edges": sorted(
            [row for row in evaluable if row["totalR"] > 0],
            key=lambda row: (row["totalR"], pf_sort(row["profit_factor"]), row["winrate"]),
            reverse=True,
        )[:25],
        "worst_edges": sorted(
            [row for row in evaluable if row["totalR"] < 0],
            key=lambda row: (row["totalR"], pf_sort(row["profit_factor"])),
        )[:25],
        "prioritize": sorted(
            [row for row in high_confidence if row["decision_hint"] == "PRIORITIZE"],
            key=lambda row: (row["totalR"], pf_sort(row["profit_factor"])),
            reverse=True,
        )[:25],
        "avoid": sorted(
            [row for row in high_confidence if row["decision_hint"] == "AVOID"],
            key=lambda row: (row["totalR"], pf_sort(row["profit_factor"])),
        )[:25],
    }


def analyze_score_effectiveness(
    closed: list[dict[str, Any]],
    groups: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    score_bucket_rows = [row for row in groups["single"] if row["dimension"] == "score_bucket"]
    exact_score_rows = [row for row in groups["single"] if row["dimension"] == "score_exact"]
    global_metrics = metrics(closed)
    bucket_90 = next((row for row in score_bucket_rows if row["value"] == "90-100"), None)
    bucket_80 = next((row for row in score_bucket_rows if row["value"] == "80-89"), None)
    conclusion = "INSUFFICIENT_DATA"
    if bucket_90 and bucket_90["n"] >= 15:
        if bucket_90["avgR"] > global_metrics["avgR"] and pf_sort(bucket_90["profit_factor"]) > pf_sort(global_metrics["profit_factor"]):
            conclusion = "HIGH_SCORE_CORRELATES_POSITIVELY"
        elif bucket_80 and bucket_90["avgR"] <= bucket_80["avgR"]:
            conclusion = "HIGH_SCORE_NOT_MONOTONIC"
        else:
            conclusion = "MIXED"
    return {
        "score_buckets": sorted(score_bucket_rows, key=lambda row: row["value"]),
        "score_exact": sorted(exact_score_rows, key=lambda row: (-row["n"], row["value"]))[:50],
        "conclusion": conclusion,
        "global_avgR": global_metrics["avgR"],
        "global_profit_factor": global_metrics["profit_factor"],
    }


def analyze_expired(closed: list[dict[str, Any]], groups: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    expired = [row for row in closed if row.get("status") == "expired"]
    expired_metrics = metrics(expired)
    total = len(closed)
    positive_expired = [row for row in expired if (row.get("result_r") or 0.0) > 0]
    conclusion = "NO_EXPIRED_TRADES"
    if expired:
        ratio = len(expired) / total if total else 0.0
        if ratio > 0.25 and expired_metrics["totalR"] > 0:
            conclusion = "MANY_POSITIVE_EXPIRED_CHECK_TP_CALIBRATION"
        elif ratio > 0.25 and expired_metrics["totalR"] < 0:
            conclusion = "MANY_NEGATIVE_EXPIRED_CHECK_TIMEOUT_OR_ENTRY"
        else:
            conclusion = "EXPIRED_NOT_DOMINANT"
    return {
        "metrics": expired_metrics,
        "expired_share": round(len(expired) / total * 100, 4) if total else 0.0,
        "positive_expired_count": len(positive_expired),
        "positive_expired_totalR": round(sum(float(row["result_r"]) for row in positive_expired), 4),
        "conclusion": conclusion,
        "top_expired_contexts": sorted(
            [row for row in groups["single"] + groups["combined"] if row["expired_count"] >= 5],
            key=lambda row: (row["expired_count"], abs(row["expired_totalR"])),
            reverse=True,
        )[:15],
    }


def analyze_long_short(groups: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    directions = {row["value"]: row for row in groups["single"] if row["dimension"] == "direction"}
    long = directions.get("long")
    short = directions.get("short")
    conclusion = "INSUFFICIENT_DATA"
    if long and short and long["n"] >= 15 and short["n"] >= 15:
        if short["totalR"] > long["totalR"] and pf_sort(short["profit_factor"]) > pf_sort(long["profit_factor"]):
            conclusion = "SHORT_OUTPERFORMS_LONG"
        elif long["totalR"] > short["totalR"] and pf_sort(long["profit_factor"]) > pf_sort(short["profit_factor"]):
            conclusion = "LONG_OUTPERFORMS_SHORT"
        else:
            conclusion = "MIXED_DIRECTION_EDGE"
    return {"direction_rows": directions, "conclusion": conclusion}


def build_actionable_decisions(groups: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = groups["single"] + groups["combined"]
    return {
        "prioritize": sorted(
            [row for row in rows if row["decision_hint"] == "PRIORITIZE"],
            key=lambda row: (row["totalR"], pf_sort(row["profit_factor"])),
            reverse=True,
        )[:20],
        "avoid": sorted(
            [row for row in rows if row["decision_hint"] == "AVOID"],
            key=lambda row: (row["totalR"], pf_sort(row["profit_factor"])),
        )[:20],
        "watch": sorted(
            [row for row in rows if row["decision_hint"] == "WATCH" and row["n"] >= 15],
            key=lambda row: abs(row["totalR"]),
            reverse=True,
        )[:20],
    }


def build_what_not_to_change_yet(groups: dict[str, list[dict[str, Any]]]) -> list[str]:
    rows = groups["single"] + groups["combined"]
    low_sample_positive = [row for row in rows if row["n"] < 15 and row["totalR"] > 0]
    low_sample_negative = [row for row in rows if row["n"] < 15 and row["totalR"] < 0]
    notes = [
        "No cambiar contextos con n < 15 aunque parezcan extremos: muestra insuficiente.",
        "No mezclar open trades con métricas cerradas; están separados en el JSON.",
    ]
    if low_sample_positive:
        notes.append("No priorizar todavía edges positivos con baja muestra; mantenerlos como hipótesis.")
    if low_sample_negative:
        notes.append("No bloquear todavía contextos negativos de baja muestra salvo que otro sistema independiente los confirme.")
    return notes


def build_next_experiments(groups: dict[str, list[dict[str, Any]]]) -> list[str]:
    decisions = build_actionable_decisions(groups)
    experiments = []
    if decisions["prioritize"]:
        top = decisions["prioritize"][0]
        experiments.append(f"Shadow priority para `{top['dimension']}={top['value']}`; evidencia HIGH y PF {top['profit_factor']}.")
    if decisions["avoid"]:
        worst = decisions["avoid"][0]
        experiments.append(f"Shadow block para `{worst['dimension']}={worst['value']}`; n={worst['n']} y TotalR {worst['totalR']}.")
    experiments.append("Comparar los próximos 7 días contra este baseline antes de promover cambios productivos.")
    return experiments


def summarize_open_trades(open_trades: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(open_trades),
        "by_status": dict(Counter(row["status"] for row in open_trades)),
        "by_direction": dict(Counter(row["direction"] for row in open_trades)),
        "by_symbol": dict(Counter(row["symbol"] for row in open_trades).most_common(20)),
        "by_setup_type": dict(Counter(row["setup_type"] for row in open_trades)),
    }


def format_console_summary(result: dict[str, Any]) -> str:
    global_metrics = result["global_performance"]
    return (
        "PERFORMANCE_INTELLIGENCE_REPORT_V2\n"
        f"- Closed trades: {global_metrics['n']}\n"
        f"- Open trades: {result['open_trades']}\n"
        f"- Total R: {global_metrics['totalR']}\n"
        f"- Winrate: {global_metrics['winrate']}%\n"
        f"- PF: {global_metrics['profit_factor']}\n"
        "- Reports:\n"
        "  reports/performance_intelligence_report_v2.md\n"
        "  reports/performance_intelligence_report_v2.json"
    )


def format_markdown(result: dict[str, Any]) -> str:
    global_metrics = result["global_performance"]
    rankings = result["rankings"]
    score = result["score_effectiveness"]
    expired = result["expired_analysis"]
    long_short = result["long_short_analysis"]
    lines = [
        "# Performance Intelligence Report V2",
        "",
        f"Generated at: {result['generated_at']}",
        f"Source: `{result['source']}`",
        "",
        "## 1. Executive Summary",
        "",
        f"- Closed/evaluable trades: {global_metrics['n']}",
        f"- Open trades kept separate: {result['open_trades']}",
        f"- Total R: {global_metrics['totalR']}",
        f"- Avg R: {global_metrics['avgR']}",
        f"- Winrate: {global_metrics['winrate']}%",
        f"- Profit factor: {global_metrics['profit_factor']}",
        f"- Score effectiveness: {score['conclusion']}",
        f"- Direction behavior: {long_short['conclusion']}",
        f"- Expired conclusion: {expired['conclusion']}",
        "",
        "## 2. Global Performance",
        "",
        metrics_table([{"dimension": "GLOBAL", "value": "ALL_CLOSED", **global_metrics}]),
        "",
        "### Status Distribution",
        "",
        simple_counter_table(result["status_distribution"]),
        "",
        "## 3. Best Edges",
        "",
        metrics_table(rankings["best_edges"][:15]),
        "",
        "## 4. Worst Edges",
        "",
        metrics_table(rankings["worst_edges"][:15]),
        "",
        "## 5. Expired Trades Analysis",
        "",
        f"- Expired share: {expired['expired_share']}%",
        f"- Positive expired count: {expired['positive_expired_count']}",
        f"- Positive expired Total R: {expired['positive_expired_totalR']}",
        "",
        metrics_table([{"dimension": "status", "value": "expired", **expired["metrics"]}]),
        "",
        "### Top Expired Contexts",
        "",
        metrics_table(expired["top_expired_contexts"][:10]),
        "",
        "## 6. Score Effectiveness",
        "",
        f"- Conclusion: {score['conclusion']}",
        "",
        metrics_table(score["score_buckets"]),
        "",
        "## 7. Session/Market/Direction Analysis",
        "",
        "### Direction",
        "",
        metrics_table(filter_rows(result, "single", "direction")),
        "",
        "### Session",
        "",
        metrics_table(filter_rows(result, "single", "session")),
        "",
        "### Market Regime",
        "",
        metrics_table(filter_rows(result, "single", "market_regime")),
        "",
        "### Direction + Market Regime + Entry Context",
        "",
        metrics_table(filter_rows(result, "combined", "direction + market_regime + entry_context")[:20]),
        "",
        "## 8. Symbol Analysis",
        "",
        metrics_table(filter_rows(result, "single", "symbol")[:25]),
        "",
        "## 9. Setup Type Analysis",
        "",
        metrics_table(filter_rows(result, "single", "setup_type")),
        "",
        "## 10. Actionable Decisions",
        "",
        "### Prioritize Candidates",
        "",
        metrics_table(result["actionable_decisions"]["prioritize"][:10]),
        "",
        "### Avoid Candidates",
        "",
        metrics_table(result["actionable_decisions"]["avoid"][:10]),
        "",
        "### Watchlist",
        "",
        metrics_table(result["actionable_decisions"]["watch"][:10]),
        "",
        "## 11. What NOT to change yet",
        "",
        *[f"- {item}" for item in result["what_not_to_change_yet"]],
        "",
        "## 12. Next experiments",
        "",
        *[f"- {item}" for item in result["next_experiments"]],
        "",
    ]
    return "\n".join(lines)


def metrics_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No rows._"
    header = "| Dimension | Value | n | TotalR | AvgR | WR | PF | W/L/N | Expired | TP2 | SL | Confidence | Hint |"
    sep = "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"
    body = []
    for row in rows:
        body.append(
            f"| {safe_cell(row.get('dimension'))} | {safe_cell(row.get('value'))} | {row.get('n', 0)} | "
            f"{row.get('totalR', 0)} | {row.get('avgR', 0)} | {row.get('winrate', 0)}% | "
            f"{row.get('profit_factor', 0)} | {row.get('wins', 0)}/{row.get('losses', 0)}/{row.get('neutral', 0)} | "
            f"{row.get('expired_count', 0)} | {row.get('tp2_count', 0)} | {row.get('sl_count', 0)} | "
            f"{row.get('confidence', '')} | {row.get('decision_hint', '')} |"
        )
    return "\n".join([header, sep, *body])


def simple_counter_table(counter: dict[str, int]) -> str:
    if not counter:
        return "_No rows._"
    lines = ["| Value | Count |", "|---|---:|"]
    for key, value in sorted(counter.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"| {safe_cell(key)} | {value} |")
    return "\n".join(lines)


def filter_rows(result: dict[str, Any], group_type: str, dimension: str) -> list[dict[str, Any]]:
    rows = [row for row in result["groups"][group_type] if row["dimension"] == dimension]
    return sorted(rows, key=lambda row: row["n"], reverse=True)


def score_bucket(score: float | None) -> str:
    if score is None:
        return "UNKNOWN"
    if score < 50:
        return "0-49"
    if score < 60:
        return "50-59"
    if score < 70:
        return "60-69"
    if score < 80:
        return "70-79"
    if score < 90:
        return "80-89"
    return "90-100"


def distance_bucket(value: float | None) -> str:
    if value is None:
        return "UNKNOWN"
    if value < 0.5:
        return "<0.5"
    if value < 1:
        return "0.5-1"
    if value < 2:
        return "1-2"
    if value < 3:
        return "2-3"
    if value < 5:
        return "3-5"
    return "5+"


def volume_bucket(value: float | None) -> str:
    if value is None:
        return "UNKNOWN"
    if value < 0.8:
        return "<0.8"
    if value < 1:
        return "0.8-1.0"
    if value < 1.2:
        return "1.0-1.2"
    if value < 1.5:
        return "1.2-1.5"
    if value < 2:
        return "1.5-2.0"
    return "2.0+"


def rsi_bucket(value: float | None) -> str:
    if value is None:
        return "UNKNOWN"
    if value < 30:
        return "<30"
    if value < 40:
        return "30-40"
    if value < 50:
        return "40-50"
    if value < 60:
        return "50-60"
    if value < 70:
        return "60-70"
    return "70+"


def bool_text(value: object) -> str:
    raw = text(value).lower()
    if raw in {"1", "true", "yes", "y"}:
        return "true"
    if raw in {"0", "false", "no", "n"}:
        return "false"
    return "UNKNOWN" if raw == "" else raw


def liquidity_from_reasons(row: dict[str, Any]) -> str:
    combined = " ".join(str(row.get(key) or "") for key in ("entry_reasons", "conditions_failed", "entry_or_rejection_reason"))
    if "bullish_sweep" in combined:
        return "bullish_sweep"
    if "bearish_sweep" in combined:
        return "bearish_sweep"
    return ""


def pf_sort(value: object) -> float:
    if value == "inf":
        return 999.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_hour(value: str) -> str:
    parsed = parse_datetime(value)
    return str(parsed.hour) if parsed else "UNKNOWN"


def parse_weekday(value: str) -> str:
    parsed = parse_datetime(value)
    return parsed.strftime("%A") if parsed else "UNKNOWN"


def parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def upper(value: object) -> str:
    raw = text(value)
    return raw.upper() if raw else "UNKNOWN"


def text(value: object) -> str:
    return str(value or "").strip()


def to_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_cell(value: object) -> str:
    return str(value if value is not None else "").replace("|", "/")


if __name__ == "__main__":
    raise SystemExit(main())
