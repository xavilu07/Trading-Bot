from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable

from trading_signals.application.use_cases.intelligence_layer_health import build_intelligence_layer_health
from trading_signals.application.use_cases.paper_stats import (
    build_paper_performance_summary,
    load_paper_trades,
)


def build_dashboard_summary(
    *,
    data_path: Path = Path("data"),
    logs_path: Path = Path("logs"),
    runtime_path: Path = Path(".runtime"),
    reports_path: Path = Path("reports"),
    latest_limit: int = 10,
) -> dict[str, object]:
    paper_trades_path = data_path / "paper_trading" / "trades.csv"
    live_trades_path = data_path / "live_trading" / "trades.csv"
    experimental_signals_path = data_path / "paper_trading" / "experimental_signals.csv"
    scheduler_log_path = _select_scheduler_log(logs_path / "scheduler.log", runtime_path / "scheduler.log")

    paper_trades = load_paper_trades(data_path)
    live_trades = _read_csv(live_trades_path)
    experimental_signals = _read_csv(experimental_signals_path)
    paper_stats = build_paper_performance_summary(data_path)

    latest_signals = _latest_rows(experimental_signals, latest_limit, keys=("timestamp", "evaluated_at"))
    latest_rejections = _latest_rejections(paper_trades, experimental_signals, latest_limit)

    return {
        "last_cycle": _build_last_cycle(scheduler_log_path),
        "latest_signals": [_signal_view(row) for row in latest_signals],
        "latest_rejections": latest_rejections,
        "paper_stats": paper_stats,
        "intelligence_layer": build_intelligence_layer_health(reports_path),
        "top_rejection_reasons": _top_rejection_reasons(paper_stats, paper_trades, experimental_signals),
        "files": {
            "paper_trades": _file_status(paper_trades_path, rows=len(paper_trades)),
            "live_trades": _file_status(live_trades_path, rows=len(live_trades)),
            "experimental_signals": _file_status(experimental_signals_path, rows=len(experimental_signals)),
            "scheduler_log": _file_status(scheduler_log_path),
            "scheduler_log_candidates": [
                _file_status(logs_path / "scheduler.log"),
                _file_status(runtime_path / "scheduler.log"),
            ],
        },
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except csv.Error:
        return []


def _select_scheduler_log(primary: Path, fallback: Path) -> Path:
    if primary.exists() and primary.stat().st_size > 0:
        return primary
    if fallback.exists() and fallback.stat().st_size > 0:
        return fallback
    return primary


def _build_last_cycle(path: Path) -> dict[str, object]:
    status = _file_status(path)
    lines = _tail_nonempty_lines(path, limit=20)
    return {
        "status": "available" if status["exists"] and not status["empty"] else status["state"],
        "log_path": status["path"],
        "updated_at": status["updated_at"],
        "size_bytes": status["size_bytes"],
        "last_lines": lines[-5:],
        "last_event": _last_json_event(lines),
    }


def _file_status(path: Path, *, rows: int | None = None) -> dict[str, object]:
    exists = path.exists()
    size = path.stat().st_size if exists else 0
    state = "missing"
    if exists and size == 0:
        state = "empty"
    elif exists:
        state = "available"
    output: dict[str, object] = {
        "path": str(path),
        "exists": exists,
        "empty": exists and size == 0,
        "state": state,
        "size_bytes": size,
        "updated_at": _mtime_iso(path),
    }
    if rows is not None:
        output["rows"] = rows
    return output


def _mtime_iso(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def _tail_nonempty_lines(path: Path, *, limit: int) -> list[str]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines()]
    except OSError:
        return []
    return [line for line in lines if line][-limit:]


def _last_json_event(lines: list[str]) -> dict[str, object] | None:
    for line in reversed(lines):
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _latest_rows(rows: list[dict[str, str]], limit: int, *, keys: tuple[str, ...]) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: _first_value(row, keys), reverse=True)[:limit]


def _latest_rejections(
    paper_trades: list[dict[str, str]],
    experimental_signals: list[dict[str, str]],
    limit: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for trade in paper_trades:
        reasons = _trade_reasons(trade)
        if not reasons:
            continue
        rows.append(
            {
                "source": "paper_trades",
                "timestamp": _first_value(trade, ("opened_at", "updated_at", "closed_at")),
                "symbol": trade.get("symbol", "UNKNOWN"),
                "direction": trade.get("direction", "UNKNOWN"),
                "score": _number_or_raw(trade.get("score")),
                "status": trade.get("status", ""),
                "reasons": reasons,
            }
        )
    for signal in experimental_signals:
        reasons = _split_tokens(signal.get("real_reason"))
        if not reasons:
            continue
        rows.append(
            {
                "source": "experimental_signals",
                "timestamp": _first_value(signal, ("timestamp", "evaluated_at")),
                "symbol": signal.get("symbol", "UNKNOWN"),
                "direction": signal.get("direction", "UNKNOWN"),
                "score": _number_or_raw(signal.get("score")),
                "status": signal.get("outcome", ""),
                "reasons": reasons,
            }
        )
    return sorted(rows, key=lambda row: str(row.get("timestamp") or ""), reverse=True)[:limit]


def _signal_view(row: dict[str, str]) -> dict[str, object]:
    return {
        "timestamp": row.get("timestamp", ""),
        "symbol": row.get("symbol", "UNKNOWN"),
        "direction": row.get("direction", "UNKNOWN"),
        "score": _number_or_raw(row.get("score")),
        "experimental_reason": row.get("experimental_reason", ""),
        "real_reason": row.get("real_reason", ""),
        "market_regime": row.get("market_regime", ""),
        "entry_context": row.get("entry_context", ""),
        "outcome": row.get("outcome", ""),
        "exit_reason": row.get("exit_reason", ""),
        "evaluated_at": row.get("evaluated_at", ""),
    }


def _top_rejection_reasons(
    paper_stats: dict[str, object],
    paper_trades: list[dict[str, str]],
    experimental_signals: list[dict[str, str]],
    *,
    limit: int = 10,
) -> list[dict[str, object]]:
    counter: Counter[str] = Counter()
    for key in ("top_failed_conditions", "top_rejection_reasons", "top_avoidance_warnings"):
        for label, count in _iter_counter_items(paper_stats.get(key)):
            if _is_rejection_token(label):
                counter[label] += count
    for trade in paper_trades:
        counter.update(_trade_reasons(trade))
    for signal in experimental_signals:
        counter.update(_split_tokens(signal.get("real_reason")))
    return [{"label": label, "count": count} for label, count in counter.most_common(limit) if _is_rejection_token(label)]


def _iter_counter_items(value: object) -> Iterable[tuple[str, int]]:
    if not isinstance(value, list):
        return []
    items: list[tuple[str, int]] = []
    for item in value:
        if isinstance(item, dict) and item.get("label"):
            items.append((str(item["label"]), int(item.get("count", 0) or 0)))
    return items


def _trade_reasons(trade: dict[str, str]) -> list[str]:
    reasons: list[str] = []
    reasons.extend(_split_tokens(trade.get("entry_or_rejection_reason")))
    reasons.extend(str(item) for item in _parse_list(trade.get("conditions_failed")))
    reasons.extend(str(item) for item in _parse_list(trade.get("avoidance_warnings")))
    return [reason for reason in dict.fromkeys(reasons) if _is_rejection_token(reason)]


def _is_rejection_token(value: object) -> bool:
    token = str(value or "").strip()
    return bool(token) and token not in {"paper_tradeable", "none", "unknown"}


def _split_tokens(value: object) -> list[str]:
    return [token.strip() for token in str(value or "").split("|") if token.strip()]


def _parse_list(value: object) -> list[object]:
    raw = str(value or "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return _split_tokens(raw)
    return parsed if isinstance(parsed, list) else []


def _first_value(row: dict[str, str], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _number_or_raw(value: object) -> float | str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        return round(float(raw), 6)
    except ValueError:
        return raw
