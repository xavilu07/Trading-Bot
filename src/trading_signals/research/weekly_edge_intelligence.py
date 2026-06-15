from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades
from trading_signals.research.elite_profile_c_shadow_tracker import matches_elite_profile_c, recommend_elite_profile_c
from trading_signals.research.elite_subprofile_shadow_tracker import matches_profile_g, matches_profile_h, recommend_subprofile
from trading_signals.research.secondary_failed_short_edge_tracker import is_secondary_failed_short, recommend_profile


def generate_weekly_edge_intelligence(*, data_path: Path, reports_path: Path, now: datetime | None = None) -> dict[str, Any]:
    result = analyze_weekly_edge_intelligence(data_path=data_path, now=now)
    paths = write_weekly_edge_intelligence_reports(result, reports_path)
    return {**result, "markdown_path": str(paths["markdown"]), "json_path": str(paths["json"])}


def analyze_weekly_edge_intelligence(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    since = now_dt - timedelta(days=7)
    canonical_rows = load_canonical_closed_trades(data_path)
    paper_rows = _read_paper_trades(data_path / "paper_trading" / "trades.csv")

    profiles = [
        _profile_payload(
            name="Elite Profile C",
            source="canonical_closed_trades",
            rows=[row for row in canonical_rows if matches_elite_profile_c(row)],
            since=since,
            recommendation_fn=recommend_elite_profile_c,
        ),
        _profile_payload(
            name="Profile G",
            source="canonical_closed_trades",
            rows=[row for row in canonical_rows if matches_profile_g(row)],
            since=since,
            recommendation_fn=recommend_subprofile,
        ),
        _profile_payload(
            name="Profile H",
            source="canonical_closed_trades",
            rows=[row for row in canonical_rows if matches_profile_h(row)],
            since=since,
            recommendation_fn=recommend_subprofile,
        ),
        _profile_payload(
            name="Secondary Failed Profile A",
            source="paper_trading_trades_csv",
            rows=[row for row in paper_rows if _matches_secondary_profile_a(row)],
            since=since,
            recommendation_fn=recommend_profile,
        ),
        _profile_payload(
            name="Secondary Failed Profile E",
            source="paper_trading_trades_csv",
            rows=[row for row in paper_rows if _matches_secondary_profile_e(row)],
            since=since,
            recommendation_fn=recommend_profile,
        ),
    ]
    summary = _summary(profiles)
    return {
        "scope": "WEEKLY_EDGE_INTELLIGENCE",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "lookback_days": 7,
        "lookback_since": since.isoformat(timespec="seconds"),
        "profiles": profiles,
        "summary": summary,
    }


def write_weekly_edge_intelligence_reports(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    markdown_path = reports_path / "weekly_edge_intelligence.md"
    json_path = reports_path / "weekly_edge_intelligence.json"
    markdown_path.write_text(format_weekly_edge_intelligence_markdown(result), encoding="utf-8")
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return {"markdown": markdown_path, "json": json_path}


def format_weekly_edge_intelligence_markdown(result: dict[str, Any]) -> str:
    summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
    lines = [
        "# Weekly Edge Intelligence",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        f"Lookback: last {result.get('lookback_days', 7)} days since {result.get('lookback_since')}",
        "",
        "## Profiles",
        "",
        "| Profile | Source | Trades | Closed | WR | PF | Total R | Avg R | New 7d | Recommendation |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    profiles = result.get("profiles", [])
    if isinstance(profiles, list) and profiles:
        for profile in profiles:
            metrics = profile.get("metrics", {}) if isinstance(profile, dict) else {}
            lines.append(
                f"| {profile.get('profile', '')} | {profile.get('source', '')} | "
                f"{metrics.get('trades', 0)} | {metrics.get('closed_trades', 0)} | {metrics.get('winrate', 0)}% | "
                f"{metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} | "
                f"{profile.get('new_trades_last_7d', 0)} | {profile.get('recommendation', 'INSUFFICIENT_DATA')} |"
            )
    else:
        lines.append("| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | INSUFFICIENT_DATA |")

    lines.extend(
        [
            "",
            "## Final Summary",
            "",
            f"- PROMOTE_TO_PRIORITY: {', '.join(summary.get('PROMOTE_TO_PRIORITY', [])) or 'none'}",
            f"- KEEP_SHADOW: {', '.join(summary.get('KEEP_SHADOW', [])) or 'none'}",
            f"- REJECT_PROFILE: {', '.join(summary.get('REJECT_PROFILE', [])) or 'none'}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _profile_payload(
    *,
    name: str,
    source: str,
    rows: list[dict[str, Any]],
    since: datetime,
    recommendation_fn,
) -> dict[str, Any]:
    metrics = _metrics(rows)
    return {
        "profile": name,
        "source": source,
        "metrics": metrics,
        "new_trades_last_7d": len([row for row in rows if _row_datetime(row) is not None and _row_datetime(row) >= since]),
        "recommendation": recommendation_fn(metrics),
    }


def _summary(profiles: list[dict[str, Any]]) -> dict[str, list[str]]:
    output = {"PROMOTE_TO_PRIORITY": [], "KEEP_SHADOW": [], "REJECT_PROFILE": []}
    for profile in profiles:
        recommendation = str(profile.get("recommendation") or "")
        if recommendation in output:
            output[recommendation].append(str(profile.get("profile") or "UNKNOWN"))
    return output


def _matches_secondary_profile_a(row: dict[str, Any]) -> bool:
    return is_secondary_failed_short(row) and _trade_location(row) == "mid_range"


def _matches_secondary_profile_e(row: dict[str, Any]) -> bool:
    return _matches_secondary_profile_a(row) and _entry_context(row) == "BREAKOUT"


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
        "profit_factor": _profit_factor(gross_win, gross_loss),
        "total_r": _round(sum(values)),
        "avg_r": _round(sum(values) / len(values)) if values else 0.0,
    }


def _read_paper_trades(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except csv.Error:
        return []


def _is_closed(row: dict[str, Any]) -> bool:
    status = str(row.get("status") or "").strip().lower()
    if status in {"tp2_hit", "tp_hit", "sl_hit", "expired", "breakeven", "closed", "win", "loss"}:
        return True
    return bool(str(row.get("closed_at") or "").strip())


def _row_datetime(row: dict[str, Any]) -> datetime | None:
    for key in ("opened_at", "created_at", "timestamp", "closed_at", "updated_at"):
        value = str(row.get(key) or "").strip()
        if not value:
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        return _aware(parsed)
    return None


def _trade_location(row: dict[str, Any]) -> str:
    return str(row.get("trade_location") or "UNKNOWN").strip()


def _entry_context(row: dict[str, Any]) -> str:
    return str(row.get("entry_context") or "UNKNOWN").strip().upper()


def _profit_factor(gross_win: float, gross_loss: float) -> float | str:
    if gross_loss > 0:
        return _round(gross_win / gross_loss)
    if gross_win > 0:
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


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
