from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


PROFILE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "profile": "PROFILE_G",
        "description": "Elite C + long + OVERLAP + near_resistance",
        "rules": {
            "setup_type": "SECONDARY_SIGNAL",
            "score": ">=90",
            "htf_alignment": "aligned_with_htf",
            "direction": "long",
            "session": "OVERLAP",
            "trade_location": "near_resistance",
        },
        "predicate": lambda row: (
            matches_elite_profile_c(row)
            and _direction(row) == "long"
            and _session(row) == "OVERLAP"
            and _trade_location(row) == "near_resistance"
        ),
    },
    {
        "profile": "PROFILE_H",
        "description": "Elite C + long + HIGH_VOLATILITY",
        "rules": {
            "setup_type": "SECONDARY_SIGNAL",
            "score": ">=90",
            "htf_alignment": "aligned_with_htf",
            "direction": "long",
            "market_regime": "HIGH_VOLATILITY",
        },
        "predicate": lambda row: (
            matches_elite_profile_c(row)
            and _direction(row) == "long"
            and _market_regime(row) == "HIGH_VOLATILITY"
        ),
    },
)


def analyze_elite_subprofile_shadow_tracker(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    all_rows = load_canonical_closed_trades(data_path)
    elite_c_rows = [row for row in all_rows if matches_elite_profile_c(row)]
    elite_c_baseline = _metrics(elite_c_rows)
    profiles = [
        _profile_payload(
            definition=definition,
            elite_c_baseline=elite_c_baseline,
            elite_c_rows=elite_c_rows,
        )
        for definition in PROFILE_DEFINITIONS
    ]
    return {
        "scope": "ELITE_SUBPROFILE_SHADOW_TRACKER",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "mode": "offline_shadow_only",
        "elite_profile_c_baseline": elite_c_baseline,
        "profiles": profiles,
        "recommendation_summary": _recommendation_summary(profiles),
    }


def write_elite_subprofile_shadow_tracker_reports(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    markdown_path = reports_path / "elite_subprofile_shadow_tracker.md"
    json_path = reports_path / "elite_subprofile_shadow_tracker.json"
    markdown_path.write_text(format_elite_subprofile_shadow_tracker_markdown(result), encoding="utf-8")
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return {"markdown": markdown_path, "json": json_path}


def format_elite_subprofile_shadow_tracker_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# ELITE_SUBPROFILE_SHADOW_TRACKER",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        "Mode: offline/shadow only",
        f"Recommendation summary: {result.get('recommendation_summary')}",
        "",
        "## Elite Profile C Baseline",
        "",
        *_metrics_table(result.get("elite_profile_c_baseline", {})),
        "",
        "## Profile Comparison",
        "",
        "| Profile | Tracked | Closed | WR | PF | Total R | Avg R | PF delta | WR delta | TotalR delta | Recommendation |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    profiles = result.get("profiles", [])
    if isinstance(profiles, list) and profiles:
        for profile in profiles:
            metrics = profile.get("metrics", {}) if isinstance(profile, dict) else {}
            deltas = profile.get("deltas_vs_elite_c", {}) if isinstance(profile, dict) else {}
            lines.append(
                f"| {profile.get('profile', '')} | {profile.get('tracked', 0)} | {profile.get('closed', 0)} | "
                f"{metrics.get('winrate', 0)}% | {metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | "
                f"{metrics.get('avg_r', 0)} | {deltas.get('pf_delta', 0)} | {deltas.get('wr_delta', 0)} | "
                f"{deltas.get('total_r_delta', 0)} | {profile.get('recommendation', 'KEEP_SHADOW')} |"
            )
    else:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | KEEP_SHADOW |")
    for profile in profiles if isinstance(profiles, list) else []:
        lines.extend(
            [
                "",
                f"## {profile.get('profile')}",
                "",
                f"Description: {profile.get('description')}",
                f"Rules: {json.dumps(profile.get('rules', {}), sort_keys=True)}",
                f"Recommendation: {profile.get('recommendation')}",
                "",
                "### By Symbol",
                "",
                *_group_table(profile.get("by_symbol", {}), "Symbol"),
                "",
                "### By Session",
                "",
                *_group_table(profile.get("by_session", {}), "Session"),
                "",
                "### By Regime",
                "",
                *_group_table(profile.get("by_regime", {}), "Regime"),
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def matches_elite_profile_c(row: dict[str, Any]) -> bool:
    return _setup_type(row) == "SECONDARY_SIGNAL" and _score_bucket(row.get("score") or row.get("setup_score")) == "90+" and _htf_alignment(row) == "aligned_with_htf"


def matches_profile_g(row: dict[str, Any]) -> bool:
    return bool(PROFILE_DEFINITIONS[0]["predicate"](row))


def matches_profile_h(row: dict[str, Any]) -> bool:
    return bool(PROFILE_DEFINITIONS[1]["predicate"](row))


def recommend_subprofile(metrics: dict[str, Any]) -> str:
    closed = int(metrics.get("trades", 0) or 0)
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    pf = _pf_float(metrics.get("profit_factor"))
    winrate = float(metrics.get("winrate", 0.0) or 0.0)
    if closed >= 20 and pf >= 2.0 and winrate >= 55 and total_r > 0:
        return "PROMOTE_TO_PRIORITY"
    if closed >= 10 and (pf < 1.0 or total_r <= 0):
        return "REJECT_PROFILE"
    return "KEEP_SHADOW"


def _profile_payload(
    *,
    definition: dict[str, Any],
    elite_c_baseline: dict[str, Any],
    elite_c_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    predicate = definition["predicate"]
    rows = [row for row in elite_c_rows if isinstance(predicate, Callable) and predicate(row)]
    metrics = _metrics(rows)
    return {
        "profile": definition["profile"],
        "description": definition["description"],
        "rules": definition["rules"],
        "tracked": len(rows),
        "closed": int(metrics.get("trades", 0) or 0),
        "metrics": metrics,
        "deltas_vs_elite_c": {
            "pf_delta": _round(_pf_float(metrics.get("profit_factor")) - _pf_float(elite_c_baseline.get("profit_factor"))),
            "wr_delta": _round(float(metrics.get("winrate", 0.0) or 0.0) - float(elite_c_baseline.get("winrate", 0.0) or 0.0)),
            "total_r_delta": _round(float(metrics.get("total_r", 0.0) or 0.0) - float(elite_c_baseline.get("total_r", 0.0) or 0.0)),
        },
        "by_symbol": _group_summary(rows, "symbol"),
        "by_session": _group_summary(rows, "session"),
        "by_regime": _group_summary(rows, "market_regime"),
        "recommendation": recommend_subprofile(metrics),
    }


def _recommendation_summary(profiles: list[dict[str, Any]]) -> str:
    if any(profile.get("recommendation") == "PROMOTE_TO_PRIORITY" for profile in profiles):
        return "PROMOTE_TO_PRIORITY"
    if any(profile.get("recommendation") == "KEEP_SHADOW" for profile in profiles):
        return "KEEP_SHADOW"
    return "REJECT_PROFILE"


def _group_summary(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_field(row, field)].append(row)
    return {
        key: {
            "tracked": len(items),
            "closed": len(items),
            "metrics": _metrics(items),
        }
        for key, items in sorted(grouped.items())
    }


def _field(row: dict[str, Any], field: str) -> str:
    if field == "direction":
        return _direction(row)
    if field == "session":
        return _session(row)
    if field == "market_regime":
        return _market_regime(row)
    if field == "trade_location":
        return _trade_location(row)
    return str(row.get(field) or "UNKNOWN").strip() or "UNKNOWN"


def _setup_type(row: dict[str, Any]) -> str:
    return str(row.get("setup_type") or "UNKNOWN").strip().upper()


def _direction(row: dict[str, Any]) -> str:
    return str(row.get("direction") or "unknown").strip().lower()


def _session(row: dict[str, Any]) -> str:
    return str(row.get("session") or "UNKNOWN").strip().upper()


def _market_regime(row: dict[str, Any]) -> str:
    return str(row.get("market_regime") or "UNKNOWN").strip().upper()


def _trade_location(row: dict[str, Any]) -> str:
    return str(row.get("trade_location") or "UNKNOWN").strip() or "UNKNOWN"


def _htf_alignment(row: dict[str, Any]) -> str:
    explicit = str(row.get("htf_alignment") or "").strip().lower()
    if explicit:
        return explicit
    direction = _direction(row)
    higher = str(row.get("trend_higher") or row.get("trend_4h") or row.get("trend_higher_timeframe") or "").strip().lower()
    if direction == "long" and higher == "bullish":
        return "aligned_with_htf"
    if direction == "short" and higher == "bearish":
        return "aligned_with_htf"
    if direction == "long" and higher == "bearish":
        return "against_htf"
    if direction == "short" and higher == "bullish":
        return "against_htf"
    return f"htf_{higher}" if higher else "UNKNOWN"


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


def _group_table(payload: object, label: str) -> list[str]:
    lines = [f"| {label} | Tracked | Closed | WR | PF | Total R | Avg R |", "|---|---:|---:|---:|---:|---:|---:|"]
    if not isinstance(payload, dict) or not payload:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 |")
        return lines
    ranked = sorted(payload.items(), key=lambda item: (float(item[1].get("metrics", {}).get("total_r", 0.0)), int(item[1].get("tracked", 0))), reverse=True)
    for key, value in ranked:
        metrics = value.get("metrics", {}) if isinstance(value, dict) else {}
        lines.append(
            f"| {key} | {value.get('tracked', 0)} | {value.get('closed', 0)} | {metrics.get('winrate', 0)}% | "
            f"{metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} |"
        )
    return lines
