from __future__ import annotations

from collections.abc import Iterable
from typing import Any


RELAXED_POLICY_VERSION = "relaxed_public_safety_v2"


def evaluate_relaxed_public_safety_v2(
    *,
    trade: dict[str, Any],
    history: Iterable[dict[str, Any]] | None = None,
    min_rr: float = 1.5,
    min_context_sample: int = 5,
) -> dict[str, Any]:
    """Shadow-only public policy candidate.

    This policy never controls public publication. It is used by offline
    backtests and by runtime private shadow diagnostics to estimate whether a
    less restrictive public policy would have improved visibility.
    """

    history_rows = list(history or [])
    direction = _norm_lower(trade.get("direction"))
    market_regime = _norm_upper(trade.get("market_regime"))
    entry_context = _norm_upper(trade.get("entry_context"))
    warnings = _tokens(trade.get("warnings") or trade.get("avoidance_warnings"))
    penalties = _tokens(trade.get("penalties"))
    reason_tokens = set(warnings) | set(penalties) | _tokens(
        trade.get("blocking_reasons")
        or trade.get("conditions_failed")
        or trade.get("entry_or_rejection_reason")
        or trade.get("rejection_reason")
    )

    edge = _historical_edge(trade, history_rows, min_context_sample=min_context_sample)
    explicit_edge = _explicit_historical_edge(trade)
    if explicit_edge["favorable"]:
        edge = {**edge, **explicit_edge}
    negative_context = _negative_context(trade, history_rows, min_context_sample=min_context_sample)
    rr = _risk_reward(trade)

    block_reasons: list[str] = []
    warnings_out: list[str] = []

    if direction == "long" and market_regime == "HIGH_VOLATILITY":
        block_reasons.append("high_volatility_long")
    if "high_volatility_long" in reason_tokens:
        block_reasons.append("high_volatility_long")

    if _risk_plan_invalid(trade, reason_tokens):
        block_reasons.append("risk_plan_missing")

    if rr is not None and rr < min_rr:
        block_reasons.append("rr_below_min")

    if negative_context["negative"]:
        block_reasons.append("negative_context_with_sufficient_sample")

    if _against_htf(trade, reason_tokens) and not edge["favorable"]:
        block_reasons.append("against_htf_without_edge")

    if direction == "short":
        if edge["favorable"]:
            warnings_out.append("short_allowed_by_historical_edge")
        else:
            block_reasons.append("short_without_demonstrated_edge")

    return {
        "public_allowed": not block_reasons,
        "block_reasons": _dedupe(block_reasons),
        "warnings": _dedupe(warnings_out),
        "policy_version": RELAXED_POLICY_VERSION,
        "historical_edge_favorable": edge["favorable"],
        "historical_context": edge,
        "negative_context": negative_context,
        "risk_reward": rr,
        "min_rr": min_rr,
    }


def _historical_edge(
    trade: dict[str, Any],
    history: list[dict[str, Any]],
    *,
    min_context_sample: int,
) -> dict[str, Any]:
    for dimensions in (
        ("direction", "setup_type", "market_regime", "session", "entry_context"),
        ("direction", "setup_type", "session", "entry_context"),
        ("direction", "session"),
        ("direction",),
    ):
        matches = _matching_history(trade, history, dimensions)
        stats = _stats(matches)
        if stats["sample_size"] >= min_context_sample:
            favorable = (
                stats["profit_factor"] >= 1.2
                or stats["avg_r"] > 0
                or stats["winrate"] >= 50
            )
            return {
                **stats,
                "dimensions": list(dimensions),
                "favorable": favorable,
            }
    return {
        "sample_size": 0,
        "winrate": 0.0,
        "avg_r": 0.0,
        "total_r": 0.0,
        "profit_factor": 0.0,
        "dimensions": [],
        "favorable": False,
    }


def _explicit_historical_edge(trade: dict[str, Any]) -> dict[str, Any]:
    candidates = [
        trade,
        _dict(trade.get("historical_edge")),
        _dict(trade.get("edge_score")),
        _dict(trade.get("pattern_memory")).get("historical_edge"),
        _dict(trade.get("pattern_memory")).get("edge_score"),
    ]
    for candidate in candidates:
        data = _dict(candidate)
        confidence = str(data.get("historical_confidence") or data.get("confidence_level") or "").upper()
        edge_score = _float(data.get("historical_edge_score"))
        winrate = _float(data.get("matched_winrate") or data.get("historical_winrate") or data.get("winrate"))
        avg_r = _float(data.get("matched_avg_r") or data.get("historical_avg_r") or data.get("avg_r"))
        profit_factor = _float(data.get("matched_profit_factor") or data.get("historical_profit_factor") or data.get("profit_factor"))
        if confidence == "HIGH" or (edge_score is not None and edge_score >= 70):
            return {
                "sample_size": int(_float(data.get("matched_patterns_count") or data.get("similar_count")) or 0),
                "winrate": round(winrate or 0.0, 2),
                "avg_r": round(avg_r or 0.0, 4),
                "total_r": 0.0,
                "profit_factor": round(profit_factor or 0.0, 4),
                "dimensions": ["explicit_historical_edge"],
                "favorable": True,
            }
    return {"favorable": False}


def _negative_context(
    trade: dict[str, Any],
    history: list[dict[str, Any]],
    *,
    min_context_sample: int,
) -> dict[str, Any]:
    dimensions = ("direction", "setup_type", "market_regime", "session", "entry_context", "trade_location")
    matches = _matching_history(trade, history, dimensions)
    stats = _stats(matches)
    negative = (
        stats["sample_size"] >= min_context_sample
        and (stats["profit_factor"] < 1.0 or stats["avg_r"] < 0)
    )
    return {
        **stats,
        "dimensions": list(dimensions),
        "negative": negative,
    }


def _matching_history(
    trade: dict[str, Any],
    history: list[dict[str, Any]],
    dimensions: tuple[str, ...],
) -> list[dict[str, Any]]:
    return [
        item
        for item in history
        if all(_dimension_value(item, dimension) == _dimension_value(trade, dimension) for dimension in dimensions)
    ]


def _stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [_float(item.get("result_r")) for item in rows]
    values = [value for value in values if value is not None]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    gross_profit = sum(max(0.0, value) for value in values)
    gross_loss = abs(sum(min(0.0, value) for value in values))
    return {
        "sample_size": len(values),
        "winrate": round(len(wins) / len(values) * 100, 2) if values else 0.0,
        "avg_r": round(sum(values) / len(values), 4) if values else 0.0,
        "total_r": round(sum(values), 4),
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0 else (round(gross_profit, 4) if gross_profit else 0.0),
    }


def _risk_plan_invalid(trade: dict[str, Any], reason_tokens: set[str]) -> bool:
    if "risk_plan_missing" in reason_tokens or "risk_plan_invalid" in reason_tokens:
        return True
    if "risk_plan_valid" in trade:
        return not _truthy(trade.get("risk_plan_valid"))
    value = str(trade.get("risk_plan") or "").strip().lower()
    return value in {"missing", "invalid", "false", "0"}


def _risk_reward(trade: dict[str, Any]) -> float | None:
    for key in ("risk_reward", "risk_reward_tp1", "risk_reward_tp2", "rr"):
        value = _float(trade.get(key))
        if value is not None:
            return value

    entry = _float(trade.get("entry") or trade.get("entry_price"))
    stop_loss = _float(trade.get("stop_loss") or trade.get("sl"))
    take_profit = _float(trade.get("take_profit") or trade.get("tp1") or trade.get("take_profit_1"))
    if entry is None or stop_loss is None or take_profit is None:
        return None
    direction = _norm_lower(trade.get("direction"))
    if direction == "short":
        risk = stop_loss - entry
        reward = entry - take_profit
    else:
        risk = entry - stop_loss
        reward = take_profit - entry
    if risk <= 0 or reward <= 0:
        return 0.0
    return round(reward / risk, 4)


def _against_htf(trade: dict[str, Any], reason_tokens: set[str]) -> bool:
    if "against_htf" in reason_tokens or "higher_timeframe_contradicts_long" in reason_tokens:
        return True
    direction = _norm_lower(trade.get("direction"))
    trend_higher = _norm_lower(trade.get("trend_higher_timeframe") or trade.get("trend_higher") or trade.get("trend_4h"))
    if direction == "long" and trend_higher == "bearish":
        return True
    if direction == "short" and trend_higher == "bullish":
        return True
    return False


def _dimension_value(item: dict[str, Any], dimension: str) -> str:
    if dimension == "direction":
        return _norm_lower(item.get(dimension))
    return _norm_upper(item.get(dimension))


def _tokens(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, list):
        return {str(item).strip().lower() for item in value if str(item).strip()}
    text = str(value).strip()
    if not text:
        return set()
    normalized = text.replace("|", ",").replace(";", ",")
    return {item.strip().lower() for item in normalized.split(",") if item.strip()}


def _truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _norm_upper(value: object) -> str:
    return str(value or "UNKNOWN").strip().upper()


def _norm_lower(value: object) -> str:
    return str(value or "").strip().lower()


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
