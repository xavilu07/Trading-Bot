from __future__ import annotations

from collections import Counter
from statistics import median, pstdev
from typing import Any


WIN_STATUSES = {"tp2_hit", "tp_hit", "tp1_hit", "win"}
LOSS_STATUSES = {"sl_hit", "loss"}


def compute_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [row for row in rows if row.get("result_r") is not None]
    values = [float(row["result_r"]) for row in closed]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    max_drawdown, current_drawdown = drawdowns(values)
    winning_streak, losing_streak = streaks(values)
    return {
        "trades": len(rows),
        "closed": len(closed),
        "open": len([row for row in rows if row.get("result_r") is None]),
        "wins": len(wins),
        "losses": len(losses),
        "neutral": len([value for value in values if value == 0]),
        "winrate": round(len(wins) / len(values) * 100, 4) if values else 0.0,
        "profit_factor": round(gross_win / gross_loss, 4) if gross_loss else (round(gross_win, 4) if gross_win else 0.0),
        "expectancy": round(sum(values) / len(values), 4) if values else 0.0,
        "avg_r": round(sum(values) / len(values), 4) if values else 0.0,
        "average_win": round(sum(wins) / len(wins), 4) if wins else 0.0,
        "average_loss": round(sum(losses) / len(losses), 4) if losses else 0.0,
        "total_r": round(sum(values), 4),
        "median_r": round(median(values), 4) if values else 0.0,
        "std_dev": round(pstdev(values), 4) if len(values) > 1 else 0.0,
        "max_drawdown": round(max_drawdown, 4),
        "current_drawdown": round(current_drawdown, 4),
        "winning_streak": winning_streak,
        "losing_streak": losing_streak,
        "confidence": confidence_level(len(values)),
        "evidence_count": len(values),
    }


def group_metrics(rows: list[dict[str, Any]], dimension: str, *, min_trades: int = 1) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = str(row.get(dimension) or "UNKNOWN")
        groups.setdefault(key, []).append(row)
    output = []
    for value, group in groups.items():
        metrics = compute_metrics(group)
        if int(metrics["closed"]) < min_trades:
            continue
        output.append({"dimension": dimension, "value": value, **metrics})
    return sorted(output, key=lambda item: (float(item["profit_factor"]), float(item["total_r"])), reverse=True)


def group_by_dimensions(rows: list[dict[str, Any]], dimensions: tuple[str, ...], *, min_trades: int = 1) -> list[dict[str, Any]]:
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for row in rows:
        key = tuple(str(row.get(dimension) or "UNKNOWN") for dimension in dimensions)
        groups.setdefault(key, []).append(row)
    output = []
    for key, group in groups.items():
        metrics = compute_metrics(group)
        if int(metrics["closed"]) < min_trades:
            continue
        context = dict(zip(dimensions, key, strict=True))
        label = " | ".join(f"{dimension}={value}" for dimension, value in context.items())
        output.append({"dimensions": list(dimensions), "context": context, "label": label, **metrics})
    return sorted(output, key=lambda item: (float(item["profit_factor"]), float(item["total_r"])), reverse=True)


def confidence_level(evidence_count: int) -> str:
    if evidence_count >= 80:
        return "HIGH"
    if evidence_count >= 30:
        return "MEDIUM"
    return "LOW"


def drawdowns(values: list[float]) -> tuple[float, float]:
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        max_drawdown = min(max_drawdown, cumulative - peak)
    return max_drawdown, cumulative - peak


def streaks(values: list[float]) -> tuple[int, int]:
    best_win = 0
    best_loss = 0
    current_win = 0
    current_loss = 0
    for value in values:
        if value > 0:
            current_win += 1
            current_loss = 0
        elif value < 0:
            current_loss += 1
            current_win = 0
        else:
            current_win = 0
            current_loss = 0
        best_win = max(best_win, current_win)
        best_loss = max(best_loss, current_loss)
    return best_win, best_loss


def summarize_statuses(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("status") or "UNKNOWN") for row in rows).most_common())
