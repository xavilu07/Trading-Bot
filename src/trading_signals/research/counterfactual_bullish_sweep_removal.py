from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades


def analyze_counterfactual_bullish_sweep_removal(*, data_path: Path, now: datetime | None = None) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    all_trades = load_canonical_closed_trades(data_path)
    bullish_sweep = [row for row in all_trades if _liquidity_context(row) == "sweep:bullish_sweep"]
    without_bullish_sweep = [row for row in all_trades if _liquidity_context(row) != "sweep:bullish_sweep"]
    current = _metrics(all_trades)
    without = _metrics(without_bullish_sweep)
    removed = _metrics(bullish_sweep)
    deltas = {
        "pf_delta": _round(_pf_float(without["profit_factor"]) - _pf_float(current["profit_factor"])),
        "total_r_delta": _round(float(without["total_r"]) - float(current["total_r"])),
        "winrate_delta": _round(float(without["winrate"]) - float(current["winrate"])),
        "avg_r_delta": _round(float(without["avg_r"]) - float(current["avg_r"])),
        "trades_removed": removed["trades"],
    }
    return {
        "scope": "COUNTERFACTUAL_BULLISH_SWEEP_REMOVAL",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "current": current,
        "without_bullish_sweep": without,
        "removed_bullish_sweep": removed,
        "deltas": deltas,
        "answer": _answer(current=current, without=without, removed=removed, deltas=deltas),
    }


def write_counterfactual_bullish_sweep_removal_report(result: dict[str, Any], reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "counterfactual_bullish_sweep_removal.md"
    path.write_text(format_counterfactual_bullish_sweep_removal_markdown(result), encoding="utf-8")
    return path


def format_counterfactual_bullish_sweep_removal_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# COUNTERFACTUAL_BULLISH_SWEEP_REMOVAL",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        "",
        "## Summary",
        "",
        "| Scenario | Trades | Wins | Losses | WR | PF | Total R | Avg R |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        _metrics_row("Current global", result.get("current", {})),
        _metrics_row("Without bullish_sweep", result.get("without_bullish_sweep", {})),
        _metrics_row("Removed bullish_sweep only", result.get("removed_bullish_sweep", {})),
        "",
        "## Delta",
        "",
        f"- PF delta: {result.get('deltas', {}).get('pf_delta', 0)}",
        f"- Total R delta: {result.get('deltas', {}).get('total_r_delta', 0)}",
        f"- Winrate delta: {result.get('deltas', {}).get('winrate_delta', 0)}",
        f"- Avg R delta: {result.get('deltas', {}).get('avg_r_delta', 0)}",
        f"- Trades removed: {result.get('deltas', {}).get('trades_removed', 0)}",
        "",
        "## Answer",
        "",
        result.get("answer", ""),
        "",
    ]
    return "\n".join(lines)


def _answer(*, current: dict[str, Any], without: dict[str, Any], removed: dict[str, Any], deltas: dict[str, Any]) -> str:
    removed_trades = int(removed.get("trades", 0) or 0)
    if removed_trades == 0:
        return "No bullish_sweep trades were found in the canonical dataset, so removing it has no measurable effect."
    pf_delta = float(deltas.get("pf_delta", 0.0) or 0.0)
    total_r_delta = float(deltas.get("total_r_delta", 0.0) or 0.0)
    winrate_delta = float(deltas.get("winrate_delta", 0.0) or 0.0)
    if total_r_delta > 0 and pf_delta > 0:
        direction = "improves"
    elif total_r_delta < 0 and pf_delta < 0:
        direction = "worsens"
    else:
        direction = "mixed effect on"
    return (
        f"Removing bullish_sweep {direction} the system: PF changes from {current.get('profit_factor')} to "
        f"{without.get('profit_factor')} ({pf_delta:+.4f}), Total R changes from {current.get('total_r')} to "
        f"{without.get('total_r')} ({total_r_delta:+.4f}), and WR changes from {current.get('winrate')}% to "
        f"{without.get('winrate')}% ({winrate_delta:+.4f} pp)."
    )


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [_float(row.get("result_r")) for row in rows]
    values = [value for value in values if value is not None]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "trades": len(values),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": _round(len(wins) / len(values) * 100) if values else 0.0,
        "profit_factor": _profit_factor(gross_profit, gross_loss),
        "total_r": _round(sum(values)),
        "avg_r": _round(sum(values) / len(values)) if values else 0.0,
    }


def _liquidity_context(row: dict[str, Any]) -> str:
    explicit = str(row.get("liquidity_context") or "").strip()
    if explicit:
        return explicit
    sweep = str(row.get("liquidity_sweep") or "").strip()
    if sweep:
        return f"sweep:{sweep}"
    return "UNKNOWN"


def _profit_factor(gross_profit: float, gross_loss: float) -> float | str:
    if gross_loss > 0:
        return _round(gross_profit / gross_loss)
    if gross_profit > 0:
        return "inf"
    return 0.0


def _pf_float(value: object) -> float:
    if value == "inf":
        return 999.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float) -> float:
    return round(value, 4)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _metrics_row(label: str, metrics: object) -> str:
    if not isinstance(metrics, dict):
        metrics = {}
    return (
        f"| {label} | {metrics.get('trades', 0)} | {metrics.get('wins', 0)} | {metrics.get('losses', 0)} | "
        f"{metrics.get('winrate', 0)}% | {metrics.get('profit_factor', 0)} | {metrics.get('total_r', 0)} | {metrics.get('avg_r', 0)} |"
    )
