from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from trading_signals.data.canonical_trade_source import TradeUniverse, load_trade_universe
from typing import Any


CLOSED_STATUSES = {"tp2_hit", "tp_hit", "sl_hit", "expired", "closed", "win", "loss"}
OPEN_STATUSES = {"open", "tp1_hit", "breakeven", "pending"}


def load_private_runtime_report_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def save_private_runtime_report_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)


def should_send_private_runtime_report(
    *,
    enabled: bool,
    cycle_number: int,
    every_cycles: int,
    state: dict[str, Any],
) -> bool:
    if not enabled:
        return False
    every = max(1, int(every_cycles or 1))
    last_cycle = _int(state.get("last_cycle_reported"))
    return cycle_number > last_cycle and (cycle_number - last_cycle) >= every


def build_private_runtime_report(
    *,
    data_path: Path,
    state: dict[str, Any],
    cycle_number: int,
    last_cycle_duration_seconds: float | int | None,
    scheduler_status: str,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    now = now or datetime.now(tz=UTC)
    trades = load_trade_universe(data_path, TradeUniverse.ACCEPTED, closed_only=False)
    previous_trades = state.get("known_paper_trades")
    previous_map = previous_trades if isinstance(previous_trades, dict) else {}
    current_map = {_trade_key(row, index): _trade_state(row) for index, row in enumerate(trades)}

    new_trades = [
        _trade_summary(row)
        for index, row in enumerate(trades)
        if _trade_key(row, index) not in previous_map
    ]
    closed_trades = []
    for index, row in enumerate(trades):
        key = _trade_key(row, index)
        current = current_map[key]
        previous = previous_map.get(key)
        if not _is_closed_status(current["status"]):
            continue
        if not isinstance(previous, dict) or not _is_closed_status(str(previous.get("status", ""))):
            closed_trades.append(_trade_summary(row))

    recent_r = round(sum(_float(item.get("result_r")) for item in closed_trades), 4)
    recent_wins = len([item for item in closed_trades if _float(item.get("result_r")) > 0])
    recent_losses = len([item for item in closed_trades if _float(item.get("result_r")) < 0])
    open_trades = [_trade_summary(row) for row in trades if _is_open_trade(row)]

    signal_rows = _read_jsonl(data_path / "bot_activity" / "signals_log.jsonl")
    last_signal_offset = _int(state.get("last_signal_log_offset"))
    if last_signal_offset > len(signal_rows):
        last_signal_offset = 0
    new_signal_rows = signal_rows[last_signal_offset:]
    public_sent = len([row for row in new_signal_rows if _is_public_published(row)])
    blocked_public = len([row for row in new_signal_rows if _is_public_blocked(row)])
    top_reasons = Counter()
    elite_matches = []
    for row in new_signal_rows:
        top_reasons.update(_extract_reasons(row))
        if _is_elite_profile_c(row):
            elite_matches.append(_signal_summary(row))

    report = {
        "cycle_number": cycle_number,
        "last_cycle_duration_seconds": last_cycle_duration_seconds,
        "scheduler_status": scheduler_status or "unknown",
        "new_paper_trades": new_trades,
        "new_paper_trades_count": len(new_trades),
        "closed_paper_trades": closed_trades,
        "closed_paper_trades_count": len(closed_trades),
        "recent_closed_r_total": recent_r,
        "recent_wins": recent_wins,
        "recent_losses": recent_losses,
        "open_paper_trades": open_trades,
        "open_paper_trades_count": len(open_trades),
        "public_signals_sent": public_sent,
        "blocked_public_signals": blocked_public,
        "top_rejection_reasons": [
            {"reason": reason, "count": count}
            for reason, count in top_reasons.most_common(3)
        ],
        "elite_profile_c_matches": elite_matches,
        "elite_profile_c_matches_count": len(elite_matches),
    }
    next_state = {
        **state,
        "last_cycle_reported": cycle_number,
        "last_trade_row_count": len(trades),
        "last_signal_log_offset": len(signal_rows),
        "last_report_at": now.isoformat(),
        "known_paper_trades": current_map,
    }
    return report, next_state


def format_private_runtime_report_for_telegram(report: dict[str, Any]) -> str:
    duration = _format_duration(report.get("last_cycle_duration_seconds"))
    recent_r = _format_r(report.get("recent_closed_r_total"))
    lines = [
        "🧭 Private Runtime Report",
        f"Cycle: {report.get('cycle_number', 0)} | Duration: {duration} | Status: {report.get('scheduler_status', 'unknown')}",
        "",
        "📄 Paper update",
        f"Opened: {report.get('new_paper_trades_count', 0)}",
        f"Closed: {report.get('closed_paper_trades_count', 0)}",
        f"Recent R: {recent_r}",
        f"W/L: {report.get('recent_wins', 0)}/{report.get('recent_losses', 0)}",
        f"Open now: {report.get('open_paper_trades_count', 0)}",
    ]
    open_lines = [_format_trade_line(item) for item in _list(report.get("open_paper_trades"))[:5]]
    lines.extend(open_lines)
    if report.get("open_paper_trades_count", 0) > len(open_lines):
        lines.append(f"+ {int(report.get('open_paper_trades_count', 0)) - len(open_lines)} more open")

    new_lines = [_format_trade_line(item) for item in _list(report.get("new_paper_trades"))[:3]]
    if new_lines:
        lines.extend(["", "New paper trades:"])
        lines.extend(new_lines)

    closed_lines = [_format_trade_line(item) for item in _list(report.get("closed_paper_trades"))[:3]]
    if closed_lines:
        lines.extend(["", "Closed paper trades:"])
        lines.extend(closed_lines)

    lines.extend(
        [
            "",
            "🚦 Public routing",
            f"Public sent: {report.get('public_signals_sent', 0)}",
            f"Public blocked: {report.get('blocked_public_signals', 0)}",
        ]
    )
    reasons = _list(report.get("top_rejection_reasons"))
    if reasons:
        lines.append("Top blocks:")
        for item in reasons:
            if isinstance(item, dict):
                lines.append(f"- {item.get('reason', 'unknown')}: {item.get('count', 0)}")

    elite = _list(report.get("elite_profile_c_matches"))
    if elite:
        lines.extend(["", "🔥 ELITE PROFILE C detected"])
        for item in elite[:5]:
            lines.append(_format_elite_line(item))
        if report.get("elite_profile_c_matches_count", 0) > len(elite[:5]):
            lines.append(f"+ {int(report.get('elite_profile_c_matches_count', 0)) - len(elite[:5])} more")

    return "\n".join(lines)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return []


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(raw, dict):
                    rows.append(raw)
    except OSError:
        return []
    return rows


def _trade_key(row: dict[str, Any], index: int) -> str:
    for key in ("trade_id", "dedupe_key"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return "|".join(
        [
            str(row.get("symbol") or ""),
            str(row.get("direction") or ""),
            str(row.get("opened_at") or ""),
            str(row.get("entry_price") or ""),
            str(index),
        ]
    )


def _trade_state(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": str(row.get("status") or "").strip().lower(),
        "result_r": str(row.get("result_r") or "0"),
        "updated_at": str(row.get("updated_at") or ""),
        "closed_at": str(row.get("closed_at") or ""),
    }


def _trade_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": str(row.get("symbol") or "UNKNOWN"),
        "direction": str(row.get("direction") or "").lower(),
        "status": str(row.get("status") or "unknown").lower(),
        "result_r": _float(row.get("result_r")),
        "score": _float(row.get("score")),
        "setup_type": str(row.get("setup_type") or row.get("paper_level") or "UNKNOWN"),
        "session": str(row.get("session") or "UNKNOWN"),
    }


def _signal_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": str(row.get("symbol") or "UNKNOWN"),
        "direction": str(row.get("direction") or "").lower(),
        "score": _float(row.get("score")),
        "setup_type": str(row.get("setup_type") or "UNKNOWN"),
        "session": str(row.get("session") or "UNKNOWN"),
        "result_r": _float(row.get("result_r")),
    }


def _is_open_trade(row: dict[str, Any]) -> bool:
    status = str(row.get("status") or "").strip().lower()
    return status in OPEN_STATUSES or (status not in CLOSED_STATUSES and not str(row.get("closed_at") or "").strip())


def _is_closed_status(status: str) -> bool:
    return status.strip().lower() in CLOSED_STATUSES


def _is_public_published(row: dict[str, Any]) -> bool:
    if _boolish(row.get("public_published")):
        return True
    if str(row.get("delivery") or "").lower() == "telegram_public":
        return True
    deliveries = row.get("deliveries")
    if isinstance(deliveries, list):
        return any(isinstance(item, dict) and item.get("channel") == "telegram_public" and item.get("status") == "sent" for item in deliveries)
    return False


def _is_public_blocked(row: dict[str, Any]) -> bool:
    if _is_public_published(row):
        return False
    if row.get("public_block_reason") or row.get("publish_filter_reason"):
        return True
    raw = row.get("raw_summary")
    return isinstance(raw, dict) and bool(raw.get("public_block_reason") or raw.get("publish_filter_reason"))


def _extract_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for key in ("public_block_reason", "publish_filter_reason", "reasons"):
        value = row.get(key)
        if value:
            reasons.extend(_split_reason_value(value))
    for key in ("rejection_reasons", "conditions_failed", "avoidance_warnings", "penalties"):
        reasons.extend(_list_strings(row.get(key)))
    raw = row.get("raw_summary")
    if isinstance(raw, dict):
        for key in ("publish_filter_reason", "public_canary_reason"):
            value = raw.get(key)
            if value:
                reasons.extend(_split_reason_value(value))
    return [item for item in dict.fromkeys(reasons) if item and item != "none"]


def _is_elite_profile_c(row: dict[str, Any]) -> bool:
    if _boolish(row.get("elite_profile_c")):
        return True
    trace = row.get("decision_trace")
    if "elite_profile_c=true" in _list_strings(trace):
        return True
    raw = row.get("raw_summary")
    if isinstance(raw, dict):
        return _boolish(raw.get("elite_profile_c")) or "elite_profile_c=true" in _list_strings(raw.get("decision_trace"))
    return False


def _list_strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            try:
                raw = json.loads(stripped)
            except json.JSONDecodeError:
                raw = None
            if isinstance(raw, list):
                return [str(item) for item in raw if str(item)]
        return _split_reason_value(stripped)
    return []


def _split_reason_value(value: Any) -> list[str]:
    return [item.strip() for item in str(value).replace(",", "|").split("|") if item.strip()]


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _format_duration(value: Any) -> str:
    number = _float(value)
    return f"{number:.1f}s"


def _format_r(value: Any) -> str:
    number = _float(value)
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.2f}R"


def _format_score(value: Any) -> str:
    number = _float(value)
    return str(int(number)) if number.is_integer() else f"{number:.1f}"


def _format_trade_line(item: dict[str, Any]) -> str:
    return (
        f"- {item.get('symbol', 'UNKNOWN')} {item.get('direction', '')} {item.get('status', 'unknown')} "
        f"{_format_r(item.get('result_r'))} score {_format_score(item.get('score'))} "
        f"{item.get('setup_type', 'UNKNOWN')} {item.get('session', 'UNKNOWN')}"
    )


def _format_elite_line(item: dict[str, Any]) -> str:
    current_r = _format_r(item.get("result_r")) if _float(item.get("result_r")) else "n/a"
    return (
        f"- {item.get('symbol', 'UNKNOWN')} {item.get('direction', '')} score {_format_score(item.get('score'))} "
        f"{item.get('setup_type', 'UNKNOWN')} {item.get('session', 'UNKNOWN')} R {current_r}"
    )
