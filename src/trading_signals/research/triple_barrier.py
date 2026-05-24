from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any


TP_HIT = "TP_HIT"
SL_HIT = "SL_HIT"
TIMEOUT = "TIMEOUT"
UNKNOWN = "UNKNOWN"

WIN_STATUSES = {"tp_hit", "tp2_hit", "win"}
LOSS_STATUSES = {"sl_hit", "loss"}
TIMEOUT_STATUSES = {"expired", "timeout"}


def label_triple_barrier(
    signal: dict[str, Any],
    bars: list[dict[str, Any]] | None = None,
    *,
    time_barrier_bars: int = 24,
) -> dict[str, Any]:
    """Label a signal with TP/SL/time barriers using only observed data.

    Bars are expected to be post-entry OHLC records. If timestamps are present,
    bars at or before the signal timestamp are ignored.
    """
    entry = _float(signal.get("entry") or signal.get("entry_price"))
    stop_loss = _float(signal.get("stop_loss") or signal.get("sl"))
    take_profit = _float(
        signal.get("take_profit")
        or signal.get("take_profit_1")
        or signal.get("tp1")
        or signal.get("tp")
    )
    direction = str(signal.get("direction") or "").strip().lower()
    if entry is None or stop_loss is None or take_profit is None or direction not in {"long", "short"}:
        return _result(UNKNOWN, "missing_required_data")

    risk = abs(entry - stop_loss)
    if risk <= 0:
        return _result(UNKNOWN, "invalid_risk")

    normalized_bars = _post_entry_bars(bars or _extract_bars(signal), _parse_datetime(str(signal.get("timestamp") or "")))
    if normalized_bars:
        return _label_from_bars(
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            direction=direction,
            risk=risk,
            bars=normalized_bars,
            time_barrier_bars=max(1, time_barrier_bars),
        )

    status_label = _label_from_recorded_status(signal, entry=entry, stop_loss=stop_loss, take_profit=take_profit, direction=direction, risk=risk)
    if status_label is not None:
        return status_label
    return _result(UNKNOWN, "missing_price_path")


def _label_from_bars(
    *,
    entry: float,
    stop_loss: float,
    take_profit: float,
    direction: str,
    risk: float,
    bars: list[dict[str, Any]],
    time_barrier_bars: int,
) -> dict[str, Any]:
    max_r: float | None = None
    min_r: float | None = None
    observed = bars[:time_barrier_bars]
    for index, bar in enumerate(observed, start=1):
        high = _float(bar.get("high"))
        low = _float(bar.get("low"))
        if high is None or low is None:
            continue

        favorable_r, adverse_r = _bar_r_range(entry=entry, high=high, low=low, direction=direction, risk=risk)
        max_r = favorable_r if max_r is None else max(max_r, favorable_r)
        min_r = adverse_r if min_r is None else min(min_r, adverse_r)

        tp_hit = high >= take_profit if direction == "long" else low <= take_profit
        sl_hit = low <= stop_loss if direction == "long" else high >= stop_loss
        if tp_hit and sl_hit:
            return _result(
                UNKNOWN,
                "ambiguous_same_bar",
                result_r=None,
                max_r=max_r,
                min_r=min_r,
                bars_to_label=index,
            )
        if tp_hit:
            return _result(
                TP_HIT,
                "take_profit_barrier_hit",
                result_r=_tp_result_r(entry, take_profit, direction, risk),
                max_r=max_r,
                min_r=min_r,
                bars_to_label=index,
            )
        if sl_hit:
            return _result(
                SL_HIT,
                "stop_loss_barrier_hit",
                result_r=-1.0,
                max_r=max_r,
                min_r=min_r,
                bars_to_label=index,
            )

    if len(observed) >= time_barrier_bars:
        close = _float(observed[-1].get("close"))
        return _result(
            TIMEOUT,
            "time_barrier_reached",
            result_r=_close_result_r(entry, close, direction, risk),
            max_r=max_r,
            min_r=min_r,
            bars_to_label=time_barrier_bars,
        )
    return _result(
        UNKNOWN,
        "insufficient_bars",
        result_r=None,
        max_r=max_r,
        min_r=min_r,
        bars_to_label=len(observed),
    )


def _label_from_recorded_status(
    signal: dict[str, Any],
    *,
    entry: float,
    stop_loss: float,
    take_profit: float,
    direction: str,
    risk: float,
) -> dict[str, Any] | None:
    status = str(signal.get("status") or signal.get("outcome") or signal.get("exit_reason") or "").strip().lower()
    result_r = _float(signal.get("result_r") or signal.get("r_result") or signal.get("realized_r"))
    max_r = _float(signal.get("mfe_r") or signal.get("max_r") or signal.get("max_favorable_move"))
    min_r = _float(signal.get("mae_r") or signal.get("min_r") or signal.get("max_adverse_move"))
    bars_to_label = _int(signal.get("bars_to_label") or signal.get("candles_held") or signal.get("bars_held") or signal.get("candles_elapsed"))
    if status in WIN_STATUSES:
        return _result(
            TP_HIT,
            "recorded_status_tp",
            result_r=result_r if result_r is not None else _tp_result_r(entry, take_profit, direction, risk),
            max_r=max_r,
            min_r=min_r,
            bars_to_label=bars_to_label,
        )
    if status in LOSS_STATUSES:
        return _result(
            SL_HIT,
            "recorded_status_sl",
            result_r=result_r if result_r is not None else -1.0,
            max_r=max_r,
            min_r=min_r,
            bars_to_label=bars_to_label,
        )
    if status in TIMEOUT_STATUSES:
        return _result(
            TIMEOUT,
            "recorded_status_timeout",
            result_r=result_r,
            max_r=max_r,
            min_r=min_r,
            bars_to_label=bars_to_label,
        )
    return None


def _bar_r_range(*, entry: float, high: float, low: float, direction: str, risk: float) -> tuple[float, float]:
    if direction == "long":
        return (high - entry) / risk, (low - entry) / risk
    return (entry - low) / risk, (entry - high) / risk


def _tp_result_r(entry: float, take_profit: float, direction: str, risk: float) -> float:
    if direction == "long":
        return round((take_profit - entry) / risk, 6)
    return round((entry - take_profit) / risk, 6)


def _close_result_r(entry: float, close: float | None, direction: str, risk: float) -> float | None:
    if close is None:
        return None
    if direction == "long":
        return round((close - entry) / risk, 6)
    return round((entry - close) / risk, 6)


def _post_entry_bars(bars: list[dict[str, Any]], timestamp: datetime | None) -> list[dict[str, Any]]:
    if timestamp is None:
        return bars
    filtered = []
    for bar in bars:
        bar_time = _parse_datetime(
            str(bar.get("timestamp") or bar.get("open_time") or bar.get("close_time") or bar.get("time") or "")
        )
        if bar_time is None or bar_time > timestamp:
            filtered.append(bar)
    return filtered


def _extract_bars(signal: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("bars", "candles", "price_bars", "ohlcv"):
        value = signal.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)]
    return []


def _result(
    label: str,
    reason: str,
    *,
    result_r: float | None = None,
    max_r: float | None = None,
    min_r: float | None = None,
    bars_to_label: int | None = None,
) -> dict[str, Any]:
    return {
        "label": label,
        "label_reason": reason,
        "result_r": "" if result_r is None else round(result_r, 6),
        "max_r": "" if max_r is None else round(max_r, 6),
        "min_r": "" if min_r is None else round(min_r, 6),
        "bars_to_label": "" if bars_to_label is None else bars_to_label,
    }


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


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
