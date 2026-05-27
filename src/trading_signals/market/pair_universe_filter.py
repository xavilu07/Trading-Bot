from __future__ import annotations

import csv
import json
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


VALID_MODES = {"disabled", "shadow_only", "enforce_paper"}


@dataclass(frozen=True)
class PairUniverseFilterConfig:
    mode: str = "shadow_only"
    min_volume: float = 0.0
    max_spread_pct: float = 5.0
    min_volatility_pct: float = 0.1
    max_volatility_pct: float = 25.0
    min_history_candles: int = 220
    blacklist: list[str] = field(default_factory=list)
    whitelist: list[str] = field(default_factory=list)
    rejection_threshold: int = 5
    rejection_lookback_hours: float = 24.0
    min_recent_avg_r: float = -0.5
    performance_min_trades: int = 3
    performance_lookback_days: float = 14.0


def evaluate_pair_universe(
    *,
    symbols: list[str],
    fetch_ohlcv,
    data_path: Path,
    timeframe: str,
    config: PairUniverseFilterConfig | None = None,
    provider: str = "unknown",
    now: datetime | None = None,
) -> dict[str, Any]:
    cfg = config or PairUniverseFilterConfig()
    mode = cfg.mode if cfg.mode in VALID_MODES else "shadow_only"
    now_dt = _aware(now or datetime.now(tz=UTC))
    if mode == "disabled":
        return {
            "mode": mode,
            "provider": provider,
            "requested_symbols": len(symbols),
            "passed_symbols": list(symbols),
            "failed_symbols": [],
            "excluded_if_enforced": [],
            "reason_counts": {},
            "impact_estimate": {"would_exclude": 0, "would_analyze": len(symbols)},
        }

    signals = _load_signal_rows(data_path / "bot_activity" / "signals_log.jsonl")
    trades = _load_closed_trades(data_path)
    passed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for symbol in symbols:
        symbol_key = symbol.strip().upper()
        reasons: list[str] = []
        metrics: dict[str, Any] = {}

        if cfg.whitelist and symbol_key not in {item.upper() for item in cfg.whitelist}:
            reasons.append("not_in_whitelist")
        if symbol_key in {item.upper() for item in cfg.blacklist}:
            reasons.append("blacklisted")

        candles = _safe_fetch(fetch_ohlcv, symbol_key, timeframe, limit=max(cfg.min_history_candles, 300))
        metrics.update(_candle_metrics(candles))
        if len(candles) < cfg.min_history_candles:
            reasons.append("insufficient_history")
        if metrics.get("volume", 0.0) < cfg.min_volume:
            reasons.append("volume_below_min")
        if metrics.get("spread_pct") is not None and metrics["spread_pct"] > cfg.max_spread_pct:
            reasons.append("spread_above_max")
        if metrics.get("volatility_pct") is not None:
            if metrics["volatility_pct"] < cfg.min_volatility_pct:
                reasons.append("volatility_below_min")
            if metrics["volatility_pct"] > cfg.max_volatility_pct:
                reasons.append("volatility_above_max")

        rejection_count = _recent_rejection_count(symbol_key, signals, now=now_dt, lookback_hours=cfg.rejection_lookback_hours)
        metrics["recent_rejections"] = rejection_count
        if rejection_count >= cfg.rejection_threshold:
            reasons.append("too_many_recent_rejections")

        performance = _recent_performance(symbol_key, trades, now=now_dt, cfg=cfg)
        metrics.update(performance)
        if (
            performance["trades"] >= cfg.performance_min_trades
            and performance["avg_r"] <= cfg.min_recent_avg_r
        ):
            reasons.append("recent_performance_too_negative")

        row = {
            "symbol": symbol_key,
            "passed": not reasons,
            "reasons": _dedupe(reasons),
            "mode": mode,
            "provider": provider,
            "metrics": metrics,
        }
        if reasons:
            failed.append(row)
        else:
            passed.append(row)

    reason_counts = Counter(reason for item in failed for reason in item["reasons"])
    excluded = [item["symbol"] for item in failed]
    return {
        "mode": mode,
        "provider": provider,
        "requested_symbols": len(symbols),
        "passed_symbols": [item["symbol"] for item in passed],
        "failed_symbols": failed,
        "excluded_if_enforced": excluded,
        "reason_counts": dict(reason_counts),
        "impact_estimate": {
            "would_exclude": len(excluded),
            "would_analyze": len(symbols) if mode == "shadow_only" else len(passed),
            "current_mode_keeps_all": mode == "shadow_only",
        },
    }


def _safe_fetch(fetch_ohlcv, symbol: str, timeframe: str, *, limit: int) -> list[dict[str, Any]]:
    try:
        rows = fetch_ohlcv(symbol, timeframe, limit=limit)
    except Exception:
        return []
    return [dict(row) for row in rows if isinstance(row, dict)]


def _candle_metrics(candles: list[dict[str, Any]]) -> dict[str, Any]:
    if not candles:
        return {"history_candles": 0, "volume": 0.0, "spread_pct": None, "volatility_pct": None}
    last = candles[-1]
    close = _float(last.get("close")) or 0.0
    high = _float(last.get("high")) or close
    low = _float(last.get("low")) or close
    open_ = _float(last.get("open")) or close
    volume = _float(last.get("volume")) or 0.0
    spread_pct = abs(close - open_) / close * 100 if close > 0 else None
    volatility_pct = (high - low) / close * 100 if close > 0 else None
    return {
        "history_candles": len(candles),
        "volume": volume,
        "spread_pct": round(spread_pct, 6) if spread_pct is not None else None,
        "volatility_pct": round(volatility_pct, 6) if volatility_pct is not None else None,
    }


def _recent_rejection_count(symbol: str, rows: list[dict[str, Any]], *, now: datetime, lookback_hours: float) -> int:
    start = now - timedelta(hours=lookback_hours)
    count = 0
    for row in rows:
        if str(row.get("symbol", "")).upper() != symbol:
            continue
        if str(row.get("status", "")).lower() not in {"rejected", "no_trade"}:
            continue
        timestamp = _timestamp(row)
        if timestamp is not None and timestamp >= start:
            count += 1
    return count


def _recent_performance(symbol: str, trades: list[dict[str, Any]], *, now: datetime, cfg: PairUniverseFilterConfig) -> dict[str, Any]:
    start = now - timedelta(days=cfg.performance_lookback_days)
    values = [
        float(row["result_r"])
        for row in trades
        if row["symbol"] == symbol and row["closed_at"] >= start
    ]
    avg_r = round(sum(values) / len(values), 4) if values else 0.0
    return {"trades": len(values), "avg_r": avg_r, "total_r": round(sum(values), 4)}


def _load_signal_rows(path: Path, *, max_lines: int = 3000) -> list[dict[str, Any]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            lines = deque(handle, maxlen=max_lines)
    except OSError:
        return []
    rows = []
    for line in lines:
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(raw, dict):
            rows.append(raw)
    return rows


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
                parsed = _normalize_trade_row(dict(row))
                if parsed is not None:
                    rows.append(parsed)
    except csv.Error:
        return []
    return rows


def _normalize_trade_row(row: dict[str, Any]) -> dict[str, Any] | None:
    closed_at = _closed_time(row)
    result_r = _result_r(row)
    if closed_at is None or result_r is None:
        return None
    return {"symbol": str(row.get("symbol", "")).upper(), "closed_at": closed_at, "result_r": result_r}


def _closed_time(row: dict[str, Any]) -> datetime | None:
    for key in ("closed_at", "evaluated_at", "updated_at", "exit_time", "timestamp"):
        parsed = _parse_datetime(str(row.get(key) or ""))
        if parsed is not None:
            return parsed
    return None


def _result_r(row: dict[str, Any]) -> float | None:
    for key in ("result_r", "r_result", "realized_r"):
        value = _float(row.get(key))
        if value is not None:
            return value
    return None


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
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _aware(value)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
