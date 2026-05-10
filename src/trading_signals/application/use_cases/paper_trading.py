from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from trading_signals.domain.entities.market_snapshot import MarketSnapshot
from trading_signals.domain.entities.risk_plan import RiskPlan


PAPER_TRADE_FIELDS = [
    "trade_id",
    "dedupe_key",
    "symbol",
    "direction",
    "setup_type",
    "paper_level",
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
    "rsi",
    "volume_current",
    "volume_average",
    "volume_ratio",
    "trend_1h",
    "trend_4h",
    "break_of_structure",
    "nearest_distance_to_liquidity_atr",
    "directional_distance_to_liquidity_atr",
    "entry_or_rejection_reason",
    "entry_reasons",
    "conditions_passed",
    "conditions_failed",
    "opened_hour_utc",
    "opened_weekday",
    "market_regime",
    "session",
    "entry_context",
    "trade_location",
    "rr_valid",
    "sl_distance_atr",
    "tp_distance_atr",
    "late_entry_from_bos",
    "avoidance_warnings",
]


@dataclass(slots=True)
class PaperTradeCandidate:
    dedupe_key: str
    symbol: str
    direction: str
    setup_type: str
    paper_level: str
    score: float
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_reward_tp1: float
    risk_reward_tp2: float
    opened_at: str
    expires_after_candles: int
    rsi: float
    volume_current: float
    volume_average: float
    volume_ratio: float
    trend_1h: str
    trend_4h: str
    break_of_structure: str
    nearest_distance_to_liquidity_atr: float
    directional_distance_to_liquidity_atr: float
    entry_or_rejection_reason: str
    entry_reasons: list[str]
    conditions_passed: list[str]
    conditions_failed: list[str]
    market_regime: str
    session: str
    entry_context: str
    trade_location: str
    rr_valid: bool
    sl_distance_atr: float | None
    tp_distance_atr: float | None
    late_entry_from_bos: bool
    avoidance_warnings: list[str]


class PaperTradingStore:
    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self.trades_file = base_path / "paper_trading" / "trades.csv"

    def list_trades(self) -> list[dict[str, str]]:
        if not self.trades_file.exists():
            return []
        with self.trades_file.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def save_trades(self, trades: list[dict[str, object]]) -> None:
        self.trades_file.parent.mkdir(parents=True, exist_ok=True)
        temp = self.trades_file.with_suffix(".csv.tmp")
        with temp.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=PAPER_TRADE_FIELDS)
            writer.writeheader()
            for trade in trades:
                writer.writerow({field: trade.get(field, "") for field in PAPER_TRADE_FIELDS})
        temp.replace(self.trades_file)

    def upsert_candidate(self, candidate: PaperTradeCandidate) -> bool:
        trades: list[dict[str, object]] = list(self.list_trades())
        if any(item.get("dedupe_key") == candidate.dedupe_key for item in trades):
            return False
        opened = datetime.fromisoformat(candidate.opened_at)
        row = asdict(candidate)
        row.update(
            {
                "trade_id": f"paper_{uuid4().hex[:12]}",
                "updated_at": candidate.opened_at,
                "closed_at": "",
                "candles_held": "0",
                "status": "open",
                "result_r": "0",
                "mfe_r": "0",
                "mae_r": "0",
                "entry_reasons": json.dumps(candidate.entry_reasons, ensure_ascii=False),
                "conditions_passed": json.dumps(candidate.conditions_passed, ensure_ascii=False),
                "conditions_failed": json.dumps(candidate.conditions_failed, ensure_ascii=False),
                "avoidance_warnings": json.dumps(candidate.avoidance_warnings, ensure_ascii=False),
                "opened_hour_utc": str(opened.hour),
                "opened_weekday": opened.strftime("%A"),
            }
        )
        trades.append(row)
        self.save_trades(trades)
        return True

    def update_open_trades_for_snapshot(self, snapshot: MarketSnapshot, updated_at: str) -> list[dict[str, object]]:
        trades: list[dict[str, object]] = list(self.list_trades())
        updated: list[dict[str, object]] = []
        changed = False
        for trade in trades:
            if trade.get("symbol") != snapshot.symbol or trade.get("status") not in {"open", "tp1_hit"}:
                continue
            previous_status = str(trade.get("status", "open"))
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

    def build_daily_summary(self, date_key: str) -> dict[str, object]:
        trades = [item for item in self.list_trades() if str(item.get("opened_at", "")).startswith(date_key)]
        closed = [item for item in trades if item.get("status") in {"tp2_hit", "sl_hit", "expired"}]
        wins = [item for item in closed if item.get("status") == "tp2_hit"]
        losses = [item for item in closed if item.get("status") == "sl_hit"]
        expired = [item for item in closed if item.get("status") == "expired"]
        return {
            "date": date_key,
            "simulated_trades": len(trades),
            "open_trades": len([item for item in trades if item.get("status") in {"open", "tp1_hit"}]),
            "closed_trades": len(closed),
            "won": len(wins),
            "lost": len(losses),
            "expired": len(expired),
            "winrate": round((len(wins) / len(closed) * 100) if closed else 0.0, 2),
            "profit_factor": profit_factor(closed),
            "by_level": grouped_stats(closed, "paper_level"),
            "by_setup": grouped_stats(closed, "setup_type"),
            "by_symbol": grouped_stats(closed, "symbol"),
            "by_direction": grouped_stats(closed, "direction"),
            "by_hour": grouped_stats(closed, "opened_hour_utc"),
            "by_weekday": grouped_stats(closed, "opened_weekday"),
            "by_market_regime": grouped_stats(closed, "market_regime"),
            "by_session": grouped_stats(closed, "session"),
            "by_entry_context": grouped_stats(closed, "entry_context"),
            "by_trade_location": grouped_stats(closed, "trade_location"),
            "best_setup": best_group(closed, "setup_type"),
            "worst_setup": worst_group(closed, "setup_type"),
            "best_symbol": best_group(closed, "symbol"),
            "worst_symbol": worst_group(closed, "symbol"),
            "recommendation": automatic_recommendation(closed),
        }


def paper_level(score: float) -> str | None:
    if score >= 45:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    if score >= 35:
        return "LOW"
    return None


def paper_level_label(score: float) -> str:
    return paper_level(score) or "BELOW_LOW"


def now_utc_date_key() -> str:
    return datetime.now(tz=UTC).date().isoformat()


def paper_signal_context(evaluation_or_decision) -> dict[str, object]:
    return {
        "score": float(getattr(evaluation_or_decision, "setup_score", getattr(evaluation_or_decision, "total_score", 0.0))),
        "entry_reasons": list(getattr(evaluation_or_decision, "decision_trace", [])),
        "conditions_passed": list(getattr(evaluation_or_decision, "passed_filters", [])),
        "conditions_failed": list(getattr(evaluation_or_decision, "failed_filters", [])),
        "direction": str(getattr(evaluation_or_decision, "decision", getattr(evaluation_or_decision, "direction", "no_trade"))),
        "setup_type": str(getattr(evaluation_or_decision, "setup_type", "")),
    }


def build_paper_candidate_from_decision(
    *,
    symbol: str,
    direction: str,
    setup_type: str,
    evaluation_or_decision,
    risk_plan: RiskPlan,
    opened_at: str,
    source_key: str,
    snapshot: MarketSnapshot,
    higher_trend: str,
    entry_or_rejection_reason: str,
    expires_after_candles: int,
    setup_context: dict[str, object],
) -> PaperTradeCandidate | None:
    context = paper_signal_context(evaluation_or_decision)
    return build_paper_candidate_from_signal(
        symbol=symbol,
        direction=direction,
        setup_type=setup_type or str(context["setup_type"]),
        score=float(context["score"]),
        risk_plan=risk_plan,
        opened_at=opened_at,
        entry_reasons=[str(item) for item in context["entry_reasons"]],
        conditions_passed=[str(item) for item in context["conditions_passed"]],
        conditions_failed=[str(item) for item in context["conditions_failed"]],
        source_key=source_key,
        snapshot=snapshot,
        higher_trend=higher_trend,
        entry_or_rejection_reason=entry_or_rejection_reason,
        expires_after_candles=expires_after_candles,
        setup_context=setup_context,
    )


def build_paper_candidate_from_signal(
    *,
    symbol: str,
    direction: str,
    setup_type: str,
    score: float,
    risk_plan: RiskPlan,
    opened_at: str,
    entry_reasons: list[str],
    conditions_passed: list[str],
    conditions_failed: list[str],
    source_key: str,
    snapshot: MarketSnapshot,
    higher_trend: str,
    entry_or_rejection_reason: str,
    expires_after_candles: int,
    setup_context: dict[str, object],
) -> PaperTradeCandidate | None:
    level = paper_level(score)
    if level is None:
        return None
    risk = abs(risk_plan.entry - risk_plan.stop_loss)
    if risk <= 0:
        return None
    if direction == "long":
        take_profit_1 = risk_plan.entry + risk
    else:
        take_profit_1 = risk_plan.entry - risk
    rr_tp1 = abs(take_profit_1 - risk_plan.entry) / risk
    rr_tp2 = abs(risk_plan.take_profit - risk_plan.entry) / risk
    if rr_tp2 < 1.5:
        return None
    metadata = snapshot.metadata
    return PaperTradeCandidate(
        dedupe_key=f"{source_key}|paper",
        symbol=symbol,
        direction=direction,
        setup_type=setup_type,
        paper_level=level,
        score=round(score, 2),
        entry_price=risk_plan.entry,
        stop_loss=risk_plan.stop_loss,
        take_profit_1=round(take_profit_1, 6),
        take_profit_2=risk_plan.take_profit,
        risk_reward_tp1=round(rr_tp1, 4),
        risk_reward_tp2=round(rr_tp2, 4),
        opened_at=opened_at,
        expires_after_candles=expires_after_candles,
        rsi=float(metadata.get("rsi", 50.0)),
        volume_current=snapshot.volume,
        volume_average=float(metadata.get("volume_average_20", 0.0)),
        volume_ratio=float(metadata.get("volume_ratio_vs_average_20", 0.0)),
        trend_1h=snapshot.trend,
        trend_4h=higher_trend,
        break_of_structure=str(metadata.get("break_of_structure", "none")),
        nearest_distance_to_liquidity_atr=float(metadata.get("nearest_distance_to_liquidity_atr", snapshot.distance_to_liquidity_atr)),
        directional_distance_to_liquidity_atr=snapshot.distance_to_liquidity_atr,
        entry_or_rejection_reason=entry_or_rejection_reason,
        entry_reasons=entry_reasons,
        conditions_passed=conditions_passed,
        conditions_failed=conditions_failed,
        market_regime=str(setup_context.get("market_regime", "UNKNOWN")),
        session=str(setup_context.get("session", "UNKNOWN")),
        entry_context=str(setup_context.get("entry_context", "UNKNOWN")),
        trade_location=str(setup_context.get("trade_location", "UNKNOWN")),
        rr_valid=bool(setup_context.get("rr_valid", False)),
        sl_distance_atr=setup_context.get("sl_distance_atr"),  # type: ignore[arg-type]
        tp_distance_atr=setup_context.get("tp_distance_atr"),  # type: ignore[arg-type]
        late_entry_from_bos=bool(setup_context.get("late_entry_from_bos", False)),
        avoidance_warnings=list(setup_context.get("avoidance_warnings", [])),
    )


def estimate_spread_atr(snapshot: MarketSnapshot) -> float:
    return round(abs(snapshot.close - snapshot.open) / snapshot.atr, 6) if snapshot.atr > 0 else 999.0


def market_movement_ok(snapshot: MarketSnapshot, *, atr_min_threshold: float) -> bool:
    candle_range = snapshot.high - snapshot.low
    if candle_range <= 0 or snapshot.close <= 0:
        return False
    return (candle_range / snapshot.close) >= atr_min_threshold * 0.5


def paper_market_is_tradeable(snapshot: MarketSnapshot, *, atr_min_threshold: float, max_spread_atr: float) -> tuple[bool, str]:
    atr_ratio = snapshot.atr / snapshot.close if snapshot.close else 0.0
    if atr_ratio < atr_min_threshold:
        return False, "paper_rejected_atr_too_low"
    candle_range = snapshot.high - snapshot.low
    if snapshot.atr <= 0 or candle_range <= 0:
        return False, "paper_rejected_no_movement"
    estimated_spread_atr = estimate_spread_atr(snapshot)
    if estimated_spread_atr > max_spread_atr:
        return False, "paper_rejected_spread_too_high"
    if not market_movement_ok(snapshot, atr_min_threshold=atr_min_threshold):
        return False, "paper_rejected_market_without_movement"
    return True, "paper_tradeable"


def build_paper_rejection_diagnostic(
    *,
    symbol: str,
    score: float,
    snapshot: MarketSnapshot,
    atr_min_threshold: float,
    max_spread_atr: float,
    rr_tp1: float | None,
    rr_tp2: float | None,
    rejection_reason: str,
    setup_context: dict[str, object] | None = None,
) -> dict[str, object]:
    setup_context = setup_context or {}
    return {
        "symbol": symbol,
        "score": round(score, 2),
        "candidate_level_detected": paper_level_label(score),
        "rr_tp1": round(rr_tp1, 4) if rr_tp1 is not None else None,
        "rr_tp2": round(rr_tp2, 4) if rr_tp2 is not None else None,
        "atr": snapshot.atr,
        "atr_min_threshold": atr_min_threshold,
        "estimated_spread_atr": estimate_spread_atr(snapshot),
        "max_spread_atr": max_spread_atr,
        "market_movement_ok": market_movement_ok(snapshot, atr_min_threshold=atr_min_threshold),
        "paper_trade_rejection_reason": rejection_reason,
        "market_regime": setup_context.get("market_regime"),
        "session": setup_context.get("session"),
        "entry_context": setup_context.get("entry_context"),
        "trade_location": setup_context.get("trade_location"),
        "risk_context": {
            "rr_valid": setup_context.get("rr_valid"),
            "sl_distance_atr": setup_context.get("sl_distance_atr"),
            "tp_distance_atr": setup_context.get("tp_distance_atr"),
            "late_entry_from_bos": setup_context.get("late_entry_from_bos"),
        },
        "avoidance_warnings": setup_context.get("avoidance_warnings", []),
    }


def evaluate_trade_status(trade: dict[str, object], snapshot: MarketSnapshot) -> tuple[str, float, float, float]:
    direction = str(trade.get("direction"))
    entry = float(trade.get("entry_price") or 0.0)
    stop_loss = float(trade.get("stop_loss") or 0.0)
    take_profit_1 = float(trade.get("take_profit_1") or 0.0)
    take_profit_2 = float(trade.get("take_profit_2") or 0.0)
    risk = abs(entry - stop_loss)
    if risk <= 0:
        return "open", 0.0, 0.0, 0.0
    previous_status = str(trade.get("status", "open"))
    if direction == "long":
        mfe_r = (snapshot.high - entry) / risk
        mae_r = (snapshot.low - entry) / risk
        if snapshot.low <= stop_loss:
            return "sl_hit", -1.0, mfe_r, min(mae_r, -1.0)
        if snapshot.high >= take_profit_2:
            return "tp2_hit", abs(take_profit_2 - entry) / risk, mfe_r, mae_r
        if snapshot.high >= take_profit_1 or previous_status == "tp1_hit":
            return "tp1_hit", abs(take_profit_1 - entry) / risk, mfe_r, mae_r
        return "open", (snapshot.close - entry) / risk, mfe_r, mae_r
    if direction == "short":
        mfe_r = (entry - snapshot.low) / risk
        mae_r = (entry - snapshot.high) / risk
        if snapshot.high >= stop_loss:
            return "sl_hit", -1.0, mfe_r, min(mae_r, -1.0)
        if snapshot.low <= take_profit_2:
            return "tp2_hit", abs(entry - take_profit_2) / risk, mfe_r, mae_r
        if snapshot.low <= take_profit_1 or previous_status == "tp1_hit":
            return "tp1_hit", abs(entry - take_profit_1) / risk, mfe_r, mae_r
        return "open", (entry - snapshot.close) / risk, mfe_r, mae_r
    return "open", 0.0, 0.0, 0.0


def profit_factor(trades: list[dict[str, str]]) -> float:
    gross_win = sum(max(0.0, float(item.get("result_r") or 0.0)) for item in trades)
    gross_loss = abs(sum(min(0.0, float(item.get("result_r") or 0.0)) for item in trades))
    return round((gross_win / gross_loss) if gross_loss > 0 else (gross_win if gross_win > 0 else 0.0), 4)


def grouped_stats(trades: list[dict[str, str]], key: str) -> dict[str, dict[str, float | int]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for trade in trades:
        groups[str(trade.get(key, "UNKNOWN"))].append(trade)
    output: dict[str, dict[str, float | int]] = {}
    for name, items in groups.items():
        wins = len([item for item in items if item.get("status") == "tp2_hit"])
        output[name] = {
            "trades": len(items),
            "winrate": round((wins / len(items) * 100) if items else 0.0, 2),
            "profit_factor": profit_factor(items),
            "avg_r": round(sum(float(item.get("result_r") or 0.0) for item in items) / len(items), 4),
        }
    return output


def best_group(trades: list[dict[str, str]], key: str) -> str:
    stats = grouped_stats(trades, key)
    if not stats:
        return "sin_datos"
    return max(stats, key=lambda item: float(stats[item]["avg_r"]))


def worst_group(trades: list[dict[str, str]], key: str) -> str:
    stats = grouped_stats(trades, key)
    if not stats:
        return "sin_datos"
    return min(stats, key=lambda item: float(stats[item]["avg_r"]))


def automatic_recommendation(closed: list[dict[str, str]]) -> str:
    if len(closed) < 5:
        return "mantener: muestra insuficiente"
    pf = profit_factor(closed)
    winrate = len([item for item in closed if item.get("status") == "tp2_hit"]) / len(closed) * 100
    if pf >= 1.3 and winrate >= 45:
        return "mantener"
    if pf < 0.8 or winrate < 35:
        return "endurecer"
    return "relajar con cautela"


def format_paper_daily_summary_for_telegram(summary: dict[str, object]) -> str:
    by_level = summary.get("by_level", {})
    level_lines = []
    if isinstance(by_level, dict):
        for level in ("HIGH", "MEDIUM", "LOW"):
            stats = by_level.get(level, {})
            if isinstance(stats, dict):
                level_lines.append(
                    f"- {level}: WR {stats.get('winrate', 0)}% | PF {stats.get('profit_factor', 0)} | trades {stats.get('trades', 0)}"
                )
    levels_text = "\n".join(level_lines) if level_lines else "- Sin trades cerrados por nivel"
    context_lines = []
    for label, key in (
        ("Regime", "by_market_regime"),
        ("Session", "by_session"),
        ("Entry", "by_entry_context"),
        ("Location", "by_trade_location"),
    ):
        stats = summary.get(key, {})
        if isinstance(stats, dict) and stats:
            best = max(stats, key=lambda item: float(stats[item].get("avg_r", 0.0)))
            context_lines.append(f"- {label}: {best} avgR {stats[best].get('avg_r', 0)}")
    context_text = "\n".join(context_lines) if context_lines else "- Sin contexto ganador todavía"
    market_regime_perf = format_grouped_performance(summary.get("by_market_regime", {}))
    session_perf = format_grouped_performance(summary.get("by_session", {}))
    entry_context_perf = format_grouped_performance(summary.get("by_entry_context", {}))
    trade_location_perf = format_grouped_performance(summary.get("by_trade_location", {}))
    return (
        "📈 Resumen paper trading diario\n\n"
        f"Fecha: {summary.get('date')}\n"
        f"Trades simulados: {summary.get('simulated_trades', 0)}\n"
        f"Abiertos: {summary.get('open_trades', 0)}\n"
        f"Cerrados: {summary.get('closed_trades', 0)}\n"
        f"Ganadas: {summary.get('won', 0)} | Perdidas: {summary.get('lost', 0)} | Expired: {summary.get('expired', 0)}\n\n"
        "Por nivel:\n"
        f"{levels_text}\n\n"
        "Contextos destacados:\n"
        f"{context_text}\n\n"
        "Performance por market_regime:\n"
        f"{market_regime_perf}\n\n"
        "Performance por session:\n"
        f"{session_perf}\n\n"
        "Performance por entry_context:\n"
        f"{entry_context_perf}\n\n"
        "Performance por trade_location:\n"
        f"{trade_location_perf}\n\n"
        f"Winrate global: {summary.get('winrate', 0)}%\n"
        f"Profit factor global: {summary.get('profit_factor', 0)}\n"
        f"Mejor setup: {summary.get('best_setup', 'sin_datos')}\n"
        f"Peor setup: {summary.get('worst_setup', 'sin_datos')}\n"
        f"Mejor símbolo: {summary.get('best_symbol', 'sin_datos')}\n"
        f"Peor símbolo: {summary.get('worst_symbol', 'sin_datos')}\n"
        f"Recomendación: {summary.get('recommendation', 'mantener')}"
    )


def format_grouped_performance(stats: object) -> str:
    if not isinstance(stats, dict) or not stats:
        return "- Sin trades cerrados"
    lines = []
    for label, values in sorted(stats.items()):
        if not isinstance(values, dict):
            continue
        lines.append(
            f"- {label}: trades {values.get('trades', 0)} | WR {values.get('winrate', 0)}% | "
            f"PF {values.get('profit_factor', 0)} | avgR {values.get('avg_r', 0)}"
        )
    return "\n".join(lines) if lines else "- Sin trades cerrados"


def trade_status_counts(trades: list[dict[str, str]]) -> dict[str, int]:
    return dict(Counter(str(item.get("status", "unknown")) for item in trades))
