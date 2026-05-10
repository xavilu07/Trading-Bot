from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from trading_signals.domain.entities.market_snapshot import MarketSnapshot
from trading_signals.domain.entities.risk_plan import RiskPlan
from trading_signals.domain.entities.trade_signal import TradeSignal


LIVE_TRADE_FIELDS = [
    "trade_id",
    "dedupe_key",
    "created_at",
    "symbol",
    "direction",
    "setup_type",
    "signal_type",
    "score",
    "entry",
    "stop_loss",
    "take_profit",
    "risk_reward",
    "market_regime",
    "session",
    "entry_context",
    "trade_location",
    "liquidity_sweep",
    "market_structure",
    "warnings",
    "penalties",
    "reasons",
    "status",
    "result_r",
    "closed_at",
    "breakeven_triggered",
    "breakeven_alert_sent_at",
    "partial_tp_suggested",
    "partial_tp_alert_sent_at",
    "public_published",
    "public_update_events_sent",
    "updated_at",
]


@dataclass(slots=True)
class LiveTradeCandidate:
    dedupe_key: str
    created_at: str
    symbol: str
    direction: str
    setup_type: str
    signal_type: str
    score: float
    entry: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    market_regime: str
    session: str
    entry_context: str
    trade_location: str
    liquidity_sweep: str
    market_structure: str
    warnings: list[str]
    penalties: list[str]
    reasons: list[str]
    public_published: bool = False


class LiveTradingStore:
    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path
        self.trades_file = base_path / "live_trading" / "trades.csv"

    def list_trades(self) -> list[dict[str, str]]:
        if not self.trades_file.exists():
            return []
        with self.trades_file.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def save_trades(self, trades: list[dict[str, object]]) -> None:
        self.trades_file.parent.mkdir(parents=True, exist_ok=True)
        temp = self.trades_file.with_suffix(".csv.tmp")
        with temp.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=LIVE_TRADE_FIELDS)
            writer.writeheader()
            for trade in trades:
                writer.writerow({field: trade.get(field, "") for field in LIVE_TRADE_FIELDS})
        temp.replace(self.trades_file)

    def upsert_candidate(self, candidate: LiveTradeCandidate) -> bool:
        trades: list[dict[str, object]] = list(self.list_trades())
        if any(item.get("dedupe_key") == candidate.dedupe_key for item in trades):
            return False
        row = asdict(candidate)
        row.update(
            {
                "trade_id": f"live_{uuid4().hex[:12]}",
                "warnings": json.dumps(candidate.warnings, ensure_ascii=False),
                "penalties": json.dumps(candidate.penalties, ensure_ascii=False),
                "reasons": json.dumps(candidate.reasons, ensure_ascii=False),
                "status": "open",
                "result_r": "0",
                "closed_at": "",
                "breakeven_triggered": "false",
                "breakeven_alert_sent_at": "",
                "partial_tp_suggested": "false",
                "partial_tp_alert_sent_at": "",
                "public_published": str(candidate.public_published).lower(),
                "public_update_events_sent": "[]",
                "updated_at": candidate.created_at,
            }
        )
        trades.append(row)
        self.save_trades(trades)
        return True

    def update_open_trades_for_snapshot(
        self,
        snapshot: MarketSnapshot,
        *,
        updated_at: str,
        breakeven_enabled: bool,
        breakeven_trigger_r: float,
        partial_tp_enabled: bool,
        partial_tp_trigger_r: float,
    ) -> list[dict[str, object]]:
        trades: list[dict[str, object]] = list(self.list_trades())
        events: list[dict[str, object]] = []
        changed = False
        for trade in trades:
            if trade.get("symbol") != snapshot.symbol or trade.get("status") != "open":
                continue
            status, result_r, current_r = evaluate_live_trade(trade, snapshot)
            trade["updated_at"] = updated_at
            if status in {"tp_hit", "sl_hit"}:
                trade["status"] = status
                trade["result_r"] = f"{result_r:.4f}"
                trade["closed_at"] = updated_at
                events.append({"event_type": status, "trade": dict(trade), "current_price": snapshot.close})
                changed = True
                continue
            if breakeven_enabled and current_r >= breakeven_trigger_r and str(trade.get("breakeven_triggered", "false")).lower() != "true":
                trade["breakeven_triggered"] = "true"
                trade["breakeven_alert_sent_at"] = updated_at
                events.append({"event_type": "breakeven", "trade": dict(trade), "current_price": snapshot.close, "current_r": current_r})
                changed = True
            if partial_tp_enabled and current_r >= partial_tp_trigger_r and str(trade.get("partial_tp_suggested", "false")).lower() != "true":
                trade["partial_tp_suggested"] = "true"
                trade["partial_tp_alert_sent_at"] = updated_at
                events.append({"event_type": "partial_tp", "trade": dict(trade), "current_price": snapshot.close, "current_r": current_r})
                changed = True
        if changed:
            self.save_trades(trades)
        return events

    def build_daily_summary(self, date_key: str) -> dict[str, object]:
        trades = [item for item in self.list_trades() if str(item.get("created_at", "")).startswith(date_key)]
        closed = [item for item in trades if item.get("status") in {"tp_hit", "sl_hit", "breakeven", "expired"}]
        wins = [item for item in closed if item.get("status") == "tp_hit"]
        losses = [item for item in closed if item.get("status") == "sl_hit"]
        return {
            "date": date_key,
            "open_trades": len([item for item in trades if item.get("status") == "open"]),
            "closed_trades": len(closed),
            "won": len(wins),
            "lost": len(losses),
            "winrate": round((len(wins) / len(closed) * 100) if closed else 0.0, 2),
            "profit_factor": profit_factor(closed),
            "avg_r": round(sum(float(item.get("result_r") or 0.0) for item in closed) / len(closed), 4) if closed else 0.0,
            "best_setup": best_group(closed, "setup_type"),
            "worst_setup": worst_group(closed, "setup_type"),
            "best_symbol": best_group(closed, "symbol"),
            "worst_symbol": worst_group(closed, "symbol"),
        }


def now_utc_date_key() -> str:
    return datetime.now(tz=UTC).date().isoformat()


def live_signal_context(evaluation_or_decision) -> dict[str, object]:
    reasons = list(getattr(evaluation_or_decision, "decision_trace", []))
    return {
        "score": float(getattr(evaluation_or_decision, "setup_score", getattr(evaluation_or_decision, "total_score", 0.0))),
        "reasons": reasons,
        "setup_type": str(getattr(evaluation_or_decision, "setup_type", "")),
        "penalties": _penalties_from_trace(reasons),
    }


def _penalties_from_trace(trace: list[object]) -> list[str]:
    for item in trace:
        text = str(item)
        if not text.startswith("penalties="):
            continue
        raw = text.split("=", 1)[1]
        if raw == "none":
            return []
        return [part.strip() for part in raw.split(",") if part.strip()]
    return []


def build_live_candidate_from_decision(
    *,
    signal: TradeSignal,
    setup_type: str,
    evaluation_or_decision,
    risk_plan: RiskPlan,
    setup_context: dict[str, object],
    public_published: bool = False,
) -> LiveTradeCandidate:
    context = live_signal_context(evaluation_or_decision)
    return build_live_candidate_from_signal(
        signal=signal,
        setup_type=setup_type or str(context["setup_type"]),
        score=float(context["score"]),
        risk_plan=risk_plan,
        setup_context=setup_context,
        reasons=[str(item) for item in context["reasons"]],
        penalties=[str(item) for item in context["penalties"]],
        public_published=public_published,
    )


def build_live_candidate_from_signal(
    *,
    signal: TradeSignal,
    setup_type: str,
    score: float,
    risk_plan: RiskPlan,
    setup_context: dict[str, object],
    reasons: list[str],
    penalties: list[str] | None = None,
    public_published: bool = False,
) -> LiveTradeCandidate:
    return LiveTradeCandidate(
        dedupe_key=signal.dedupe_key,
        created_at=signal.published_at or signal.created_at,
        symbol=signal.symbol,
        direction=signal.decision,
        setup_type=setup_type,
        signal_type=signal.signal_type,
        score=round(score, 2),
        entry=risk_plan.entry,
        stop_loss=risk_plan.stop_loss,
        take_profit=risk_plan.take_profit,
        risk_reward=risk_plan.risk_reward,
        market_regime=str(setup_context.get("market_regime", "UNKNOWN")),
        session=str(setup_context.get("session", "UNKNOWN")),
        entry_context=str(setup_context.get("entry_context", "UNKNOWN")),
        trade_location=str(setup_context.get("trade_location", "UNKNOWN")),
        liquidity_sweep=str(setup_context.get("liquidity_sweep", "UNKNOWN")),
        market_structure=str(setup_context.get("market_structure", "UNKNOWN")),
        warnings=list(setup_context.get("avoidance_warnings", [])),
        penalties=list(penalties or setup_context.get("penalties", []) or []),
        reasons=reasons,
        public_published=public_published,
    )


def evaluate_live_trade(trade: dict[str, object], snapshot: MarketSnapshot) -> tuple[str, float, float]:
    direction = str(trade.get("direction"))
    entry = float(trade.get("entry") or 0.0)
    stop_loss = float(trade.get("stop_loss") or 0.0)
    take_profit = float(trade.get("take_profit") or 0.0)
    risk = abs(entry - stop_loss)
    if risk <= 0:
        return "open", 0.0, 0.0
    if direction == "long":
        current_r = (snapshot.close - entry) / risk
        if snapshot.low <= stop_loss:
            return "sl_hit", -1.0, current_r
        if snapshot.high >= take_profit:
            return "tp_hit", abs(take_profit - entry) / risk, current_r
        return "open", current_r, current_r
    if direction == "short":
        current_r = (entry - snapshot.close) / risk
        if snapshot.high >= stop_loss:
            return "sl_hit", -1.0, current_r
        if snapshot.low <= take_profit:
            return "tp_hit", abs(entry - take_profit) / risk, current_r
        return "open", current_r, current_r
    return "open", 0.0, 0.0


def format_live_trade_event_for_telegram(event: dict[str, object], *, partial_percentage: str = "30-50") -> str:
    trade = event.get("trade", {})
    if not isinstance(trade, dict):
        trade = {}
    event_type = str(event.get("event_type"))
    direction = str(trade.get("direction", "-")).upper()
    setup = str(trade.get("setup_type", "-"))
    if event_type == "tp_hit":
        return (
            "✅ TP alcanzado\n"
            f"- Símbolo: {trade.get('symbol', '-')}\n"
            f"- Dirección: {direction}\n"
            f"- Setup: {setup}\n"
            f"- Entry: {trade.get('entry', '-')}\n"
            f"- TP: {trade.get('take_profit', '-')}\n"
            f"- Resultado: {trade.get('result_r', '0')}R"
        )
    if event_type == "sl_hit":
        return (
            "❌ SL alcanzado\n"
            f"- Símbolo: {trade.get('symbol', '-')}\n"
            f"- Dirección: {direction}\n"
            f"- Setup: {setup}\n"
            f"- Entry: {trade.get('entry', '-')}\n"
            f"- SL: {trade.get('stop_loss', '-')}\n"
            f"- Resultado: {trade.get('result_r', '0')}R"
        )
    if event_type == "breakeven":
        return (
            "🛡️ Break-even sugerido\n"
            f"- Símbolo: {trade.get('symbol', '-')}\n"
            f"- Dirección: {direction}\n"
            f"- Precio actual: {event.get('current_price', '-')}\n"
            f"- Entry: {trade.get('entry', '-')}\n"
            "- Sugerencia: mover SL a entrada"
        )
    if event_type == "partial_tp":
        return (
            "💰 TP parcial sugerido\n"
            f"- Símbolo: {trade.get('symbol', '-')}\n"
            f"- Dirección: {direction}\n"
            f"- Precio actual: {event.get('current_price', '-')}\n"
            f"- Sugerencia: cerrar {partial_percentage}%"
        )
    return ""


def is_public_live_trade_event(event: dict[str, object]) -> bool:
    trade = event.get("trade", {})
    if not isinstance(trade, dict):
        return False
    return str(trade.get("public_published", "false")).lower() == "true"


def format_public_live_trade_event_for_telegram(event: dict[str, object]) -> str:
    if not is_public_live_trade_event(event):
        return ""
    trade = event.get("trade", {})
    if not isinstance(trade, dict):
        trade = {}
    direction = str(trade.get("direction", "")).lower()
    emoji = "🟢" if direction == "long" else "🔴"
    symbol = _public_symbol(str(trade.get("symbol", "-")))
    event_type = str(event.get("event_type"))
    if event_type == "tp_hit":
        return (
            "✅ TP1 ALCANZADO\n\n"
            f"{emoji} {symbol}\n"
            f"📍 Entry: {trade.get('entry', '-')}\n"
            f"🎯 TP1: {trade.get('take_profit', '-')}\n\n"
            "🔥 Recomendado:\n"
            "Cerrar parcial y proteger operación.\n\n"
            "🛡️ Gestiona tu capital con responsabilidad."
        )
    if event_type == "sl_hit":
        return (
            "🛑 STOP LOSS TOCADO\n\n"
            f"{emoji} {symbol}\n"
            "Operación cerrada por SL.\n\n"
            "Gestionar riesgo es parte del sistema."
        )
    if event_type == "breakeven":
        return (
            "🛡️ BREAK EVEN\n\n"
            f"{emoji} {symbol}\n"
            "SL recomendado a precio de entrada.\n\n"
            "La operación queda protegida."
        )
    if event_type == "partial_tp":
        return (
            "💰 CIERRE PARCIAL RECOMENDADO\n\n"
            f"{emoji} {symbol}\n"
            "Cerrar parcial y proteger operación.\n\n"
            "🛡️ Gestiona tu capital con responsabilidad."
        )
    return ""


def _public_symbol(symbol: str) -> str:
    if symbol.endswith("USDT") and len(symbol) > 4:
        return f"{symbol[:-4]}/USDT"
    return symbol


def format_live_daily_summary_for_telegram(summary: dict[str, object]) -> str:
    return (
        "📌 Resumen live trading diario\n\n"
        f"Fecha: {summary.get('date')}\n"
        f"Abiertos: {summary.get('open_trades', 0)}\n"
        f"Cerrados: {summary.get('closed_trades', 0)}\n"
        f"Ganadas: {summary.get('won', 0)} | Perdidas: {summary.get('lost', 0)}\n"
        f"Winrate: {summary.get('winrate', 0)}%\n"
        f"Profit factor: {summary.get('profit_factor', 0)}\n"
        f"AvgR: {summary.get('avg_r', 0)}\n"
        f"Mejor setup: {summary.get('best_setup', 'sin_datos')}\n"
        f"Peor setup: {summary.get('worst_setup', 'sin_datos')}\n"
        f"Mejor símbolo: {summary.get('best_symbol', 'sin_datos')}\n"
        f"Peor símbolo: {summary.get('worst_symbol', 'sin_datos')}"
    )


def profit_factor(trades: list[dict[str, str]]) -> float:
    gross_win = sum(max(0.0, float(item.get("result_r") or 0.0)) for item in trades)
    gross_loss = abs(sum(min(0.0, float(item.get("result_r") or 0.0)) for item in trades))
    return round((gross_win / gross_loss) if gross_loss > 0 else (gross_win if gross_win > 0 else 0.0), 4)


def grouped_stats(trades: list[dict[str, str]], key: str) -> dict[str, float]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for trade in trades:
        groups[str(trade.get(key, "UNKNOWN"))].append(trade)
    return {
        name: round(sum(float(item.get("result_r") or 0.0) for item in items) / len(items), 4)
        for name, items in groups.items()
    }


def best_group(trades: list[dict[str, str]], key: str) -> str:
    stats = grouped_stats(trades, key)
    if not stats:
        return "sin_datos"
    return max(stats, key=lambda item: stats[item])


def worst_group(trades: list[dict[str, str]], key: str) -> str:
    stats = grouped_stats(trades, key)
    if not stats:
        return "sin_datos"
    return min(stats, key=lambda item: stats[item])
