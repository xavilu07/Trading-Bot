from __future__ import annotations

import logging
from pathlib import Path

from trading_signals.infrastructure.logging.logger import log_json
from trading_signals.memory.adaptive_thresholds import calculate_adaptive_thresholds
from trading_signals.memory.edge_confirmation import calculate_edge_confirmation
from trading_signals.memory.edge_memory import evaluate_edge_for_context
from trading_signals.memory.edge_score import calculate_historical_edge_score
from trading_signals.memory.insights import build_pattern_memory_insights
from trading_signals.memory.meta_decision_engine import evaluate_meta_decision
from trading_signals.memory.pattern_memory import evaluate_pattern_memory
from trading_signals.memory.trade_quality import classify_trade_quality


def build_performance_intelligence(
    *,
    pattern_record: dict[str, object],
    pattern_history: list[dict[str, object]],
    edge_memory_data_path: Path | None = None,
) -> dict[str, object]:
    """Build all historical-performance signals for a candidate without side effects."""
    pattern_memory = evaluate_pattern_memory(pattern_record, pattern_history[-500:])
    historical_edge = calculate_historical_edge_score(pattern_record, pattern_history[-1000:])
    edge_memory_v1 = None
    if edge_memory_data_path is not None:
        edge_memory_v1 = evaluate_edge_for_context(edge_memory_data_path, pattern_record)
        if (
            int(historical_edge.get("matched_patterns_count", 0) or 0) == 0
            and int(edge_memory_v1.get("matched_patterns_count", 0) or 0) > 0
        ):
            best_edge = edge_memory_v1.get("best_edge") if isinstance(edge_memory_v1.get("best_edge"), dict) else {}
            worst_edge = edge_memory_v1.get("worst_edge") if isinstance(edge_memory_v1.get("worst_edge"), dict) else {}
            historical_edge = {
                **historical_edge,
                "historical_edge_score": edge_memory_v1["historical_edge_score"],
                "historical_confidence": edge_memory_v1["historical_confidence"],
                "matched_patterns_count": edge_memory_v1["matched_patterns_count"],
                "matched_winrate": float(best_edge.get("winrate", 0.0) or 0.0),
                "matched_avg_r": float(best_edge.get("avg_r", 0.0) or 0.0),
                "matched_profit_factor": best_edge.get("profit_factor", 0.0),
                "positive_edge_reasons": _edge_memory_reasons(best_edge, positive=True),
                "negative_edge_reasons": _edge_memory_reasons(worst_edge, positive=False),
                "source": "EDGE_MEMORY_V1",
            }
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
        "edge_memory_v1": edge_memory_v1,
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
        "edge_memory_v1_analysis",
        **common,
        **_dict(performance_intelligence.get("edge_memory_v1")),
    )
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


def _edge_memory_reasons(edge: dict[str, object], *, positive: bool) -> list[str]:
    if not edge:
        return []
    label = f"{edge.get('group')}:{edge.get('values')}"
    if positive:
        reasons = []
        if _float(edge.get("avg_r")) > 0:
            reasons.append(f"EDGE_MEMORY_V1 avgR positivo {edge.get('avg_r')} en {label}")
        if _pf_float(edge.get("profit_factor")) >= 1.5:
            reasons.append(f"EDGE_MEMORY_V1 PF favorable {edge.get('profit_factor')} en {label}")
        if _float(edge.get("winrate")) >= 52:
            reasons.append(f"EDGE_MEMORY_V1 winrate favorable {edge.get('winrate')}% en {label}")
        return reasons
    reasons = []
    if _float(edge.get("avg_r")) < 0:
        reasons.append(f"EDGE_MEMORY_V1 avgR negativo {edge.get('avg_r')} en {label}")
    if _pf_float(edge.get("profit_factor")) < 0.95:
        reasons.append(f"EDGE_MEMORY_V1 PF débil {edge.get('profit_factor')} en {label}")
    if _float(edge.get("winrate")) < 38:
        reasons.append(f"EDGE_MEMORY_V1 winrate bajo {edge.get('winrate')}% en {label}")
    return reasons


def _float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _pf_float(value: object) -> float:
    if value == "inf":
        return 999.0
    return _float(value)
