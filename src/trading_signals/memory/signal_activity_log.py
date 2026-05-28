from __future__ import annotations

import hashlib
import json
import logging
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SIGNALS_LOG_PATH = Path("data/bot_activity/signals_log.jsonl")
MAX_SIGNALS_LOG_BYTES = 5 * 1024 * 1024
RECENT_DEDUPE_LINES = 1000

logger = logging.getLogger("trading_signals")


def append_signal_log(entry: dict) -> bool:
    """Append one evaluated signal to JSONL storage.

    The logger is intentionally best-effort: it never raises into the bot loop.
    Returns True when a row is appended, False when skipped or failed.
    """
    try:
        normalized = _normalize_entry(entry)
        log_path = SIGNALS_LOG_PATH
        log_path.parent.mkdir(parents=True, exist_ok=True)
        _rotate_if_needed(log_path)

        dedupe_key = _dedupe_key(normalized)
        if dedupe_key in _recent_dedupe_keys(log_path):
            return False

        normalized["dedupe_key"] = dedupe_key
        with log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(normalized, ensure_ascii=False, sort_keys=True, default=str) + "\n")
        return True
    except Exception as exc:  # pragma: no cover - defensive guard for live bot stability
        logger.warning("signal_activity_log_append_failed: %s", exc)
        return False


def _normalize_entry(entry: dict) -> dict[str, Any]:
    allowed_keys = [
        "timestamp",
        "symbol",
        "direction",
        "score",
        "status",
        "setup_type",
        "reasons",
        "rejection_reasons",
        "conditions_failed",
        "avoidance_warnings",
        "failed_conditions",
        "penalties",
        "rr",
        "entry_price",
        "stop_loss",
        "take_profit",
        "trend_entry",
        "trend_higher",
        "market_structure",
        "liquidity_sweep",
        "market_regime",
        "entry_context",
        "source_engine",
        "meta_decision",
        "public_canary_decision",
        "public_canary_match",
        "public_canary_reason",
        "relaxed_public_policy_decision",
        "relaxed_public_policy_vs_current",
        "relaxed_public_shadow_sent_dev",
        "raw_summary",
    ]
    normalized = {key: entry.get(key) for key in allowed_keys if entry.get(key) is not None}
    normalized["timestamp"] = str(normalized.get("timestamp") or _now_minute_iso())
    normalized["symbol"] = str(normalized.get("symbol") or "").upper()
    normalized["direction"] = str(normalized.get("direction") or "no_trade").lower()
    normalized["status"] = _normalize_status(normalized.get("status"))
    return normalized


def _normalize_status(value: object) -> str:
    status = str(value or "no_trade").lower()
    if status in {"sent", "rejected", "paper", "experimental", "no_trade"}:
        return status
    return "no_trade"


def _dedupe_key(entry: dict[str, Any]) -> str:
    payload = {
        "symbol": entry.get("symbol"),
        "direction": entry.get("direction"),
        "score": entry.get("score"),
        "status": entry.get("status"),
        "timestamp_minute": _timestamp_minute(str(entry.get("timestamp") or "")),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _timestamp_minute(timestamp: str) -> str:
    if not timestamp:
        return _now_minute_iso()
    return timestamp[:16]


def _now_minute_iso() -> str:
    return datetime.now(tz=UTC).replace(second=0, microsecond=0).isoformat()


def _rotate_if_needed(log_path: Path) -> None:
    if not log_path.exists() or log_path.stat().st_size <= MAX_SIGNALS_LOG_BYTES:
        return
    rotated_path = log_path.with_suffix(".jsonl.1")
    if rotated_path.exists():
        rotated_path.unlink()
    log_path.rename(rotated_path)


def _recent_dedupe_keys(log_path: Path) -> set[str]:
    if not log_path.exists():
        return set()

    keys = set()
    with log_path.open(encoding="utf-8", errors="ignore") as file:
        for line in deque(file, maxlen=RECENT_DEDUPE_LINES):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                key = row.get("dedupe_key")
                if key:
                    keys.add(str(key))
    return keys
