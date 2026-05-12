from __future__ import annotations

from trading_signals.app.cli import (
    build_scheduler_diagnostic_summary,
    format_scheduler_diagnostic_summary_for_telegram,
    load_scheduler_heartbeat,
    load_scheduler_results_window,
    save_scheduler_heartbeat,
    save_scheduler_results_window,
    scheduler_heartbeat_cycle_number,
)


def test_scheduler_diagnostic_summary_aggregates_five_cycles() -> None:
    result = {
        "scan_run": {
            "symbols_processed": 2,
            "signals_emitted": 0,
        },
        "results": [
            {
                "evaluation": {
                    "rejection_reasons": ["distance_to_liquidity_extreme"],
                },
                "paper_candidate_detected": True,
                "paper_trade_created": False,
                "paper_trade_rejection": {
                    "paper_trade_rejection_reason": "paper_rejected_below_low",
                },
                "setup_context": {
                    "market_regime": "RANGING",
                    "session": "NEW_YORK",
                    "entry_context": "CHOPPY_RANGE",
                    "trade_location": "discount_zone",
                    "avoidance_warnings": ["low_volume", "price_far_from_liquidity"],
                },
                "candidate_rejected": {
                    "symbol": "XRPUSDT",
                    "setup_type": "SECONDARY_SIGNAL",
                    "direction": "short",
                    "setup_score_final": 65.0,
                    "rejection_reason": "distance_to_liquidity_extreme",
                },
                "high_score_rejected": {
                    "symbol": "ETHUSDT",
                    "direction": "long",
                    "score": 100,
                    "setup_type": "MAIN_SIGNAL",
                    "blocking_reasons": ["directional_confluence_failed"],
                    "rr": 2.0,
                },
                "pattern_memory": {
                    "similar_count": 8,
                    "historical_winrate": 62.5,
                    "historical_avg_r": 0.7,
                    "repeated_warnings": ["low_volume"],
                    "repeated_penalties": ["distance_to_liquidity_penalty:10"],
                    "confidence_level": "MEDIUM",
                },
            },
            {
                "evaluation": {
                    "rejection_reasons": ["market_structure_range_penalty", "directional_confluence_failed"],
                },
                "paper_candidate_detected": True,
                "paper_trade_created": True,
                "setup_context": {
                    "market_regime": "TRENDING",
                    "session": "LONDON",
                    "entry_context": "BREAKOUT",
                    "trade_location": "near_support",
                    "avoidance_warnings": ["low_volume"],
                },
                "candidate_rejected": {
                    "symbol": "DOGEUSDT",
                    "setup_type": "MAIN_SIGNAL",
                    "direction": "long",
                    "setup_score_final": 55.0,
                    "rejection_reason": "directional_confluence_failed",
                },
            },
        ],
    }

    summary = build_scheduler_diagnostic_summary([result, result, result, result, result])

    assert summary["cycles"] == 5
    assert summary["total_symbols_analyzed"] == 10
    assert summary["signals_sent"] == 0
    assert summary["candidates_rejected"] == 10
    assert summary["candidates_by_type"] == {
        "MAIN_SIGNAL": 5,
        "SECONDARY_SIGNAL": 5,
    }
    assert summary["paper_candidates_detected"] == 10
    assert summary["paper_trades_opened"] == 5
    assert summary["top_paper_rejection_reasons"] == [
        {"reason": "paper_rejected_below_low", "count": 5},
    ]
    assert summary["market_regime_count"] == {"RANGING": 5, "TRENDING": 5}
    assert summary["session_count"] == {"NEW_YORK": 5, "LONDON": 5}
    assert summary["entry_context_count"] == {"CHOPPY_RANGE": 5, "BREAKOUT": 5}
    assert summary["trade_location_count"] == {"discount_zone": 5, "near_support": 5}
    assert summary["avoidance_warnings_count"] == {
        "low_volume": 10,
        "price_far_from_liquidity": 5,
    }
    assert summary["best_rejected_candidate"] == {
        "symbol": "XRPUSDT",
        "setup_score_final": 65.0,
        "direction": "short",
        "rejection_reason": "distance_to_liquidity_extreme",
        "setup_type": "SECONDARY_SIGNAL",
    }
    assert len(summary["high_score_rejected"]) == 5
    assert summary["high_score_rejected"][0]["symbol"] == "ETHUSDT"
    assert summary["pattern_memory"] == {
        "similar_count": 8,
        "historical_winrate": 62.5,
        "historical_avg_r": 0.7,
        "confidence_level": "MEDIUM",
        "repeated_warnings": ["low_volume"],
        "repeated_penalties": ["distance_to_liquidity_penalty:10"],
    }
    assert "0 señales enviadas" in str(summary["zero_signal_bottleneck"])


def test_scheduler_diagnostic_summary_telegram_format() -> None:
    summary = {
        "total_symbols_analyzed": 35,
        "signals_sent": 0,
        "candidates_rejected": 2,
        "top_rejection_reasons": [
            {"reason": "distance_to_liquidity_extreme", "count": 2},
            {"reason": "directional_confluence_failed", "count": 1},
        ],
        "candidates_by_type": {
            "MAIN_SIGNAL": 0,
            "SECONDARY_SIGNAL": 2,
        },
        "best_rejected_candidate": {
            "symbol": "XRPUSDT",
            "setup_type": "SECONDARY_SIGNAL",
            "direction": "short",
            "setup_score_final": 65.0,
            "rejection_reason": "distance_to_liquidity_extreme",
        },
        "zero_signal_bottleneck": "0 señales enviadas. Principal cuello de botella: distance_to_liquidity_extreme",
        "paper_candidates_detected": 2,
        "paper_trades_opened": 1,
        "top_paper_rejection_reasons": [
            {"reason": "paper_rejected_below_low", "count": 1},
        ],
        "top_market_regimes": [{"label": "RANGING", "count": 2}],
        "top_sessions": [{"label": "NEW_YORK", "count": 2}],
        "top_entry_contexts": [{"label": "CHOPPY_RANGE", "count": 2}],
        "top_trade_locations": [{"label": "discount_zone", "count": 2}],
        "top_avoidance_warnings": [{"label": "low_volume", "count": 2}],
        "high_score_rejected": [
            {
                "symbol": "ETHUSDT",
                "direction": "long",
                "score": 100,
                "setup_type": "MAIN_SIGNAL",
                "blocking_reasons": ["directional_confluence_failed", "publish_filter_harmful_filter"],
                "rr": 2.0,
            },
            {
                "symbol": "BTCUSDT",
                "direction": "short",
                "score": 91,
                "setup_type": "SECONDARY_SIGNAL",
                "blocking_reasons": ["against_htf"],
                "rr": None,
            },
            {
                "symbol": "SOLUSDT",
                "direction": "long",
                "score": 90,
                "setup_type": "MAIN_SIGNAL",
                "blocking_reasons": ["duplicate_signal_suppressed"],
                "rr": 1.8,
            },
            {
                "symbol": "AVAXUSDT",
                "direction": "long",
                "score": 89,
                "setup_type": "MAIN_SIGNAL",
                "blocking_reasons": ["publish_filter_session"],
                "rr": 2.1,
            },
            {
                "symbol": "ADAUSDT",
                "direction": "short",
                "score": 88,
                "setup_type": "SECONDARY_SIGNAL",
                "blocking_reasons": ["directional_confluence_failed"],
                "rr": 2.4,
            },
            {
                "symbol": "OPUSDT",
                "direction": "long",
                "score": 87,
                "setup_type": "MAIN_SIGNAL",
                "blocking_reasons": ["publish_decision_filtered"],
                "rr": 2.0,
            },
        ],
        "pattern_memory": {
            "similar_count": 8,
            "historical_winrate": 62.5,
            "historical_avg_r": 0.7,
            "repeated_warnings": ["low_volume"],
            "repeated_penalties": ["distance_to_liquidity_penalty:10"],
            "confidence_level": "MEDIUM",
        },
        "pattern_memory_insights": {
            "has_sufficient_data": True,
            "positive_patterns": [
                {
                    "label": "LONG | BREAKOUT | TRENDING",
                    "historical_winrate": 68.0,
                    "historical_avg_r": 1.2,
                    "cases": 12,
                }
            ],
            "negative_patterns": [
                {
                    "label": "SHORT | against_htf | near_resistance",
                    "historical_winrate": 22.0,
                    "historical_avg_r": -0.6,
                    "cases": 9,
                }
            ],
        },
        "historical_edge": {
            "historical_edge_score": 74,
            "historical_confidence": "MEDIUM",
            "matched_patterns_count": 12,
            "matched_winrate": 66.67,
            "matched_avg_r": 0.8,
            "matched_profit_factor": 2.1,
            "positive_edge_reasons": ["avgR positivo (0.8)", "profit factor fuerte (2.1)"],
            "negative_edge_reasons": ["warnings repetidos: low_volume"],
        },
        "adaptive_thresholds": {
            "base_threshold": 45,
            "adaptive_threshold": 38,
            "threshold_delta": -7,
            "adaptive_confidence": "MEDIUM",
            "adaptive_bias": "BULLISH",
            "adaptive_reasoning": ["PF > 1.5 reduce threshold (-6)", "BREAKOUT reduce threshold (-4)"],
        },
        "edge_confirmation": {
            "edge_confirmation_score": 78.5,
            "edge_confirmation_level": "HIGH",
            "edge_bias": "POSITIVE",
            "confidence_boost": 26.5,
            "confidence_penalty": 3.0,
            "confirmation_reasons": ["historical edge HIGH", "PF > 1.2 (2.1)", "BREAKOUT rentable"],
            "risk_reasons": ["pocos matches históricos (8)"],
            "historical_alignment": {"matched_patterns_count": 8},
        },
        "trade_quality": {
            "trade_quality_score": 86.0,
            "trade_quality_grade": "A",
            "quality_confidence": "HIGH",
            "quality_bias": "POSITIVE",
            "quality_reasons": ["HIGH_VOLATILITY", "BREAKOUT", "RR válido (2.0)"],
            "quality_risks": ["low matches históricos (8)"],
            "historical_quality_alignment": {"matched_patterns_count": 8},
        },
        "meta_decision": {
            "meta_decision_score": 91.0,
            "meta_decision": "STRONG_SEND",
            "meta_confidence": "HIGH",
            "capital_preservation_mode": False,
            "aggressive_mode": True,
            "meta_reasons": ["historical edge HIGH", "trade quality A", "RR válido (2.0)"],
            "meta_risks": ["low confidence contexts"],
            "system_alignment": {"historical_edge_score": 82},
        },
    }

    message = format_scheduler_diagnostic_summary_for_telegram(summary)

    assert "📊 Resumen del bot - últimos 5 ciclos" in message
    assert "⚡ Actividad" in message
    assert "- Símbolos analizados: 35" in message
    assert "- Señales enviadas: 0" in message
    assert "- Candidatos rechazados: 2" in message
    assert "🧠 Lectura rápida" in message
    assert "🌍 Contexto dominante" in message
    assert "⚠️ Riesgos" in message
    assert "🚧 Bloqueos" in message
    assert "🚧 High Score Rejected" in message
    assert "🧪 Paper trading" in message
    assert "🎯 Mejor candidato" in message
    assert "🧠 Pattern Memory" in message
    assert "📊 Conclusión" in message
    assert "Paper candidates detected: 2" in message
    assert "Paper trades opened: 1" in message
    assert "score por debajo del nivel LOW: 1 veces" in message
    assert "Régimen: RANGING (2)" in message
    assert "Sesión: NEW_YORK (2)" in message
    assert "Entrada: CHOPPY_RANGE (2)" in message
    assert "Ubicación: discount_zone (2)" in message
    assert "Warnings principales: low_volume (2)" in message
    assert "1. precio demasiado lejos de liquidez: 2 veces" in message
    assert "- ETHUSDT LONG | Score 100 | Bloqueo: directional_confluence_failed, publish_filter_harmful_filter | MAIN_SIGNAL | RR 2.0" in message
    assert "- BTCUSDT SHORT | Score 91 | Bloqueo: against_htf | SECONDARY_SIGNAL" in message
    assert "+ 1 más en logs" in message
    assert "- Setups similares: 8" in message
    assert "- Winrate histórico: 62.5%" in message
    assert "- Avg R: 0.7" in message
    assert "- Confianza: MEDIUM" in message
    assert "- Warnings repetidos: low_volume" in message
    assert "- Penalties repetidas: distance_to_liquidity_penalty:10" in message
    assert "🧠 Pattern Memory Insights" in message
    assert "✅ Patrones positivos" in message
    assert "- LONG | BREAKOUT | TRENDING | Winrate 68% | AvgR +1.2 | Casos: 12" in message
    assert "⚠️ Patrones negativos" in message
    assert "- SHORT | against_htf | near_resistance | Winrate 22% | AvgR -0.6 | Casos: 9" in message
    assert "🧠 Historical Edge" in message
    assert "- Score: 74/100" in message
    assert "- Confidence: MEDIUM" in message
    assert "- Matches: 12" in message
    assert "- WR histórico: 66.67%" in message
    assert "- AvgR: 0.8" in message
    assert "- PF: 2.1" in message
    assert "- Riesgos: warnings repetidos: low_volume" in message
    assert "- Fortalezas: avgR positivo (0.8), profit factor fuerte (2.1)" in message
    assert "🧠 Adaptive Thresholds" in message
    assert "- Base Threshold: 45" in message
    assert "- Adaptive Threshold: 38" in message
    assert "- Delta: -7" in message
    assert "- Confidence: MEDIUM" in message
    assert "- Bias: BULLISH" in message
    assert "  - PF > 1.5 reduce threshold (-6)" in message
    assert "🧠 Edge Confirmation" in message
    assert "- Score: 78.5/100" in message
    assert "- Level: HIGH" in message
    assert "- Bias: POSITIVE" in message
    assert "- Boost/Penalty: +26.5 / -3.0" in message
    assert "  - + historical edge HIGH" in message
    assert "  - - pocos matches históricos (8)" in message
    assert "🏆 Trade Quality" in message
    assert "- Score: 86.0/100" in message
    assert "- Grade: A" in message
    assert "- Confidence: HIGH" in message
    assert "- Bias: POSITIVE" in message
    assert "- Main reasons: HIGH_VOLATILITY, BREAKOUT, RR válido (2.0)" in message
    assert "- Risks: low matches históricos (8)" in message
    assert "🧠 Meta Decision Engine" in message
    assert "- Score: 91.0/100" in message
    assert "- Decision: STRONG_SEND" in message
    assert "- Confidence: HIGH" in message
    assert "- Aggressive mode: YES" in message
    assert "- Preservation mode: NO" in message
    assert "- Main reasons: historical edge HIGH, trade quality A, RR válido (2.0)" in message
    assert "- Risks: low confidence contexts" in message
    assert "- Símbolo: XRPUSDT" in message
    assert "0 señales enviadas" in message


def test_scheduler_diagnostic_summary_telegram_format_without_candidates() -> None:
    summary = {
        "total_symbols_analyzed": 35,
        "signals_sent": 0,
        "candidates_rejected": 0,
        "top_rejection_reasons": [],
        "candidates_by_type": {
            "MAIN_SIGNAL": 0,
            "SECONDARY_SIGNAL": 0,
        },
        "best_rejected_candidate": None,
        "zero_signal_bottleneck": "0 señales enviadas. Principal cuello de botella: sin_datos",
        "paper_candidates_detected": 0,
        "paper_trades_opened": 0,
        "top_paper_rejection_reasons": [],
    }

    message = format_scheduler_diagnostic_summary_for_telegram(summary)

    assert "No hubo candidatos rechazados" in message
    assert "- Sin candidatos rechazados" in message
    assert "Sin bloqueos registrados" in message
    assert "High Score Rejected" not in message
    assert "🧠 Pattern Memory Insights" in message
    assert "Memoria aún insuficiente para insights fiables." in message


def test_scheduler_results_window_persists_between_restarts(tmp_path) -> None:
    state_file = tmp_path / "scheduler_diagnostic_window.json"
    window = [{"scan_run": {"symbols_processed": 7, "signals_emitted": 0}, "results": []}]

    save_scheduler_results_window(state_file, window)

    assert load_scheduler_results_window(state_file) == window


def test_scheduler_heartbeat_persists_between_restarts(tmp_path) -> None:
    heartbeat_file = tmp_path / "runtime" / "scheduler_heartbeat.json"
    heartbeat = {
        "last_cycle_started_at": "2026-05-12T10:00:00+00:00",
        "last_cycle_finished_at": "2026-05-12T10:00:03+00:00",
        "last_cycle_duration_seconds": 3.0,
        "cycle_number": 7,
        "status": "ok",
        "last_error": None,
    }

    save_scheduler_heartbeat(heartbeat_file, heartbeat)

    assert load_scheduler_heartbeat(heartbeat_file) == heartbeat


def test_scheduler_heartbeat_returns_empty_dict_for_corrupt_file(tmp_path) -> None:
    heartbeat_file = tmp_path / "scheduler_heartbeat.json"
    heartbeat_file.write_text("{invalid", encoding="utf-8")

    assert load_scheduler_heartbeat(heartbeat_file) == {}


def test_scheduler_heartbeat_cycle_number_handles_invalid_values() -> None:
    assert scheduler_heartbeat_cycle_number({"cycle_number": "12"}) == 12
    assert scheduler_heartbeat_cycle_number({"cycle_number": "invalid"}) == 0
