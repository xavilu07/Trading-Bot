from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from trading_signals.risk.kill_switch import evaluate_kill_switch


CSV_FIELDS = [
    "signal_id",
    "timestamp",
    "symbol",
    "direction",
    "setup_type",
    "entry",
    "stop_loss",
    "take_profit",
    "result_r",
    "public_published",
    "meta_decision",
    "trade_quality_grade",
    "edge_confirmation_level",
    "adaptive_threshold",
    "market_regime",
    "session",
    "entry_context",
    "trade_location",
    "warnings",
    "penalties",
    "would_meta_filter_block",
    "would_kill_switch_block",
    "audit_recommendation",
]

WIN_STATUSES = {"tp_hit", "tp2_hit", "win"}
LOSS_STATUSES = {"sl_hit", "loss"}


def analyze_recent_public_signals(
    *,
    data_path: Path,
    logs_path: Path,
    reports_path: Path,
    days: int = 7,
    limit: int = 100,
    now: datetime | None = None,
) -> dict[str, object]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    since = now_dt - timedelta(days=days)
    activity = _read_jsonl(data_path / "bot_activity" / "signals_log.jsonl")
    live_trades = _read_csv(data_path / "live_trading" / "trades.csv")
    paper_trades = _read_paper_trades(data_path / "paper_trading")
    scheduler_events = _read_scheduler_public_events(logs_path / "scheduler.log")
    live_by_key = _index_trades(live_trades)
    paper_by_key = _index_trades(paper_trades)
    scheduler_public_ids = {
        str(item.get("signal_id"))
        for item in scheduler_events
        if item.get("signal_id")
    }
    kill_switch_status = evaluate_kill_switch(data_path, enabled=True, now=now_dt)

    rows: list[dict[str, object]] = []
    for signal in activity:
        if not _is_recent(signal, since):
            continue
        if not _is_public_signal(signal, scheduler_public_ids):
            continue
        row = _build_audit_row(
            signal,
            live_by_key=live_by_key,
            paper_by_key=paper_by_key,
            kill_switch_active=bool(kill_switch_status.get("kill_switch_active")),
        )
        rows.append(row)
    for trade in live_trades:
        if str(trade.get("public_published", "")).lower() != "true":
            continue
        if not _is_recent_trade(trade, since):
            continue
        if any(row.get("signal_id") and row.get("signal_id") == trade.get("signal_id") for row in rows):
            continue
        rows.append(_build_trade_only_row(trade, kill_switch_active=bool(kill_switch_status.get("kill_switch_active"))))

    rows = sorted(rows, key=lambda row: str(row.get("timestamp") or ""), reverse=True)[:limit]
    reports_path.mkdir(parents=True, exist_ok=True)
    csv_path = reports_path / "recent_public_signals_audit.csv"
    _write_csv(csv_path, rows)
    return {
        "rows": rows,
        "csv_path": csv_path,
        "summary": _summary(rows),
    }


def format_audit(result: dict[str, object]) -> str:
    summary = _dict(result.get("summary"))
    return (
        "📡 Recent Public Signals Audit\n"
        f"- Total public signals: {summary.get('total_public_signals', 0)}\n"
        f"- Wins / Losses: {summary.get('wins', 0)} / {summary.get('losses', 0)}\n"
        f"- Total R: {summary.get('total_r', 0)}\n"
        f"- Avg R: {summary.get('avg_r', 0)}\n"
        f"- Winrate: {summary.get('winrate', 0)}%\n"
        f"- Signals that meta filter would block today: {summary.get('meta_filter_blocks', 0)}\n"
        f"- Signals that kill switch would block today: {summary.get('kill_switch_blocks', 0)}\n"
        f"- Common loss reasons: {_format_counter(summary.get('common_loss_reasons'))}\n"
        f"- Worst contexts: {_format_counter(summary.get('worst_contexts'))}\n"
        f"- Best contexts: {_format_counter(summary.get('best_contexts'))}\n"
        f"- CSV: {result.get('csv_path')}"
    )


def _build_audit_row(
    signal: dict[str, object],
    *,
    live_by_key: dict[str, dict[str, str]],
    paper_by_key: dict[str, dict[str, str]],
    kill_switch_active: bool,
) -> dict[str, object]:
    raw = _dict(signal.get("raw_summary"))
    match = _match_trade(signal, live_by_key) or _match_trade(signal, paper_by_key) or {}
    intelligence = _extract_intelligence(signal)
    result_r = _float(match.get("result_r"))
    if result_r is None:
        result_r = _float(signal.get("result_r"))
    would_meta_block, meta_reason = _would_meta_filter_block(intelligence)
    warnings = _jsonish(signal.get("avoidance_warnings") or match.get("warnings"))
    penalties = _jsonish(signal.get("penalties") or match.get("penalties"))
    row = {
        "signal_id": raw.get("signal_id") or signal.get("signal_id") or match.get("signal_id") or "",
        "timestamp": signal.get("timestamp") or match.get("created_at") or match.get("opened_at") or "",
        "symbol": signal.get("symbol") or match.get("symbol") or "",
        "direction": signal.get("direction") or match.get("direction") or "",
        "setup_type": signal.get("setup_type") or match.get("setup_type") or "",
        "entry": signal.get("entry_price") or match.get("entry") or match.get("entry_price") or "",
        "stop_loss": signal.get("stop_loss") or match.get("stop_loss") or "",
        "take_profit": signal.get("take_profit") or match.get("take_profit") or match.get("take_profit_2") or match.get("take_profit_1") or "",
        "result_r": result_r if result_r is not None else "",
        "public_published": True,
        "meta_decision": intelligence["meta_decision"],
        "trade_quality_grade": intelligence["trade_quality_grade"],
        "edge_confirmation_level": intelligence["edge_confirmation_level"],
        "adaptive_threshold": intelligence["adaptive_threshold"],
        "market_regime": signal.get("market_regime") or match.get("market_regime") or "",
        "session": signal.get("session") or match.get("session") or "",
        "entry_context": signal.get("entry_context") or match.get("entry_context") or "",
        "trade_location": signal.get("trade_location") or match.get("trade_location") or "",
        "warnings": "|".join(warnings),
        "penalties": "|".join(penalties),
        "would_meta_filter_block": would_meta_block,
        "would_kill_switch_block": kill_switch_active,
        "audit_recommendation": _recommendation(result_r, would_meta_block, kill_switch_active, meta_reason, warnings, penalties),
    }
    return row


def _build_trade_only_row(trade: dict[str, str], *, kill_switch_active: bool) -> dict[str, object]:
    result_r = _float(trade.get("result_r"))
    warnings = _jsonish(trade.get("warnings"))
    penalties = _jsonish(trade.get("penalties"))
    return {
        "signal_id": trade.get("signal_id") or trade.get("trade_id") or "",
        "timestamp": trade.get("created_at") or trade.get("opened_at") or trade.get("closed_at") or "",
        "symbol": trade.get("symbol", ""),
        "direction": trade.get("direction", ""),
        "setup_type": trade.get("setup_type", ""),
        "entry": trade.get("entry") or trade.get("entry_price") or "",
        "stop_loss": trade.get("stop_loss", ""),
        "take_profit": trade.get("take_profit") or trade.get("take_profit_2") or trade.get("take_profit_1") or "",
        "result_r": result_r if result_r is not None else "",
        "public_published": True,
        "meta_decision": "UNKNOWN",
        "trade_quality_grade": "UNKNOWN",
        "edge_confirmation_level": "UNKNOWN",
        "adaptive_threshold": "",
        "market_regime": trade.get("market_regime", ""),
        "session": trade.get("session", ""),
        "entry_context": trade.get("entry_context", ""),
        "trade_location": trade.get("trade_location", ""),
        "warnings": "|".join(warnings),
        "penalties": "|".join(penalties),
        "would_meta_filter_block": False,
        "would_kill_switch_block": kill_switch_active,
        "audit_recommendation": _recommendation(result_r, False, kill_switch_active, "", warnings, penalties),
    }


def _extract_intelligence(signal: dict[str, object]) -> dict[str, object]:
    meta = _dict(signal.get("meta_decision"))
    pattern = _dict(signal.get("pattern_memory"))
    if not meta:
        meta = _dict(pattern.get("meta_decision"))
    quality = _dict(signal.get("trade_quality") or pattern.get("trade_quality"))
    edge = _dict(signal.get("edge_confirmation") or pattern.get("edge_confirmation"))
    adaptive = _dict(signal.get("adaptive_thresholds") or pattern.get("adaptive_thresholds"))
    return {
        "meta_decision": str(meta.get("meta_decision") or "UNKNOWN"),
        "capital_preservation_mode": bool(meta.get("capital_preservation_mode")),
        "trade_quality_grade": str(quality.get("trade_quality_grade") or "UNKNOWN"),
        "edge_confirmation_level": str(edge.get("edge_confirmation_level") or "UNKNOWN"),
        "adaptive_threshold": adaptive.get("adaptive_threshold", ""),
    }


def _would_meta_filter_block(intelligence: dict[str, object]) -> tuple[bool, str]:
    if str(intelligence.get("meta_decision", "")).upper() == "REJECT":
        return True, "meta_decision_reject"
    if bool(intelligence.get("capital_preservation_mode")):
        return True, "capital_preservation_mode"
    if str(intelligence.get("trade_quality_grade", "")).upper() == "TRASH":
        return True, "trade_quality_trash"
    return False, ""


def _recommendation(
    result_r: float | None,
    would_meta_block: bool,
    would_kill_switch_block: bool,
    meta_reason: str,
    warnings: list[str],
    penalties: list[str],
) -> str:
    if result_r is not None and result_r < 0:
        if would_meta_block:
            return f"loss_avoidable_by_meta_filter:{meta_reason}"
        if would_kill_switch_block:
            return "loss_avoidable_by_kill_switch"
        if warnings:
            return f"review_warning:{warnings[0]}"
        if penalties:
            return f"review_penalty:{penalties[0]}"
        return "loss_needs_context_review"
    if would_meta_block:
        return f"meta_filter_would_block:{meta_reason}"
    if would_kill_switch_block:
        return "kill_switch_would_block"
    return "keep_observing"


def _summary(rows: list[dict[str, object]]) -> dict[str, object]:
    closed = [row for row in rows if _float(row.get("result_r")) is not None]
    wins = [row for row in closed if _float(row.get("result_r")) and float(row["result_r"]) > 0]
    losses = [row for row in closed if _float(row.get("result_r")) is not None and float(row["result_r"]) < 0]
    total_r = round(sum(float(row["result_r"]) for row in closed), 4) if closed else 0.0
    return {
        "total_public_signals": len(rows),
        "wins": len(wins),
        "losses": len(losses),
        "total_r": total_r,
        "avg_r": round(total_r / len(closed), 4) if closed else 0.0,
        "winrate": round(len(wins) / len(closed) * 100, 2) if closed else 0.0,
        "meta_filter_blocks": len([row for row in rows if _bool(row.get("would_meta_filter_block"))]),
        "kill_switch_blocks": len([row for row in rows if _bool(row.get("would_kill_switch_block"))]),
        "common_loss_reasons": _common_loss_reasons(losses),
        "worst_contexts": _context_counts(losses),
        "best_contexts": _context_counts(wins),
    }


def _common_loss_reasons(losses: list[dict[str, object]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in losses:
        for key in ("warnings", "penalties", "audit_recommendation"):
            values = _jsonish(row.get(key))
            counter.update(value for value in values if value)
    return dict(counter.most_common(5))


def _context_counts(rows: list[dict[str, object]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        for key in ("setup_type", "market_regime", "session", "entry_context", "trade_location"):
            value = str(row.get(key) or "").strip()
            if value:
                counter[f"{key}:{value}"] += 1
    return dict(counter.most_common(5))


def _is_public_signal(signal: dict[str, object], scheduler_public_ids: set[str]) -> bool:
    raw = _dict(signal.get("raw_summary"))
    signal_id = str(raw.get("signal_id") or signal.get("signal_id") or "")
    if str(signal.get("public_published", "")).lower() == "true":
        return True
    if signal.get("status") == "sent":
        return True
    return bool(signal_id and signal_id in scheduler_public_ids)


def _is_recent(item: dict[str, object], since: datetime) -> bool:
    parsed = _parse_datetime(str(item.get("timestamp") or ""))
    return parsed is not None and parsed >= since


def _is_recent_trade(item: dict[str, str], since: datetime) -> bool:
    for key in ("created_at", "opened_at", "closed_at", "updated_at"):
        parsed = _parse_datetime(str(item.get(key) or ""))
        if parsed is not None:
            return parsed >= since
    return False


def _match_trade(signal: dict[str, object], index: dict[str, dict[str, str]]) -> dict[str, str] | None:
    raw = _dict(signal.get("raw_summary"))
    keys = [
        str(signal.get("dedupe_key") or ""),
        str(raw.get("signal_id") or ""),
        "|".join([str(signal.get("symbol") or ""), str(signal.get("direction") or "")]).lower(),
    ]
    for key in keys:
        if key and key in index:
            return index[key]
    return None


def _index_trades(trades: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for trade in trades:
        for key in (
            trade.get("dedupe_key"),
            trade.get("signal_id"),
            trade.get("trade_id"),
            "|".join([str(trade.get("symbol") or ""), str(trade.get("direction") or "")]).lower(),
        ):
            if key:
                index[str(key)] = trade
    return index


def _read_paper_trades(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not path.exists():
        return rows
    for csv_path in sorted(path.glob("*.csv")):
        rows.extend(_read_csv(csv_path))
    return rows


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except csv.Error:
        return []


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _read_scheduler_public_events(path: Path) -> list[dict[str, object]]:
    # Scheduler logs are implementation-dependent. Keep this parser best-effort.
    events: list[dict[str, object]] = []
    for row in _read_jsonl(path):
        if row.get("event") in {"telegram_public", "signal_published"}:
            events.append(row)
    return events


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})


def _format_counter(value: object) -> str:
    data = _dict(value)
    if not data:
        return "none"
    return ", ".join(f"{key}: {count}" for key, count in list(data.items())[:5])


def _jsonish(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, list):
        return [str(item) for item in parsed if str(item)]
    return [item for item in text.replace("|", ",").split(",") if item.strip()]


def _parse_datetime(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="analyze-recent-public-signals")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--logs-path", default="logs")
    parser.add_argument("--reports-path", default="reports")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=100)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_recent_public_signals(
        data_path=Path(args.data_path),
        logs_path=Path(args.logs_path),
        reports_path=Path(args.reports_path),
        days=args.days,
        limit=args.limit,
    )
    print(format_audit(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
