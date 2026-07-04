from __future__ import annotations

import math
from statistics import median, pstdev
from typing import Any, Iterable


def to_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def rounded(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def confidence_level(evidence: int) -> str:
    if evidence >= 80:
        return "HIGH"
    if evidence >= 30:
        return "MEDIUM"
    if evidence >= 10:
        return "LOW"
    return "VERY_LOW"


def compute_metrics(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    materialized = list(rows)
    closed = [row for row in materialized if to_float(row.get("result_r")) is not None]
    returns = [to_float(row.get("result_r")) or 0.0 for row in closed]
    wins = [value for value in returns if value > 0]
    losses = [value for value in returns if value < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    total_r = sum(returns)
    return {
        "trades": len(materialized),
        "closed": len(closed),
        "open": len(materialized) - len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "neutral": len([value for value in returns if value == 0]),
        "winrate": rounded((len(wins) / len(closed) * 100) if closed else 0.0),
        "profit_factor": rounded((gross_win / gross_loss) if gross_loss else (gross_win if gross_win else 0.0)),
        "total_r": rounded(total_r),
        "avg_r": rounded((total_r / len(closed)) if closed else 0.0),
        "median_r": rounded(median(returns) if returns else 0.0),
        "expectancy": rounded((total_r / len(closed)) if closed else 0.0),
        "average_win": rounded((sum(wins) / len(wins)) if wins else 0.0),
        "average_loss": rounded((sum(losses) / len(losses)) if losses else 0.0),
        "std_dev": rounded(pstdev(returns) if len(returns) > 1 else 0.0),
        "drawdown": rounded(max_drawdown(returns)),
        "evidence": len(closed),
        "confidence": confidence_level(len(closed)),
    }


def max_drawdown(returns: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for value in returns:
        equity += value
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return worst


def group_metrics(rows: list[dict[str, Any]], feature: str, *, min_trades: int = 1) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        value = normalize_group_value(row.get(feature))
        grouped.setdefault(value, []).append(row)
    output = []
    for value, group_rows in grouped.items():
        metrics = compute_metrics(group_rows)
        if metrics["closed"] < min_trades:
            continue
        output.append({"feature": feature, "value": value, **metrics})
    return sorted(output, key=lambda item: (item["profit_factor"], item["total_r"], item["closed"]), reverse=True)


def combination_metrics(
    rows: list[dict[str, Any]],
    features: tuple[str, ...],
    *,
    min_trades: int = 1,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for row in rows:
        key = tuple(normalize_group_value(row.get(feature)) for feature in features)
        if any(value == "UNKNOWN" for value in key):
            continue
        grouped.setdefault(key, []).append(row)
    output = []
    for key, group_rows in grouped.items():
        metrics = compute_metrics(group_rows)
        if metrics["closed"] < min_trades:
            continue
        context = dict(zip(features, key, strict=True))
        output.append({"features": list(features), "context": context, "label": " + ".join(key), **metrics})
    return sorted(output, key=lambda item: (item["profit_factor"], item["expectancy"], item["total_r"]), reverse=True)


def normalize_group_value(value: Any) -> str:
    if value in (None, ""):
        return "UNKNOWN"
    if isinstance(value, bool):
        return str(value).lower()
    return str(value).strip() or "UNKNOWN"


def pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(ys) < 2 or len(xs) != len(ys):
        return 0.0
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    denom_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    denom_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if denom_x == 0 or denom_y == 0:
        return 0.0
    return numerator / (denom_x * denom_y)
