from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_recent_public_signals import (
    TRI_FALSE,
    TRI_TRUE,
    TRI_UNKNOWN,
    _build_audit_row,
    _build_trade_only_row,
    _closed_trade_events,
    _float,
    _index_trades,
    _is_public_signal,
    _is_recent,
    _is_recent_trade,
    _match_trade,
    _parse_datetime,
    _read_csv,
    _read_jsonl,
    _read_paper_trades,
    _read_scheduler_public_events,
    _retrospective_kill_switch_state,
)


SCENARIOS = (
    "BASELINE",
    "META_FILTER",
    "KILL_SWITCH",
    "META_FILTER_PLUS_KILL_SWITCH",
)

DETAIL_FIELDS = [
    "scenario",
    "signal_id",
    "timestamp",
    "symbol",
    "direction",
    "setup_type",
    "result_r",
    "meta_filter_state",
    "meta_filter_evaluable",
    "kill_switch_state",
    "blocked",
    "block_reason",
    "executed",
    "cumulative_r",
]

SUMMARY_FIELDS = [
    "scenario",
    "total_signals",
    "wins",
    "losses",
    "winrate",
    "total_r",
    "avg_r",
    "max_drawdown_r",
    "consecutive_losses_max",
    "blocked_signals",
    "avoided_losses",
    "missed_wins",
    "meta_filter_evaluable",
    "meta_unknown_signals",
]


@dataclass(frozen=True)
class ScenarioConfig:
    name: str
    use_meta_filter: bool = False
    use_kill_switch: bool = False


def backtest_public_signal_filters(
    *,
    data_path: Path,
    logs_path: Path,
    reports_path: Path,
    days: int | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    rows = _load_public_signal_rows(data_path=data_path, logs_path=logs_path, days=days, now=now)
    detail_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []

    for scenario in _scenario_configs():
        result = _simulate_scenario(rows, scenario)
        detail_rows.extend(result["details"])
        summary_rows.append(result["summary"])

    reports_path.mkdir(parents=True, exist_ok=True)
    detail_path = reports_path / "public_signal_filter_backtest.csv"
    summary_path = reports_path / "public_signal_filter_backtest_summary.csv"
    _write_csv(detail_path, detail_rows, DETAIL_FIELDS)
    _write_csv(summary_path, summary_rows, SUMMARY_FIELDS)
    return {
        "rows": rows,
        "details": detail_rows,
        "summary": summary_rows,
        "detail_csv_path": detail_path,
        "summary_csv_path": summary_path,
    }


def format_backtest(result: dict[str, object]) -> str:
    summary_rows = [row for row in result.get("summary", []) if isinstance(row, dict)]
    lines = ["🧪 Public Signal Filter Backtest"]
    for scenario in SCENARIOS:
        row = next((item for item in summary_rows if item.get("scenario") == scenario), {})
        label = "COMBINED" if scenario == "META_FILTER_PLUS_KILL_SWITCH" else scenario
        lines.append(
            f"{label}: signals={row.get('total_signals', 0)} | "
            f"WR={row.get('winrate', 0)}% | R={row.get('total_r', 0)} | "
            f"blocked={row.get('blocked_signals', 0)} | "
            f"avoided_losses={row.get('avoided_losses', 0)} | "
            f"missed_wins={row.get('missed_wins', 0)}"
        )
    lines.append(f"Detail CSV: {result.get('detail_csv_path')}")
    lines.append(f"Summary CSV: {result.get('summary_csv_path')}")
    return "\n".join(lines)


def _scenario_configs() -> tuple[ScenarioConfig, ...]:
    return (
        ScenarioConfig("BASELINE"),
        ScenarioConfig("META_FILTER", use_meta_filter=True),
        ScenarioConfig("KILL_SWITCH", use_kill_switch=True),
        ScenarioConfig("META_FILTER_PLUS_KILL_SWITCH", use_meta_filter=True, use_kill_switch=True),
    )


def _load_public_signal_rows(
    *,
    data_path: Path,
    logs_path: Path,
    days: int | None,
    now: datetime | None,
) -> list[dict[str, object]]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    since = now_dt - timedelta(days=days) if days is not None else None
    activity = _read_jsonl(data_path / "bot_activity" / "signals_log.jsonl")
    live_trades = _read_csv(data_path / "live_trading" / "trades.csv")
    paper_trades = _read_paper_trades(data_path / "paper_trading")
    scheduler_events = _read_scheduler_public_events(logs_path / "scheduler.log")
    live_by_key = _index_trades(live_trades)
    paper_by_key = _index_trades(paper_trades)
    closed_trade_events = _closed_trade_events(live_trades + paper_trades)
    scheduler_public_ids = {
        str(item.get("signal_id"))
        for item in scheduler_events
        if item.get("signal_id")
    }

    rows: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for signal in activity:
        if since is not None and not _is_recent(signal, since):
            continue
        if not _is_public_signal(signal, scheduler_public_ids):
            continue
        match = _match_trade(signal, live_by_key) or _match_trade(signal, paper_by_key) or {}
        row = _build_audit_row(
            signal,
            live_by_key=live_by_key,
            paper_by_key=paper_by_key,
            closed_trade_events=closed_trade_events,
        )
        _add_backtest_fields(row, match)
        rows.append(row)
        _add_seen_id(seen_ids, row)

    for trade in live_trades:
        if str(trade.get("public_published", "")).lower() != "true":
            continue
        if since is not None and not _is_recent_trade(trade, since):
            continue
        signal_id = str(trade.get("signal_id") or trade.get("trade_id") or "")
        if signal_id and signal_id in seen_ids:
            continue
        row = _build_trade_only_row(trade, closed_trade_events=closed_trade_events)
        _add_backtest_fields(row, trade)
        rows.append(row)
        _add_seen_id(seen_ids, row)

    return sorted(rows, key=lambda row: _parse_datetime(str(row.get("timestamp") or "")) or datetime.min.replace(tzinfo=UTC))


def _add_backtest_fields(row: dict[str, object], source: dict[str, str]) -> None:
    row["closed_at"] = (
        source.get("closed_at")
        or source.get("exit_time")
        or source.get("evaluated_at")
        or source.get("updated_at")
        or ""
    )


def _add_seen_id(seen_ids: set[str], row: dict[str, object]) -> None:
    signal_id = str(row.get("signal_id") or "")
    if signal_id:
        seen_ids.add(signal_id)


def _simulate_scenario(rows: list[dict[str, object]], scenario: ScenarioConfig) -> dict[str, object]:
    executed_events: list[dict[str, object]] = []
    executed_r: list[float] = []
    detail_rows: list[dict[str, object]] = []
    blocked_signals = 0
    avoided_losses = 0
    missed_wins = 0
    cumulative_r = 0.0

    for row in rows:
        signal_time = _parse_datetime(str(row.get("timestamp") or ""))
        result_r = _float(row.get("result_r"))
        meta_state = _tri_state(row.get("would_meta_filter_block"))
        kill_state = (
            _retrospective_kill_switch_state(executed_events, signal_time)
            if scenario.use_kill_switch
            else TRI_FALSE
        )
        block_reasons: list[str] = []
        if scenario.use_meta_filter and meta_state == TRI_TRUE:
            block_reasons.append("meta_filter")
        if scenario.use_kill_switch and kill_state == TRI_TRUE:
            block_reasons.append("kill_switch")

        blocked = bool(block_reasons)
        if blocked:
            blocked_signals += 1
            if result_r is not None and result_r < 0:
                avoided_losses += 1
            if result_r is not None and result_r > 0:
                missed_wins += 1
        else:
            if result_r is not None:
                executed_r.append(result_r)
                cumulative_r = round(cumulative_r + result_r, 4)
                event = _closed_event_from_row(row, result_r)
                if event is not None:
                    executed_events.append(event)
                    executed_events = sorted(executed_events, key=lambda item: item["closed_at"])

        detail_rows.append(
            {
                "scenario": scenario.name,
                "signal_id": row.get("signal_id", ""),
                "timestamp": row.get("timestamp", ""),
                "symbol": row.get("symbol", ""),
                "direction": row.get("direction", ""),
                "setup_type": row.get("setup_type", ""),
                "result_r": result_r if result_r is not None else "",
                "meta_filter_state": meta_state,
                "meta_filter_evaluable": TRI_FALSE if meta_state == TRI_UNKNOWN else TRI_TRUE,
                "kill_switch_state": kill_state,
                "blocked": blocked,
                "block_reason": "|".join(block_reasons),
                "executed": not blocked,
                "cumulative_r": cumulative_r,
            }
        )

    summary = _scenario_summary(
        scenario=scenario,
        rows=rows,
        executed_r=executed_r,
        blocked_signals=blocked_signals,
        avoided_losses=avoided_losses,
        missed_wins=missed_wins,
    )
    return {"summary": summary, "details": detail_rows}


def _closed_event_from_row(row: dict[str, object], result_r: float) -> dict[str, object] | None:
    closed_at = _parse_datetime(str(row.get("closed_at") or ""))
    if closed_at is None:
        closed_at = _parse_datetime(str(row.get("timestamp") or ""))
    if closed_at is None:
        return None
    return {"closed_at": closed_at, "result_r": result_r}


def _scenario_summary(
    *,
    scenario: ScenarioConfig,
    rows: list[dict[str, object]],
    executed_r: list[float],
    blocked_signals: int,
    avoided_losses: int,
    missed_wins: int,
) -> dict[str, object]:
    wins = [value for value in executed_r if value > 0]
    losses = [value for value in executed_r if value < 0]
    total_r = round(sum(executed_r), 4)
    meta_unknown = sum(1 for row in rows if _tri_state(row.get("would_meta_filter_block")) == TRI_UNKNOWN)
    return {
        "scenario": scenario.name,
        "total_signals": len(executed_r),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": round(len(wins) / (len(wins) + len(losses)) * 100, 2) if wins or losses else 0.0,
        "total_r": total_r,
        "avg_r": round(total_r / len(executed_r), 4) if executed_r else 0.0,
        "max_drawdown_r": round(_max_drawdown(executed_r), 4),
        "consecutive_losses_max": _max_consecutive_losses(executed_r),
        "blocked_signals": blocked_signals,
        "avoided_losses": avoided_losses,
        "missed_wins": missed_wins,
        "meta_filter_evaluable": TRI_TRUE if meta_unknown == 0 else TRI_FALSE,
        "meta_unknown_signals": meta_unknown,
    }


def _max_drawdown(values: list[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    drawdown = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        drawdown = min(drawdown, cumulative - peak)
    return drawdown


def _max_consecutive_losses(values: list[float]) -> int:
    current = 0
    maximum = 0
    for value in values:
        if value < 0:
            current += 1
            maximum = max(maximum, current)
        elif value > 0:
            current = 0
    return maximum


def _tri_state(value: object) -> str:
    text = str(value).strip().lower()
    if text == TRI_TRUE:
        return TRI_TRUE
    if text == TRI_FALSE:
        return TRI_FALSE
    return TRI_UNKNOWN


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="backtest-public-signal-filters")
    parser.add_argument("--data-path", default="data")
    parser.add_argument("--logs-path", default="logs")
    parser.add_argument("--reports-path", default="reports")
    parser.add_argument("--days", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = backtest_public_signal_filters(
        data_path=Path(args.data_path),
        logs_path=Path(args.logs_path),
        reports_path=Path(args.reports_path),
        days=args.days,
    )
    print(format_backtest(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
