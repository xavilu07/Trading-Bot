from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from trading_signals.application.use_cases.paper_trading import evaluate_trade_status
from trading_signals.data.canonical_trade_source import compute_trade_metrics
from trading_signals.domain.entities.market_snapshot import MarketSnapshot


SAFE_TO_RELAX_FILTERS = {
    "edge_activation_requires_overlap_session",
    "breakout_bad_location",
    "against_htf",
    "market_regime_ranging",
    "edge_activation_requires_trending",
    "setup_type_secondary_signal",
    "edge_activation_secondary_signal",
}

RELAXATION_SHADOW_FIELDS = [
    "trade_id",
    "dedupe_key",
    "symbol",
    "direction",
    "setup_type",
    "score",
    "entry_price",
    "stop_loss",
    "take_profit_1",
    "take_profit_2",
    "risk_reward_tp1",
    "risk_reward_tp2",
    "opened_at",
    "updated_at",
    "closed_at",
    "expires_after_candles",
    "candles_held",
    "status",
    "result_r",
    "mfe_r",
    "mae_r",
    "session",
    "market_regime",
    "entry_context",
    "trade_location",
    "market_structure",
    "liquidity_sweep",
    "trend_1h",
    "trend_4h",
    "rr_valid",
    "relaxed_filters",
    "original_rejection_reasons",
    "relaxed_reasons",
    "context",
]

SUMMARY_FIELDS = [
    "group",
    "value",
    "trades",
    "closed_trades",
    "open_trades",
    "winrate",
    "profit_factor",
    "total_r",
    "avg_r",
]

RELAXATION_SHADOW_SKIP_FIELDS = [
    "symbol",
    "direction",
    "score",
    "block_reasons",
    "safe_filters",
    "unsafe_filters",
    "skip_reason",
]


@dataclass(slots=True)
class RelaxationShadowCandidate:
    dedupe_key: str
    symbol: str
    direction: str
    setup_type: str
    score: float
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_reward_tp1: float
    risk_reward_tp2: float
    opened_at: str
    expires_after_candles: int
    session: str
    market_regime: str
    entry_context: str
    trade_location: str
    market_structure: str
    liquidity_sweep: str
    trend_1h: str
    trend_4h: str
    rr_valid: bool
    relaxed_filters: list[str]
    original_rejection_reasons: list[str]
    relaxed_reasons: list[str]
    context: dict[str, Any]


@dataclass(slots=True)
class RelaxationShadowSkip:
    symbol: str
    direction: str
    score: float
    block_reasons: list[str]
    safe_filters: list[str]
    unsafe_filters: list[str]
    skip_reason: str


class RelaxationShadowV1Store:
    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self.trades_file = base_path / "shadow_relaxation" / "trades.csv"
        self.skips_file = base_path / "shadow_relaxation" / "skips.csv"

    def list_trades(self) -> list[dict[str, str]]:
        if not self.trades_file.exists():
            return []
        with self.trades_file.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def list_skips(self) -> list[dict[str, str]]:
        if not self.skips_file.exists():
            return []
        with self.skips_file.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def save_trades(self, trades: list[dict[str, object]]) -> None:
        self.trades_file.parent.mkdir(parents=True, exist_ok=True)
        temp = self.trades_file.with_suffix(".csv.tmp")
        with temp.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=RELAXATION_SHADOW_FIELDS)
            writer.writeheader()
            for trade in trades:
                writer.writerow({field: _serialize(trade.get(field, "")) for field in RELAXATION_SHADOW_FIELDS})
        temp.replace(self.trades_file)

    def upsert_candidate(self, candidate: RelaxationShadowCandidate) -> bool:
        trades: list[dict[str, object]] = list(self.list_trades())
        if any(item.get("dedupe_key") == candidate.dedupe_key for item in trades):
            return False
        row = asdict(candidate)
        row.update(
            {
                "trade_id": f"relax_{uuid4().hex[:12]}",
                "updated_at": candidate.opened_at,
                "closed_at": "",
                "candles_held": "0",
                "status": "open",
                "result_r": "0",
                "mfe_r": "0",
                "mae_r": "0",
            }
        )
        trades.append(row)
        self.save_trades(trades)
        return True

    def record_skip(self, skip: RelaxationShadowSkip) -> None:
        skips: list[dict[str, object]] = list(self.list_skips())
        skips.append(asdict(skip))
        self.skips_file.parent.mkdir(parents=True, exist_ok=True)
        temp = self.skips_file.with_suffix(".csv.tmp")
        with temp.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=RELAXATION_SHADOW_SKIP_FIELDS)
            writer.writeheader()
            for row in skips:
                writer.writerow({field: _serialize(row.get(field, "")) for field in RELAXATION_SHADOW_SKIP_FIELDS})
        temp.replace(self.skips_file)

    def update_open_trades_for_snapshot(self, snapshot: MarketSnapshot, updated_at: str) -> list[dict[str, object]]:
        trades: list[dict[str, object]] = list(self.list_trades())
        updated: list[dict[str, object]] = []
        changed = False
        for trade in trades:
            if trade.get("symbol") != snapshot.symbol or trade.get("status") not in {"open", "tp1_hit"}:
                continue
            previous_status = str(trade.get("status") or "open")
            status, result_r, mfe_r, mae_r = evaluate_trade_status(trade, snapshot)
            candles_held = int(float(trade.get("candles_held") or 0)) + 1
            expires_after = int(float(trade.get("expires_after_candles") or 0))
            if status in {"open", "tp1_hit"} and expires_after > 0 and candles_held >= expires_after:
                status = "expired"
            trade["status"] = status
            trade["result_r"] = f"{result_r:.4f}"
            trade["mfe_r"] = f"{max(float(trade.get('mfe_r') or 0.0), mfe_r):.4f}"
            trade["mae_r"] = f"{min(float(trade.get('mae_r') or 0.0), mae_r):.4f}"
            trade["candles_held"] = str(candles_held)
            trade["updated_at"] = updated_at
            if status in {"tp2_hit", "sl_hit", "expired"}:
                trade["closed_at"] = updated_at
            if status != previous_status or status in {"open", "tp1_hit", "expired"}:
                updated.append(dict(trade))
                changed = True
        if changed:
            self.save_trades(trades)
        return updated


def safe_relaxation_filter_result(block_reasons: object) -> dict[str, Any]:
    reasons = _dedupe(_tokens(block_reasons))
    unsafe = [reason for reason in reasons if reason not in SAFE_TO_RELAX_FILTERS]
    safe = [reason for reason in reasons if reason in SAFE_TO_RELAX_FILTERS]
    return {
        "eligible": bool(safe) and not unsafe,
        "safe_filters": safe,
        "unsafe_filters": unsafe,
        "original_rejection_reasons": reasons,
    }


def build_relaxation_shadow_candidate(
    *,
    signal,
    evaluation,
    risk_plan,
    entry_snapshot: MarketSnapshot,
    higher_snapshot: MarketSnapshot,
    setup_context: dict[str, object],
    current_policy: dict[str, object],
    opened_at: str,
    expires_after_candles: int = 24,
) -> RelaxationShadowCandidate | None:
    if risk_plan is None:
        return None
    filter_result = safe_relaxation_filter_result(current_policy.get("block_reasons", []))
    if not filter_result["eligible"]:
        return None
    risk = abs(float(risk_plan.entry) - float(risk_plan.stop_loss))
    if risk <= 0:
        return None
    direction = str(signal.decision).lower()
    take_profit_1 = float(risk_plan.entry) + risk if direction == "long" else float(risk_plan.entry) - risk
    take_profit_2 = float(risk_plan.take_profit)
    score = float(getattr(evaluation, "setup_score", getattr(evaluation, "total_score", setup_context.get("score", 0.0))) or 0.0)
    return RelaxationShadowCandidate(
        dedupe_key=relaxation_shadow_dedupe_key(
            symbol=signal.symbol,
            direction=direction,
            candle_timestamp=entry_snapshot.timestamp,
        ),
        symbol=str(signal.symbol).upper(),
        direction=direction,
        setup_type=str(setup_context.get("setup_type") or getattr(evaluation, "setup_type", "UNKNOWN") or "UNKNOWN").upper(),
        score=round(score, 2),
        entry_price=float(risk_plan.entry),
        stop_loss=float(risk_plan.stop_loss),
        take_profit_1=round(take_profit_1, 6),
        take_profit_2=take_profit_2,
        risk_reward_tp1=1.0,
        risk_reward_tp2=round(abs(take_profit_2 - float(risk_plan.entry)) / risk, 4),
        opened_at=opened_at,
        expires_after_candles=expires_after_candles,
        session=str(setup_context.get("session", "UNKNOWN")),
        market_regime=str(setup_context.get("market_regime", "UNKNOWN")),
        entry_context=str(setup_context.get("entry_context", "UNKNOWN")),
        trade_location=str(setup_context.get("trade_location", "UNKNOWN")),
        market_structure=str(setup_context.get("market_structure") or entry_snapshot.market_structure),
        liquidity_sweep=str(setup_context.get("liquidity_sweep") or entry_snapshot.liquidity_sweep),
        trend_1h=str(setup_context.get("trend_entry") or entry_snapshot.trend),
        trend_4h=str(setup_context.get("trend_higher") or higher_snapshot.trend),
        rr_valid=bool(setup_context.get("rr_valid", True)),
        relaxed_filters=list(filter_result["safe_filters"]),
        original_rejection_reasons=list(filter_result["original_rejection_reasons"]),
        relaxed_reasons=["safe_to_relax_filters_only"],
        context={
            "policy_version": current_policy.get("policy_version"),
            "edge_activation_mode": current_policy.get("edge_activation_mode"),
            "edge_activation_reasons": current_policy.get("edge_activation_reasons", []),
            "warnings": current_policy.get("warnings", []),
        },
    )


def evaluate_relaxation_shadow_v1(
    *,
    signal,
    evaluation,
    risk_plan,
    entry_snapshot: MarketSnapshot,
    higher_snapshot: MarketSnapshot,
    setup_context: dict[str, object],
    current_policy: dict[str, object],
    store,
    opened_at: str,
    expires_after_candles: int = 24,
) -> dict[str, object]:
    filter_result = safe_relaxation_filter_result(current_policy.get("block_reasons", []))
    if store is None:
        return {"should_send_dev": False, "skip_reason": "store_not_configured", "filter_result": filter_result}
    if not filter_result["eligible"]:
        record_relaxation_shadow_skip(
            store=store,
            signal=signal,
            evaluation=evaluation,
            setup_context=setup_context,
            filter_result=filter_result,
            skip_reason="unsafe_or_empty_filters",
        )
        return {"should_send_dev": False, "skip_reason": "unsafe_or_empty_filters", "filter_result": filter_result}
    candidate = build_relaxation_shadow_candidate(
        signal=signal,
        evaluation=evaluation,
        risk_plan=risk_plan,
        entry_snapshot=entry_snapshot,
        higher_snapshot=higher_snapshot,
        setup_context=setup_context,
        current_policy=current_policy,
        opened_at=opened_at,
        expires_after_candles=expires_after_candles,
    )
    if candidate is None:
        record_relaxation_shadow_skip(
            store=store,
            signal=signal,
            evaluation=evaluation,
            setup_context=setup_context,
            filter_result=filter_result,
            skip_reason="candidate_not_created",
        )
        return {"should_send_dev": False, "skip_reason": "candidate_not_created", "filter_result": filter_result}
    created = store.upsert_candidate(candidate)
    if not created:
        store.record_skip(
            RelaxationShadowSkip(
                symbol=candidate.symbol,
                direction=candidate.direction,
                score=candidate.score,
                block_reasons=list(filter_result["original_rejection_reasons"]),
                safe_filters=list(filter_result["safe_filters"]),
                unsafe_filters=list(filter_result["unsafe_filters"]),
                skip_reason="duplicate",
            )
        )
        return {"should_send_dev": False, "skip_reason": "duplicate", "filter_result": filter_result, "candidate": candidate}
    return {
        "should_send_dev": True,
        "skip_reason": "",
        "filter_result": filter_result,
        "candidate": candidate,
    }


def record_relaxation_shadow_skip(
    *,
    store,
    signal,
    evaluation,
    setup_context: dict[str, object],
    filter_result: dict[str, object],
    skip_reason: str,
) -> None:
    score = float(
        getattr(
            evaluation,
            "setup_score",
            getattr(evaluation, "total_score", setup_context.get("score", 0.0)),
        )
        or 0.0
    )
    store.record_skip(
        RelaxationShadowSkip(
            symbol=str(signal.symbol).upper(),
            direction=str(signal.decision).lower(),
            score=round(score, 2),
            block_reasons=list(filter_result.get("original_rejection_reasons", [])),
            safe_filters=list(filter_result.get("safe_filters", [])),
            unsafe_filters=list(filter_result.get("unsafe_filters", [])),
            skip_reason=skip_reason,
        )
    )


def format_relaxation_shadow_v1_message(candidate: RelaxationShadowCandidate) -> str:
    return (
        "🧪 RELAXATION SHADOW V1\n"
        "No publicada en canal público.\n\n"
        f"Symbol: {candidate.symbol}\n"
        f"Direction: {candidate.direction.upper()}\n"
        f"Score: {candidate.score}\n"
        f"Entry: {candidate.entry_price}\n"
        f"SL: {candidate.stop_loss}\n"
        f"TP1: {candidate.take_profit_1}\n"
        f"TP2: {candidate.take_profit_2}\n"
        f"Relaxed filters: {', '.join(candidate.relaxed_filters)}\n"
        f"Original rejection reasons: {', '.join(candidate.original_rejection_reasons)}"
    )


def build_relaxation_shadow_summary(base_path: Path) -> dict[str, Any]:
    store = RelaxationShadowV1Store(base_path)
    trades = store.list_trades()
    skips = store.list_skips()
    closed = [_normalize_for_metrics(trade) for trade in trades if str(trade.get("status")) in {"tp2_hit", "sl_hit", "expired"}]
    metrics = compute_trade_metrics([trade for trade in closed if trade is not None])
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "trades": len(trades),
        "skips": len(skips),
        "top_unsafe_filters": _top_tokens(skips, "unsafe_filters"),
        "last_skip_reason": str(skips[-1].get("skip_reason") or "none") if skips else "none",
        "closed_trades": metrics["closed_trades"],
        "open_trades": len([trade for trade in trades if str(trade.get("status")) in {"open", "tp1_hit"}]),
        "metrics": metrics,
        "by_relaxed_filter": _group_by_token(trades, "relaxed_filters"),
        "by_direction": _group_by(trades, "direction"),
        "by_session": _group_by(trades, "session"),
        "by_setup_type": _group_by(trades, "setup_type"),
        "by_market_regime": _group_by(trades, "market_regime"),
        "by_entry_context": _group_by(trades, "entry_context"),
    }


def write_relaxation_shadow_reports(base_path: Path, reports_path: Path) -> dict[str, Path]:
    reports_path.mkdir(parents=True, exist_ok=True)
    store = RelaxationShadowV1Store(base_path)
    trades = store.list_trades()
    skips = store.list_skips()
    summary = build_relaxation_shadow_summary(base_path)
    trades_csv = reports_path / "relaxation_shadow_v1_trades.csv"
    summary_md = reports_path / "relaxation_shadow_v1_summary.md"
    summary_csv = reports_path / "relaxation_shadow_v1_summary.csv"
    skips_md = reports_path / "relaxation_shadow_v1_skips.md"
    skips_csv = reports_path / "relaxation_shadow_v1_skips.csv"
    activation_audit_md = reports_path / "relaxation_shadow_activation_audit.md"
    _write_rows(trades_csv, trades, RELAXATION_SHADOW_FIELDS)
    _write_rows(summary_csv, _summary_rows(summary), SUMMARY_FIELDS)
    _write_rows(skips_csv, skips, RELAXATION_SHADOW_SKIP_FIELDS)
    summary_md.write_text(format_relaxation_shadow_summary(summary), encoding="utf-8")
    skips_md.write_text(format_relaxation_shadow_skips(skips), encoding="utf-8")
    activation_audit_md.write_text(format_relaxation_shadow_activation_audit(summary, skips), encoding="utf-8")
    return {
        "trades_csv": trades_csv,
        "summary_md": summary_md,
        "summary_csv": summary_csv,
        "skips_md": skips_md,
        "skips_csv": skips_csv,
        "activation_audit_md": activation_audit_md,
    }


def format_relaxation_shadow_summary(summary: dict[str, Any]) -> str:
    metrics = summary.get("metrics", {})
    lines = [
        "# RELAXATION_SHADOW_V1 Summary",
        "",
        f"- Generated at: {summary.get('generated_at')}",
        f"- Total trades: {summary.get('trades', 0)}",
        f"- Total skips: {summary.get('skips', 0)}",
        f"- Top unsafe filters: {_format_filter_counts(summary.get('top_unsafe_filters'))}",
        f"- Last skip reason: {summary.get('last_skip_reason', 'none')}",
        f"- Closed trades: {summary.get('closed_trades', 0)}",
        f"- Open trades: {summary.get('open_trades', 0)}",
        f"- WR: {metrics.get('winrate', 0)}%",
        f"- PF: {metrics.get('profit_factor', 0)}",
        f"- Total R: {metrics.get('total_r', 0)}",
        f"- Avg R: {metrics.get('avg_r', 0)}",
        f"- Max DD: {metrics.get('max_drawdown', 0)}",
        f"- Current DD: {metrics.get('current_drawdown', 0)}",
        "",
    ]
    for title, key in (
        ("Performance by relaxed filter", "by_relaxed_filter"),
        ("Performance by direction", "by_direction"),
        ("Performance by session", "by_session"),
        ("Performance by setup_type", "by_setup_type"),
        ("Performance by market_regime", "by_market_regime"),
        ("Performance by entry_context", "by_entry_context"),
    ):
        lines.extend([f"## {title}", "", "| Value | Closed | Open | WR | PF | Total R | Avg R |", "|---|---:|---:|---:|---:|---:|---:|"])
        group = summary.get(key, {})
        if isinstance(group, dict) and group:
            for value, stats in sorted(group.items()):
                if not isinstance(stats, dict):
                    continue
                lines.append(
                    f"| {value} | {stats.get('closed_trades', 0)} | {stats.get('open_trades', 0)} | "
                    f"{stats.get('winrate', 0)}% | {stats.get('profit_factor', 0)} | "
                    f"{stats.get('total_r', 0)} | {stats.get('avg_r', 0)} |"
                )
        else:
            lines.append("| none | 0 | 0 | 0% | 0 | 0 | 0 |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def format_relaxation_shadow_skips(skips: list[dict[str, Any]]) -> str:
    top_unsafe = _top_tokens(skips, "unsafe_filters")
    last_skip = str(skips[-1].get("skip_reason") or "none") if skips else "none"
    lines = [
        "# RELAXATION_SHADOW_V1_SKIP_DIAGNOSTICS",
        "",
        f"- Total skips: {len(skips)}",
        f"- Top unsafe filters: {_format_filter_counts(top_unsafe)}",
        f"- Last skip reason: {last_skip}",
        "",
        "| Symbol | Direction | Score | Block reasons | Safe filters | Unsafe filters | Skip reason |",
        "|---|---|---:|---|---|---|---|",
    ]
    if not skips:
        lines.append("| none | none | 0 | none | none | none | none |")
        return "\n".join(lines).rstrip() + "\n"
    for skip in skips:
        lines.append(
            f"| {_md(skip.get('symbol'))} | {_md(skip.get('direction'))} | {_md(skip.get('score'))} | "
            f"{_md_list(skip.get('block_reasons'))} | {_md_list(skip.get('safe_filters'))} | "
            f"{_md_list(skip.get('unsafe_filters'))} | {_md(skip.get('skip_reason'))} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def format_relaxation_shadow_activation_audit(summary: dict[str, Any], skips: list[dict[str, Any]]) -> str:
    return (
        "# RELAXATION_SHADOW_V1 Activation Audit\n\n"
        f"- Trades captured: {summary.get('trades', 0)}\n"
        f"- Skips captured: {len(skips)}\n"
        f"- Top unsafe filters: {_format_filter_counts(summary.get('top_unsafe_filters'))}\n"
        f"- Last skip reason: {summary.get('last_skip_reason', 'none')}\n"
        f"- Status: {_activation_status(summary, skips)}\n"
    )


def relaxation_shadow_dedupe_key(*, symbol: str, direction: str, candle_timestamp: str) -> str:
    return f"{symbol.strip().upper()}|{direction.strip().lower()}|{candle_timestamp}|RELAXATION_SHADOW_V1"


def _activation_status(summary: dict[str, Any], skips: list[dict[str, Any]]) -> str:
    trades = int(summary.get("trades", 0) or 0)
    if trades > 0:
        return "reachable"
    if skips:
        return "observing_skips_only"
    return "no_candidates_observed"


def _group_by(trades: list[dict[str, str]], key: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for trade in trades:
        grouped[str(trade.get(key) or "UNKNOWN")].append(trade)
    return {name: _stats(items) for name, items in grouped.items()}


def _group_by_token(trades: list[dict[str, str]], key: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for trade in trades:
        for token in _tokens(trade.get(key)):
            grouped[token].append(trade)
    return {name: _stats(items) for name, items in grouped.items()}


def _stats(trades: list[dict[str, str]]) -> dict[str, Any]:
    closed = [_normalize_for_metrics(trade) for trade in trades if str(trade.get("status")) in {"tp2_hit", "sl_hit", "expired"}]
    closed = [trade for trade in closed if trade is not None]
    metrics = compute_trade_metrics(closed)
    return {
        "trades": len(trades),
        "closed_trades": metrics["closed_trades"],
        "open_trades": len([trade for trade in trades if str(trade.get("status")) in {"open", "tp1_hit"}]),
        "winrate": metrics["winrate"],
        "profit_factor": metrics["profit_factor"],
        "total_r": metrics["total_r"],
        "avg_r": metrics["avg_r"],
    }


def _normalize_for_metrics(trade: dict[str, Any]) -> dict[str, Any] | None:
    try:
        result_r = float(trade.get("result_r") or 0.0)
    except (TypeError, ValueError):
        return None
    return {
        **trade,
        "result_r": result_r,
        "status": str(trade.get("status") or "").lower(),
    }


def _summary_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for group_key in ("by_relaxed_filter", "by_direction", "by_session", "by_setup_type", "by_market_regime", "by_entry_context"):
        group = summary.get(group_key, {})
        if not isinstance(group, dict):
            continue
        for value, stats in group.items():
            if not isinstance(stats, dict):
                continue
            rows.append({"group": group_key, "value": value, **stats})
    return rows


def _top_tokens(rows: list[dict[str, Any]], field: str, limit: int = 5) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for row in rows:
        for token in _tokens(row.get(field)):
            counts[token] = counts.get(token, 0) + 1
    return [{"filter": name, "count": count} for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]]


def _format_filter_counts(value: object) -> str:
    rows = value if isinstance(value, list) else []
    if not rows:
        return "none"
    parts = []
    for row in rows[:5]:
        if isinstance(row, dict):
            parts.append(f"{row.get('filter')} ({row.get('count')})")
    return ", ".join(parts) if parts else "none"


def _write_rows(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _serialize(row.get(field, "")) for field in fields})


def _tokens(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return _dedupe(str(item).strip() for item in value if str(item).strip())
    text = str(value).strip()
    if not text:
        return []
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        decoded = None
    if isinstance(decoded, list):
        return _dedupe(str(item).strip() for item in decoded if str(item).strip())
    return _dedupe(item.strip() for item in text.replace("|", ",").replace(";", ",").split(",") if item.strip())


def _md(value: object) -> str:
    text = str(value or "").strip() or "none"
    return text.replace("|", "\\|")


def _md_list(value: object) -> str:
    tokens = _tokens(value)
    if not tokens:
        return "none"
    return ", ".join(_md(token) for token in tokens)


def _dedupe(values: object) -> list[str]:
    output: list[str] = []
    for value in values if not isinstance(values, str) else [values]:
        text = str(value).strip()
        if text and text not in output:
            output.append(text)
    return output


def _serialize(value: object) -> object:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value
