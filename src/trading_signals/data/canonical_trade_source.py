from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


CANONICAL_TRADES_RELATIVE_PATH = Path("paper_trading") / "trades.csv"
CLOSED_STATUSES = {"tp2_hit", "tp_hit", "sl_hit", "expired", "breakeven", "closed", "win", "loss"}
WIN_STATUSES = {"tp2_hit", "tp_hit", "win"}


def canonical_trades_path(data_path: Path) -> Path:
    return data_path / CANONICAL_TRADES_RELATIVE_PATH


def load_canonical_trade_rows(data_path: Path) -> list[dict[str, str]]:
    path = canonical_trades_path(data_path)
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except csv.Error:
        return []


def load_canonical_closed_trades(data_path: Path) -> list[dict[str, Any]]:
    return [
        trade
        for trade in (_normalize_trade(row, source=str(canonical_trades_path(data_path))) for row in load_canonical_trade_rows(data_path))
        if trade is not None
    ]


def canonical_trade_metrics(data_path: Path) -> dict[str, Any]:
    return compute_trade_metrics(load_canonical_closed_trades(data_path))


def compute_trade_metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = list(trades)
    values = [float(row["result_r"]) for row in ordered if row.get("result_r") is not None]
    wins = [row for row in ordered if is_win(row)]
    gross_profit = sum(max(0.0, value) for value in values)
    gross_loss = abs(sum(min(0.0, value) for value in values))
    max_drawdown, current_drawdown = drawdowns(values)
    return {
        "closed_trades": len(values),
        "wins": len(wins),
        "losses": len([value for value in values if value < 0]),
        "total_r": round(sum(values), 4),
        "winrate": round(len(wins) / len(values) * 100, 2) if values else 0.0,
        "avg_r": round(sum(values) / len(values), 4) if values else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else (round(gross_profit, 4) if gross_profit else 0.0),
        "max_drawdown": round(max_drawdown, 4),
        "current_drawdown": round(current_drawdown, 4),
    }


def is_win(trade: dict[str, Any]) -> bool:
    status = str(trade.get("status") or "").strip().lower()
    result_r = _float(trade.get("result_r")) or 0.0
    return status in WIN_STATUSES or result_r > 0


def drawdowns(values: list[float]) -> tuple[float, float]:
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        max_drawdown = min(max_drawdown, cumulative - peak)
    return max_drawdown, cumulative - peak


def normalize_for_research(row: dict[str, Any]) -> dict[str, Any] | None:
    return _normalize_trade(row, source=str(row.get("source_csv") or row.get("source") or "canonical"))


def tokens(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, set):
        return {str(item).strip() for item in value if str(item).strip()}
    if isinstance(value, list):
        return {str(item).strip() for item in value if str(item).strip()}
    text = str(value).strip()
    if not text:
        return set()
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        decoded = None
    if isinstance(decoded, list):
        return {str(item).strip() for item in decoded if str(item).strip()}
    return {item.strip() for item in text.replace("|", ",").replace(";", ",").split(",") if item.strip()}


def _normalize_trade(row: dict[str, Any], *, source: str) -> dict[str, Any] | None:
    result_r = _float(row.get("result_r") or row.get("r_result") or row.get("realized_r"))
    status = str(row.get("status") or row.get("outcome") or "").strip().lower()
    timestamp = _first_nonempty(row, ("closed_at", "updated_at", "evaluated_at", "exit_time", "opened_at", "created_at", "timestamp"))
    if result_r is None:
        return None
    if status and status not in CLOSED_STATUSES and not str(row.get("closed_at") or "").strip():
        return None
    normalized = {
        **row,
        "source": source,
        "source_csv": source,
        "timestamp": timestamp,
        "symbol": str(row.get("symbol") or "UNKNOWN").strip().upper(),
        "direction": str(row.get("direction") or "unknown").strip().lower(),
        "setup_type": str(row.get("setup_type") or "UNKNOWN").strip().upper(),
        "market_regime": _upper_or_unknown(row.get("market_regime")),
        "session": _upper_or_unknown(row.get("session")),
        "entry_context": _upper_or_unknown(row.get("entry_context")),
        "trade_location": str(row.get("trade_location") or "UNKNOWN").strip() or "UNKNOWN",
        "status": status,
        "result_r": result_r,
        "score": _float(row.get("score") or row.get("setup_score") or row.get("setup_score_final")),
        "volume_ratio": _float(row.get("volume_ratio") or row.get("volume_ratio_vs_average_20")),
        "body_ratio": _float(row.get("body_ratio")),
        "risk_reward": _float(row.get("risk_reward") or row.get("risk_reward_tp2") or row.get("rr")),
        "trend_entry": str(row.get("trend_entry") or row.get("trend_1h") or "").lower(),
        "trend_higher": str(row.get("trend_higher") or row.get("trend_4h") or row.get("trend_higher_timeframe") or "").lower(),
        "opened_hour_utc": str(row.get("opened_hour_utc") or _hour(timestamp)),
        "warnings": sorted(tokens(row.get("warnings") or row.get("avoidance_warnings"))),
        "avoidance_warnings": sorted(tokens(row.get("avoidance_warnings") or row.get("warnings"))),
        "penalties": sorted(tokens(row.get("penalties"))),
        "rejection_reasons": sorted(tokens(row.get("rejection_reasons") or row.get("conditions_failed") or row.get("entry_or_rejection_reason"))),
        "allowed": True,
        "blocked": False,
    }
    return normalized


def _first_nonempty(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _upper_or_unknown(value: object) -> str:
    text = str(value or "").strip()
    return text.upper() if text else "UNKNOWN"


def _hour(value: object) -> str:
    if not value:
        return "UNKNOWN"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return "UNKNOWN"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return str(parsed.astimezone(UTC).hour)


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
