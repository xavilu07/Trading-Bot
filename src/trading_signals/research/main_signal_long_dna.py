from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


TOXIC_MIN_TRADES = 10
SURVIVOR_MIN_TRADES = 10
CRITICAL_MIN_TRADES = 30


PARTIAL_BLOCKS: tuple[tuple[str, Callable[[dict[str, Any]], bool]], ...] = (
    ("MAIN_SIGNAL LONG + bullish_sweep", lambda row: _is_main_long(row) and _is_bullish_sweep(row)),
    ("MAIN_SIGNAL LONG + against_htf", lambda row: _is_main_long(row) and _is_against_htf(row)),
    ("MAIN_SIGNAL LONG + near_support", lambda row: _is_main_long(row) and _is_near_support(row)),
    ("MAIN_SIGNAL LONG + BREAKOUT", lambda row: _is_main_long(row) and _entry_context(row) == "BREAKOUT"),
    ("MAIN_SIGNAL LONG + HIGH_VOLATILITY", lambda row: _is_main_long(row) and _market_regime(row) == "HIGH_VOLATILITY"),
    ("MAIN_SIGNAL LONG + RANGING", lambda row: _is_main_long(row) and _market_regime(row) == "RANGING"),
    ("MAIN_SIGNAL LONG + directional_confluence_failed", lambda row: _is_main_long(row) and _has_token(row, "directional_confluence_failed")),
    ("MAIN_SIGNAL LONG + distance_to_liquidity_penalty", lambda row: _is_main_long(row) and _has_token(row, "distance_to_liquidity_penalty")),
    ("MAIN_SIGNAL LONG + body_ratio_below_threshold", lambda row: _is_main_long(row) and _has_token(row, "body_ratio_below_threshold")),
)


def analyze_main_signal_long_dna(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    all_trades = load_canonical_closed_trades(data_path)
    long_rows = [row for row in all_trades if _is_main_long(row)]
    short_rows = [row for row in all_trades if _is_main_short(row)]
    metrics = _metrics(long_rows)
    breakdowns = {
        "symbol": _group_summary(long_rows, "symbol"),
        "session": _group_summary(long_rows, "session"),
        "market_regime": _group_summary(long_rows, "market_regime"),
        "entry_context": _group_summary(long_rows, "entry_context"),
        "liquidity_context": _group_summary(long_rows, "liquidity_context"),
        "trade_location": _group_summary(long_rows, "trade_location"),
        "trend_alignment": _group_summary(long_rows, "trend_alignment"),
        "htf_alignment": _group_summary(long_rows, "htf_alignment"),
        "score_bucket": _group_summary(long_rows, "score_bucket"),
        "warning": _token_summary(long_rows, "warnings", "avoidance_warnings"),
        "penalty": _token_summary(long_rows, "penalties"),
        "rejection_reason": _token_summary(long_rows, "rejection_reasons"),
        "condition_failed": _token_summary(long_rows, "conditions_failed"),
    }
    groups = _flatten_groups(breakdowns)
    toxic = _rank_toxic(groups)
    survivors = _rank_survivors(groups)
    comparison = _long_vs_short_dna_comparison(long_rows, short_rows)
    counterfactual = _counterfactual_remove_main_long(all_trades)
    partial_blocks = _partial_block_counterfactuals(all_trades)
    answers = _answers(
        long_metrics=metrics,
        short_metrics=_metrics(short_rows),
        toxic=toxic,
        survivors=survivors,
        counterfactual=counterfactual,
        partial_blocks=partial_blocks,
    )
    return {
        "scope": "MAIN_SIGNAL_LONG_DNA",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "method": "Analyze canonical closed trades where setup_type=MAIN_SIGNAL and direction=long.",
        "baseline_metrics": _metrics(all_trades),
        "main_signal_long_metrics": metrics,
        "main_signal_short_metrics": _metrics(short_rows),
        "classification": classify_main_signal_long(metrics),
        "breakdowns": breakdowns,
        "toxic_long_clusters": toxic,
        "profitable_long_survivors": survivors,
        "long_vs_short_dna_comparison": comparison,
        "counterfactual_removal": counterfactual,
        "counterfactual_partial_blocks": partial_blocks,
        "answers": answers,
        "recommended_action": answers["recommended_action"],
    }


def write_main_signal_long_dna_report(result: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "main_signal_long_dna.md"
    path.write_text(format_main_signal_long_dna_markdown(result), encoding="utf-8")
    return path


def format_main_signal_long_dna_markdown(result: dict[str, Any]) -> str:
    answers = result.get("answers", {})
    counterfactual = result.get("counterfactual_removal", {})
    breakdowns = result.get("breakdowns", {})
    lines = [
        "# MAIN_SIGNAL_LONG_DNA",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        f"Method: {result.get('method')}",
        f"Classification: {result.get('classification')}",
        "",
        "## Executive Summary",
        "",
        f"- Baseline: {_metrics_inline(result.get('baseline_metrics', {}))}",
        f"- MAIN_SIGNAL LONG: {_metrics_inline(result.get('main_signal_long_metrics', {}))}",
        f"- MAIN_SIGNAL SHORT: {_metrics_inline(result.get('main_signal_short_metrics', {}))}",
        f"- What causes MAIN_SIGNAL LONG losses? {answers.get('loss_cause', '')}",
        f"- Most damaging subgroup: {answers.get('main_loss_subgroup', '')}",
        f"- Best survivor: {answers.get('survivor_subgroup', '')}",
        f"- Is MAIN_SIGNAL LONG salvageable? {answers.get('salvageable', '')}",
        f"- Partial blocking beats full removal? {answers.get('partial_beats_full_removal', '')}",
        f"- Dominant issue: {answers.get('dominant_issue', '')}",
        f"- Recommended action: {result.get('recommended_action', 'KEEP')}",
        "",
        "## Toxic LONG Clusters",
        "",
        "Criteria: minimum 10 trades, PF < 1, TotalR < 0.",
        "",
        *_rank_table(result.get("toxic_long_clusters", [])),
        "",
        "## Profitable LONG Survivors",
        "",
        "Criteria: minimum 10 trades, PF > 1.1, TotalR > 0.",
        "",
        *_rank_table(result.get("profitable_long_survivors", [])),
        "",
        "## LONG vs SHORT DNA Comparison",
        "",
        *_comparison_table(result.get("long_vs_short_dna_comparison", {})),
        "",
        "## Counterfactual Removal",
        "",
        f"- PF current: {counterfactual.get('current_metrics', {}).get('profit_factor', 0)}",
        f"- PF without MAIN_SIGNAL_LONG: {counterfactual.get('without_main_long_metrics', {}).get('profit_factor', 0)}",
        f"- TotalR current: {counterfactual.get('current_metrics', {}).get('total_r', 0)}",
        f"- TotalR without MAIN_SIGNAL_LONG: {counterfactual.get('without_main_long_metrics', {}).get('total_r', 0)}",
        f"- Winrate delta: {counterfactual.get('winrate_delta', 0)}",
        f"- Trades removed: {counterfactual.get('trades_removed', 0)}",
        "",
        "## Counterfactual Partial Blocks",
        "",
        *_partial_block_table(result.get("counterfactual_partial_blocks", [])),
        "",
        "## Breakdowns",
        "",
    ]
    for title, key in (
        ("By Symbol", "symbol"),
        ("By Session", "session"),
        ("By Market Regime", "market_regime"),
        ("By Entry Context", "entry_context"),
        ("By Liquidity Context", "liquidity_context"),
        ("By Trade Location", "trade_location"),
        ("By Trend Alignment", "trend_alignment"),
        ("By HTF Alignment", "htf_alignment"),
        ("By Score Bucket", "score_bucket"),
        ("By Warning", "warning"),
        ("By Penalty", "penalty"),
        ("By Rejection Reason", "rejection_reason"),
        ("By Conditions Failed", "condition_failed"),
    ):
        lines.extend([f"### {title}", "", *_group_table(breakdowns.get(key, {}), title), ""])
    lines.extend(["## Recommended Action", "", result.get("recommended_action", "KEEP")])
    return "\n".join(lines).rstrip() + "\n"


def classify_main_signal_long(metrics: dict[str, Any]) -> str:
    trades = int(metrics.get("trades", 0) or 0)
    total_r = float(metrics.get("total_r", 0.0) or 0.0)
    pf = _pf_float(metrics.get("profit_factor"))
    if total_r >= 0 or pf >= 1:
        return "NOISE"
    if trades >= CRITICAL_MIN_TRADES and total_r <= -10:
        return "CRITICAL"
    if trades >= TOXIC_MIN_TRADES:
        return "IMPORTANT"
    if trades >= 3:
        return "WATCH"
    return "NOISE"


def classify_partial_block(payload: dict[str, Any]) -> str:
    removed = int(payload.get("removed_trades", 0) or 0)
    r_improvement = float(payload.get("r_improvement", 0.0) or 0.0)
    pf_improvement = float(payload.get("pf_improvement", 0.0) or 0.0)
    profitable_lost = int(payload.get("profitable_trades_lost", 0) or 0)
    losing_removed = int(payload.get("losing_trades_removed", 0) or 0)
    if removed >= 30 and r_improvement >= 10 and pf_improvement >= 0.10 and losing_removed > profitable_lost:
        return "DEPLOY_CANDIDATE"
    if removed >= 10 and r_improvement > 0 and losing_removed >= profitable_lost:
        return "SHADOW_TEST"
    if removed >= 5:
        return "WATCH"
    return "REJECT"


def _answers(
    *,
    long_metrics: dict[str, Any],
    short_metrics: dict[str, Any],
    toxic: list[dict[str, Any]],
    survivors: list[dict[str, Any]],
    counterfactual: dict[str, Any],
    partial_blocks: list[dict[str, Any]],
) -> dict[str, str]:
    classification = classify_main_signal_long(long_metrics)
    globally_toxic = classification in {"CRITICAL", "IMPORTANT"}
    long_pf = _pf_float(long_metrics.get("profit_factor"))
    short_pf = _pf_float(short_metrics.get("profit_factor"))
    long_total_r = float(long_metrics.get("total_r", 0.0) or 0.0)
    short_total_r = float(short_metrics.get("total_r", 0.0) or 0.0)
    worse_than_short = long_pf < short_pf and long_total_r < short_total_r
    full_r_improvement = float(counterfactual.get("without_main_long_metrics", {}).get("total_r", 0.0) or 0.0) - float(
        counterfactual.get("current_metrics", {}).get("total_r", 0.0) or 0.0
    )
    best_partial = partial_blocks[0] if partial_blocks else {}
    partial_beats_full = float(best_partial.get("r_improvement", 0.0) or 0.0) > full_r_improvement and bool(survivors)
    deploy_candidates = [row for row in partial_blocks if row.get("classification") == "DEPLOY_CANDIDATE"]
    shadow_candidates = [row for row in partial_blocks if row.get("classification") == "SHADOW_TEST"]
    if not globally_toxic:
        action = "KEEP"
    elif deploy_candidates:
        action = "PARTIAL_BLOCK"
    elif survivors and (shadow_candidates or partial_beats_full):
        action = "REDEFINE_MAIN_SIGNAL_LONG"
    elif full_r_improvement > 0 and not survivors:
        action = "FULL_BLOCK"
    elif shadow_candidates:
        action = "SHADOW_BLOCK"
    else:
        action = "PARTIAL_BLOCK"
    return {
        "loss_cause": _loss_cause(toxic),
        "main_loss_subgroup": _describe_group(toxic[0]) if toxic else "none",
        "survivor_subgroup": _describe_group(survivors[0]) if survivors else "none",
        "salvageable": "YES" if survivors else "NO",
        "partial_beats_full_removal": "YES" if partial_beats_full else "NO",
        "dominant_issue": _dominant_issue(toxic),
        "worse_than_main_short": "YES" if worse_than_short else "NO",
        "recommended_action": action,
    }


def _loss_cause(toxic: list[dict[str, Any]]) -> str:
    if not toxic:
        return "No toxic MAIN_SIGNAL LONG cluster met minimum sample criteria."
    return "; ".join(_describe_group(row) for row in toxic[:3])


def _dominant_issue(toxic: list[dict[str, Any]]) -> str:
    if not toxic:
        return "unknown"
    dimensions = [str(row.get("dimension") or "") for row in toxic[:5]]
    for candidate in ("liquidity_context", "htf_alignment", "trend_alignment", "score_bucket", "market_regime"):
        if candidate in dimensions:
            return candidate
    return dimensions[0] or "unknown"


def _long_vs_short_dna_comparison(long_rows: list[dict[str, Any]], short_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "MAIN_SIGNAL_LONG": _dna_payload(long_rows),
        "MAIN_SIGNAL_SHORT": _dna_payload(short_rows),
    }


def _dna_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "metrics": _metrics(rows),
        "symbol_distribution": _distribution(rows, "symbol"),
        "session_distribution": _distribution(rows, "session"),
        "regime_distribution": _distribution(rows, "market_regime"),
        "liquidity_distribution": _distribution(rows, "liquidity_context"),
        "htf_distribution": _distribution(rows, "htf_alignment"),
    }


def _distribution(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[_field_value(row, field)].append(row)
    total = len(rows)
    return {
        key: {"count": len(items), "share": _round(len(items) / total * 100) if total else 0.0, "metrics": _metrics(items)}
        for key, items in sorted(groups.items())
    }


def _counterfactual_remove_main_long(all_trades: list[dict[str, Any]]) -> dict[str, Any]:
    removed = [row for row in all_trades if _is_main_long(row)]
    without = [row for row in all_trades if not _is_main_long(row)]
    current = _metrics(all_trades)
    without_metrics = _metrics(without)
    return {
        "current_metrics": current,
        "without_main_long_metrics": without_metrics,
        "removed_metrics": _metrics(removed),
        "trades_removed": len(removed),
        "winrate_delta": _round(float(without_metrics.get("winrate", 0.0) or 0.0) - float(current.get("winrate", 0.0) or 0.0)),
    }


def _partial_block_counterfactuals(all_trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    current = _metrics(all_trades)
    results = []
    for name, predicate in PARTIAL_BLOCKS:
        removed = [row for row in all_trades if predicate(row)]
        without = [row for row in all_trades if not predicate(row)]
        without_metrics = _metrics(without)
        removed_metrics = _metrics(removed)
        payload = {
            "name": name,
            "removed_trades": len(removed),
            "pf_before": current["profit_factor"],
            "pf_after": without_metrics["profit_factor"],
            "total_r_before": current["total_r"],
            "total_r_after": without_metrics["total_r"],
            "r_improvement": _round(float(without_metrics["total_r"]) - float(current["total_r"])),
            "pf_improvement": _round(_pf_float(without_metrics["profit_factor"]) - _pf_float(current["profit_factor"])),
            "profitable_trades_lost": int(removed_metrics.get("wins", 0) or 0),
            "losing_trades_removed": int(removed_metrics.get("losses", 0) or 0),
            "removed_metrics": removed_metrics,
        }
        payload["classification"] = classify_partial_block(payload)
        results.append(payload)
    return sorted(results, key=lambda row: (float(row["r_improvement"]), float(row["pf_improvement"]), int(row["removed_trades"])), reverse=True)


def _flatten_groups(breakdowns: dict[str, dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dimension, groups in breakdowns.items():
        for value, payload in groups.items():
            rows.append(
                {
                    "dimension": dimension,
                    "value": value,
                    "metrics": payload.get("metrics", {}),
                    "classification": payload.get("classification", "NOISE"),
                }
            )
    return rows


def _rank_toxic(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    toxic = []
    for row in groups:
        metrics = row.get("metrics", {})
        if (
            int(metrics.get("trades", 0) or 0) >= TOXIC_MIN_TRADES
            and _pf_float(metrics.get("profit_factor")) < 1
            and float(metrics.get("total_r", 0.0) or 0.0) < 0
        ):
            toxic.append(row)
    return sorted(toxic, key=lambda row: (float(row["metrics"].get("total_r", 0.0)), _pf_float(row["metrics"].get("profit_factor"))))[:30]


def _rank_survivors(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    survivors = []
    for row in groups:
        metrics = row.get("metrics", {})
        if (
            int(metrics.get("trades", 0) or 0) >= SURVIVOR_MIN_TRADES
            and _pf_float(metrics.get("profit_factor")) > 1.10
            and float(metrics.get("total_r", 0.0) or 0.0) > 0
        ):
            survivors.append(row)
    return sorted(survivors, key=lambda row: (float(row["metrics"].get("total_r", 0.0)), _pf_float(row["metrics"].get("profit_factor"))), reverse=True)


def _group_summary(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[_field_value(row, field)].append(row)
    return _summaries(groups)


def _token_summary(rows: list[dict[str, Any]], *fields: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        values: set[str] = set()
        for field in fields:
            values |= _tokens(row.get(field))
        if not values:
            groups["none"].append(row)
            continue
        for value in sorted(values):
            groups[value].append(row)
    return _summaries(groups)


def _summaries(groups: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    result = {}
    for key, items in sorted(groups.items()):
        metrics = _metrics(items)
        result[key] = {"metrics": metrics, "classification": classify_main_signal_long(metrics)}
    return result


def _field_value(row: dict[str, Any], field: str) -> str:
    if field == "score_bucket":
        return _score_bucket(row.get("score"))
    if field == "liquidity_context":
        return _liquidity_context(row)
    if field == "trend_alignment":
        return _trend_alignment(row)
    if field == "htf_alignment":
        return _htf_alignment(row)
    if field == "direction":
        return _direction(row)
    if field == "setup_type":
        return _setup_type(row)
    if field == "market_regime":
        return _market_regime(row)
    if field == "entry_context":
        return _entry_context(row)
    return str(row.get(field) or "UNKNOWN")


def _is_main_long(row: dict[str, Any]) -> bool:
    return _setup_type(row) == "MAIN_SIGNAL" and _direction(row) == "long"


def _is_main_short(row: dict[str, Any]) -> bool:
    return _setup_type(row) == "MAIN_SIGNAL" and _direction(row) == "short"


def _setup_type(row: dict[str, Any]) -> str:
    return str(row.get("setup_type") or "UNKNOWN").strip().upper()


def _direction(row: dict[str, Any]) -> str:
    return str(row.get("direction") or "unknown").strip().lower()


def _market_regime(row: dict[str, Any]) -> str:
    return str(row.get("market_regime") or "UNKNOWN").strip().upper()


def _entry_context(row: dict[str, Any]) -> str:
    return str(row.get("entry_context") or "UNKNOWN").strip().upper()


def _is_bullish_sweep(row: dict[str, Any]) -> bool:
    return _liquidity_context(row) == "sweep:bullish_sweep"


def _is_near_support(row: dict[str, Any]) -> bool:
    return str(row.get("trade_location") or "").strip() == "near_support" or _liquidity_context(row) == "location:near_support"


def _is_against_htf(row: dict[str, Any]) -> bool:
    return "against_htf" in _all_tokens(row) or _htf_alignment(row) == "against_htf"


def _has_token(row: dict[str, Any], token: str) -> bool:
    return token in _all_tokens(row)


def _all_tokens(row: dict[str, Any]) -> set[str]:
    return (
        _tokens(row.get("warnings"))
        | _tokens(row.get("avoidance_warnings"))
        | _tokens(row.get("penalties"))
        | _tokens(row.get("rejection_reasons"))
        | _tokens(row.get("conditions_failed"))
    )


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
    liquidity_reasons = sorted(
        reason
        for reason in _tokens(row.get("rejection_reasons")) | _tokens(row.get("warnings")) | _tokens(row.get("penalties"))
        if "liquidity" in reason.lower()
    )
    if liquidity_reasons:
        return f"reason:{liquidity_reasons[0]}"
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
    direction = _direction(row)
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


def _describe_group(row: dict[str, Any] | None) -> str:
    if not row:
        return "none"
    metrics = row.get("metrics", {})
    return (
        f"{row.get('dimension')}={row.get('value')} "
        f"(trades={metrics.get('trades', 0)}, PF={metrics.get('profit_factor', 0)}, "
        f"TotalR={metrics.get('total_r', 0)}, class={row.get('classification', 'NOISE')})"
    )


def _metrics_inline(metrics: object) -> str:
    if not isinstance(metrics, dict):
        metrics = {}
    return (
        f"trades={metrics.get('trades', 0)}, WR={metrics.get('winrate', 0)}%, "
        f"PF={metrics.get('profit_factor', 0)}, TotalR={metrics.get('total_r', 0)}, AvgR={metrics.get('avg_r', 0)}"
    )


def _group_table(payload: object, label: str) -> list[str]:
    lines = [f"| {label} | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |", "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    if not isinstance(payload, dict) or not payload:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |")
        return lines
    ranked = sorted(
        payload.items(),
        key=lambda item: (
            float(item[1].get("metrics", {}).get("total_r", 0.0)),
            _pf_float(item[1].get("metrics", {}).get("profit_factor")),
            -int(item[1].get("metrics", {}).get("trades", 0) or 0),
        ),
    )
    for key, value in ranked[:30]:
        metrics = value.get("metrics", {}) if isinstance(value, dict) else {}
        lines.append(
            f"| {key} | {metrics.get('trades', 0)} | {metrics.get('wins', 0)} | {metrics.get('losses', 0)} | "
            f"{metrics.get('winrate', 0)}% | {metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | "
            f"{metrics.get('avg_r', 0)} | {value.get('classification', 'NOISE') if isinstance(value, dict) else 'NOISE'} |"
        )
    return lines


def _rank_table(rows: object) -> list[str]:
    lines = ["| Dimension | Value | Trades | Wins | Losses | WR | PF | Total R | Avg R | Classification |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    if not isinstance(rows, list) or not rows:
        lines.append("| none | none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | NOISE |")
        return lines
    for row in rows[:30]:
        metrics = row.get("metrics", {}) if isinstance(row, dict) else {}
        lines.append(
            f"| {row.get('dimension', '')} | {row.get('value', '')} | {metrics.get('trades', 0)} | "
            f"{metrics.get('wins', 0)} | {metrics.get('losses', 0)} | {metrics.get('winrate', 0)}% | "
            f"{metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} | "
            f"{row.get('classification', 'NOISE')} |"
        )
    return lines


def _comparison_table(payload: object) -> list[str]:
    lines = ["| Side | Trades | Wins | Losses | WR | PF | Total R | Avg R | Top Symbol | Top Session | Top Regime | Top Liquidity | Top HTF |", "|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|"]
    if not isinstance(payload, dict) or not payload:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | none | none | none | none | none |")
        return lines
    for side in ("MAIN_SIGNAL_LONG", "MAIN_SIGNAL_SHORT"):
        item = payload.get(side, {})
        metrics = item.get("metrics", {}) if isinstance(item, dict) else {}
        lines.append(
            f"| {side} | {metrics.get('trades', 0)} | {metrics.get('wins', 0)} | {metrics.get('losses', 0)} | "
            f"{metrics.get('winrate', 0)}% | {metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | "
            f"{metrics.get('avg_r', 0)} | {_top_dist(item.get('symbol_distribution', {}))} | "
            f"{_top_dist(item.get('session_distribution', {}))} | {_top_dist(item.get('regime_distribution', {}))} | "
            f"{_top_dist(item.get('liquidity_distribution', {}))} | {_top_dist(item.get('htf_distribution', {}))} |"
        )
    return lines


def _partial_block_table(rows: object) -> list[str]:
    lines = [
        "| Rule | Removed | PF Before | PF After | TotalR Before | TotalR After | R Improvement | Profitable Lost | Losing Removed | Classification |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    if not isinstance(rows, list) or not rows:
        lines.append("| none | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | REJECT |")
        return lines
    for row in rows:
        lines.append(
            f"| {row.get('name')} | {row.get('removed_trades', 0)} | {row.get('pf_before', 0)} | "
            f"{row.get('pf_after', 0)} | {row.get('total_r_before', 0)} | {row.get('total_r_after', 0)} | "
            f"{row.get('r_improvement', 0)} | {row.get('profitable_trades_lost', 0)} | "
            f"{row.get('losing_trades_removed', 0)} | {row.get('classification', 'REJECT')} |"
        )
    return lines


def _top_dist(payload: object) -> str:
    if not isinstance(payload, dict) or not payload:
        return "none"
    key, value = max(payload.items(), key=lambda item: int(item[1].get("count", 0) or 0))
    return f"{key} ({value.get('share', 0)}%)"
