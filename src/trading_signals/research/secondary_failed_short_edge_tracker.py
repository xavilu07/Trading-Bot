from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


TARGET_REASON = "secondary_setup_requirements_failed"

PROFILE_DEFINITIONS = (
    {
        "profile": "BASE",
        "description": "secondary_setup_requirements_failed + short",
        "rules": {"direction": "short", "contains": TARGET_REASON},
        "predicate": lambda row: is_secondary_failed_short(row),
    },
    {
        "profile": "PROFILE_A",
        "description": "BASE + trade_location == mid_range",
        "rules": {"trade_location": "mid_range"},
        "predicate": lambda row: is_secondary_failed_short(row) and _trade_location(row) == "mid_range",
    },
    {
        "profile": "PROFILE_B",
        "description": "BASE + session == LONDON + market_regime == RANGING",
        "rules": {"session": "LONDON", "market_regime": "RANGING"},
        "predicate": lambda row: is_secondary_failed_short(row) and _session(row) == "LONDON" and _market_regime(row) == "RANGING",
    },
    {
        "profile": "PROFILE_C",
        "description": "BASE + session == ASIA + trade_location == mid_range",
        "rules": {"session": "ASIA", "trade_location": "mid_range"},
        "predicate": lambda row: is_secondary_failed_short(row) and _session(row) == "ASIA" and _trade_location(row) == "mid_range",
    },
    {
        "profile": "PROFILE_D",
        "description": "BASE + market_regime == HIGH_VOLATILITY + trade_location == mid_range",
        "rules": {"market_regime": "HIGH_VOLATILITY", "trade_location": "mid_range"},
        "predicate": lambda row: is_secondary_failed_short(row) and _market_regime(row) == "HIGH_VOLATILITY" and _trade_location(row) == "mid_range",
    },
    {
        "profile": "PROFILE_E",
        "description": "BASE + trade_location == mid_range + entry_context == BREAKOUT",
        "rules": {"trade_location": "mid_range", "entry_context": "BREAKOUT"},
        "predicate": lambda row: is_secondary_failed_short(row) and _trade_location(row) == "mid_range" and _entry_context(row) == "BREAKOUT",
    },
)


def analyze_secondary_failed_short_edge_tracker(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    trades_path = data_path / "paper_trading" / "trades.csv"
    rows = _read_trades_csv(trades_path)
    profiles = [_profile_payload(definition, rows) for definition in PROFILE_DEFINITIONS]
    return {
        "scope": "SECONDARY_FAILED_SHORT_EDGE_TRACKER",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "trades_file": str(trades_path),
        "mode": "offline_shadow_only",
        "target_reason": TARGET_REASON,
        "profiles": profiles,
        "recommendation_summary": _recommendation_summary(profiles),
    }


def write_secondary_failed_short_edge_tracker_reports(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    markdown_path = reports_path / "secondary_failed_short_edge_tracker.md"
    json_path = reports_path / "secondary_failed_short_edge_tracker.json"
    markdown_path.write_text(format_secondary_failed_short_edge_tracker_markdown(result), encoding="utf-8")
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return {"markdown": markdown_path, "json": json_path}


def format_secondary_failed_short_edge_tracker_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# SECONDARY_FAILED_SHORT_EDGE_TRACKER",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        f"Trades file: {result.get('trades_file')}",
        "Mode: offline/shadow only",
        f"Target reason: {result.get('target_reason')}",
        f"Recommendation summary: {result.get('recommendation_summary')}",
        "",
        "## Profile Summary",
        "",
        "| Profile | Description | Trades | Closed | Wins | Losses | WR | Gross Win R | Gross Loss R | PF | Total R | Avg R | Recommendation |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    profiles = result.get("profiles", [])
    if isinstance(profiles, list) and profiles:
        for profile in profiles:
            metrics = profile.get("metrics", {}) if isinstance(profile, dict) else {}
            lines.append(
                f"| {profile.get('profile', '')} | {profile.get('description', '')} | "
                f"{metrics.get('trades', 0)} | {metrics.get('closed_trades', 0)} | {metrics.get('wins', 0)} | "
                f"{metrics.get('losses', 0)} | {metrics.get('winrate', 0)}% | {metrics.get('gross_win_r', 0)} | "
                f"{metrics.get('gross_loss_r', 0)} | {metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | "
                f"{metrics.get('avg_r', 0)} | {profile.get('recommendation', 'INSUFFICIENT_DATA')} |"
            )
    else:
        lines.append("| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | INSUFFICIENT_DATA |")
    lines.extend(["", "## Profile Rules", ""])
    for profile in profiles if isinstance(profiles, list) else []:
        lines.extend(
            [
                f"### {profile.get('profile')}",
                "",
                f"- Description: {profile.get('description')}",
                f"- Rules: {json.dumps(profile.get('rules', {}), sort_keys=True)}",
                f"- Recommendation: {profile.get('recommendation')}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def is_secondary_failed_short(row: dict[str, Any]) -> bool:
    return _direction(row) == "short" and row_contains_reason(row, TARGET_REASON)


def row_contains_reason(row: dict[str, Any], reason: str = TARGET_REASON) -> bool:
    needle = reason.strip().lower()
    return any(needle in str(value or "").lower() for value in row.values())


def recommend_profile(metrics: dict[str, Any]) -> str:
    trades = int(metrics.get("trades", 0) or 0)
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    profit_factor = _pf_float(metrics.get("profit_factor"))
    winrate = float(metrics.get("winrate", 0.0) or 0.0)
    if trades >= 20 and total_r > 0 and profit_factor >= 1.5 and winrate >= 50:
        return "PROMOTE_TO_PRIORITY"
    if trades >= 5 and total_r > 0:
        return "KEEP_SHADOW"
    if trades >= 10 and total_r <= 0:
        return "REJECT_PROFILE"
    return "INSUFFICIENT_DATA"


def _profile_payload(definition: dict[str, Any], rows: list[dict[str, str]]) -> dict[str, Any]:
    predicate = definition["predicate"]
    matched = [row for row in rows if predicate(row)]
    metrics = _metrics(matched)
    return {
        "profile": definition["profile"],
        "description": definition["description"],
        "rules": definition["rules"],
        "metrics": metrics,
        "recommendation": recommend_profile(metrics),
    }


def _recommendation_summary(profiles: list[dict[str, Any]]) -> str:
    recommendations = [str(profile.get("recommendation") or "") for profile in profiles]
    if "PROMOTE_TO_PRIORITY" in recommendations:
        return "PROMOTE_TO_PRIORITY"
    if "KEEP_SHADOW" in recommendations:
        return "KEEP_SHADOW"
    if recommendations and all(item == "REJECT_PROFILE" for item in recommendations if item):
        return "REJECT_PROFILE"
    return "INSUFFICIENT_DATA"


def _read_trades_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except csv.Error:
        return []


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [_float(row.get("result_r")) for row in rows if _is_closed(row)]
    values = [value for value in values if value is not None]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "trades": len(rows),
        "closed_trades": len(values),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": _round(len(wins) / len(values) * 100) if values else 0.0,
        "gross_win_r": _round(gross_win),
        "gross_loss_r": _round(gross_loss),
        "profit_factor": _profit_factor(gross_win, gross_loss),
        "total_r": _round(sum(values)),
        "avg_r": _round(sum(values) / len(values)) if values else 0.0,
    }


def _is_closed(row: dict[str, Any]) -> bool:
    status = str(row.get("status") or "").strip().lower()
    if status in {"tp2_hit", "tp_hit", "sl_hit", "expired", "breakeven", "closed", "win", "loss"}:
        return True
    return bool(str(row.get("closed_at") or "").strip())


def _profit_factor(gross_win: float, gross_loss: float) -> float | str:
    if gross_loss > 0:
        return _round(gross_win / gross_loss)
    if gross_win > 0:
        return "inf"
    return 0.0


def _direction(row: dict[str, Any]) -> str:
    return str(row.get("direction") or "unknown").strip().lower()


def _trade_location(row: dict[str, Any]) -> str:
    return str(row.get("trade_location") or "UNKNOWN").strip()


def _session(row: dict[str, Any]) -> str:
    return str(row.get("session") or "UNKNOWN").strip().upper()


def _market_regime(row: dict[str, Any]) -> str:
    return str(row.get("market_regime") or "UNKNOWN").strip().upper()


def _entry_context(row: dict[str, Any]) -> str:
    return str(row.get("entry_context") or "UNKNOWN").strip().upper()


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
