from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


MIN_ENOUGH_TRADES = 10


PROFILE_RULES: tuple[tuple[str, tuple[str, ...], Callable[[dict[str, Any]], bool]], ...] = (
    ("PROFILE_A", ("score_bucket=90+",), lambda row: _score_bucket(row.get("score")) == "90+"),
    ("PROFILE_B", ("score_bucket=90+", "htf_alignment=aligned_with_htf"), lambda row: _score_bucket(row.get("score")) == "90+" and _htf_alignment(row) == "aligned_with_htf"),
    (
        "PROFILE_C",
        ("score_bucket=90+", "htf_alignment=aligned_with_htf", "setup_type=SECONDARY_SIGNAL"),
        lambda row: _score_bucket(row.get("score")) == "90+" and _htf_alignment(row) == "aligned_with_htf" and _setup_type(row) == "SECONDARY_SIGNAL",
    ),
    (
        "PROFILE_D",
        ("score_bucket=90+", "htf_alignment=aligned_with_htf", "setup_type=SECONDARY_SIGNAL", "liquidity_sweep=bearish_sweep"),
        lambda row: (
            _score_bucket(row.get("score")) == "90+"
            and _htf_alignment(row) == "aligned_with_htf"
            and _setup_type(row) == "SECONDARY_SIGNAL"
            and _liquidity_sweep(row) == "bearish_sweep"
        ),
    ),
    (
        "PROFILE_E",
        ("score_bucket=90+", "htf_alignment=aligned_with_htf", "setup_type=SECONDARY_SIGNAL", "liquidity_sweep=bearish_sweep", "session=LONDON"),
        lambda row: (
            _score_bucket(row.get("score")) == "90+"
            and _htf_alignment(row) == "aligned_with_htf"
            and _setup_type(row) == "SECONDARY_SIGNAL"
            and _liquidity_sweep(row) == "bearish_sweep"
            and _session(row) == "LONDON"
        ),
    ),
    (
        "PROFILE_F",
        (
            "score_bucket=90+",
            "htf_alignment=aligned_with_htf",
            "setup_type=SECONDARY_SIGNAL",
            "liquidity_sweep=bearish_sweep",
            "market_regime=HIGH_VOLATILITY",
        ),
        lambda row: (
            _score_bucket(row.get("score")) == "90+"
            and _htf_alignment(row) == "aligned_with_htf"
            and _setup_type(row) == "SECONDARY_SIGNAL"
            and _liquidity_sweep(row) == "bearish_sweep"
            and _market_regime(row) == "HIGH_VOLATILITY"
        ),
    ),
)


def analyze_elite_shadow_mode_simulation(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    all_trades = load_canonical_closed_trades(data_path)
    baseline_rows = [row for row in all_trades if not _is_existing_production_block_context(row)]
    baseline = _metrics(baseline_rows)
    profiles = [_profile_payload(name, factors, predicate, baseline_rows, baseline) for name, factors, predicate in PROFILE_RULES]
    answers = _answers(baseline=baseline, profiles=profiles)
    return {
        "scope": "ELITE_SHADOW_MODE_SIMULATION",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "method": "Simulate PROFILE_A-F over canonical closed trades after excluding bullish_sweep and against_htf+BREAKOUT production blocks.",
        "excluded_production_blocks": ["bullish_sweep", "against_htf+BREAKOUT"],
        "baseline_after_production_blocks": baseline,
        "excluded_metrics": _metrics([row for row in all_trades if _is_existing_production_block_context(row)]),
        "profiles": profiles,
        "answers": answers,
        "recommended_action": answers["recommended_action"],
    }


def write_elite_shadow_mode_simulation_reports(result: dict[str, Any], reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    markdown_path = reports_path / "elite_shadow_mode_simulation.md"
    json_path = reports_path / "elite_shadow_mode_simulation.json"
    markdown_path.write_text(format_elite_shadow_mode_simulation_markdown(result), encoding="utf-8")
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return {"markdown": markdown_path, "json": json_path}


def format_elite_shadow_mode_simulation_markdown(result: dict[str, Any]) -> str:
    answers = result.get("answers", {})
    lines = [
        "# ELITE_SHADOW_MODE_SIMULATION",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        f"Method: {result.get('method')}",
        f"Recommended action: {result.get('recommended_action')}",
        "",
        "## Executive Summary",
        "",
        f"- Baseline after production blocks: {_metrics_inline(result.get('baseline_after_production_blocks', {}))}",
        f"- Excluded production blocks: {_metrics_inline(result.get('excluded_metrics', {}))}",
        f"- Max PF profile: {answers.get('max_pf_profile', 'none')}",
        f"- Max TotalR profile: {answers.get('max_total_r_profile', 'none')}",
        f"- Best PF with enough trades: {answers.get('best_pf_enough_trades_profile', 'none')}",
        f"- Worth shadow testing? {answers.get('worth_shadow_testing', 'UNKNOWN')}",
        f"- Production-only elite impact: {answers.get('production_only_elite_impact', 'UNKNOWN')}",
        "",
        "## Baseline",
        "",
        *_single_metrics_table(result.get("baseline_after_production_blocks", {})),
        "",
        "## Profile Simulation",
        "",
        *_profile_table(result.get("profiles", [])),
        "",
        "## Answers",
        "",
    ]
    for question, answer in answers.items():
        if question == "recommended_action":
            continue
        lines.append(f"- {question}: {answer}")
    lines.extend(["", "## Recommended Action", "", str(result.get("recommended_action", "KEEP_BASELINE"))])
    return "\n".join(lines).rstrip() + "\n"


def classify_elite_profile(metrics: dict[str, Any]) -> str:
    trades = int(metrics.get("trades", 0) or 0)
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    pf = _pf_float(metrics.get("profit_factor"))
    if trades < MIN_ENOUGH_TRADES or total_r <= 0 or pf <= 1:
        return "NO_EDGE"
    if pf > 1.8:
        return "ELITE"
    if pf > 1.4:
        return "STRONG"
    if pf > 1.2:
        return "PROMISING"
    return "NO_EDGE"


def _profile_payload(
    name: str,
    factors: tuple[str, ...],
    predicate: Callable[[dict[str, Any]], bool],
    baseline_rows: list[dict[str, Any]],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    rows = [row for row in baseline_rows if predicate(row)]
    metrics = _metrics(rows)
    baseline_trades = int(baseline.get("trades", 0) or 0)
    baseline_pf = _pf_float(baseline.get("profit_factor"))
    baseline_total_r = float(baseline.get("total_r", 0.0) or 0.0)
    return {
        "profile": name,
        "factors": list(factors),
        "metrics": metrics,
        "classification": classify_elite_profile(metrics),
        "trade_reduction_pct": _round((1 - (int(metrics["trades"]) / baseline_trades)) * 100) if baseline_trades else 0.0,
        "pf_improvement_pct": _pct_improvement(_pf_float(metrics["profit_factor"]), baseline_pf),
        "r_improvement_pct": _pct_improvement(float(metrics["total_r"]), baseline_total_r),
        "pf_delta": _round(_pf_float(metrics["profit_factor"]) - baseline_pf),
        "r_delta": _round(float(metrics["total_r"]) - baseline_total_r),
    }


def _answers(*, baseline: dict[str, Any], profiles: list[dict[str, Any]]) -> dict[str, str]:
    max_pf = _best_profile(profiles, key="profit_factor")
    max_total_r = _best_profile(profiles, key="total_r")
    enough = [row for row in profiles if int(row.get("metrics", {}).get("trades", 0) or 0) >= MIN_ENOUGH_TRADES]
    best_enough = _best_profile(enough, key="profit_factor")
    worth_shadow = best_enough is not None and best_enough.get("classification") in {"PROMISING", "STRONG", "ELITE"}
    if best_enough and best_enough.get("classification") == "ELITE" and float(best_enough.get("r_delta", 0.0) or 0.0) >= 0:
        action = "ELITE_MODE_READY"
    elif best_enough and best_enough.get("classification") in {"ELITE", "STRONG"}:
        action = f"SHADOW_TEST_{best_enough['profile']}"
    elif worth_shadow:
        action = f"SHADOW_TEST_{best_enough['profile']}"
    elif max_pf and max_pf.get("classification") in {"ELITE", "STRONG"}:
        action = "BUILD_ELITE_FILTER"
    else:
        action = "KEEP_BASELINE"
    return {
        "max_pf_profile": _describe_profile(max_pf),
        "max_total_r_profile": _describe_profile(max_total_r),
        "best_pf_enough_trades_profile": _describe_profile(best_enough),
        "worth_shadow_testing": "YES" if worth_shadow else "NO",
        "production_only_elite_impact": _production_impact_text(baseline, best_enough),
        "recommended_action": action,
    }


def _best_profile(profiles: list[dict[str, Any]], *, key: str) -> dict[str, Any] | None:
    profiles = [row for row in profiles if int(row.get("metrics", {}).get("trades", 0) or 0) > 0]
    if not profiles:
        return None
    if key == "profit_factor":
        return max(
            profiles,
            key=lambda row: (
                _pf_float(row.get("metrics", {}).get("profit_factor")),
                float(row.get("metrics", {}).get("total_r", 0.0)),
                len(row.get("factors", [])),
                -int(row.get("metrics", {}).get("trades", 0) or 0),
            ),
        )
    if key == "total_r":
        return max(profiles, key=lambda row: (float(row.get("metrics", {}).get("total_r", 0.0)), _pf_float(row.get("metrics", {}).get("profit_factor")), int(row.get("metrics", {}).get("trades", 0) or 0)))
    return None


def _production_impact_text(baseline: dict[str, Any], profile: dict[str, Any] | None) -> str:
    if not profile:
        return "No profile has enough trades."
    metrics = profile.get("metrics", {})
    return (
        f"Only {profile.get('profile')} would keep {metrics.get('trades', 0)} of {baseline.get('trades', 0)} trades, "
        f"PF {metrics.get('profit_factor', 0)} vs baseline {baseline.get('profit_factor', 0)}, "
        f"TotalR {metrics.get('total_r', 0)} vs baseline {baseline.get('total_r', 0)}."
    )


def _describe_profile(profile: dict[str, Any] | None) -> str:
    if not profile:
        return "none"
    return (
        f"{profile.get('profile')} ({_metrics_inline(profile.get('metrics', {}))}, "
        f"class={profile.get('classification')}, trade_reduction={profile.get('trade_reduction_pct')}%, "
        f"PF improvement={profile.get('pf_improvement_pct')}%, R improvement={profile.get('r_improvement_pct')}%)"
    )


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
    return "UNKNOWN"


def _htf_alignment(row: dict[str, Any]) -> str:
    explicit = str(row.get("htf_alignment") or "").strip().lower()
    if explicit:
        return explicit
    direction = str(row.get("direction") or "unknown").strip().lower()
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


def _pct_improvement(value: float, baseline: float) -> float:
    if baseline == 0:
        return 0.0
    return _round((value - baseline) / abs(baseline) * 100)


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


def _profile_table(rows: object) -> list[str]:
    lines = [
        "| Profile | Factors | Trades | WR | PF | Total R | Avg R | Reduction | PF Improvement | R Improvement | Class |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    if not isinstance(rows, list) or not rows:
        lines.append("| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NO_EDGE |")
        return lines
    for row in rows:
        metrics = row.get("metrics", {}) if isinstance(row, dict) else {}
        lines.append(
            f"| {row.get('profile', '')} | {', '.join(row.get('factors', []))} | {metrics.get('trades', 0)} | "
            f"{metrics.get('winrate', 0)}% | {metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | "
            f"{metrics.get('avg_r', 0)} | {row.get('trade_reduction_pct', 0)}% | "
            f"{row.get('pf_improvement_pct', 0)}% | {row.get('r_improvement_pct', 0)}% | {row.get('classification', 'NO_EDGE')} |"
        )
    return lines
