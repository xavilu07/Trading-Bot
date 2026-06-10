from __future__ import annotations

import itertools
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


MIN_COMBO_TRADES = 5
PROFILE_NAME = "ELITE_PROFILE_C"
PROFILE_DEFINITION = {
    "setup_type": "SECONDARY_SIGNAL",
    "score": ">=90",
    "htf_alignment": "aligned_with_htf",
}
SINGLE_FACTOR_DIMENSIONS = (
    ("direction", "Direction analysis"),
    ("session", "Session analysis"),
    ("market_regime", "Market regime analysis"),
    ("trade_location", "Trade location analysis"),
    ("entry_context", "Entry context analysis"),
    ("liquidity_sweep", "Liquidity sweep analysis"),
)
MULTI_FACTOR_FIELDS = ("direction", "session", "market_regime", "trade_location", "entry_context", "liquidity_sweep")


def analyze_elite_profile_c_dna_expansion(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    rows = [row for row in load_canonical_closed_trades(data_path) if matches_elite_profile_c(row)]
    baseline = _metrics(rows)
    factor_breakdowns = {field: _breakdown(rows, field) for field, _title in SINGLE_FACTOR_DIMENSIONS}
    combinations = _generate_multi_factor_combinations(rows)
    rankings = {
        "BEST_PF_COMBINATIONS": _rank_combinations(combinations, metric="profit_factor"),
        "BEST_TOTAL_R_COMBINATIONS": _rank_combinations(combinations, metric="total_r"),
        "BEST_WINRATE_COMBINATIONS": _rank_combinations(combinations, metric="winrate"),
    }
    final_answer = _final_answer(baseline=baseline, combinations=combinations, factor_breakdowns=factor_breakdowns)
    return {
        "scope": "ELITE_PROFILE_C_DNA_EXPANSION",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "definition": PROFILE_DEFINITION,
        "minimum_combo_trades": MIN_COMBO_TRADES,
        "baseline": baseline,
        "factor_breakdowns": factor_breakdowns,
        "multi_factor_combinations": combinations,
        "rankings": rankings,
        "final_answer": final_answer,
        "recommendation": final_answer["recommendation"],
    }


def write_elite_profile_c_dna_expansion_reports(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    markdown_path = reports_path / "elite_profile_c_dna_expansion.md"
    json_path = reports_path / "elite_profile_c_dna_expansion.json"
    markdown_path.write_text(format_elite_profile_c_dna_expansion_markdown(result), encoding="utf-8")
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return {"markdown": markdown_path, "json": json_path}


def format_elite_profile_c_dna_expansion_markdown(result: dict[str, Any]) -> str:
    final = result.get("final_answer", {}) if isinstance(result.get("final_answer"), dict) else {}
    lines = [
        "# ELITE_PROFILE_C_DNA_EXPANSION",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        f"Recommendation: {result.get('recommendation')}",
        "",
        "## Definition",
        "",
        "- setup_type = SECONDARY_SIGNAL",
        "- score >= 90",
        "- htf_alignment = aligned_with_htf",
        "",
        "## Baseline",
        "",
        *_metrics_table(result.get("baseline", {})),
        "",
        "## Single Factor Analysis",
        "",
    ]
    breakdowns = result.get("factor_breakdowns", {})
    if not isinstance(breakdowns, dict):
        breakdowns = {}
    for field, title in SINGLE_FACTOR_DIMENSIONS:
        lines.extend([f"### {title}", "", *_breakdown_table(breakdowns.get(field, []), field), ""])
    lines.extend(
        [
            "## Multi-factor Analysis",
            "",
            *_combo_table(result.get("multi_factor_combinations", []), limit=30),
            "",
            "## Rankings",
            "",
        ]
    )
    rankings = result.get("rankings", {})
    if not isinstance(rankings, dict):
        rankings = {}
    for title in ("BEST_PF_COMBINATIONS", "BEST_TOTAL_R_COMBINATIONS", "BEST_WINRATE_COMBINATIONS"):
        lines.extend([f"### {title}", "", *_combo_table(rankings.get(title, []), limit=10), ""])
    lines.extend(
        [
            "## Final Answer",
            "",
            f"- Strongest elite DNA discovered: {final.get('strongest_elite_dna', 'none')}",
            f"- Safest elite DNA: {final.get('safest_elite_dna', 'none')}",
            f"- Highest PF elite DNA: {final.get('highest_pf_elite_dna', 'none')}",
            f"- Highest TotalR elite DNA: {final.get('highest_total_r_elite_dna', 'none')}",
            f"- Recommendation: {final.get('recommendation', 'KEEP_SHADOW')}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def matches_elite_profile_c(row: dict[str, Any]) -> bool:
    return _setup_type(row) == "SECONDARY_SIGNAL" and _score_bucket(row.get("score") or row.get("setup_score")) == "90+" and _htf_alignment(row) == "aligned_with_htf"


def classify_combo(metrics: dict[str, Any]) -> str:
    trades = int(metrics.get("trades", 0) or 0)
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    pf = _pf_float(metrics.get("profit_factor"))
    winrate = float(metrics.get("winrate", 0.0) or 0.0)
    if trades < MIN_COMBO_TRADES:
        return "NOISE"
    if total_r > 0 and pf >= 2.0 and winrate >= 55:
        return "ELITE"
    if total_r > 0 and pf >= 1.4:
        return "STRONG"
    if total_r >= 0 and pf >= 1.0:
        return "NEUTRAL"
    return "NOISE"


def _breakdown(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_field_value(row, field)].append(row)
    output = []
    for value, items in grouped.items():
        metrics = _metrics(items)
        output.append(
            {
                "dimension": field,
                "value": value,
                "metrics": metrics,
                "classification": classify_combo(metrics),
            }
        )
    return sorted(output, key=lambda item: (float(item["metrics"]["total_r"]), _pf_float(item["metrics"]["profit_factor"]), int(item["metrics"]["trades"])), reverse=True)


def _generate_multi_factor_combinations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for size in (2, 3):
        for fields in itertools.combinations(MULTI_FACTOR_FIELDS, size):
            grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
            for row in rows:
                values = tuple(_field_value(row, field) for field in fields)
                if any(value == "UNKNOWN" for value in values):
                    continue
                grouped[values].append(row)
            for values, items in grouped.items():
                if len(items) < MIN_COMBO_TRADES:
                    continue
                factors = [f"{field}={value}" for field, value in zip(fields, values, strict=True)]
                metrics = _metrics(items)
                candidates.append(
                    {
                        "factors": factors,
                        "factor_count": size,
                        "metrics": metrics,
                        "classification": classify_combo(metrics),
                    }
                )
    return sorted(candidates, key=lambda item: (float(item["metrics"]["total_r"]), _pf_float(item["metrics"]["profit_factor"]), int(item["metrics"]["trades"])), reverse=True)


def _rank_combinations(combinations: list[dict[str, Any]], *, metric: str) -> list[dict[str, Any]]:
    if metric == "profit_factor":
        key = lambda item: (_pf_float(item["metrics"]["profit_factor"]), float(item["metrics"]["total_r"]), float(item["metrics"]["winrate"]), int(item["metrics"]["trades"]))
    elif metric == "winrate":
        key = lambda item: (float(item["metrics"]["winrate"]), _pf_float(item["metrics"]["profit_factor"]), float(item["metrics"]["total_r"]), int(item["metrics"]["trades"]))
    else:
        key = lambda item: (float(item["metrics"]["total_r"]), _pf_float(item["metrics"]["profit_factor"]), float(item["metrics"]["winrate"]), int(item["metrics"]["trades"]))
    return sorted(combinations, key=key, reverse=True)[:10]


def _final_answer(*, baseline: dict[str, Any], combinations: list[dict[str, Any]], factor_breakdowns: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    elite_or_strong = [item for item in combinations if item.get("classification") in {"ELITE", "STRONG"}]
    best_pf = _first(_rank_combinations(elite_or_strong or combinations, metric="profit_factor"))
    best_total_r = _first(_rank_combinations(elite_or_strong or combinations, metric="total_r"))
    safest = _safest_combo(elite_or_strong or combinations)
    strongest = _strongest_combo(elite_or_strong or combinations)
    if strongest and strongest.get("classification") == "ELITE":
        recommendation = "BUILD_ELITE_SUBPROFILE_SHADOW"
    elif strongest and strongest.get("classification") == "STRONG":
        recommendation = "KEEP_SHADOW_AND_MONITOR"
    elif int(baseline.get("trades", 0) or 0) >= MIN_COMBO_TRADES and _pf_float(baseline.get("profit_factor")) > 1:
        recommendation = "KEEP_PROFILE_C_BASELINE"
    else:
        recommendation = "NEED_MORE_DATA"
    return {
        "strongest_elite_dna": _describe_combo(strongest),
        "safest_elite_dna": _describe_combo(safest),
        "highest_pf_elite_dna": _describe_combo(best_pf),
        "highest_total_r_elite_dna": _describe_combo(best_total_r),
        "recommendation": recommendation,
        "best_direction": _best_factor(factor_breakdowns, "direction"),
        "best_session": _best_factor(factor_breakdowns, "session"),
        "best_market_regime": _best_factor(factor_breakdowns, "market_regime"),
        "best_trade_location": _best_factor(factor_breakdowns, "trade_location"),
    }


def _safest_combo(combinations: list[dict[str, Any]]) -> dict[str, Any] | None:
    return _first(
        sorted(
            combinations,
            key=lambda item: (
                item.get("classification") == "ELITE",
                int(item["metrics"]["trades"]),
                _pf_float(item["metrics"]["profit_factor"]),
                float(item["metrics"]["total_r"]),
            ),
            reverse=True,
        )
    )


def _strongest_combo(combinations: list[dict[str, Any]]) -> dict[str, Any] | None:
    return _first(
        sorted(
            combinations,
            key=lambda item: (
                item.get("classification") == "ELITE",
                item.get("classification") == "STRONG",
                float(item["metrics"]["total_r"]),
                _pf_float(item["metrics"]["profit_factor"]),
                int(item["metrics"]["trades"]),
            ),
            reverse=True,
        )
    )


def _best_factor(factor_breakdowns: dict[str, list[dict[str, Any]]], field: str) -> str:
    items = factor_breakdowns.get(field, [])
    if not items:
        return "none"
    return _describe_factor(max(items, key=lambda item: (float(item["metrics"]["total_r"]), _pf_float(item["metrics"]["profit_factor"]))))


def _describe_factor(item: dict[str, Any] | None) -> str:
    if not item:
        return "none"
    return f"{item.get('dimension')}={item.get('value')} ({_metrics_inline(item.get('metrics', {}))}, class={item.get('classification')})"


def _describe_combo(item: dict[str, Any] | None) -> str:
    if not item:
        return "none"
    return f"{' + '.join(item.get('factors', []))} ({_metrics_inline(item.get('metrics', {}))}, class={item.get('classification')})"


def _field_value(row: dict[str, Any], field: str) -> str:
    if field == "direction":
        return str(row.get("direction") or "UNKNOWN").strip().lower()
    if field == "liquidity_sweep":
        return _liquidity_sweep(row)
    value = str(row.get(field) or "UNKNOWN").strip()
    if field in {"session", "market_regime", "entry_context", "setup_type"}:
        return value.upper() if value else "UNKNOWN"
    return value if value else "UNKNOWN"


def _setup_type(row: dict[str, Any]) -> str:
    return str(row.get("setup_type") or "UNKNOWN").strip().upper()


def _liquidity_sweep(row: dict[str, Any]) -> str:
    sweep = str(row.get("liquidity_sweep") or "").strip()
    if sweep:
        return sweep
    context = str(row.get("liquidity_context") or "").strip().lower()
    if context.startswith("sweep:"):
        return context.split(":", 1)[1]
    return "none"


def _htf_alignment(row: dict[str, Any]) -> str:
    explicit = str(row.get("htf_alignment") or "").strip().lower()
    if explicit:
        return explicit
    direction = str(row.get("direction") or "unknown").strip().lower()
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


def _first(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    return items[0] if items else None


def _metrics_inline(metrics: object) -> str:
    payload = metrics if isinstance(metrics, dict) else {}
    return (
        f"trades={payload.get('trades', 0)}, WR={payload.get('winrate', 0)}%, "
        f"PF={payload.get('profit_factor', 0)}, TotalR={payload.get('total_r', 0)}, AvgR={payload.get('avg_r', 0)}"
    )


def _metrics_table(metrics: object) -> list[str]:
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


def _breakdown_table(rows: object, field: str) -> list[str]:
    lines = [f"| {field} | Trades | WR | PF | Total R | Avg R | Class |", "|---|---:|---:|---:|---:|---:|---|"]
    if not isinstance(rows, list) or not rows:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | NOISE |")
        return lines
    for row in rows:
        metrics = row.get("metrics", {}) if isinstance(row, dict) else {}
        lines.append(
            f"| {row.get('value', 'UNKNOWN')} | {metrics.get('trades', 0)} | {metrics.get('winrate', 0)}% | "
            f"{metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} | "
            f"{row.get('classification', 'NOISE')} |"
        )
    return lines


def _combo_table(rows: object, *, limit: int) -> list[str]:
    lines = ["| Factors | Trades | WR | PF | Total R | Avg R | Class |", "|---|---:|---:|---:|---:|---:|---|"]
    if not isinstance(rows, list) or not rows:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | NOISE |")
        return lines
    for row in rows[:limit]:
        metrics = row.get("metrics", {}) if isinstance(row, dict) else {}
        lines.append(
            f"| {' + '.join(row.get('factors', []))} | {metrics.get('trades', 0)} | {metrics.get('winrate', 0)}% | "
            f"{metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} | "
            f"{row.get('classification', 'NOISE')} |"
        )
    return lines
