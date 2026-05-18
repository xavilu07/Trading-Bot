from __future__ import annotations

import logging

from trading_signals.infrastructure.logging.logger import log_json
from trading_signals.memory.adaptive_thresholds import calculate_adaptive_thresholds
from trading_signals.memory.edge_confirmation import calculate_edge_confirmation
from trading_signals.memory.edge_score import calculate_historical_edge_score
from trading_signals.memory.insights import build_pattern_memory_insights
from trading_signals.memory.meta_decision_engine import evaluate_meta_decision
from trading_signals.memory.pattern_memory import evaluate_pattern_memory
from trading_signals.memory.trade_quality import classify_trade_quality


def build_performance_intelligence(
    *,
    pattern_record: dict[str, object],
    pattern_history: list[dict[str, object]],
) -> dict[str, object]:
    """Build all historical-performance signals for a candidate without side effects."""
    pattern_memory = evaluate_pattern_memory(pattern_record, pattern_history[-500:])
    historical_edge = calculate_historical_edge_score(pattern_record, pattern_history[-1000:])
    adaptive_thresholds = calculate_adaptive_thresholds({**pattern_record, **historical_edge})
    edge_confirmation = calculate_edge_confirmation(
        {
            **pattern_record,
            "historical_edge": historical_edge,
            "adaptive_thresholds": adaptive_thresholds,
        }
    )
    trade_quality = classify_trade_quality(
        {
            **pattern_record,
            "historical_edge": historical_edge,
            "adaptive_thresholds": adaptive_thresholds,
            "edge_confirmation": edge_confirmation,
        }
    )
    meta_decision = evaluate_meta_decision(
        {
            **pattern_record,
            "historical_edge": historical_edge,
            "adaptive_thresholds": adaptive_thresholds,
            "edge_confirmation": edge_confirmation,
            "trade_quality": trade_quality,
        }
    )

    return {
        **pattern_memory,
        "historical_edge": historical_edge,
        "adaptive_thresholds": adaptive_thresholds,
        "edge_confirmation": edge_confirmation,
        "trade_quality": trade_quality,
        "meta_decision": meta_decision,
        "insights": build_pattern_memory_insights(pattern_history),
    }


def log_performance_intelligence(
    logger: logging.Logger,
    *,
    symbol: str,
    pattern_record: dict[str, object],
    performance_intelligence: dict[str, object],
) -> None:
    """Emit the shadow-analysis events from a single place."""
    common = {
        "symbol": symbol,
        "direction": pattern_record.get("direction"),
        "setup_type": pattern_record.get("setup_type"),
    }
    log_json(
        logger,
        "adaptive_threshold_shadow_analysis",
        **common,
        **_dict(performance_intelligence.get("adaptive_thresholds")),
    )
    log_json(
        logger,
        "edge_confirmation_shadow_analysis",
        **common,
        **_dict(performance_intelligence.get("edge_confirmation")),
    )
    log_json(
        logger,
        "trade_quality_shadow_analysis",
        **common,
        **_dict(performance_intelligence.get("trade_quality")),
    )
    log_json(
        logger,
        "meta_decision_shadow_analysis",
        **common,
        **_dict(performance_intelligence.get("meta_decision")),
    )


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}
