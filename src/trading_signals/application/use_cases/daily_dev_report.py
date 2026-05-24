from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

from trading_signals.memory.insights import build_pattern_memory_insights
from trading_signals.risk.kill_switch import evaluate_kill_switch


CLOSED_STATUSES = {"tp2_hit", "tp_hit", "sl_hit", "expired", "breakeven"}
WIN_STATUSES = {"tp2_hit", "tp_hit"}
LOSS_STATUSES = {"sl_hit"}


def build_daily_dev_report(
    data_path: Path,
    *,
    logs_path: Path = Path("logs"),
    report_date: date | None = None,
    now: datetime | None = None,
    scheduler_expected_interval_seconds: int = 900,
    kill_switch_enabled: bool = False,
    max_daily_loss_r: float = 2.0,
    max_consecutive_losses: int = 2,
    max_weekly_drawdown_r: float = 4.0,
    kill_switch_cooldown_hours: int = 12,
) -> dict[str, object]:
    now_dt = now or datetime.now(timezone.utc)
    day = report_date or now_dt.date()
    paper_trades = _read_csv(data_path / "paper_trading" / "trades.csv")
    live_trades = _read_csv(data_path / "live_trading" / "trades.csv")
    pattern_records = _read_jsonl(data_path / "pattern_memory" / "patterns.jsonl")
    closed_today = [trade for trade in paper_trades if _is_closed(trade) and _date_matches(trade, day)]
    open_live = [trade for trade in live_trades if str(trade.get("status", "")).strip().lower() in {"open", "tp1_hit", "breakeven"}]
    scheduler_log = logs_path / "scheduler.log"
    last_cycle_minutes = _minutes_since_mtime(scheduler_log, now_dt)
    scheduler_ok = last_cycle_minutes is not None and last_cycle_minutes <= max(5, scheduler_expected_interval_seconds / 60 * 3)
    performance = _stats(closed_today)
    kill_switch = evaluate_kill_switch(
        data_path,
        enabled=kill_switch_enabled,
        max_daily_loss_r=max_daily_loss_r,
        max_consecutive_losses=max_consecutive_losses,
        max_weekly_drawdown_r=max_weekly_drawdown_r,
        cooldown_hours=kill_switch_cooldown_hours,
        now=now_dt,
    )
    return {
        "date": day.isoformat(),
        "status": {
            "scheduler_ok": scheduler_ok,
            "last_cycle_minutes_ago": last_cycle_minutes,
            "pattern_memory_records": len(pattern_records),
            "open_live_trades": len(open_live),
            "paper_trades_closed_today": len(closed_today),
        },
        "kill_switch": kill_switch,
        "performance_today": performance,
        "breakdown": {
            "direction": _group_stats(closed_today, "direction"),
            "setup_type": _group_stats(closed_today, "setup_type"),
        },
        "leaks": _build_leaks(closed_today),
        "pattern_memory": _build_pattern_memory_section(pattern_records),
    }


def format_daily_dev_report(report: dict[str, object]) -> str:
    status = _dict(report.get("status"))
    performance = _dict(report.get("performance_today"))
    breakdown = _dict(report.get("breakdown"))
    direction_stats = _dict(breakdown.get("direction"))
    setup_stats = _dict(breakdown.get("setup_type"))
    leaks = _dict(report.get("leaks"))
    memory = _dict(report.get("pattern_memory"))
    kill_switch = _dict(report.get("kill_switch"))
    return (
        "📊 Daily Bot Report\n"
        f"Fecha: {report.get('date', '-')}\n\n"
        "⚙️ Estado\n"
        f"- Scheduler: {'OK' if status.get('scheduler_ok') else 'NO DATA'}\n"
        f"- Último ciclo: {_format_last_cycle(status.get('last_cycle_minutes_ago'))}\n"
        f"- Pattern Memory records: {status.get('pattern_memory_records', 0)}\n"
        f"- Open live trades: {status.get('open_live_trades', 0)}\n"
        f"- Paper trades cerrados hoy: {status.get('paper_trades_closed_today', 0)}\n\n"
        "🛑 Kill Switch\n"
        f"- Active: {_yes_no(kill_switch.get('kill_switch_active'))}\n"
        f"- Reason: {kill_switch.get('kill_switch_reason') or 'none'}\n"
        f"- Daily R: {kill_switch.get('daily_realized_r', 0)}\n"
        f"- Weekly R: {kill_switch.get('weekly_realized_r', 0)}\n"
        f"- Consecutive losses: {kill_switch.get('consecutive_losses', 0)}\n"
        f"- Cooldown until: {kill_switch.get('cooldown_until') or 'none'}\n\n"
        "📈 Performance hoy\n"
        f"- Trades cerrados: {performance.get('trades', 0)}\n"
        f"- Winrate: {performance.get('winrate', 0)}%\n"
        f"- Total R: {performance.get('total_r', 0)}\n"
        f"- Avg R: {performance.get('avg_r', 0)}\n"
        f"- Profit Factor: {performance.get('profit_factor', 0)}\n\n"
        "🧪 Breakdown rápido\n"
        f"- LONG: {_format_group_line(direction_stats.get('long') or direction_stats.get('LONG'))}\n"
        f"- SHORT: {_format_group_line(direction_stats.get('short') or direction_stats.get('SHORT'))}\n"
        f"- MAIN_SIGNAL: {_format_group_line(setup_stats.get('MAIN_SIGNAL'))}\n"
        f"- SECONDARY_SIGNAL: {_format_group_line(setup_stats.get('SECONDARY_SIGNAL'))}\n\n"
        "⚠️ Fugas principales\n"
        f"{_format_leaks(leaks)}\n\n"
        "🧠 Pattern Memory\n"
        f"- Insights ready: {_yes_no(memory.get('insights_ready'))}\n"
        f"- Top insight: {memory.get('top_insight') or 'Datos insuficientes todavía.'}"
    )


def send_daily_dev_report(notifier, data_path: Path, *, logs_path: Path = Path("logs"), dry_run: bool = False, settings=None) -> list[dict[str, object]]:
    interval = int(getattr(settings, "scan_interval_seconds", 900)) if settings is not None else 900
    report = build_daily_dev_report(
        data_path,
        logs_path=logs_path,
        scheduler_expected_interval_seconds=interval,
        kill_switch_enabled=bool(getattr(settings, "kill_switch_enabled", False)) if settings is not None else False,
        max_daily_loss_r=float(getattr(settings, "max_daily_loss_r", 2.0)) if settings is not None else 2.0,
        max_consecutive_losses=int(getattr(settings, "max_consecutive_losses", 2)) if settings is not None else 2,
        max_weekly_drawdown_r=float(getattr(settings, "max_weekly_drawdown_r", 4.0)) if settings is not None else 4.0,
        kill_switch_cooldown_hours=int(getattr(settings, "kill_switch_cooldown_hours", 12)) if settings is not None else 12,
    )
    message = format_daily_dev_report(report)
    if dry_run:
        print(message)
        return [{"recipient": "dry_run", "status": "printed", "provider_message_id": "dry_run"}]
    return notifier.send_dev_message(message, dry_run=False)


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
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            records.append(item)
    return records


def _is_closed(trade: dict[str, str]) -> bool:
    status = str(trade.get("status", "")).strip().lower()
    return status in CLOSED_STATUSES or bool(str(trade.get("closed_at", "")).strip())


def _date_matches(trade: dict[str, str], day: date) -> bool:
    for key in ("closed_at", "updated_at", "created_at", "timestamp"):
        raw = str(trade.get(key) or "").strip()
        if raw.startswith(day.isoformat()):
            return True
    return False


def _stats(trades: list[dict[str, str]]) -> dict[str, float | int]:
    total_r = sum(_float(trade.get("result_r")) for trade in trades)
    return {
        "trades": len(trades),
        "wins": len([trade for trade in trades if _is_win(trade)]),
        "losses": len([trade for trade in trades if _is_loss(trade)]),
        "winrate": _winrate(trades),
        "total_r": round(total_r, 4),
        "avg_r": round(total_r / len(trades), 4) if trades else 0.0,
        "profit_factor": _profit_factor(trades),
    }


def _group_stats(trades: list[dict[str, str]], key: str) -> dict[str, dict[str, float | int]]:
    groups: dict[str, list[dict[str, str]]] = {}
    for trade in trades:
        label = str(trade.get(key) or "UNKNOWN").strip() or "UNKNOWN"
        groups.setdefault(label, []).append(trade)
    return {label: _stats(items) for label, items in groups.items()}


def _build_leaks(closed_today: list[dict[str, str]]) -> dict[str, object]:
    if len(closed_today) < 2:
        return {"has_data": False}
    groups: list[tuple[str, dict[str, float | int]]] = []
    for key in ("direction", "setup_type", "session", "entry_context", "trade_location"):
        for label, stats in _group_stats(closed_today, key).items():
            groups.append((f"{key}:{label}", stats))
    losing = [(label, stats) for label, stats in groups if int(stats.get("trades", 0)) > 0]
    losing.sort(key=lambda item: (float(item[1].get("total_r", 0.0)), float(item[1].get("avg_r", 0.0))))
    if not losing:
        return {"has_data": False}
    label, stats = losing[0]
    if float(stats.get("total_r", 0.0)) >= 0:
        return {"has_data": False}
    return {"has_data": True, "label": label, **stats}


def _build_pattern_memory_section(records: list[dict[str, object]]) -> dict[str, object]:
    insights = build_pattern_memory_insights(records)
    if not insights.get("has_sufficient_data"):
        return {"insights_ready": False, "top_insight": ""}
    positives = insights.get("positive_patterns", [])
    negatives = insights.get("negative_patterns", [])
    selected = None
    prefix = ""
    if isinstance(positives, list) and positives:
        selected = positives[0]
        prefix = "positivo"
    elif isinstance(negatives, list) and negatives:
        selected = negatives[0]
        prefix = "negativo"
    if not isinstance(selected, dict):
        return {"insights_ready": False, "top_insight": ""}
    return {
        "insights_ready": True,
        "top_insight": (
            f"{prefix}: {selected.get('label', selected.get('value', '-'))} | "
            f"WR {selected.get('historical_winrate', 0)}% | "
            f"AvgR {selected.get('historical_avg_r', 0)} | Casos {selected.get('cases', 0)}"
        ),
    }


def _minutes_since_mtime(path: Path, now: datetime) -> int | None:
    if not path.exists():
        return None
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=now.tzinfo or timezone.utc)
    return max(0, int((now - mtime).total_seconds() // 60))


def _float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _is_win(trade: dict[str, str]) -> bool:
    status = str(trade.get("status", "")).strip().lower()
    return status in WIN_STATUSES or _float(trade.get("result_r")) > 0


def _is_loss(trade: dict[str, str]) -> bool:
    status = str(trade.get("status", "")).strip().lower()
    return status in LOSS_STATUSES or _float(trade.get("result_r")) < 0


def _winrate(trades: list[dict[str, str]]) -> float:
    if not trades:
        return 0.0
    return round(len([trade for trade in trades if _is_win(trade)]) / len(trades) * 100, 2)


def _profit_factor(trades: list[dict[str, str]]) -> float:
    gross_win = sum(max(0.0, _float(trade.get("result_r"))) for trade in trades)
    gross_loss = abs(sum(min(0.0, _float(trade.get("result_r"))) for trade in trades))
    if gross_loss == 0:
        return round(gross_win, 4) if gross_win > 0 else 0.0
    return round(gross_win / gross_loss, 4)


def _format_last_cycle(value: object) -> str:
    if value is None:
        return "desconocido"
    return f"hace {int(value)} min"


def _format_group_line(stats: object) -> str:
    if not isinstance(stats, dict):
        return "trades 0 | R 0 | WR 0%"
    return f"trades {stats.get('trades', 0)} | R {stats.get('total_r', 0)} | WR {stats.get('winrate', 0)}%"


def _format_leaks(leaks: dict[str, object]) -> str:
    if not leaks.get("has_data"):
        return "- Datos insuficientes todavía."
    return (
        f"- Peor grupo: {leaks.get('label')} | trades {leaks.get('trades', 0)} | "
        f"R {leaks.get('total_r', 0)} | WR {leaks.get('winrate', 0)}%"
    )


def _yes_no(value: object) -> str:
    return "YES" if bool(value) else "NO"


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}
