from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from trading_signals.research.statistics import to_float


DEFAULT_DATA_PATH = Path("data")


def load_research_dataset(data_path: Path = DEFAULT_DATA_PATH) -> dict[str, Any]:
    trades_path = data_path / "paper_trading" / "trades.csv"
    raw_rows = _read_csv(trades_path)
    rows = [normalize_trade(row) for row in raw_rows]
    return {
        "source": str(trades_path),
        "rows": rows,
        "columns": list(raw_rows[0].keys()) if raw_rows else [],
        "auxiliary_sources": auxiliary_sources(data_path),
    }


def normalize_trade(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    direction = _lower(row.get("direction"))
    score = to_float(row.get("score"))
    rr = to_float(row.get("risk_reward_tp2") or row.get("risk_reward") or row.get("rr"))
    volume_ratio = to_float(row.get("volume_ratio"))
    rsi = to_float(row.get("rsi"))
    liquidity_distance = to_float(
        row.get("directional_distance_to_liquidity_atr")
        or row.get("nearest_distance_to_liquidity_atr")
        or row.get("distance_to_liquidity_atr")
    )
    candles_held = to_float(row.get("candles_held") or row.get("bars_held"))
    normalized.update(
        {
            "symbol": _upper(row.get("symbol")),
            "direction": direction,
            "setup": _upper(row.get("setup_type") or row.get("setup")),
            "setup_type": _upper(row.get("setup_type") or row.get("setup")),
            "strategy": _text(row.get("strategy") or row.get("strategy_id") or "liquidity_sweep_mtf_v1"),
            "session": _upper(row.get("session")),
            "utc_hour": _text(row.get("opened_hour_utc") or _hour_from_timestamp(row.get("opened_at"))),
            "market_regime": _upper(row.get("market_regime")),
            "location": _text(row.get("trade_location") or row.get("location")),
            "trade_location": _text(row.get("trade_location") or row.get("location")),
            "entry_zone": _upper(row.get("entry_context") or row.get("entry_zone")),
            "entry_context": _upper(row.get("entry_context") or row.get("entry_zone")),
            "score": score,
            "score_bucket": score_bucket(score),
            "rr": rr,
            "rr_bucket": rr_bucket(rr),
            "volume_ratio": volume_ratio,
            "volume_ratio_bucket": volume_bucket(volume_ratio),
            "rsi": rsi,
            "rsi_bucket": rsi_bucket(rsi),
            "bos": _text(row.get("break_of_structure") or row.get("bos")),
            "break_of_structure": _text(row.get("break_of_structure") or row.get("bos")),
            "liquidity_sweep": _text(row.get("liquidity_sweep") or _extract_token(row, "liquidity_sweep")),
            "liquidity_distance": liquidity_distance,
            "liquidity_distance_bucket": distance_bucket(liquidity_distance),
            "htf_alignment": alignment(direction, row.get("trend_4h")),
            "ltf_alignment": alignment(direction, row.get("trend_1h")),
            "trend_1h": _lower(row.get("trend_1h")),
            "trend_4h": _lower(row.get("trend_4h")),
            "atr": to_float(row.get("atr") or row.get("sl_distance_atr") or row.get("tp_distance_atr")),
            "holding_candles": candles_held,
            "holding_candles_bucket": holding_bucket(candles_held),
            "holding_hours": candles_held,
            "status": _lower(row.get("status")),
            "result_r": to_float(row.get("result_r")),
            "outcome": outcome(row),
            "warnings": _text(row.get("avoidance_warnings")),
            "penalties": _text(row.get("penalties")),
            "conditions_failed": _text(row.get("conditions_failed")),
            "rejection_reason": _text(row.get("entry_or_rejection_reason")),
        }
    )
    return normalized


def auxiliary_sources(data_path: Path) -> dict[str, Any]:
    trade_signal_files = list((data_path / "trade_signals").glob("**/*.json"))
    pattern_path = data_path / "pattern_memory" / "patterns.jsonl"
    reports_path = data_path.parent / "reports"
    return {
        "trade_signals_files": len(trade_signal_files),
        "pattern_memory_records": _count_lines(pattern_path),
        "historical_reports_found": len(list(reports_path.glob("*.json"))) if reports_path.exists() else 0,
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _extract_token(row: dict[str, Any], token: str) -> str:
    text = " ".join(str(row.get(field) or "") for field in ("entry_reasons", "conditions_failed", "avoidance_warnings"))
    if token not in text:
        return ""
    try:
        parsed = json.loads(row.get("entry_reasons") or "[]")
    except json.JSONDecodeError:
        return token
    for item in parsed:
        if token in str(item):
            return str(item).split("=", 1)[-1]
    return token


def outcome(row: dict[str, Any]) -> str:
    result = to_float(row.get("result_r"))
    if result is None:
        return "open"
    if result > 0:
        return "win"
    if result < 0:
        return "loss"
    return "neutral"


def alignment(direction: str, trend: Any) -> str:
    trend_value = _lower(trend)
    if direction == "long" and trend_value == "bullish":
        return "aligned"
    if direction == "short" and trend_value == "bearish":
        return "aligned"
    if direction in {"long", "short"} and trend_value in {"bullish", "bearish"}:
        return "against"
    return "unknown"


def score_bucket(score: float | None) -> str:
    if score is None:
        return "UNKNOWN"
    if score < 50:
        return "0-49"
    if score < 60:
        return "50-59"
    if score < 70:
        return "60-69"
    if score < 80:
        return "70-79"
    if score < 90:
        return "80-89"
    return "90-100"


def rr_bucket(rr: float | None) -> str:
    if rr is None:
        return "UNKNOWN"
    if rr < 1:
        return "<1"
    if rr < 1.5:
        return "1-1.49"
    if rr < 2:
        return "1.5-1.99"
    if rr < 3:
        return "2-2.99"
    return "3+"


def volume_bucket(value: float | None) -> str:
    if value is None:
        return "UNKNOWN"
    if value < 0.8:
        return "low"
    if value < 1.2:
        return "normal"
    if value < 1.8:
        return "high"
    return "very_high"


def rsi_bucket(value: float | None) -> str:
    if value is None:
        return "UNKNOWN"
    if value < 30:
        return "oversold"
    if value < 45:
        return "weak"
    if value <= 55:
        return "neutral"
    if value <= 70:
        return "strong"
    return "overbought"


def distance_bucket(value: float | None) -> str:
    if value is None:
        return "UNKNOWN"
    if value < 1:
        return "<1atr"
    if value < 2:
        return "1-2atr"
    if value < 4:
        return "2-4atr"
    return "4atr+"


def holding_bucket(value: float | None) -> str:
    if value is None:
        return "UNKNOWN"
    if value <= 3:
        return "0-3"
    if value <= 8:
        return "4-8"
    if value <= 16:
        return "9-16"
    return "17+"


def _hour_from_timestamp(value: Any) -> str:
    text = str(value or "")
    if "T" in text and len(text.split("T", 1)[1]) >= 2:
        return text.split("T", 1)[1][:2]
    return "UNKNOWN"


def _upper(value: Any) -> str:
    return _text(value).upper()


def _lower(value: Any) -> str:
    return _text(value).lower()


def _text(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "UNKNOWN"
