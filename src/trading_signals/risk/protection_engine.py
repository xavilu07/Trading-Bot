from __future__ import annotations

import csv
import json
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


VALID_MODES = {"disabled", "shadow_only", "enforce_paper"}
CLOSED_STATUSES = {"tp2_hit", "tp_hit", "sl_hit", "expired", "breakeven", "closed"}
LOSS_STATUSES = {"sl_hit", "loss"}
WIN_OUTCOMES = {"win", "tp_hit", "tp2_hit"}
LOSS_OUTCOMES = {"loss", "sl_hit"}


@dataclass(frozen=True)
class ProtectionEngineConfig:
    mode: str = "shadow_only"
    symbol_loss_cooldown_hours: float = 6.0
    symbol_rejection_threshold: int = 3
    symbol_rejection_lookback_hours: float = 12.0
    symbol_rejection_cooldown_hours: float = 6.0
    max_drawdown_guard_r: float = 4.0
    max_drawdown_lookback_days: float = 7.0
    low_profit_min_trades: int = 5
    low_profit_min_avg_r: float = -0.2
    low_profit_lookback_days: float = 14.0
    toxic_context_shadow_enabled: bool = True


def evaluate_protection_engine(
    *,
    data_path: Path,
    symbol: str,
    direction: str,
    setup_type: str,
    setup_context: dict[str, Any] | None = None,
    config: ProtectionEngineConfig | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    cfg = config or ProtectionEngineConfig()
    mode = cfg.mode if cfg.mode in VALID_MODES else "shadow_only"
    now_dt = _aware(now or datetime.now(tz=UTC))
    context = setup_context or {}
    symbol_key = symbol.strip().upper()
    direction_key = direction.strip().lower()
    setup_type_key = setup_type.strip().upper()

    if mode == "disabled":
        return _result(
            mode=mode,
            symbol=symbol_key,
            direction=direction_key,
            setup_type=setup_type_key,
            context=context,
            triggers=[],
        )

    trades = _load_closed_trades(data_path)
    signals = _load_signal_rows(data_path / "bot_activity" / "signals_log.jsonl")
    triggers: list[dict[str, Any]] = []

    loss_trigger = _symbol_loss_cooldown(symbol_key, trades, cfg=cfg, now=now_dt)
    if loss_trigger:
        triggers.append(loss_trigger)

    rejection_trigger = _symbol_rejection_cooldown(symbol_key, signals, cfg=cfg, now=now_dt)
    if rejection_trigger:
        triggers.append(rejection_trigger)

    drawdown_trigger = _max_drawdown_guard(trades, cfg=cfg, now=now_dt)
    if drawdown_trigger:
        triggers.append(drawdown_trigger)

    low_profit_trigger = _low_profit_context_lock(
        trades,
        symbol=symbol_key,
        direction=direction_key,
        setup_type=setup_type_key,
        context=context,
        cfg=cfg,
        now=now_dt,
    )
    if low_profit_trigger:
        triggers.append(low_profit_trigger)

    toxic_trigger = _toxic_context_guard(direction_key, context, cfg=cfg)
    if toxic_trigger:
        triggers.append(toxic_trigger)

    return _result(
        mode=mode,
        symbol=symbol_key,
        direction=direction_key,
        setup_type=setup_type_key,
        context=context,
        triggers=triggers,
    )


def _result(
    *,
    mode: str,
    symbol: str,
    direction: str,
    setup_type: str,
    context: dict[str, Any],
    triggers: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "protection_mode": mode,
        "protection_triggered": bool(triggers),
        "protection_enforced": bool(triggers and mode == "enforce_paper"),
        "protection_reasons": [str(item.get("protection_reason", "unknown")) for item in triggers],
        "triggers": triggers,
        "affected_symbol": symbol,
        "affected_context": {
            "direction": direction,
            "setup_type": setup_type,
            "market_regime": context.get("market_regime"),
            "session": context.get("session"),
            "entry_context": context.get("entry_context"),
            "trade_location": context.get("trade_location"),
        },
    }


def _symbol_loss_cooldown(
    symbol: str,
    trades: list[dict[str, Any]],
    *,
    cfg: ProtectionEngineConfig,
    now: datetime,
) -> dict[str, Any] | None:
    losses = [
        trade for trade in trades
        if trade.get("symbol") == symbol and float(trade.get("result_r", 0.0)) < 0
    ]
    if not losses:
        return None
    last_loss = max(losses, key=lambda item: item["closed_at"])
    cooldown_until = last_loss["closed_at"] + timedelta(hours=cfg.symbol_loss_cooldown_hours)
    if now >= cooldown_until:
        return None
    return {
        "protection_reason": "symbol_loss_cooldown",
        "last_loss_time": last_loss["closed_at"].isoformat(),
        "cooldown_until": cooldown_until.isoformat(),
        "result_r": last_loss.get("result_r"),
    }


def _symbol_rejection_cooldown(
    symbol: str,
    signals: list[dict[str, Any]],
    *,
    cfg: ProtectionEngineConfig,
    now: datetime,
) -> dict[str, Any] | None:
    lookback_start = now - timedelta(hours=cfg.symbol_rejection_lookback_hours)
    rejected = [
        row for row in signals
        if str(row.get("symbol", "")).upper() == symbol
        and str(row.get("status", "")).lower() in {"rejected", "no_trade"}
        and _timestamp(row) is not None
        and _timestamp(row) >= lookback_start
    ]
    if len(rejected) < cfg.symbol_rejection_threshold:
        return None
    last_rejection_time = max(_timestamp(row) for row in rejected if _timestamp(row) is not None)
    if last_rejection_time is None:
        return None
    cooldown_until = last_rejection_time + timedelta(hours=cfg.symbol_rejection_cooldown_hours)
    if now >= cooldown_until:
        return None
    return {
        "protection_reason": "symbol_rejection_cooldown",
        "rejection_count": len(rejected),
        "threshold": cfg.symbol_rejection_threshold,
        "lookback_hours": cfg.symbol_rejection_lookback_hours,
        "cooldown_until": cooldown_until.isoformat(),
    }


def _max_drawdown_guard(
    trades: list[dict[str, Any]],
    *,
    cfg: ProtectionEngineConfig,
    now: datetime,
) -> dict[str, Any] | None:
    lookback_start = now - timedelta(days=cfg.max_drawdown_lookback_days)
    values = [
        float(trade["result_r"])
        for trade in trades
        if trade["closed_at"] >= lookback_start
    ]
    realized_r = round(sum(values), 4)
    if realized_r > -abs(cfg.max_drawdown_guard_r):
        return None
    return {
        "protection_reason": "max_drawdown_guard",
        "realized_r": realized_r,
        "threshold_r": -abs(cfg.max_drawdown_guard_r),
        "lookback_days": cfg.max_drawdown_lookback_days,
        "trades": len(values),
    }


def _low_profit_context_lock(
    trades: list[dict[str, Any]],
    *,
    symbol: str,
    direction: str,
    setup_type: str,
    context: dict[str, Any],
    cfg: ProtectionEngineConfig,
    now: datetime,
) -> dict[str, Any] | None:
    lookback_start = now - timedelta(days=cfg.low_profit_lookback_days)
    context_key = _context_key(
        symbol=symbol,
        direction=direction,
        setup_type=setup_type,
        market_regime=context.get("market_regime"),
        session=context.get("session"),
        entry_context=context.get("entry_context"),
        trade_location=context.get("trade_location"),
    )
    matches = [
        trade for trade in trades
        if trade["closed_at"] >= lookback_start
        and _context_key(
            symbol=str(trade.get("symbol", "")),
            direction=str(trade.get("direction", "")),
            setup_type=str(trade.get("setup_type", "")),
            market_regime=trade.get("market_regime"),
            session=trade.get("session"),
            entry_context=trade.get("entry_context"),
            trade_location=trade.get("trade_location"),
        ) == context_key
    ]
    if len(matches) < cfg.low_profit_min_trades:
        return None
    avg_r = round(sum(float(item["result_r"]) for item in matches) / len(matches), 4)
    if avg_r > cfg.low_profit_min_avg_r:
        return None
    return {
        "protection_reason": "low_profit_context_lock",
        "context_key": context_key,
        "trades": len(matches),
        "avg_r": avg_r,
        "threshold_avg_r": cfg.low_profit_min_avg_r,
    }


def _toxic_context_guard(
    direction: str,
    context: dict[str, Any],
    *,
    cfg: ProtectionEngineConfig,
) -> dict[str, Any] | None:
    if not cfg.toxic_context_shadow_enabled:
        return None
    session = str(context.get("session") or "").upper()
    market_regime = str(context.get("market_regime") or "").upper()
    reasons = []
    if session == "NEW_YORK":
        reasons.append("session_new_york")
    if market_regime == "HIGH_VOLATILITY" and direction == "long":
        reasons.append("high_volatility_long")
    if not reasons:
        return None
    return {
        "protection_reason": "toxic_context_guard",
        "toxic_reasons": reasons,
    }


def _load_closed_trades(data_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    paper_path = data_path / "paper_trading"
    if paper_path.exists():
        for path in sorted(paper_path.glob("*.csv")):
            rows.extend(_read_closed_trade_rows(path))
    rows.extend(_read_closed_trade_rows(data_path / "live_trading" / "trades.csv"))
    return rows


def _read_closed_trade_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                normalized = _normalize_trade_row(dict(row))
                if normalized is not None:
                    rows.append(normalized)
    except csv.Error:
        return []
    return rows


def _normalize_trade_row(row: dict[str, Any]) -> dict[str, Any] | None:
    closed_at = _closed_time(row)
    result_r = _result_r(row)
    if closed_at is None or result_r is None:
        return None
    return {
        "symbol": str(row.get("symbol", "")).upper(),
        "direction": str(row.get("direction", "")).lower(),
        "setup_type": str(row.get("setup_type", "")).upper(),
        "market_regime": row.get("market_regime"),
        "session": row.get("session"),
        "entry_context": row.get("entry_context"),
        "trade_location": row.get("trade_location"),
        "closed_at": closed_at,
        "result_r": result_r,
    }


def _load_signal_rows(path: Path, *, max_lines: int = 2000) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    rows = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            lines = deque(handle, maxlen=max_lines)
    except OSError:
        return []
    for line in lines:
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(raw, dict):
            rows.append(raw)
    return rows


def _closed_time(row: dict[str, Any]) -> datetime | None:
    status = str(row.get("status") or row.get("outcome") or "").strip().lower()
    has_closed_status = status in CLOSED_STATUSES or status in WIN_OUTCOMES or status in LOSS_OUTCOMES
    for key in ("closed_at", "evaluated_at", "updated_at", "exit_time", "timestamp"):
        raw = str(row.get(key) or "").strip()
        if not raw:
            continue
        parsed = _parse_datetime(raw)
        if parsed is not None and (has_closed_status or key in {"closed_at", "evaluated_at", "exit_time"}):
            return parsed
    return None


def _result_r(row: dict[str, Any]) -> float | None:
    for key in ("result_r", "r_result", "realized_r"):
        value = _float(row.get(key))
        if value is not None:
            return value
    outcome = str(row.get("outcome") or row.get("status") or "").strip().lower()
    if outcome in WIN_OUTCOMES:
        return 1.0
    if outcome in LOSS_OUTCOMES:
        return -1.0
    return None


def _context_key(
    *,
    symbol: str,
    direction: str,
    setup_type: str,
    market_regime: Any,
    session: Any,
    entry_context: Any,
    trade_location: Any,
) -> str:
    return "|".join(
        [
            symbol.strip().upper(),
            direction.strip().lower(),
            setup_type.strip().upper(),
            str(market_regime or "").strip().upper(),
            str(session or "").strip().upper(),
            str(entry_context or "").strip().upper(),
            str(trade_location or "").strip(),
        ]
    )


def _timestamp(row: dict[str, Any]) -> datetime | None:
    for key in ("timestamp", "created_at", "opened_at", "closed_at"):
        parsed = _parse_datetime(str(row.get(key) or ""))
        if parsed is not None:
            return parsed
    return None


def _parse_datetime(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        return _aware(datetime.fromisoformat(raw.replace("Z", "+00:00")))
    except ValueError:
        return None


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
