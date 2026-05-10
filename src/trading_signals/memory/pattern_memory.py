from __future__ import annotations

from trading_signals.memory.similarity import compare_with_history


def build_pattern_record(
    *,
    timestamp: str,
    symbol: str,
    direction: str,
    setup_type: str,
    score: float,
    setup_context: dict[str, object],
    htf_trend: str,
    ltf_trend: str,
    timeframe_alignment: bool,
    penalties: list[str],
    blocking_reasons: list[str],
    risk_plan,
    final_status: str,
    outcome: str | None = None,
    r_result: float | None = None,
) -> dict[str, object]:
    return {
        "timestamp": timestamp,
        "symbol": symbol,
        "direction": direction,
        "setup_type": setup_type,
        "score": score,
        "market_regime": setup_context.get("market_regime"),
        "session": setup_context.get("session"),
        "entry_context": setup_context.get("entry_context"),
        "trade_location": setup_context.get("trade_location"),
        "htf_trend": htf_trend,
        "ltf_trend": ltf_trend,
        "timeframe_alignment": timeframe_alignment,
        "warnings": list(setup_context.get("avoidance_warnings", []) or []),
        "penalties": penalties,
        "blocking_reasons": blocking_reasons,
        "entry": getattr(risk_plan, "entry", None),
        "stop_loss": getattr(risk_plan, "stop_loss", None),
        "take_profit": getattr(risk_plan, "take_profit", None),
        "rr": getattr(risk_plan, "risk_reward", None),
        "final_status": final_status,
        "outcome": outcome,
        "r_result": r_result,
    }


def evaluate_pattern_memory(record: dict[str, object], history: list[dict[str, object]]) -> dict[str, object]:
    summary = compare_with_history(record, history)
    return {
        **summary,
        "has_sufficient_memory": int(summary["similar_count"]) >= 3,
    }
