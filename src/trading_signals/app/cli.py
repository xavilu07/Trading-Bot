from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from trading_signals.app.container import build_container
from trading_signals.application.use_cases.live_trading import (
    format_live_daily_summary_for_telegram,
    now_utc_date_key as live_now_utc_date_key,
)
from trading_signals.application.use_cases.paper_trading import format_paper_daily_summary_for_telegram, now_utc_date_key
from trading_signals.application.use_cases.run_market_scan import run_market_scan
from trading_signals.infrastructure.logging.logger import log_json


def load_scheduler_results_window(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def save_scheduler_results_window(path: Path, results_window: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(results_window, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def build_scheduler_diagnostic_summary(results_window: list[dict[str, object]]) -> dict[str, object]:
    total_symbols = 0
    signals_sent = 0
    candidates: list[dict[str, object]] = []
    rejection_reasons: Counter[str] = Counter()
    candidate_types: Counter[str] = Counter({"MAIN_SIGNAL": 0, "SECONDARY_SIGNAL": 0})
    paper_candidates_detected = 0
    paper_trades_opened = 0
    paper_rejection_reasons: Counter[str] = Counter()
    market_regimes: Counter[str] = Counter()
    sessions: Counter[str] = Counter()
    entry_contexts: Counter[str] = Counter()
    trade_locations: Counter[str] = Counter()
    avoidance_warnings: Counter[str] = Counter()
    high_score_rejected: list[dict[str, object]] = []
    pattern_memory_items: list[dict[str, object]] = []
    pattern_memory_insights = None
    historical_edge_items: list[dict[str, object]] = []
    adaptive_threshold_items: list[dict[str, object]] = []
    edge_confirmation_items: list[dict[str, object]] = []

    for result in results_window:
        scan_run = result.get("scan_run", {})
        if isinstance(scan_run, dict):
            total_symbols += int(scan_run.get("symbols_processed", 0))
            signals_sent += int(scan_run.get("signals_emitted", 0))
        for item in result.get("results", []):
            if not isinstance(item, dict):
                continue
            evaluation = item.get("evaluation", {})
            if isinstance(evaluation, dict):
                reason = "|".join(evaluation.get("rejection_reasons", []) or [])
                if reason:
                    rejection_reasons[reason] += 1
            candidate = item.get("candidate_rejected")
            if isinstance(candidate, dict):
                candidates.append(candidate)
                candidate_type = str(candidate.get("setup_type", "UNKNOWN"))
                candidate_types[candidate_type] += 1
            high_score_item = item.get("high_score_rejected")
            if isinstance(high_score_item, dict):
                high_score_rejected.append(high_score_item)
            pattern_memory = item.get("pattern_memory")
            if isinstance(pattern_memory, dict) and int(pattern_memory.get("similar_count", 0)) >= 3:
                pattern_memory_items.append(pattern_memory)
            if isinstance(pattern_memory, dict) and isinstance(pattern_memory.get("insights"), dict):
                pattern_memory_insights = pattern_memory.get("insights")
            if isinstance(pattern_memory, dict) and isinstance(pattern_memory.get("historical_edge"), dict):
                historical_edge_items.append(pattern_memory["historical_edge"])
            if isinstance(pattern_memory, dict) and isinstance(pattern_memory.get("adaptive_thresholds"), dict):
                adaptive_threshold_items.append(pattern_memory["adaptive_thresholds"])
            if isinstance(pattern_memory, dict) and isinstance(pattern_memory.get("edge_confirmation"), dict):
                edge_confirmation_items.append(pattern_memory["edge_confirmation"])
            if item.get("paper_candidate_detected") is True:
                paper_candidates_detected += 1
            if item.get("paper_trade_created") is True:
                paper_trades_opened += 1
            paper_rejection = item.get("paper_trade_rejection")
            if isinstance(paper_rejection, dict):
                reason = str(paper_rejection.get("paper_trade_rejection_reason", "unknown"))
                paper_rejection_reasons[reason] += 1
            setup_context = item.get("setup_context")
            if isinstance(setup_context, dict):
                market_regimes[str(setup_context.get("market_regime", "UNKNOWN"))] += 1
                sessions[str(setup_context.get("session", "UNKNOWN"))] += 1
                entry_contexts[str(setup_context.get("entry_context", "UNKNOWN"))] += 1
                trade_locations[str(setup_context.get("trade_location", "UNKNOWN"))] += 1
                warnings = setup_context.get("avoidance_warnings", [])
                if isinstance(warnings, list):
                    for warning in warnings:
                        avoidance_warnings[str(warning)] += 1

    best_candidate = None
    if candidates:
        best_candidate = max(candidates, key=lambda item: float(item.get("setup_score_final", 0.0)))

    top_rejection_reasons = [
        {"reason": reason, "count": count}
        for reason, count in rejection_reasons.most_common(5)
    ]
    main_bottleneck = top_rejection_reasons[0]["reason"] if signals_sent == 0 and top_rejection_reasons else "sin_datos"

    return {
        "cycles": len(results_window),
        "total_symbols_analyzed": total_symbols,
        "signals_sent": signals_sent,
        "candidates_rejected": len(candidates),
        "top_rejection_reasons": top_rejection_reasons,
        "candidates_by_type": {
            "MAIN_SIGNAL": candidate_types["MAIN_SIGNAL"],
            "SECONDARY_SIGNAL": candidate_types["SECONDARY_SIGNAL"],
        },
        "paper_candidates_detected": paper_candidates_detected,
        "paper_trades_opened": paper_trades_opened,
        "top_paper_rejection_reasons": [
            {"reason": reason, "count": count}
            for reason, count in paper_rejection_reasons.most_common(5)
        ],
        "top_market_regimes": [
            {"label": label, "count": count}
            for label, count in market_regimes.most_common(3)
        ],
        "market_regime_count": dict(market_regimes),
        "session_count": dict(sessions),
        "entry_context_count": dict(entry_contexts),
        "trade_location_count": dict(trade_locations),
        "avoidance_warnings_count": dict(avoidance_warnings),
        "top_sessions": [
            {"label": label, "count": count}
            for label, count in sessions.most_common(3)
        ],
        "top_entry_contexts": [
            {"label": label, "count": count}
            for label, count in entry_contexts.most_common(3)
        ],
        "top_trade_locations": [
            {"label": label, "count": count}
            for label, count in trade_locations.most_common(3)
        ],
        "top_avoidance_warnings": [
            {"label": label, "count": count}
            for label, count in avoidance_warnings.most_common(3)
        ],
        "best_rejected_candidate": None
        if best_candidate is None
        else {
            "symbol": best_candidate.get("symbol"),
            "setup_score_final": best_candidate.get("setup_score_final"),
            "direction": best_candidate.get("direction"),
            "rejection_reason": best_candidate.get("rejection_reason"),
            "setup_type": best_candidate.get("setup_type"),
        },
        "zero_signal_bottleneck": None
        if signals_sent > 0
        else f"0 señales enviadas. Principal cuello de botella: {main_bottleneck}",
        "high_score_rejected": sorted(
            high_score_rejected,
            key=lambda item: float(item.get("score", 0.0)),
            reverse=True,
        ),
        "pattern_memory": _aggregate_pattern_memory(pattern_memory_items),
        "pattern_memory_insights": pattern_memory_insights,
        "historical_edge": _aggregate_historical_edge(historical_edge_items),
        "adaptive_thresholds": _aggregate_adaptive_thresholds(adaptive_threshold_items),
        "edge_confirmation": _aggregate_edge_confirmation(edge_confirmation_items),
    }


def format_scheduler_diagnostic_summary_for_telegram(summary: dict[str, object]) -> str:
    top_reasons = summary.get("top_rejection_reasons", [])
    if isinstance(top_reasons, list) and top_reasons:
        reasons_lines = []
        for idx, item in enumerate(top_reasons[:3], start=1):
            if not isinstance(item, dict):
                continue
            reasons_lines.append(f"{idx}. {_humanize_reason(str(item.get('reason', 'unknown')))}: {item.get('count', 0)} veces")
        reasons_text = "\n".join(reasons_lines) if reasons_lines else "Sin bloqueos registrados"
    else:
        reasons_text = "Sin bloqueos registrados"

    candidates_by_type = summary.get("candidates_by_type", {})
    if not isinstance(candidates_by_type, dict):
        candidates_by_type = {}
    candidates_text = (
        f"MAIN_SIGNAL: {candidates_by_type.get('MAIN_SIGNAL', 0)} | "
        f"SECONDARY_SIGNAL: {candidates_by_type.get('SECONDARY_SIGNAL', 0)}"
    )
    paper_reasons = summary.get("top_paper_rejection_reasons", [])
    if isinstance(paper_reasons, list) and paper_reasons:
        paper_reasons_text = "\n".join(
            f"{idx}. {_humanize_reason(str(item.get('reason', 'unknown')))}: {item.get('count', 0)} veces"
            for idx, item in enumerate(paper_reasons[:3], start=1)
            if isinstance(item, dict)
        )
    else:
        paper_reasons_text = "Sin rechazos paper-only registrados"
    context_text = _format_label_counts(summary.get("top_market_regimes", []), "Sin contextos registrados")
    session_text = _format_label_counts(summary.get("top_sessions", []), "Sin sesiones registradas")
    entry_context_text = _format_label_counts(summary.get("top_entry_contexts", []), "Sin entry context registrado")
    trade_location_text = _format_label_counts(summary.get("top_trade_locations", []), "Sin ubicaciones registradas")
    warnings_text = _format_label_counts(summary.get("top_avoidance_warnings", []), "Sin warnings registrados")
    best_candidate = summary.get("best_rejected_candidate")
    if isinstance(best_candidate, dict):
        best_text = (
            f"- Símbolo: {best_candidate.get('symbol', '-')}\n"
            f"- Tipo: {best_candidate.get('setup_type', '-')}\n"
            f"- Dirección: {best_candidate.get('direction', '-')}\n"
            f"- Score: {best_candidate.get('setup_score_final', '-')}\n"
            f"- Motivo: {_humanize_reason(str(best_candidate.get('rejection_reason', '-')))}"
        )
    else:
        best_text = "- Sin candidatos rechazados"

    bottleneck = summary.get("zero_signal_bottleneck") or "Hubo señales enviadas en esta ventana."
    if int(summary.get("candidates_rejected", 0)) == 0:
        candidates_note = "No hubo candidatos rechazados en esta ventana."
    else:
        candidates_note = candidates_text
    quick_read = _build_scheduler_quick_read(summary)
    bottleneck_text = _humanize_bottleneck(str(bottleneck))
    high_score_text = _format_high_score_rejected(summary.get("high_score_rejected", []))
    pattern_memory_text = _format_pattern_memory(summary.get("pattern_memory"))
    pattern_memory_insights_text = _format_pattern_memory_insights(summary.get("pattern_memory_insights"))
    historical_edge_text = _format_historical_edge(summary.get("historical_edge"))
    adaptive_thresholds_text = _format_adaptive_thresholds(summary.get("adaptive_thresholds"))
    edge_confirmation_text = _format_edge_confirmation(summary.get("edge_confirmation"))

    return (
        "📊 Resumen del bot - últimos 5 ciclos\n\n"
        "⚡ Actividad\n"
        f"- Símbolos analizados: {summary.get('total_symbols_analyzed', 0)}\n"
        f"- Señales enviadas: {summary.get('signals_sent', 0)}\n"
        f"- Candidatos rechazados: {summary.get('candidates_rejected', 0)}\n\n"
        "🧠 Lectura rápida\n"
        f"{quick_read}\n\n"
        "🌍 Contexto dominante\n"
        f"- Régimen: {context_text}\n"
        f"- Sesión: {session_text}\n"
        f"- Entrada: {entry_context_text}\n"
        f"- Ubicación: {trade_location_text}\n\n"
        "⚠️ Riesgos\n"
        f"- Warnings principales: {warnings_text}\n"
        f"- Cuello de botella: {bottleneck_text}\n\n"
        "🚧 Bloqueos\n"
        f"{reasons_text}\n"
        f"- Tipos de candidato: {candidates_note}\n\n"
        f"{high_score_text}"
        "🧪 Paper trading\n"
        f"- Paper candidates detected: {summary.get('paper_candidates_detected', 0)}\n"
        f"- Paper trades opened: {summary.get('paper_trades_opened', 0)}\n"
        "- Rechazos paper-only:\n"
        f"{paper_reasons_text}\n\n"
        "🎯 Mejor candidato\n"
        f"{best_text}\n\n"
        f"{pattern_memory_text}"
        f"{pattern_memory_insights_text}"
        f"{historical_edge_text}"
        f"{adaptive_thresholds_text}"
        f"{edge_confirmation_text}"
        "📊 Conclusión\n"
        f"{_build_scheduler_conclusion(summary, bottleneck_text)}"
    )


def _aggregate_edge_confirmation(items: list[dict[str, object]]) -> dict[str, object] | None:
    if not items:
        return None
    def key(item: dict[str, object]) -> tuple[int, float]:
        alignment = item.get("historical_alignment", {})
        matches = int(alignment.get("matched_patterns_count", 0)) if isinstance(alignment, dict) else 0
        score = float(item.get("edge_confirmation_score", 50.0))
        return matches, abs(score - 50.0)

    selected = max(items, key=key)
    return {
        "edge_confirmation_score": selected.get("edge_confirmation_score", 50.0),
        "edge_confirmation_level": selected.get("edge_confirmation_level", "MEDIUM"),
        "edge_bias": selected.get("edge_bias", "NEUTRAL"),
        "confidence_boost": selected.get("confidence_boost", 0.0),
        "confidence_penalty": selected.get("confidence_penalty", 0.0),
        "confirmation_reasons": selected.get("confirmation_reasons", []),
        "risk_reasons": selected.get("risk_reasons", []),
        "historical_alignment": selected.get("historical_alignment", {}),
    }


def _aggregate_adaptive_thresholds(items: list[dict[str, object]]) -> dict[str, object] | None:
    if not items:
        return None
    strongest = max(items, key=lambda item: abs(int(float(item.get("threshold_delta", 0)))))
    return {
        "base_threshold": strongest.get("base_threshold", 45),
        "adaptive_threshold": strongest.get("adaptive_threshold", 45),
        "threshold_delta": strongest.get("threshold_delta", 0),
        "adaptive_confidence": strongest.get("adaptive_confidence", "LOW"),
        "adaptive_bias": strongest.get("adaptive_bias", "NEUTRAL"),
        "adaptive_reasoning": strongest.get("adaptive_reasoning", []),
        "edge_adjustment": strongest.get("edge_adjustment", 0.0),
    }


def _aggregate_historical_edge(items: list[dict[str, object]]) -> dict[str, object] | None:
    valid = [item for item in items if int(item.get("matched_patterns_count", 0)) > 0]
    if not valid:
        return None
    best = max(valid, key=lambda item: (int(item.get("matched_patterns_count", 0)), int(item.get("historical_edge_score", 0))))
    return {
        "historical_edge_score": best.get("historical_edge_score", 50),
        "historical_confidence": best.get("historical_confidence", "LOW"),
        "matched_patterns_count": best.get("matched_patterns_count", 0),
        "matched_winrate": best.get("matched_winrate", 0.0),
        "matched_avg_r": best.get("matched_avg_r", 0.0),
        "matched_profit_factor": best.get("matched_profit_factor", 0.0),
        "positive_edge_reasons": best.get("positive_edge_reasons", []),
        "negative_edge_reasons": best.get("negative_edge_reasons", []),
    }


def _aggregate_pattern_memory(items: list[dict[str, object]]) -> dict[str, object] | None:
    if not items:
        return None
    best = max(items, key=lambda item: int(item.get("similar_count", 0)))
    return {
        "similar_count": best.get("similar_count", 0),
        "historical_winrate": best.get("historical_winrate"),
        "historical_avg_r": best.get("historical_avg_r"),
        "confidence_level": best.get("confidence_level", "LOW"),
        "repeated_warnings": best.get("repeated_warnings", []),
        "repeated_penalties": best.get("repeated_penalties", []),
    }


def _format_pattern_memory(item: object) -> str:
    if not isinstance(item, dict):
        return ""
    similar_count = int(item.get("similar_count", 0))
    if similar_count < 3:
        return "🧠 Pattern Memory\n- Memoria insuficiente\n\n"
    winrate = item.get("historical_winrate")
    avg_r = item.get("historical_avg_r")
    warnings = item.get("repeated_warnings", [])
    penalties = item.get("repeated_penalties", [])
    warnings_text = ", ".join(str(value) for value in warnings[:5]) if isinstance(warnings, list) and warnings else "ninguno"
    penalties_text = ", ".join(str(value) for value in penalties[:5]) if isinstance(penalties, list) and penalties else "ninguna"
    winrate_text = f"{winrate}%" if winrate is not None else "sin cierres"
    avg_r_text = str(avg_r) if avg_r is not None else "sin datos"
    return (
        "🧠 Pattern Memory\n"
        f"- Setups similares: {similar_count}\n"
        f"- Winrate histórico: {winrate_text}\n"
        f"- Avg R: {avg_r_text}\n"
        f"- Confianza: {item.get('confidence_level', 'LOW')}\n"
        f"- Warnings repetidos: {warnings_text}\n"
        f"- Penalties repetidas: {penalties_text}\n\n"
    )


def _format_edge_confirmation(item: object) -> str:
    if not isinstance(item, dict):
        return ""
    positives = item.get("confirmation_reasons", [])
    negatives = item.get("risk_reasons", [])
    main_reasons = []
    if isinstance(positives, list):
        main_reasons.extend(f"+ {reason}" for reason in positives[:3])
    if isinstance(negatives, list):
        main_reasons.extend(f"- {reason}" for reason in negatives[:3])
    reason_text = "\n".join(f"  - {reason}" for reason in main_reasons[:5]) if main_reasons else "  - sin razones concluyentes"
    return (
        "🧠 Edge Confirmation\n"
        f"- Score: {item.get('edge_confirmation_score', 50.0)}/100\n"
        f"- Level: {item.get('edge_confirmation_level', 'MEDIUM')}\n"
        f"- Bias: {item.get('edge_bias', 'NEUTRAL')}\n"
        f"- Boost/Penalty: +{item.get('confidence_boost', 0.0)} / -{item.get('confidence_penalty', 0.0)}\n"
        "- Main reasons:\n"
        f"{reason_text}\n\n"
    )


def _format_adaptive_thresholds(item: object) -> str:
    if not isinstance(item, dict):
        return ""
    delta = int(float(item.get("threshold_delta", 0)))
    delta_text = f"+{delta}" if delta > 0 else str(delta)
    reasons = item.get("adaptive_reasoning", [])
    if isinstance(reasons, list) and reasons:
        reason_lines = "\n".join(f"  - {reason}" for reason in reasons[:5])
    else:
        reason_lines = "  - sin ajustes adaptativos relevantes"
    return (
        "🧠 Adaptive Thresholds\n"
        f"- Base Threshold: {item.get('base_threshold', 45)}\n"
        f"- Adaptive Threshold: {item.get('adaptive_threshold', 45)}\n"
        f"- Delta: {delta_text}\n"
        f"- Confidence: {item.get('adaptive_confidence', 'LOW')}\n"
        f"- Bias: {item.get('adaptive_bias', 'NEUTRAL')}\n"
        "- Razones:\n"
        f"{reason_lines}\n\n"
    )


def _format_historical_edge(item: object) -> str:
    if not isinstance(item, dict):
        return ""
    positives = item.get("positive_edge_reasons", [])
    negatives = item.get("negative_edge_reasons", [])
    positive_text = ", ".join(str(value) for value in positives[:3]) if isinstance(positives, list) and positives else "sin fortalezas concluyentes"
    negative_text = ", ".join(str(value) for value in negatives[:3]) if isinstance(negatives, list) and negatives else "sin riesgos destacados"
    return (
        "🧠 Historical Edge\n"
        f"- Score: {item.get('historical_edge_score', 50)}/100\n"
        f"- Confidence: {item.get('historical_confidence', 'LOW')}\n"
        f"- Matches: {item.get('matched_patterns_count', 0)}\n"
        f"- WR histórico: {item.get('matched_winrate', 0.0)}%\n"
        f"- AvgR: {item.get('matched_avg_r', 0.0)}\n"
        f"- PF: {item.get('matched_profit_factor', 0.0)}\n"
        f"- Riesgos: {negative_text}\n"
        f"- Fortalezas: {positive_text}\n\n"
    )


def _format_pattern_memory_insights(item: object) -> str:
    if not isinstance(item, dict) or not item.get("has_sufficient_data"):
        return "🧠 Pattern Memory Insights\nMemoria aún insuficiente para insights fiables.\n\n"
    positives = item.get("positive_patterns", [])
    negatives = item.get("negative_patterns", [])
    lines = ["🧠 Pattern Memory Insights"]
    lines.append("✅ Patrones positivos")
    if isinstance(positives, list) and positives:
        lines.extend(_format_insight_line(pattern) for pattern in positives[:3] if isinstance(pattern, dict))
    else:
        lines.append("- Sin patrones positivos fiables")
    lines.append("")
    lines.append("⚠️ Patrones negativos")
    if isinstance(negatives, list) and negatives:
        lines.extend(_format_insight_line(pattern) for pattern in negatives[:3] if isinstance(pattern, dict))
    else:
        lines.append("- Sin patrones negativos fiables")
    return "\n".join(lines) + "\n\n"


def _format_insight_line(pattern: dict[str, object]) -> str:
    avg_r = float(pattern.get("historical_avg_r", 0.0))
    avg_r_text = f"{avg_r:+g}"
    winrate = float(pattern.get("historical_winrate", 0.0))
    return (
        f"- {pattern.get('label', pattern.get('value', '-'))} | "
        f"Winrate {winrate:g}% | AvgR {avg_r_text} | Casos: {pattern.get('cases', 0)}"
    )


def _format_high_score_rejected(items: object) -> str:
    if not isinstance(items, list) or not items:
        return ""
    lines = ["🚧 High Score Rejected"]
    valid_items = [item for item in items if isinstance(item, dict)]
    for item in valid_items[:5]:
        reasons = item.get("blocking_reasons", [])
        if isinstance(reasons, list):
            reason_text = ", ".join(str(reason) for reason in reasons[:2]) or "unknown"
        else:
            reason_text = str(reasons or "unknown")
        setup_type = item.get("setup_type")
        rr = item.get("rr")
        extras = []
        if setup_type:
            extras.append(str(setup_type))
        if rr is not None:
            extras.append(f"RR {rr}")
        extra_text = f" | {' | '.join(extras)}" if extras else ""
        lines.append(
            f"- {item.get('symbol', '-')} {str(item.get('direction', '-')).upper()} | "
            f"Score {item.get('score', '-')} | Bloqueo: {reason_text}{extra_text}"
        )
    remaining = len(valid_items) - 5
    if remaining > 0:
        lines.append(f"+ {remaining} más en logs")
    return "\n".join(lines) + "\n\n"


def _format_label_counts(items: object, empty: str) -> str:
    if not isinstance(items, list) or not items:
        return empty
    parts = []
    for item in items[:3]:
        if isinstance(item, dict):
            parts.append(f"{item.get('label', 'UNKNOWN')} ({item.get('count', 0)})")
    return ", ".join(parts) if parts else empty


def _build_scheduler_quick_read(summary: dict[str, object]) -> str:
    signals_sent = int(summary.get("signals_sent", 0))
    candidates_rejected = int(summary.get("candidates_rejected", 0))
    paper_candidates = int(summary.get("paper_candidates_detected", 0))
    top_reasons = summary.get("top_rejection_reasons", [])
    top_reason = "sin bloqueo dominante"
    if isinstance(top_reasons, list) and top_reasons and isinstance(top_reasons[0], dict):
        top_reason = _humanize_reason(str(top_reasons[0].get("reason", "unknown")))
    regime = _top_label(summary.get("top_market_regimes", []))
    entry_context = _top_label(summary.get("top_entry_contexts", []))

    if signals_sent > 0:
        signal_text = f"El bot encontró {signals_sent} oportunidad(es) publicables."
    elif candidates_rejected > 0:
        signal_text = f"Hay setups cerca de validar, pero el bloqueo principal es: {top_reason}."
    else:
        signal_text = "No aparecieron candidatos suficientemente fuertes en esta ventana."

    return (
        f"{signal_text}\n"
        f"Mercado dominante: {regime}; contexto de entrada: {entry_context}.\n"
        f"Paper trading detectó {paper_candidates} candidato(s) para validación estadística."
    )


def _build_scheduler_conclusion(summary: dict[str, object], bottleneck_text: str) -> str:
    signals_sent = int(summary.get("signals_sent", 0))
    candidates_rejected = int(summary.get("candidates_rejected", 0))
    paper_trades_opened = int(summary.get("paper_trades_opened", 0))
    if signals_sent > 0:
        return "El sistema está encontrando señales reales. Revisar calidad posterior en paper trading antes de relajar filtros."
    if candidates_rejected > 0:
        return f"El sistema está detectando intención, pero todavía filtra por calidad/riesgo. Principal punto a revisar: {bottleneck_text}."
    if paper_trades_opened > 0:
        return "No hubo señales reales, pero paper trading abrió validaciones. Mantener observación antes de tocar thresholds."
    return "Ventana sin oportunidades claras. No conviene ajustar estrategia solo con este bloque de ciclos."


def _top_label(items: object) -> str:
    if isinstance(items, list) and items and isinstance(items[0], dict):
        return str(items[0].get("label", "UNKNOWN"))
    return "sin datos"


def _humanize_bottleneck(text: str) -> str:
    if "Principal cuello de botella:" not in text:
        return text
    prefix, reason = text.split("Principal cuello de botella:", 1)
    return f"{prefix}Principal cuello de botella: {_humanize_reason(reason.strip())}"


def _humanize_reason(reason: str) -> str:
    labels = {
        "distance_to_liquidity_extreme": "precio demasiado lejos de liquidez",
        "directional_confluence_failed": "falta de confluencia direccional",
        "timeframe_alignment_penalty": "1H y 4H no alinean perfecto",
        "market_structure_range_penalty": "estructura en rango resta calidad",
        "quality_score_failed": "score insuficiente",
        "body_ratio_below_threshold": "vela con cuerpo débil",
        "paper_rejected_below_low": "score por debajo del nivel LOW",
        "paper_rejected_rr_below_min": "RR inferior al mínimo paper",
        "paper_rejected_spread_too_high": "spread estimado alto",
        "paper_rejected_atr_too_low": "ATR demasiado bajo",
        "paper_rejected_market_movement_low": "mercado sin movimiento suficiente",
        "sin_datos": "sin datos suficientes",
    }
    parts = [part for part in reason.split("|") if part]
    if not parts:
        return reason
    return " + ".join(labels.get(part, part.replace("_", " ")) for part in parts)


def maybe_send_paper_daily_summary(container: dict[str, object], *, dry_run: bool = False) -> None:
    settings = container["settings"]
    if not settings.paper_trading_summary_enabled:
        return
    date_key = now_utc_date_key()
    state_file = settings.paper_trading_summary_state_file
    last_sent_date = ""
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            if isinstance(state, dict):
                last_sent_date = str(state.get("last_sent_date", ""))
        except json.JSONDecodeError:
            last_sent_date = ""
    if last_sent_date == date_key:
        return
    summary = container["paper_trading_store"].build_daily_summary(date_key)
    container["notifier"].publish(format_paper_daily_summary_for_telegram(summary), dry_run=dry_run)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(
            {
                "last_sent_date": date_key,
                "sent_at": datetime.now(tz=UTC).isoformat(),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def maybe_send_live_daily_summary(container: dict[str, object], *, dry_run: bool = False) -> None:
    settings = container["settings"]
    if not settings.live_trade_tracking_enabled or not settings.live_trading_summary_enabled:
        return
    date_key = live_now_utc_date_key()
    state_file = settings.live_trading_summary_state_file
    last_sent_date = ""
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            if isinstance(state, dict):
                last_sent_date = str(state.get("last_sent_date", ""))
        except json.JSONDecodeError:
            last_sent_date = ""
    if last_sent_date == date_key:
        return
    summary = container["live_trading_store"].build_daily_summary(date_key)
    container["notifier"].publish(format_live_daily_summary_for_telegram(summary), dry_run=dry_run)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(
            {
                "last_sent_date": date_key,
                "sent_at": datetime.now(tz=UTC).isoformat(),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trading-signals")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan")
    scan.add_argument("--symbols", default="")
    scan.add_argument("--dry-run", action="store_true")
    scheduler = subparsers.add_parser("scheduler")
    scheduler.add_argument("--symbols", default="")
    scheduler.add_argument("--dry-run", action="store_true")
    scheduler.add_argument("--interval-seconds", type=int, default=None)
    telegram_start = subparsers.add_parser("telegram-start")
    telegram_start.add_argument("--dry-run", action="store_true")
    telegram_listener = subparsers.add_parser("telegram-listener")
    telegram_listener.add_argument("--dry-run", action="store_true")
    telegram_listener.add_argument("--sleep-seconds", type=int, default=None)
    args = parser.parse_args(argv)

    container = build_container()
    if args.command == "scan":
        symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()] or None
        result = run_market_scan(
            settings=container["settings"],
            market_data=container["market_data"],
            scan_repo=container["scan_repo"],
            signal_repo=container["signal_repo"],
            notifier=container["notifier"],
            diagnostics_store=container["diagnostics_store"],
            metrics=container["metrics"],
            paper_trading_store=container["paper_trading_store"],
            experimental_signal_store=container["experimental_signal_store"],
            shadow_signal_store=container["shadow_signal_store"],
            modular_signal_store=container["modular_signal_store"],
            live_trading_store=container["live_trading_store"],
            pattern_memory_store=container["pattern_memory_store"],
            symbols=symbols,
            dry_run=args.dry_run,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "scheduler":
        symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()] or None
        settings = container["settings"]
        interval = args.interval_seconds or settings.scan_interval_seconds
        summary_every_cycles = max(1, settings.telegram_diagnostic_summary_every_cycles)
        logger = container["logger"]
        results_window = load_scheduler_results_window(settings.scheduler_diagnostic_state_file)
        log_json(
            logger,
            "scheduler_diagnostic_counter_state",
            current_cycles=len(results_window),
            summary_every_cycles=summary_every_cycles,
            telegram_diagnostic_summary_enabled=settings.telegram_diagnostic_summary_enabled,
            interval_seconds=interval,
            state_file=str(settings.scheduler_diagnostic_state_file),
        )
        while True:
            result = run_market_scan(
                settings=container["settings"],
                market_data=container["market_data"],
                scan_repo=container["scan_repo"],
                signal_repo=container["signal_repo"],
                notifier=container["notifier"],
                diagnostics_store=container["diagnostics_store"],
                metrics=container["metrics"],
                paper_trading_store=container["paper_trading_store"],
                experimental_signal_store=container["experimental_signal_store"],
                shadow_signal_store=container["shadow_signal_store"],
                modular_signal_store=container["modular_signal_store"],
                live_trading_store=container["live_trading_store"],
                pattern_memory_store=container["pattern_memory_store"],
                symbols=symbols,
                dry_run=args.dry_run,
            )
            print(json.dumps(result["scan_run"], ensure_ascii=False))
            results_window.append(result)
            save_scheduler_results_window(settings.scheduler_diagnostic_state_file, results_window)
            log_json(
                logger,
                "scheduler_diagnostic_counter_state",
                current_cycles=len(results_window),
                summary_every_cycles=summary_every_cycles,
                telegram_diagnostic_summary_enabled=settings.telegram_diagnostic_summary_enabled,
                interval_seconds=interval,
                state_file=str(settings.scheduler_diagnostic_state_file),
            )
            if len(results_window) == summary_every_cycles:
                summary = build_scheduler_diagnostic_summary(results_window)
                log_json(logger, "scheduler_diagnostic_summary", **summary)
                if settings.telegram_diagnostic_summary_enabled:
                    container["notifier"].publish(
                        format_scheduler_diagnostic_summary_for_telegram(summary),
                        dry_run=args.dry_run,
                    )
                results_window.clear()
                save_scheduler_results_window(settings.scheduler_diagnostic_state_file, results_window)
            maybe_send_paper_daily_summary(container, dry_run=args.dry_run)
            maybe_send_live_daily_summary(container, dry_run=args.dry_run)
            time.sleep(interval)
    if args.command == "telegram-start":
        result = container["notifier"].sync_start_users(
            welcome_message=(
                "Bienvenido al bot de señales. "
                "A partir de ahora recibirás señales cuando haya setups válidos."
            ),
            dry_run=args.dry_run,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "telegram-listener":
        logger = container["logger"]
        configured_sleep = args.sleep_seconds or container["settings"].telegram_listener_sleep_seconds
        sleep_seconds = min(max(5, configured_sleep), 10)
        while True:
            try:
                result = container["notifier"].process_updates(
                    welcome_message=(
                        "Bienvenido al bot de señales. "
                        "A partir de ahora recibirás señales cuando haya setups válidos."
                    ),
                    default_message=(
                        "Hola 👋 Soy un bot automático de señales. "
                        "No respondo análisis personalizados por chat. "
                        "Cuando detecte una oportunidad válida, te enviaré la señal directamente."
                    ),
                    dry_run=args.dry_run,
                )
                log_json(
                    logger,
                    "telegram_listener_cycle",
                    processed_updates=len(result),
                    sleep_seconds=sleep_seconds,
                )
                if result:
                    print(json.dumps(result, ensure_ascii=False))
            except Exception as exc:  # pragma: no cover - defensive loop
                log_json(logger, "telegram_listener_error", error=str(exc))
            time.sleep(sleep_seconds)
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
