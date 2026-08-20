from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


CLOSED_STATUSES = {"tp2_hit", "tp_hit", "sl_hit", "expired", "breakeven", "closed"}
#: Universes the strategy declined. Their trades are tracked as counterfactuals —
#: "what would have happened had we taken this" — and must not drive the risk
#: brake, which exists to stop trading when the trades we *did* take go badly.
DECLINED_UNIVERSES = {"rejected", "shadow"}
LOSS_STATUSES = {"sl_hit", "loss"}
WIN_OUTCOMES = {"win", "tp_hit", "tp2_hit"}
LOSS_OUTCOMES = {"loss", "sl_hit"}


@dataclass(frozen=True)
class KillSwitchConfig:
    enabled: bool = False
    max_daily_loss_r: float = 2.0
    max_consecutive_losses: int = 2
    max_weekly_drawdown_r: float = 4.0
    cooldown_hours: int = 12


def evaluate_kill_switch(
    data_path: Path,
    *,
    enabled: bool = False,
    max_daily_loss_r: float = 2.0,
    max_consecutive_losses: int = 2,
    max_weekly_drawdown_r: float = 4.0,
    cooldown_hours: int = 12,
    consecutive_loss_reset_hours: float = 12.0,
    now: datetime | None = None,
) -> dict[str, object]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    trades = sorted(_load_closed_trades(data_path), key=lambda item: item["closed_at"])
    day_start = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now_dt - timedelta(days=7)
    daily_realized_r = round(sum(float(item["result_r"]) for item in trades if item["closed_at"] >= day_start), 4)
    weekly_realized_r = round(sum(float(item["result_r"]) for item in trades if item["closed_at"] >= week_start), 4)
    consecutive_losses = _consecutive_losses(trades)
    last_loss = _last_loss_time(trades)
    cooldown_until = last_loss + timedelta(hours=cooldown_hours) if last_loss is not None else None
    in_cooldown = cooldown_until is not None and now_dt < cooldown_until
    # A consecutive-loss streak can never resolve itself through new trades while it is
    # itself the thing blocking new trades from opening (see resolved incident 2026-08-02:
    # trading stayed paused for days past the intended -4R weekly cap because 2 old losses
    # kept "winning" the elif race forever). Past this window with no further losses, treat
    # the streak as stale and let daily/weekly checks (which do decay with real time as old
    # trades age out of their rolling windows) decide instead.
    consecutive_losses_stale = (
        last_loss is not None
        and consecutive_loss_reset_hours > 0
        and now_dt >= last_loss + timedelta(hours=consecutive_loss_reset_hours)
    )

    reason = ""
    if enabled:
        if daily_realized_r <= -abs(max_daily_loss_r):
            reason = "daily_loss_limit"
        elif consecutive_losses >= max_consecutive_losses and not consecutive_losses_stale:
            reason = "consecutive_losses_limit"
        elif weekly_realized_r <= -abs(max_weekly_drawdown_r):
            reason = "weekly_drawdown_limit"
        elif in_cooldown:
            reason = "cooldown_active"

    return {
        "enabled": enabled,
        "daily_realized_r": daily_realized_r,
        "weekly_realized_r": weekly_realized_r,
        "consecutive_losses": consecutive_losses,
        "consecutive_losses_stale": consecutive_losses_stale,
        "last_loss_time": last_loss.isoformat() if last_loss is not None else None,
        "kill_switch_active": bool(enabled and reason),
        "kill_switch_reason": reason,
        "cooldown_until": cooldown_until.isoformat() if cooldown_until is not None else None,
    }


def _load_closed_trades(data_path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted((data_path / "paper_trading").glob("*.csv")):
        rows.extend(_read_closed_trade_rows(path))
    rows.extend(_read_closed_trade_rows(data_path / "live_trading" / "trades.csv"))
    return rows


def _read_closed_trade_rows(path: Path) -> list[dict[str, object]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    rows: list[dict[str, object]] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                normalized = _normalize_trade_row(row)
                if normalized is not None:
                    rows.append(normalized)
    except csv.Error:
        return []
    return rows


def _normalize_trade_row(row: dict[str, str]) -> dict[str, object] | None:
    if str(row.get("universe") or "").strip().lower() in DECLINED_UNIVERSES:
        # Paper trades whose signal failed the quality gate are still recorded,
        # with a full lifecycle and a result_r, as `universe=rejected`. They used
        # to count here, so the bot disabled itself over trades it had refused to
        # take: in the five days to 2026-08-20, 8 of the 15 losses the kill
        # switch saw were rejected-universe, and 4 of the 5 pauses were triggered
        # by one — including a pause opened on a day whose realized R was +1.0.
        return None
    closed_at = _closed_time(row)
    if closed_at is None:
        return None
    result_r = _result_r(row)
    if result_r is None:
        return None
    return {"closed_at": closed_at, "result_r": result_r}


def _closed_time(row: dict[str, str]) -> datetime | None:
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


def _result_r(row: dict[str, str]) -> float | None:
    for key in ("result_r", "r_result", "realized_r"):
        raw = row.get(key)
        if raw not in {None, ""}:
            value = _float(raw)
            if value is not None:
                return value
    outcome = str(row.get("outcome") or row.get("status") or "").strip().lower()
    if outcome in WIN_OUTCOMES:
        return 1.0
    if outcome in LOSS_OUTCOMES:
        return -1.0
    return None


def _consecutive_losses(trades: list[dict[str, object]]) -> int:
    count = 0
    for trade in reversed(trades):
        result = float(trade["result_r"])
        if result < 0:
            count += 1
            continue
        if result > 0:
            break
    return count


def _last_loss_time(trades: list[dict[str, object]]) -> datetime | None:
    for trade in reversed(trades):
        if float(trade["result_r"]) < 0:
            return trade["closed_at"]  # type: ignore[return-value]
    return None


def _parse_datetime(raw: str) -> datetime | None:
    try:
        return _aware(datetime.fromisoformat(raw.replace("Z", "+00:00")))
    except ValueError:
        return None


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
