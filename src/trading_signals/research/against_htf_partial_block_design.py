from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


TARGET_REASON = "against_htf"
MIN_DEPLOY_TRADES = 20
MIN_SHADOW_TRADES = 5


CandidatePredicate = Callable[[dict[str, Any]], bool]


def analyze_against_htf_partial_block_design(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    all_trades = load_canonical_closed_trades(data_path)
    baseline = [row for row in all_trades if not _is_bullish_sweep(row)]
    against_htf_rows = [row for row in baseline if _is_against_htf(row)]
    before_metrics = _metrics(against_htf_rows)
    candidates = [_evaluate_candidate(against_htf_rows, candidate) for candidate in _candidate_filters()]
    ranking = _rank_candidates(candidates)
    answers = _answers(ranking)
    return {
        "scope": "AGAINST_HTF_PARTIAL_BLOCK_DESIGN",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "method": "Exclude bullish_sweep, isolate against_htf, then simulate candidate partial blocks.",
        "baseline_metrics": before_metrics,
        "candidate_results": candidates,
        "filter_ranking": ranking,
        "answers": answers,
        "recommended_next_action": answers["recommended_next_action"],
    }


def write_against_htf_partial_block_design_report(result: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "against_htf_partial_block_design.md"
    path.write_text(format_against_htf_partial_block_design_markdown(result), encoding="utf-8")
    return path


def format_against_htf_partial_block_design_markdown(result: dict[str, Any]) -> str:
    answers = result.get("answers", {})
    lines = [
        "# AGAINST_HTF_PARTIAL_BLOCK_DESIGN",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        f"Method: {result.get('method')}",
        "",
        "## Executive Summary",
        "",
        f"- Baseline against_htf: {_metrics_inline(result.get('baseline_metrics', {}))}",
        f"- Best candidate: {answers.get('best_candidate', '')}",
        f"- Safest candidate: {answers.get('safest_candidate', '')}",
        f"- Highest PF improvement: {answers.get('highest_pf_improvement', '')}",
        f"- Lowest collateral damage: {answers.get('lowest_collateral_damage', '')}",
        f"- Recommended shadow filter: {answers.get('recommended_shadow_filter', '')}",
        "",
        "## Filter Ranking",
        "",
        *_candidate_table(result.get("filter_ranking", [])),
        "",
        "## Candidate Details",
        "",
        *_candidate_table(result.get("candidate_results", [])),
        "",
        "## Recommended Next Action",
        "",
        result.get("recommended_next_action", "continue monitoring"),
    ]
    return "\n".join(lines).rstrip() + "\n"


def classify_candidate(result: dict[str, Any]) -> str:
    trades_removed = int(result.get("trades_removed", 0) or 0)
    r_improvement = float(result.get("r_improvement", 0.0) or 0.0)
    pf_improvement = float(result.get("pf_improvement", 0.0) or 0.0)
    profitable_lost = int(result.get("profitable_trades_lost", 0) or 0)
    losing_removed = int(result.get("losing_trades_removed", 0) or 0)
    if trades_removed == 0 or r_improvement <= 0 or pf_improvement <= 0:
        return "REJECT"
    collateral_ratio = profitable_lost / trades_removed if trades_removed else 1.0
    loss_efficiency = losing_removed / trades_removed if trades_removed else 0.0
    if trades_removed >= MIN_DEPLOY_TRADES and r_improvement >= 5 and pf_improvement >= 0.10 and collateral_ratio <= 0.35:
        return "DEPLOY"
    if trades_removed >= MIN_SHADOW_TRADES and r_improvement > 0 and loss_efficiency >= 0.50:
        return "SHADOW_TEST"
    return "WATCH"


def _candidate_filters() -> list[dict[str, Any]]:
    return [
        {"name": "against_htf AND session=ASIA", "predicate": lambda row: _session(row) == "ASIA"},
        {"name": "against_htf AND low_volume", "predicate": lambda row: _has_token(row, "low_volume")},
        {"name": "against_htf AND BREAKOUT", "predicate": lambda row: _entry_context(row) == "BREAKOUT"},
        {"name": "against_htf AND SECONDARY_SIGNAL", "predicate": lambda row: _setup_type(row) == "SECONDARY_SIGNAL"},
        {"name": "against_htf AND ASIA AND low_volume", "predicate": lambda row: _session(row) == "ASIA" and _has_token(row, "low_volume")},
        {"name": "against_htf AND ASIA AND BREAKOUT", "predicate": lambda row: _session(row) == "ASIA" and _entry_context(row) == "BREAKOUT"},
        {"name": "against_htf AND low_volume AND BREAKOUT", "predicate": lambda row: _has_token(row, "low_volume") and _entry_context(row) == "BREAKOUT"},
    ]


def _evaluate_candidate(rows: list[dict[str, Any]], candidate: dict[str, Any]) -> dict[str, Any]:
    predicate: CandidatePredicate = candidate["predicate"]
    removed = [row for row in rows if predicate(row)]
    remaining = [row for row in rows if not predicate(row)]
    before = _metrics(rows)
    after = _metrics(remaining)
    result = {
        "candidate": candidate["name"],
        "trades_removed": len(removed),
        "pf_before": before["profit_factor"],
        "pf_after": after["profit_factor"],
        "total_r_before": before["total_r"],
        "total_r_after": after["total_r"],
        "winrate_before": before["winrate"],
        "winrate_after": after["winrate"],
        "winrate_delta": _round(float(after["winrate"]) - float(before["winrate"])),
        "r_improvement": _round(float(after["total_r"]) - float(before["total_r"])),
        "pf_improvement": _round(_pf_float(after["profit_factor"]) - _pf_float(before["profit_factor"])),
        "profitable_trades_lost": len([row for row in removed if (_float(row.get("result_r")) or 0.0) > 0]),
        "losing_trades_removed": len([row for row in removed if (_float(row.get("result_r")) or 0.0) < 0]),
        "removed_metrics": _metrics(removed),
        "remaining_metrics": after,
    }
    result["classification"] = classify_candidate(result)
    return result


def _rank_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        candidates,
        key=lambda row: (
            float(row.get("pf_improvement", 0.0) or 0.0),
            float(row.get("r_improvement", 0.0) or 0.0),
            int(row.get("trades_removed", 0) or 0),
        ),
        reverse=True,
    )


def _answers(ranking: list[dict[str, Any]]) -> dict[str, str]:
    viable = [row for row in ranking if row.get("classification") in {"DEPLOY", "SHADOW_TEST", "WATCH"}]
    best = viable[0] if viable else None
    safest = _safest_candidate(viable)
    highest_pf = max(viable, key=lambda row: float(row.get("pf_improvement", 0.0) or 0.0), default=None)
    lowest_collateral = min(viable, key=lambda row: (int(row.get("profitable_trades_lost", 0) or 0), -float(row.get("r_improvement", 0.0) or 0.0)), default=None)
    recommended = next((row for row in viable if row.get("classification") == "SHADOW_TEST"), best)
    if recommended is None:
        action = "No candidate has positive enough effect. Keep against_htf unchanged and continue monitoring."
    else:
        action = f"Shadow-test `{recommended['candidate']}` before any production change."
    return {
        "best_candidate": _describe_candidate(best),
        "safest_candidate": _describe_candidate(safest),
        "highest_pf_improvement": _describe_candidate(highest_pf),
        "lowest_collateral_damage": _describe_candidate(lowest_collateral),
        "recommended_shadow_filter": _describe_candidate(recommended),
        "recommended_next_action": action,
    }


def _safest_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda row: (
            float(row.get("r_improvement", 0.0) or 0.0),
            -int(row.get("profitable_trades_lost", 0) or 0),
            int(row.get("losing_trades_removed", 0) or 0),
        ),
    )


def _is_against_htf(row: dict[str, Any]) -> bool:
    return "against_htf" in _all_tokens(row) or _htf_alignment(row) == "against_htf"


def _is_bullish_sweep(row: dict[str, Any]) -> bool:
    explicit = str(row.get("liquidity_context") or "").strip()
    if explicit:
        return explicit == "sweep:bullish_sweep"
    sweep = str(row.get("liquidity_sweep") or "").strip()
    return sweep == "bullish_sweep"


def _has_token(row: dict[str, Any], token: str) -> bool:
    return token in _all_tokens(row)


def _all_tokens(row: dict[str, Any]) -> set[str]:
    return (
        _tokens(row.get("warnings"))
        | _tokens(row.get("avoidance_warnings"))
        | _tokens(row.get("rejection_reasons"))
        | _tokens(row.get("penalties"))
    )


def _session(row: dict[str, Any]) -> str:
    return str(row.get("session") or "UNKNOWN").upper()


def _entry_context(row: dict[str, Any]) -> str:
    return str(row.get("entry_context") or "UNKNOWN").upper()


def _setup_type(row: dict[str, Any]) -> str:
    return str(row.get("setup_type") or "UNKNOWN").upper()


def _htf_alignment(row: dict[str, Any]) -> str:
    direction = str(row.get("direction") or "").strip().lower()
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
        "winrate": round(len(wins) / len(values) * 100, 2) if values else 0.0,
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


def _tokens(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, set, tuple)):
        return {str(item).strip() for item in value if str(item).strip()}
    text = str(value).strip()
    if not text:
        return set()
    return {item.strip() for item in text.replace("|", ",").replace(";", ",").split(",") if item.strip()}


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


def _describe_candidate(candidate: dict[str, Any] | None) -> str:
    if not candidate:
        return "none"
    return (
        f"{candidate.get('candidate')} "
        f"(removed={candidate.get('trades_removed', 0)}, PF {candidate.get('pf_before', 0)}->{candidate.get('pf_after', 0)}, "
        f"R improvement={candidate.get('r_improvement', 0)}, profitable lost={candidate.get('profitable_trades_lost', 0)}, "
        f"class={candidate.get('classification', 'REJECT')})"
    )


def _candidate_table(rows: object) -> list[str]:
    lines = [
        "| Candidate | Removed | PF Before | PF After | TotalR Before | TotalR After | WR Delta | R Improvement | Profitable Lost | Losing Removed | Classification |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    if not isinstance(rows, list) or not rows:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | REJECT |")
        return lines
    for row in rows:
        lines.append(
            f"| {row.get('candidate', '')} | {row.get('trades_removed', 0)} | {row.get('pf_before', 0)} | "
            f"{row.get('pf_after', 0)} | {row.get('total_r_before', 0)} | {row.get('total_r_after', 0)} | "
            f"{row.get('winrate_delta', 0)} | {row.get('r_improvement', 0)} | {row.get('profitable_trades_lost', 0)} | "
            f"{row.get('losing_trades_removed', 0)} | {row.get('classification', 'REJECT')} |"
        )
    return lines
