from __future__ import annotations

import logging
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from inspect import Parameter, signature
from pathlib import Path
from uuid import uuid4

from trading_signals.app.settings import Settings
from trading_signals.agents.coordinator import coordinate_votes
from trading_signals.agents.historical_agent import vote_historical
from trading_signals.agents.risk_agent import vote_risk
from trading_signals.agents.skeptic_agent import vote_skeptic
from trading_signals.agents.technical_agent import vote_technical
from trading_signals.analysis.liquidity import analyze_liquidity
from trading_signals.analysis.market_regime import analyze_market_regime
from trading_signals.analysis.momentum import analyze_momentum
from trading_signals.analysis.risk import analyze_risk
from trading_signals.analysis.trend import analyze_trend
from trading_signals.application.policies.public_safety_policy import POLICY_VERSION, evaluate_public_safety_policy
from trading_signals.application.policies.public_canary_policy import PublicShortCanaryConfig, evaluate_public_short_canary
from trading_signals.application.use_cases.analyze_symbol import analyze_symbol
from trading_signals.application.use_cases.candidate_funnel import (
    finalize_candidate_funnel_cycle,
    increment_candidate_funnel,
    new_candidate_funnel_cycle,
    record_candidate_rejection,
    record_relaxation_shadow_observation,
)
from trading_signals.application.use_cases.elite_profile_c_dev_tag import (
    apply_elite_profile_c_dev_tag,
    format_elite_profile_c_dev_note,
)
from trading_signals.application.use_cases.elite_subprofile_dev_tag import (
    apply_elite_subprofile_dev_tag,
    format_elite_subprofile_dev_note,
)
from trading_signals.application.use_cases.edge_knowledge_shadow_v1 import (
    evaluate_edge_knowledge_shadow_v1,
    format_edge_knowledge_shadow_dev_note,
)
from trading_signals.application.use_cases.edge_optimizer_shadow_v1 import evaluate_edge_optimizer_shadow_v1
from trading_signals.application.use_cases.edge_optimizer_active_v1 import apply_edge_optimizer_active_v1
from trading_signals.application.use_cases.active_signal_cleanup_shadow_v1 import (
    evaluate_active_signal_cleanup_shadow_v1,
)
from trading_signals.application.use_cases.active_signal_expiration_v1 import apply_active_signal_expiration_v1
from trading_signals.application.use_cases.paper_trading import (
    build_paper_candidate_from_decision,
    build_paper_rejection_diagnostic,
    paper_level_label,
    paper_market_is_tradeable,
)
from trading_signals.application.use_cases.performance_intelligence import (
    build_performance_intelligence,
    log_performance_intelligence,
)
from trading_signals.application.use_cases.performance_gate import evaluate_performance_gate
from trading_signals.application.use_cases.live_trading import (
    build_live_candidate_from_decision,
    format_public_live_trade_event_for_telegram,
    format_live_trade_event_for_telegram,
)
from trading_signals.application.use_cases.relaxation_shadow_v1 import (
    evaluate_relaxation_shadow_v1,
    format_relaxation_shadow_v1_message,
)
from trading_signals.notifications.telegram import send_dev_message, send_dev_signal_detail, send_public_signal
from trading_signals.application.use_cases.modular_paper import build_modular_signal_row
from trading_signals.application.use_cases.experimental_paper import build_experimental_signal_row
from trading_signals.application.use_cases.shadow_paper import build_shadow_signal_row
from trading_signals.application.use_cases.publish_signal import publish_signal
from trading_signals.application.use_cases.publish_signal import publish_filter_rejection_reason
from trading_signals.application.use_cases.publish_signal import meta_decision_public_filter_reason
from trading_signals.application.use_cases.publish_signal import public_routing_rejection_reason
from trading_signals.application.use_cases.setup_context import build_setup_context
from trading_signals.application.use_cases.signal_lifecycle import classify_signal_lifecycle
from trading_signals.application.use_cases.signal_update_v1 import (
    diagnose_signal_update_v1_skip,
    evaluate_signal_update_v1,
    format_signal_update_v1_dev_message,
    write_signal_update_v1_shadow_report,
)
from trading_signals.application.use_cases.strategy_v2_1_htf_alignment_filter import (
    apply_strategy_v2_1_htf_alignment_filter,
)
from trading_signals.data.market_data import market_data_status
from trading_signals.data.canonical_trade_source import TradeUniverse
from trading_signals.runtime.identity import build_runtime_identity, metadata_from_identity
from trading_signals.diagnostics.logger import log_module_diagnostic
from trading_signals.domain.entities.scan_run import ScanRun
from trading_signals.domain.entities.system_error import SystemError
from trading_signals.domain.entities.trade_signal import TradeSignal
from trading_signals.domain.services.risk_service import calculate_risk_plan
from trading_signals.domain.strategies.liquidity_sweep_mtf_v1 import LiquiditySweepMTFV1
from trading_signals.domain.value_objects.enums import SignalDecision, SignalStatus
from trading_signals.infrastructure.logging.logger import log_json
from trading_signals.market.pair_universe_filter import PairUniverseFilterConfig, evaluate_pair_universe
from trading_signals.memory.pattern_memory import build_pattern_record
from trading_signals.memory.signal_activity_log import append_signal_log
from trading_signals.notifications.telegram import telegram_status
from trading_signals.risk.kill_switch import evaluate_kill_switch
from trading_signals.risk.protection_engine import ProtectionEngineConfig, evaluate_protection_engine
from trading_signals.risk.trading_pause import is_trading_paused
from trading_signals.strategy.decision_engine import (
    build_signal_decision_from_modules,
    build_signal_decision_from_strategy_evaluation,
    evaluate_parallel_decision,
)
from trading_signals.strategy.decision_engine_selector import select_signal_decision
from trading_signals.strategy.experimental_decision_engine import evaluate_experimental_decision
from trading_signals.strategy.signal_builder import build_signal_diagnostic
from trading_signals.strategy.strategy_gate import analyze_strategy_gate


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def effective_config(settings: Settings, symbols: list[str] | None = None) -> dict[str, object]:
    effective_symbols = symbols if symbols is not None else settings.scan_symbols
    return {
        "strategy_id": "liquidity_sweep_mtf",
        "strategy_version": "v1",
        "entry_timeframe": settings.entry_timeframe,
        "higher_timeframe": settings.higher_timeframe,
        "symbols": effective_symbols,
        "setup_score_threshold": settings.setup_score_threshold,
        "atr_min_threshold": settings.atr_min_threshold,
        "max_distance_to_liquidity_atr": settings.max_distance_to_liquidity_atr,
        "min_body_ratio": settings.min_body_ratio,
        "risk_per_trade": settings.risk_per_trade,
        "min_rr": settings.min_rr,
        "scan_interval_seconds": settings.scan_interval_seconds,
        "publish_signal_decisions": settings.publish_signal_decisions,
        "protection_engine_mode": settings.protection_engine_mode,
        "pair_universe_filter_mode": settings.pair_universe_filter_mode,
    }


def validate_symbol_universe(settings: Settings, market_data, symbols: list[str]) -> dict[str, object]:
    provider = getattr(market_data, "provider_name", "unknown")
    fetch = market_data.get_ohlcv if hasattr(market_data, "get_ohlcv") else market_data.fetch_ohlcv
    valid_symbols: list[str] = []
    skipped_symbols: list[dict[str, str]] = []
    for symbol in symbols:
        normalized = market_data.normalize_symbol(symbol) if hasattr(market_data, "normalize_symbol") else symbol.strip().upper()
        try:
            entry = fetch(normalized, settings.entry_timeframe, limit=300)
            higher = fetch(normalized, settings.higher_timeframe, limit=300)
            if len(entry) < 220 or len(higher) < 220:
                skipped_symbols.append({"symbol": normalized, "reason": "insufficient_history", "provider": provider})
                continue
            valid_symbols.append(normalized)
        except Exception as exc:
            if "not supported" in str(exc).lower():
                reason = "unsupported_symbol"
            elif hasattr(market_data, "validate_symbol") and market_data.validate_symbol(normalized) is False:
                reason = "unsupported_symbol"
            else:
                reason = "provider_validation_error"
            skipped_symbols.append({"symbol": normalized, "reason": reason, "provider": provider})
    return {
        "requested_symbols": len(symbols),
        "valid_symbols": valid_symbols,
        "skipped_symbols": skipped_symbols,
        "skipped_reasons": dict(Counter(item["reason"] for item in skipped_symbols)),
        "provider": provider,
    }


def _pair_universe_filter_config(settings: Settings) -> PairUniverseFilterConfig:
    return PairUniverseFilterConfig(
        mode=settings.pair_universe_filter_mode,
        min_volume=settings.pair_universe_min_volume,
        max_spread_pct=settings.pair_universe_max_spread_pct,
        min_volatility_pct=settings.pair_universe_min_volatility_pct,
        max_volatility_pct=settings.pair_universe_max_volatility_pct,
        min_history_candles=settings.pair_universe_min_history_candles,
        blacklist=settings.pair_universe_blacklist,
        whitelist=settings.pair_universe_whitelist,
        rejection_threshold=settings.pair_universe_rejection_threshold,
        rejection_lookback_hours=settings.pair_universe_rejection_lookback_hours,
        min_recent_avg_r=settings.pair_universe_min_recent_avg_r,
        performance_min_trades=settings.pair_universe_performance_min_trades,
        performance_lookback_days=settings.pair_universe_performance_lookback_days,
    )


def _log_pair_universe_filter(logger, summary: dict[str, object]) -> None:
    mode = str(summary.get("mode", "shadow_only"))
    failed = summary.get("failed_symbols", [])
    passed = set(str(symbol) for symbol in summary.get("passed_symbols", []) if symbol)
    for symbol in passed:
        log_json(
            logger,
            "pair_filter_evaluated",
            symbol=symbol,
            mode=mode,
            pair_filter_passed=True,
            pair_filter_failed=False,
            pair_filter_reason="passed",
        )
    if isinstance(failed, list):
        for item in failed:
            if not isinstance(item, dict):
                continue
            reasons = item.get("reasons", [])
            if not isinstance(reasons, list):
                reasons = [str(reasons)]
            log_json(
                logger,
                "pair_filter_evaluated",
                symbol=item.get("symbol"),
                mode=mode,
                pair_filter_passed=False,
                pair_filter_failed=True,
                pair_filter_reason="|".join(str(reason) for reason in reasons) or "unknown",
                metrics=item.get("metrics", {}),
            )
            log_json(
                logger,
                "pair_filter_failed",
                symbol=item.get("symbol"),
                mode=mode,
                pair_filter_reason="|".join(str(reason) for reason in reasons) or "unknown",
                metrics=item.get("metrics", {}),
            )


def build_signal_dedupe_key(symbol: str, decision: str, strategy_id: str, strategy_version: str, entry_snapshot) -> str:
    return "|".join(
        [
            symbol,
            decision,
            strategy_id,
            strategy_version,
            entry_snapshot.timeframe,
            entry_snapshot.timestamp,
        ]
    )


def _no_send_reason(signal: TradeSignal, status: str, should_publish_decision: bool, is_duplicate: bool, rejection_reasons: list[str]) -> str:
    if signal.status == SignalStatus.PUBLISHED.value:
        return ""
    if signal.decision == SignalDecision.NO_TRADE.value:
        return "|".join(rejection_reasons) if rejection_reasons else "no_trade_without_rejection_reason"
    if status != SignalStatus.VALID.value:
        return "|".join(rejection_reasons) if rejection_reasons else status
    if not should_publish_decision:
        return "publish_decision_filtered"
    if is_duplicate:
        return "duplicate_signal_suppressed"
    return "not_published"


def _log_symbol_diagnostics(
    *,
    settings: Settings,
    symbol: str,
    analysis,
    evaluation,
    signal: TradeSignal,
    status: str,
    should_publish_decision: bool,
    is_duplicate: bool,
    setup_context: dict[str, object],
) -> None:
    entry = analysis.entry_snapshot
    logger = logging.getLogger("trading_signals")
    setup_type = "SECONDARY_SIGNAL" if "secondary_setup" in evaluation.passed_filters else "PRIMARY_SWEEP_SIGNAL" if "primary_sweep_setup" in evaluation.passed_filters else "NO_SIGNAL"
    directional_distance_check = _trace_value(evaluation, "directional_distance_check")
    nearest_liquidity_check = _trace_value(evaluation, "nearest_liquidity_check")
    liquidity_rule_applied = _trace_value(evaluation, "liquidity_rule_applied")
    log_json(
        logger,
        "trading_symbol_diagnostics",
        symbol=symbol,
        current_price=entry.close,
        rsi=entry.metadata.get("rsi"),
        trend=entry.trend,
        trend_higher_timeframe=analysis.higher_snapshot.trend,
        body_ratio=entry.body_ratio,
        volume_current=entry.volume,
        volume_average=entry.metadata.get("volume_average_20"),
        volume_ratio=entry.metadata.get("volume_ratio_vs_average_20"),
        decision=signal.decision,
        setup_score_final=evaluation.setup_score,
        setup_score_min_required=settings.setup_score_threshold,
        market_structure=entry.market_structure,
        liquidity_sweep=entry.liquidity_sweep,
        break_of_structure=entry.metadata.get("break_of_structure"),
        setup_type=setup_type,
        atr=entry.atr,
        liquidity_trade_direction=_candidate_direction(analysis),
        directional_liquidity_level=entry.metadata.get("directional_liquidity_level"),
        directional_liquidity_side=entry.metadata.get("directional_liquidity_side"),
        nearest_liquidity_level=entry.metadata.get("nearest_liquidity_level"),
        nearest_liquidity_side=entry.metadata.get("nearest_liquidity_side"),
        distance_to_liquidity_atr=entry.distance_to_liquidity_atr,
        nearest_distance_to_liquidity_atr=entry.metadata.get("nearest_distance_to_liquidity_atr"),
        distance_to_liquidity_threshold_atr=settings.max_distance_to_liquidity_atr,
        distance_to_liquidity_extreme_threshold_atr=settings.max_distance_to_liquidity_atr * 2,
        directional_distance_check=directional_distance_check,
        nearest_liquidity_check=nearest_liquidity_check,
        liquidity_rule_applied=liquidity_rule_applied,
        conditions_passed=evaluation.passed_filters,
        conditions_failed=evaluation.failed_filters,
        rejection_reasons=evaluation.rejection_reasons,
        no_signal_reason=_no_send_reason(
            signal,
            status,
            should_publish_decision,
            is_duplicate,
            evaluation.rejection_reasons,
        ),
        market_regime=setup_context.get("market_regime"),
        session=setup_context.get("session"),
        entry_context=setup_context.get("entry_context"),
        trade_location=setup_context.get("trade_location"),
        risk_context={
            "rr_valid": setup_context.get("rr_valid"),
            "sl_distance_atr": setup_context.get("sl_distance_atr"),
            "tp_distance_atr": setup_context.get("tp_distance_atr"),
            "late_entry_from_bos": setup_context.get("late_entry_from_bos"),
        },
        avoidance_warnings=setup_context.get("avoidance_warnings", []),
    )


def _trace_value(evaluation, key: str) -> str | None:
    prefix = f"{key}="
    for item in evaluation.decision_trace:
        if item.startswith(prefix):
            return item[len(prefix):]
    return None


def _candidate_direction(analysis) -> str:
    entry = analysis.entry_snapshot
    bos = str(entry.metadata.get("break_of_structure", "none"))
    if entry.liquidity_sweep == "bullish_sweep" or bos == "bullish_bos":
        return SignalDecision.LONG.value
    if entry.liquidity_sweep == "bearish_sweep" or bos == "bearish_bos":
        return SignalDecision.SHORT.value
    if entry.trend in {"bullish", "bearish"}:
        return SignalDecision.LONG.value if entry.trend == "bullish" else SignalDecision.SHORT.value
    return SignalDecision.NO_TRADE.value


def _candidate_setup_type(analysis, evaluation) -> str | None:
    entry = analysis.entry_snapshot
    if evaluation.decision != SignalDecision.NO_TRADE.value:
        return None
    if entry.liquidity_sweep in {"bullish_sweep", "bearish_sweep"}:
        return "MAIN_SIGNAL"
    bos = str(entry.metadata.get("break_of_structure", "none"))
    score_near_secondary = evaluation.setup_score >= 0.8 * (45 + 15)
    has_secondary_context = (
        entry.trend == analysis.higher_snapshot.trend
        or bos in {"bullish_bos", "bearish_bos"}
        or float(entry.metadata.get("volume_ratio_vs_average_20", 0.0)) >= 1.2
    )
    if bos in {"bullish_bos", "bearish_bos"} and has_secondary_context and score_near_secondary:
        return "SECONDARY_SIGNAL"
    return None


def _multi_agent_shadow_decision(
    *,
    setup_context: dict[str, object],
    evaluation,
    analysis,
    risk_plan,
    performance_gate: dict[str, object] | None,
) -> dict[str, object]:
    votes = [
        vote_technical(setup_context=setup_context, evaluation=evaluation, analysis=analysis),
        vote_risk(risk_plan=risk_plan, setup_context=setup_context),
        vote_historical(performance_gate=performance_gate),
        vote_skeptic(evaluation=evaluation, setup_context=setup_context, performance_gate=performance_gate),
    ]
    return coordinate_votes(votes)


def _signal_setup_type(evaluation) -> str:
    if "secondary_setup" in evaluation.passed_filters:
        return "SECONDARY_SIGNAL"
    if "primary_sweep_setup" in evaluation.passed_filters:
        return "MAIN_SIGNAL"
    return "SIGNAL"


def _candidate_rejected_payload(
    *,
    symbol: str,
    analysis,
    evaluation,
) -> dict[str, object] | None:
    setup_type = _candidate_setup_type(analysis, evaluation)
    if setup_type is None:
        return None
    entry = analysis.entry_snapshot
    return {
        "symbol": symbol,
        "setup_type": setup_type,
        "direction": _candidate_direction(analysis),
        "setup_score_final": evaluation.setup_score,
        "rejection_reason": "|".join(evaluation.rejection_reasons) if evaluation.rejection_reasons else "unknown",
        "current_price": entry.close,
        "rsi": entry.metadata.get("rsi"),
        "volume_current": entry.volume,
        "volume_average": entry.metadata.get("volume_average_20"),
        "volume_ratio": entry.metadata.get("volume_ratio_vs_average_20"),
        "trend_1h": entry.trend,
        "trend_4h": analysis.higher_snapshot.trend,
        "break_of_structure": entry.metadata.get("break_of_structure"),
        "directional_liquidity_level": entry.metadata.get("directional_liquidity_level"),
        "directional_liquidity_side": entry.metadata.get("directional_liquidity_side"),
        "nearest_liquidity_level": entry.metadata.get("nearest_liquidity_level"),
        "nearest_liquidity_side": entry.metadata.get("nearest_liquidity_side"),
        "distance_to_liquidity_atr": entry.distance_to_liquidity_atr,
        "nearest_distance_to_liquidity_atr": entry.metadata.get("nearest_distance_to_liquidity_atr"),
        "directional_distance_check": _trace_value(evaluation, "directional_distance_check"),
        "nearest_liquidity_check": _trace_value(evaluation, "nearest_liquidity_check"),
        "liquidity_rule_applied": _trace_value(evaluation, "liquidity_rule_applied"),
    }


def _log_candidate_rejected(
    *,
    payload: dict[str, object] | None,
) -> None:
    if payload is None:
        return
    logger = logging.getLogger("trading_signals")
    log_json(logger, "CANDIDATE_REJECTED", **payload)


def _log_paper_candidate_rejected(payload: dict[str, object] | None) -> None:
    if payload is None:
        return
    logger = logging.getLogger("trading_signals")
    log_json(logger, "PAPER_CANDIDATE_REJECTED", **payload)


def _penalties_from_trace(evaluation) -> list[str]:
    penalties = _trace_value(evaluation, "penalties")
    if not penalties or penalties == "none":
        return []
    return [item.strip() for item in penalties.split(",") if item.strip()]


def _directional_confluence_status(evaluation) -> str:
    if "directional_confluence" in evaluation.passed_filters:
        return "passed"
    if "directional_confluence_failed" in evaluation.failed_filters or "directional_confluence_failed" in evaluation.rejection_reasons:
        return "failed"
    return "not_evaluated"


def _high_score_rejected_payload(
    *,
    symbol: str,
    analysis,
    evaluation,
    signal: TradeSignal,
    status: str,
    should_publish_decision: bool,
    is_duplicate: bool,
    setup_context: dict[str, object],
    risk_plan,
    publish_filter_reason: str | None,
    lifecycle,
) -> dict[str, object] | None:
    if float(evaluation.setup_score) < 85:
        return None
    if signal.status == SignalStatus.PUBLISHED.value:
        return None
    entry = analysis.entry_snapshot
    blocking_reasons = list(dict.fromkeys(evaluation.rejection_reasons))
    if publish_filter_reason and publish_filter_reason not in blocking_reasons:
        blocking_reasons.append(publish_filter_reason)
    if is_duplicate and "duplicate_signal_suppressed" not in blocking_reasons:
        blocking_reasons.append("duplicate_signal_suppressed")
    if not should_publish_decision and "publish_decision_filtered" not in blocking_reasons:
        blocking_reasons.append("publish_decision_filtered")
    if lifecycle is not None and not lifecycle.should_publish and lifecycle.reason not in blocking_reasons:
        blocking_reasons.append(lifecycle.reason)
    if not blocking_reasons:
        blocking_reasons.append(
            _no_send_reason(signal, status, should_publish_decision, is_duplicate, evaluation.rejection_reasons)
        )
    return {
        "symbol": symbol,
        "direction": evaluation.decision if evaluation.decision != SignalDecision.NO_TRADE.value else _candidate_direction(analysis),
        "score": evaluation.setup_score,
        "setup_type": _signal_setup_type(evaluation) if evaluation.decision != SignalDecision.NO_TRADE.value else (_candidate_setup_type(analysis, evaluation) or "NO_SIGNAL"),
        "final_decision": "send" if signal.status == SignalStatus.PUBLISHED.value else "not_send",
        "signal_decision": signal.decision,
        "signal_status": signal.status,
        "blocking_reasons": blocking_reasons,
        "directional_confluence_status": _directional_confluence_status(evaluation),
        "htf_trend": analysis.higher_snapshot.trend,
        "ltf_trend": entry.trend,
        "timeframe_alignment": entry.trend == analysis.higher_snapshot.trend,
        "warnings": setup_context.get("avoidance_warnings", []),
        "penalties": _penalties_from_trace(evaluation),
        "rr": getattr(risk_plan, "risk_reward", None),
        "entry": getattr(risk_plan, "entry", None),
        "stop_loss": getattr(risk_plan, "stop_loss", None),
        "take_profit": getattr(risk_plan, "take_profit", None),
        "passed_filters": evaluation.passed_filters,
        "failed_filters": evaluation.failed_filters,
        "decision_trace": evaluation.decision_trace,
    }


def _log_high_score_rejected(payload: dict[str, object] | None) -> None:
    if payload is None:
        return
    logger = logging.getLogger("trading_signals")
    log_json(logger, "HIGH_SCORE_REJECTED", **payload)


def _pattern_final_status(*, signal: TradeSignal, high_score_rejected: dict[str, object] | None, paper_trade_created: bool) -> str:
    if signal.status == SignalStatus.PUBLISHED.value:
        return "sent_signal"
    if high_score_rejected is not None:
        return "high_score_rejected"
    if paper_trade_created:
        return "paper_trade"
    return "rejected"


def _risk_reward_values(risk_plan) -> tuple[float | None, float | None]:
    if risk_plan is None:
        return None, None
    risk = abs(risk_plan.entry - risk_plan.stop_loss)
    if risk <= 0:
        return None, None
    return 1.0, abs(risk_plan.take_profit - risk_plan.entry) / risk


def _protection_engine_config(settings: Settings) -> ProtectionEngineConfig:
    return ProtectionEngineConfig(
        mode=settings.protection_engine_mode,
        symbol_loss_cooldown_hours=settings.protection_symbol_loss_cooldown_hours,
        symbol_rejection_threshold=settings.protection_symbol_rejection_threshold,
        symbol_rejection_lookback_hours=settings.protection_symbol_rejection_lookback_hours,
        symbol_rejection_cooldown_hours=settings.protection_symbol_rejection_cooldown_hours,
        max_drawdown_guard_r=settings.protection_max_drawdown_guard_r,
        max_drawdown_lookback_days=settings.protection_max_drawdown_lookback_days,
        low_profit_min_trades=settings.protection_low_profit_min_trades,
        low_profit_min_avg_r=settings.protection_low_profit_min_avg_r,
        low_profit_lookback_days=settings.protection_low_profit_lookback_days,
        toxic_context_shadow_enabled=settings.protection_toxic_context_shadow_enabled,
    )


def _public_short_canary_config(settings: Settings) -> PublicShortCanaryConfig:
    return PublicShortCanaryConfig(
        enabled=settings.public_short_canary_enabled,
        session=settings.public_short_canary_session,
        direction=settings.public_short_canary_direction,
        entry_context=settings.public_short_canary_entry_context,
        setup_type=settings.public_short_canary_setup_type,
        min_score=settings.public_short_canary_min_score,
    )


def _relaxed_public_shadow_from_deliveries(deliveries) -> dict[str, object] | None:
    for delivery in deliveries or []:
        if getattr(delivery, "channel", "") != "telegram_dev_relaxed_shadow":
            continue
        payload = getattr(delivery, "payload", {})
        if isinstance(payload, dict) and isinstance(payload.get("relaxed_public_policy"), dict):
            return payload["relaxed_public_policy"]
    return None


def _observe_relaxation_shadow_v1(
    *,
    logger,
    notifier,
    signal: TradeSignal,
    evaluation,
    risk_plan,
    analysis,
    setup_context: dict[str, object],
    current_policy: dict[str, object],
    store,
    expires_after_candles: int,
    dry_run: bool,
    stage: str,
) -> dict[str, object]:
    result = evaluate_relaxation_shadow_v1(
        signal=signal,
        evaluation=evaluation,
        risk_plan=risk_plan,
        entry_snapshot=analysis.entry_snapshot,
        higher_snapshot=analysis.higher_snapshot,
        setup_context=setup_context,
        current_policy=current_policy,
        store=store,
        opened_at=_now_iso(),
        expires_after_candles=expires_after_candles,
    )
    payload: dict[str, object] = {
        "stage": stage,
        "should_send_dev": result.get("should_send_dev", False),
        "skip_reason": result.get("skip_reason", ""),
        "filter_result": result.get("filter_result", {}),
    }
    if result.get("should_send_dev") and result.get("candidate") is not None:
        candidate = result["candidate"]
        message = format_relaxation_shadow_v1_message(candidate)
        send_dev_signal_detail(notifier, message, dry_run=dry_run)
        log_json(
            logger,
            "relaxation_shadow_v1_signal_sent_dev",
            symbol=signal.symbol,
            direction=signal.decision,
            stage=stage,
            relaxed_filters=getattr(candidate, "relaxed_filters", []),
            original_rejection_reasons=getattr(candidate, "original_rejection_reasons", []),
        )
        payload.update(
            {
                "trade_created": True,
                "dedupe_key": getattr(candidate, "dedupe_key", ""),
                "relaxed_filters": getattr(candidate, "relaxed_filters", []),
                "original_rejection_reasons": getattr(candidate, "original_rejection_reasons", []),
            }
        )
    else:
        filter_result = result.get("filter_result", {})
        log_json(
            logger,
            "relaxation_shadow_v1_signal_skipped",
            symbol=signal.symbol,
            direction=signal.decision,
            stage=stage,
            reason=result.get("skip_reason", ""),
            safe_filters=filter_result.get("safe_filters", []) if isinstance(filter_result, dict) else [],
            unsafe_filters=filter_result.get("unsafe_filters", []) if isinstance(filter_result, dict) else [],
        )
        payload["trade_created"] = False
    return payload


def _observe_signal_update_v1(
    *,
    logger,
    notifier,
    settings: Settings,
    signal_repo,
    signal: TradeSignal,
    evaluation,
    risk_plan,
    entry_snapshot,
    setup_context: dict[str, object],
    is_duplicate: bool,
    lifecycle,
    dry_run: bool,
) -> dict[str, object] | None:
    update = evaluate_signal_update_v1(
        signal_repo=signal_repo,
        signal=signal,
        evaluation=evaluation,
        entry_snapshot=entry_snapshot,
        risk_plan=risk_plan,
        setup_context=setup_context,
        is_duplicate=is_duplicate,
        lifecycle=lifecycle,
        dev_note_enabled=settings.signal_update_v1_dev_note_enabled,
    )
    if update is None:
        skip = diagnose_signal_update_v1_skip(
            signal_repo=signal_repo,
            signal=signal,
            is_duplicate=is_duplicate,
            lifecycle=lifecycle,
            dev_note_enabled=settings.signal_update_v1_dev_note_enabled,
        )
        if skip is not None:
            payload = skip.to_dict()
            log_json(
                logger,
                "signal_update_v1_skipped",
                symbol=skip.symbol,
                direction=skip.direction,
                skip_reason=skip.skip_reason,
                current_dedupe_key=skip.current_dedupe_key,
                is_duplicate=skip.is_duplicate,
                lifecycle_reason=skip.lifecycle_reason,
                reasons=skip.reasons,
                shadow_only=True,
                public_allowed=False,
                dev_note_enabled=settings.signal_update_v1_dev_note_enabled,
            )
            try:
                write_signal_update_v1_shadow_report(
                    reports_path=settings.data_storage_path.parent / "reports",
                    update=skip,
                )
            except OSError as exc:
                log_json(
                    logger,
                    "signal_update_v1_report_write_failed",
                    symbol=skip.symbol,
                    direction=skip.direction,
                    error=str(exc),
                )
            return payload
        return None

    payload = update.to_dict()
    log_json(
        logger,
        "signal_update_v1_detected",
        symbol=update.symbol,
        direction=update.direction,
        active_signal_id=update.active_signal_id,
        active_dedupe_key=update.active_dedupe_key,
        current_dedupe_key=update.current_dedupe_key,
        reasons=update.reasons,
    )
    log_json(
        logger,
        "signal_update_v1_classified",
        symbol=update.symbol,
        direction=update.direction,
        update_type=update.update_type,
        score=update.score,
        active_score=update.active_score,
        rr=update.rr,
        active_rr=update.active_rr,
        new_snapshot=update.new_snapshot,
        reentry_confirmation=update.reentry_confirmation,
        risks=update.risks,
    )
    log_json(
        logger,
        "signal_update_v1_shadow_decision",
        symbol=update.symbol,
        direction=update.direction,
        update_type=update.update_type,
        shadow_only=True,
        public_allowed=False,
        dev_note_enabled=settings.signal_update_v1_dev_note_enabled,
    )
    try:
        write_signal_update_v1_shadow_report(
            reports_path=settings.data_storage_path.parent / "reports",
            update=update,
        )
    except OSError as exc:
        log_json(
            logger,
            "signal_update_v1_report_write_failed",
            symbol=update.symbol,
            direction=update.direction,
            error=str(exc),
        )
    if settings.signal_update_v1_dev_note_enabled:
        send_dev_message(notifier, format_signal_update_v1_dev_message(update), dry_run=dry_run)
    return payload


def _observe_active_signal_cleanup_shadow_v1(
    *,
    logger,
    signal_repo,
    signal: TradeSignal,
    is_duplicate: bool,
    lifecycle,
) -> dict[str, object] | None:
    cleanup = evaluate_active_signal_cleanup_shadow_v1(
        signal_repo=signal_repo,
        signal=signal,
        is_duplicate=is_duplicate,
        lifecycle=lifecycle,
    )
    if cleanup is None:
        return None
    log_json(
        logger,
        "active_signal_cleanup_shadow_analysis",
        symbol=cleanup.get("symbol"),
        direction=cleanup.get("direction"),
        active_key=cleanup.get("active_key"),
        is_duplicate=cleanup.get("is_duplicate"),
        lifecycle_reason=cleanup.get("lifecycle_reason"),
        blocking_active_count=cleanup.get("blocking_active_count"),
        cleanup_classification=cleanup.get("cleanup_classification"),
        likely_zombie_count=cleanup.get("likely_zombie_count", 0),
        stale_count=cleanup.get("stale_count", 0),
        shadow_only=True,
        public_allowed=False,
    )
    log_json(
        logger,
        "active_signal_cleanup_shadow_candidate",
        symbol=cleanup.get("symbol"),
        direction=cleanup.get("direction"),
        active_key=cleanup.get("active_key"),
        cleanup_classification=cleanup.get("cleanup_classification"),
        estimated_released_candidate_if_cleanup=cleanup.get("estimated_released_candidate_if_cleanup", False),
        blocking_active_signals=cleanup.get("blocking_active_signals", []),
        skip_reason=cleanup.get("skip_reason"),
        shadow_only=True,
        public_allowed=False,
    )
    return cleanup


def _pre_publishability_block_reasons(
    *,
    should_publish_decision: bool,
    publish_filter_reason: str | None,
    is_duplicate: bool,
    lifecycle,
    current_public_policy: dict[str, object],
) -> list[str]:
    reasons = []
    if not should_publish_decision:
        reasons.append("publish_decision_filtered")
    if publish_filter_reason:
        reasons.append(publish_filter_reason)
    if is_duplicate:
        reasons.append("duplicate_signal_suppressed")
    if lifecycle is not None and not lifecycle.should_publish:
        reasons.append(str(lifecycle.reason))
    if not reasons and not bool(current_public_policy.get("public_allowed")):
        reasons.extend(str(reason) for reason in current_public_policy.get("block_reasons", []) or [])
    return list(dict.fromkeys(reason for reason in reasons if reason))


def _funnel_publishability_reason(
    *,
    should_publish_decision: bool,
    publish_filter_reason: str | None,
    is_duplicate: bool,
    lifecycle,
    public_block_reason: str | None,
) -> str | None:
    reasons: list[str] = []
    if not should_publish_decision:
        reasons.append("publish_decision_filtered")
    if publish_filter_reason:
        reasons.append(publish_filter_reason)
    if is_duplicate:
        reasons.append("duplicate_signal_suppressed")
    if lifecycle is not None and not lifecycle.should_publish:
        reasons.append(str(lifecycle.reason))
    if public_block_reason:
        reasons.append(public_block_reason)
    return "|".join(dict.fromkeys(reasons)) if reasons else None


def _log_protection_diagnostics(logger, *, symbol: str, protection: dict[str, object]) -> None:
    if not protection.get("protection_triggered"):
        return
    triggers = protection.get("triggers", [])
    if not isinstance(triggers, list):
        triggers = []
    for trigger in triggers:
        if not isinstance(trigger, dict):
            continue
        log_json(
            logger,
            "protection_triggered",
            protection_triggered=True,
            protection_reason=trigger.get("protection_reason", "unknown"),
            protection_mode=protection.get("protection_mode"),
            protection_enforced=protection.get("protection_enforced"),
            affected_symbol=symbol,
            affected_context=protection.get("affected_context", {}),
            details=trigger,
        )


def _build_performance_intelligence_with_optional_edge_memory(
    *,
    pattern_record: dict[str, object],
    pattern_history: list[dict[str, object]],
    edge_memory_data_path,
) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "pattern_record": pattern_record,
        "pattern_history": pattern_history,
    }
    parameters = signature(build_performance_intelligence).parameters
    accepts_edge_memory = (
        "edge_memory_data_path" in parameters
        or any(parameter.kind == Parameter.VAR_KEYWORD for parameter in parameters.values())
    )
    if accepts_edge_memory:
        kwargs["edge_memory_data_path"] = edge_memory_data_path
    return build_performance_intelligence(**kwargs)


def _signal_activity_status(*, signal: TradeSignal, paper_trade_created: bool, experimental_signal_saved: bool) -> str:
    if signal.status == SignalStatus.PUBLISHED.value:
        return "sent"
    if paper_trade_created:
        return "paper"
    if experimental_signal_saved:
        return "experimental"
    if signal.decision == SignalDecision.NO_TRADE.value:
        return "no_trade"
    return "rejected"


def _signal_activity_entry(
    *,
    timestamp: str,
    symbol: str,
    analysis,
    evaluation,
    risk_plan,
    signal: TradeSignal,
    signal_decision,
    selected_engine: str,
    setup_context: dict[str, object],
    module_diagnostics: dict[str, dict[str, object]],
    paper_trade_created: bool,
    experimental_signal_saved: bool,
    publish_filter_reason: str | None,
    paper_rejection: dict[str, object] | None,
    public_published: bool = False,
    public_block_reason: str | None = None,
    public_canary: dict[str, object] | None = None,
    relaxed_public_shadow: dict[str, object] | None = None,
    signal_update_v1: dict[str, object] | None = None,
    edge_knowledge_shadow: dict[str, object] | None = None,
    edge_optimizer_shadow: dict[str, object] | None = None,
    edge_optimizer_active: dict[str, object] | None = None,
    strategy_v2_1_htf_alignment_filter: dict[str, object] | None = None,
    runtime_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    entry = analysis.entry_snapshot
    strategy_gate = module_diagnostics.get("strategy_gate", {})
    strategy_details = strategy_gate.get("details", {}) if isinstance(strategy_gate.get("details"), dict) else {}
    direction = evaluation.decision if evaluation.decision != SignalDecision.NO_TRADE.value else _candidate_direction(analysis)
    rr_tp1, rr_tp2 = _risk_reward_values(risk_plan)
    rejection_reasons = list(dict.fromkeys(
        [
            *list(evaluation.rejection_reasons),
            *list(getattr(signal_decision, "rejection_reasons", [])),
            *([publish_filter_reason] if publish_filter_reason else []),
            *([str(paper_rejection.get("rejection_reason"))] if paper_rejection else []),
        ]
    ))
    metadata = dict(runtime_metadata or {})
    accepted = evaluation.decision in {SignalDecision.LONG.value, SignalDecision.SHORT.value}
    universe = TradeUniverse.ACCEPTED.value if accepted else (
        TradeUniverse.SHADOW.value if experimental_signal_saved else TradeUniverse.REJECTED.value
    )
    return {
        "timestamp": timestamp,
        "symbol": symbol,
        "direction": direction,
        "score": float(evaluation.setup_score),
        "status": _signal_activity_status(
            signal=signal,
            paper_trade_created=paper_trade_created,
            experimental_signal_saved=experimental_signal_saved,
        ),
        "universe": universe,
        "accepted": accepted,
        "created_at": timestamp,
        "accepted_at": timestamp if accepted else None,
        "setup_type": _signal_setup_type(evaluation) if evaluation.decision != SignalDecision.NO_TRADE.value else (_candidate_setup_type(analysis, evaluation) or "NO_SIGNAL"),
        "reasons": strategy_details.get("reason_final") or "|".join(evaluation.rejection_reasons) or signal_decision.decision,
        "rejection_reasons": rejection_reasons,
        "conditions_failed": list(evaluation.failed_filters),
        "avoidance_warnings": setup_context.get("avoidance_warnings", []),
        "failed_conditions": strategy_details.get("failed_conditions", []),
        "penalties": _penalties_from_trace(evaluation),
        "rr": rr_tp2 if rr_tp2 is not None else getattr(risk_plan, "risk_reward", None),
        "entry_price": getattr(risk_plan, "entry", None),
        "stop_loss": getattr(risk_plan, "stop_loss", None),
        "take_profit": getattr(risk_plan, "take_profit", None),
        "trend_entry": entry.trend,
        "trend_higher": analysis.higher_snapshot.trend,
        "market_structure": entry.market_structure,
        "liquidity_sweep": entry.liquidity_sweep,
        "market_regime": setup_context.get("market_regime"),
        "entry_context": setup_context.get("entry_context"),
        "source_engine": getattr(signal_decision, "source_engine", selected_engine),
        "public_published": public_published,
        "published_at": timestamp if public_published else None,
        "strategy_version": evaluation.strategy_version,
        "git_commit_sha": metadata.get("git_commit_sha", "unknown"),
        "config_hash": metadata.get("config_hash", "unknown"),
        "runtime_flags": metadata.get("runtime_flags", {}),
        "deployment_id": metadata.get("deployment_id", "unknown"),
        "selected_engine": selected_engine,
        "policy_version": metadata.get("policy_version", POLICY_VERSION),
        "experiment_id": metadata.get("experiment_id", "none" if accepted else "unknown"),
        "public_block_reason": public_block_reason,
        "public_canary_decision": (public_canary or {}).get("public_canary_decision"),
        "public_canary_match": (public_canary or {}).get("public_canary_match"),
        "public_canary_reason": (public_canary or {}).get("public_canary_reason"),
        "relaxed_public_policy_decision": (relaxed_public_shadow or {}).get("relaxed_public_policy_decision"),
        "relaxed_public_policy_vs_current": (relaxed_public_shadow or {}).get("relaxed_public_policy_vs_current"),
        "relaxed_public_shadow_sent_dev": (relaxed_public_shadow or {}).get("relaxed_public_shadow_sent_dev"),
        "signal_update_v1_type": (signal_update_v1 or {}).get("update_type"),
        "signal_update_v1_shadow_only": (signal_update_v1 or {}).get("shadow_only"),
        "edge_knowledge_bonus": (edge_knowledge_shadow or {}).get("ekb_bonus"),
        "edge_knowledge_bias": (edge_knowledge_shadow or {}).get("hypothetical_bias"),
        "edge_knowledge_confidence": (edge_knowledge_shadow or {}).get("ekb_confidence"),
        "edge_knowledge_matched_edges_count": (edge_knowledge_shadow or {}).get("matched_edges_count"),
        "edge_optimizer_adjustment": (edge_optimizer_shadow or {}).get("optimizer_adjustment"),
        "edge_optimizer_bias": (edge_optimizer_shadow or {}).get("hypothetical_bias"),
        "edge_optimizer_confidence": (edge_optimizer_shadow or {}).get("optimizer_confidence"),
        "edge_optimizer_matched_edges_count": (edge_optimizer_shadow or {}).get("matched_edges_count"),
        "original_score": (edge_optimizer_active or {}).get("original_score"),
        "edge_optimizer_active_adjustment": (edge_optimizer_active or {}).get("active_adjustment"),
        "adjusted_score": (edge_optimizer_active or {}).get("adjusted_score"),
        "strategy_v2_1_htf_alignment": (strategy_v2_1_htf_alignment_filter or {}).get("strategy_v2_1_htf_alignment"),
        "strategy_v2_1_would_block": (strategy_v2_1_htf_alignment_filter or {}).get("strategy_v2_1_would_block"),
        "strategy_v2_1_blocked": (strategy_v2_1_htf_alignment_filter or {}).get("strategy_v2_1_blocked"),
        "strategy_v2_1_mode": (strategy_v2_1_htf_alignment_filter or {}).get("strategy_v2_1_mode"),
        "strategy_v2_1_rejection_reason": (strategy_v2_1_htf_alignment_filter or {}).get("strategy_v2_1_rejection_reason"),
        "raw_summary": {
            "signal_id": signal.id,
            "evaluation_id": evaluation.id,
            "signal_status": signal.status,
            "signal_decision": signal_decision.decision,
            "selected_engine": selected_engine,
            "strategy_gate_reason": strategy_gate.get("reason"),
            "strategy_gate_ok": strategy_gate.get("ok"),
            "strategy_gate_score": strategy_gate.get("score"),
            "suggested_direction": strategy_details.get("suggested_direction"),
            "setup_detected": strategy_details.get("setup_detected"),
            "paper_trade_created": paper_trade_created,
            "experimental_signal_saved": experimental_signal_saved,
            "publish_filter_reason": publish_filter_reason,
            "public_published": public_published,
            "public_block_reason": public_block_reason,
            "public_canary_decision": (public_canary or {}).get("public_canary_decision"),
            "public_canary_match": (public_canary or {}).get("public_canary_match"),
            "public_canary_reason": (public_canary or {}).get("public_canary_reason"),
            "relaxed_public_policy_decision": (relaxed_public_shadow or {}).get("relaxed_public_policy_decision"),
            "relaxed_public_policy_vs_current": (relaxed_public_shadow or {}).get("relaxed_public_policy_vs_current"),
            "relaxed_public_shadow_sent_dev": (relaxed_public_shadow or {}).get("relaxed_public_shadow_sent_dev"),
            "signal_update_v1": signal_update_v1,
            "edge_knowledge_shadow": edge_knowledge_shadow,
            "edge_optimizer_shadow": edge_optimizer_shadow,
            "edge_optimizer_active": edge_optimizer_active,
        },
    }


def _log_signal_decision(logger, event: str, decision) -> None:
    log_json(
        logger,
        event,
        symbol=decision.symbol,
        decision=decision.decision,
        direction=decision.direction,
        total_score=decision.total_score,
        source_engine=decision.source_engine,
        rejection_reasons=decision.rejection_reasons,
    )


def _log_signal_decision_comparison(logger, *, symbol: str, current, parallel, module_diagnostics: dict[str, dict[str, object]]) -> None:
    decision_details = module_diagnostics.get("decision_engine", {}).get("details", {})
    if not isinstance(decision_details, dict):
        decision_details = {}
    log_json(
        logger,
        "signal_decision_comparison",
        symbol=symbol,
        current_decision=current.decision,
        parallel_decision=parallel.decision,
        shadow_decision=decision_details.get("shadow_decision"),
        current_score=current.total_score,
        parallel_score=parallel.total_score,
        shadow_score=decision_details.get("shadow_score"),
        current_rejection_reasons=current.rejection_reasons,
        parallel_rejection_reasons=parallel.rejection_reasons,
        shadow_rejection_reasons=decision_details.get("shadow_rejection_reasons", []),
    )


def build_parallel_module_diagnostics(
    *,
    symbol: str,
    settings: Settings,
    notifier,
    analysis,
    evaluation,
    risk_plan,
) -> dict[str, dict[str, object]]:
    setup_type = _signal_setup_type(evaluation)
    modules = {
        "market_data": market_data_status(symbol, analysis.entry_snapshot, analysis.higher_snapshot),
        "trend": analyze_trend(analysis.entry_snapshot, analysis.higher_snapshot),
        "momentum": analyze_momentum(
            analysis.entry_snapshot,
            min_body_ratio=settings.min_body_ratio,
            direction=evaluation.decision if evaluation.decision != SignalDecision.NO_TRADE.value else _candidate_direction(analysis),
        ),
        "liquidity": analyze_liquidity(
            analysis.entry_snapshot,
            max_distance_to_liquidity_atr=settings.max_distance_to_liquidity_atr,
        ),
        "market_regime": analyze_market_regime(
            analysis.entry_snapshot,
            atr_min_threshold=settings.paper_trading_atr_min_threshold,
        ),
        "risk": analyze_risk(risk_plan, min_rr=settings.min_rr),
        "telegram": telegram_status(notifier),
        "signal_builder": build_signal_diagnostic(symbol, evaluation, risk_plan, setup_type=setup_type),
        "strategy_gate": analyze_strategy_gate(settings, analysis, evaluation),
    }
    modules["decision_engine"] = evaluate_parallel_decision(modules)
    modules["experimental_decision_engine"] = evaluate_experimental_decision(modules)
    return modules


def _paper_trace_shadow_call(service, operation: str, logger, *args, **kwargs):
    """Run optional shadow telemetry without changing the operational flow."""

    try:
        method = getattr(service, operation)
        return method(*args, **kwargs)
    except Exception as exc:
        error_code = str(
            getattr(exc, "code", f"PAPER_TRACE_{type(exc).__name__.upper()}")
        )[:100]
        isolate = getattr(service, "isolate", None)
        if callable(isolate):
            isolate(error_code)
        log_json(
            logger,
            "paper_trace_shadow_isolated",
            operation=operation,
            error_code=error_code,
        )
        return None


def run_market_scan(
    *,
    settings: Settings,
    market_data,
    scan_repo,
    signal_repo,
    notifier,
    diagnostics_store,
    metrics,
    paper_trading_store=None,
    paper_trace_service=None,
    relaxation_shadow_store=None,
    experimental_signal_store=None,
    shadow_signal_store=None,
    modular_signal_store=None,
    live_trading_store=None,
    pattern_memory_store=None,
    symbols: list[str] | None = None,
    dry_run: bool = False,
    runtime_identity: dict[str, object] | None = None,
) -> dict[str, object]:
    """Run the production scan while keeping the engine migration boundary explicit.

    LiquiditySweepMTFV1 is still the real engine and produces StrategyEvaluation.
    The evaluation is persisted and kept in the result for legacy compatibility.
    The operational contract inside this use case is SignalDecision, adapted from
    StrategyEvaluation and used for publish, paper-trading candidate creation and
    live-tracking candidate creation. Parallel/shadow decisions remain diagnostic.
    """
    started_at = _now_iso()
    effective_symbols = [symbol.strip().upper() for symbol in (symbols or settings.scan_symbols) if symbol.strip()]
    universe_validation = validate_symbol_universe(settings, market_data, effective_symbols)
    valid_symbols = [str(symbol) for symbol in universe_validation["valid_symbols"]]
    logger = logging.getLogger("trading_signals")
    scan_runtime_identity = runtime_identity or build_runtime_identity(
        root=Path.cwd(),
        settings=settings,
        strict=not dry_run,
    ).to_dict()
    for skipped in universe_validation["skipped_symbols"]:
        if isinstance(skipped, dict):
            log_json(
                logger,
                "symbol_skipped",
                symbol=skipped.get("symbol"),
                reason=skipped.get("reason"),
                provider=skipped.get("provider"),
            )
    fetch = market_data.get_ohlcv if hasattr(market_data, "get_ohlcv") else market_data.fetch_ohlcv
    pair_universe_filter = evaluate_pair_universe(
        symbols=valid_symbols,
        fetch_ohlcv=fetch,
        data_path=settings.data_storage_path,
        timeframe=settings.entry_timeframe,
        config=_pair_universe_filter_config(settings),
        provider=str(universe_validation.get("provider", getattr(market_data, "provider_name", "unknown"))),
    )
    _log_pair_universe_filter(logger, pair_universe_filter)
    if settings.pair_universe_filter_mode == "enforce_paper":
        valid_symbols = [str(symbol) for symbol in pair_universe_filter.get("passed_symbols", [])]
    scan_run = ScanRun(
        id=f"run_{uuid4().hex[:12]}",
        started_at=started_at,
        status="running",
        symbols_total=len(effective_symbols),
        symbols_processed=0,
        signals_emitted=0,
        signals_rejected=0,
        errors_count=0,
        config=effective_config(settings, effective_symbols),
        created_at=started_at,
    )
    scan_repo.save_scan_run(scan_run)
    strategy = LiquiditySweepMTFV1(settings)
    results: list[dict[str, object]] = []
    candidate_funnel = new_candidate_funnel_cycle(scan_run_id=scan_run.id, started_at=started_at)
    candidate_funnel_report: dict[str, object] | None = None

    for symbol in valid_symbols:
        try:
            analysis = analyze_symbol(market_data=market_data, settings=settings, scan_run_id=scan_run.id, symbol=symbol)
            if paper_trace_service is not None:
                _paper_trace_shadow_call(
                    paper_trace_service,
                    "advance_snapshot",
                    logger,
                    analysis.entry_snapshot,
                )
            paper_updates = []
            if settings.paper_trading_enabled and paper_trading_store is not None:
                paper_updates = paper_trading_store.update_open_trades_for_snapshot(
                    analysis.entry_snapshot,
                    updated_at=_now_iso(),
                )
            relaxation_shadow_updates = []
            if relaxation_shadow_store is not None:
                relaxation_shadow_updates = relaxation_shadow_store.update_open_trades_for_snapshot(
                    analysis.entry_snapshot,
                    updated_at=_now_iso(),
                )
            live_trade_updates = []
            if settings.live_trade_tracking_enabled and live_trading_store is not None:
                live_trade_updates = live_trading_store.update_open_trades_for_snapshot(
                    analysis.entry_snapshot,
                    updated_at=_now_iso(),
                    breakeven_enabled=settings.live_breakeven_alert_enabled,
                    breakeven_trigger_r=settings.live_breakeven_trigger_r,
                    partial_tp_enabled=settings.live_partial_tp_alert_enabled,
                    partial_tp_trigger_r=settings.live_partial_tp_trigger_r,
                )
                for event in live_trade_updates:
                    message = format_live_trade_event_for_telegram(
                        event,
                        partial_percentage=settings.live_partial_tp_percentage_suggestion,
                    )
                    if message:
                        notifier.publish(message, dry_run=dry_run)
                    public_message = format_public_live_trade_event_for_telegram(event)
                    if public_message:
                        send_public_signal(notifier, public_message, dry_run=dry_run)
            scan_repo.save_snapshot(analysis.entry_snapshot)
            scan_repo.save_snapshot(analysis.higher_snapshot)
            evaluation = strategy.evaluate(analysis, evaluation_id=f"eval_{uuid4().hex[:12]}", created_at=_now_iso())
            elite_profile_c = apply_elite_profile_c_dev_tag(
                evaluation,
                setup_type=_signal_setup_type(evaluation)
                if evaluation.decision != SignalDecision.NO_TRADE.value
                else (_candidate_setup_type(analysis, evaluation) or _signal_setup_type(evaluation)),
                direction=evaluation.decision if evaluation.decision != SignalDecision.NO_TRADE.value else _candidate_direction(analysis),
                higher_trend=analysis.higher_snapshot.trend,
            )
            if elite_profile_c.matched:
                log_json(
                    logger,
                    "elite_profile_c_dev_tag",
                    symbol=symbol,
                    direction=evaluation.decision if evaluation.decision != SignalDecision.NO_TRADE.value else _candidate_direction(analysis),
                    setup_type=elite_profile_c.setup_type,
                    score=evaluation.setup_score,
                    score_bucket=elite_profile_c.score_bucket,
                    htf_alignment=elite_profile_c.htf_alignment,
                    dev_note_enabled=settings.elite_profile_c_dev_note_enabled,
                )
                if settings.elite_profile_c_dev_note_enabled:
                    send_dev_message(
                        notifier,
                        format_elite_profile_c_dev_note(
                            symbol=symbol,
                            direction=evaluation.decision if evaluation.decision != SignalDecision.NO_TRADE.value else _candidate_direction(analysis),
                            score=evaluation.setup_score,
                        ),
                        dry_run=dry_run,
                    )
            increment_candidate_funnel(candidate_funnel, "raw_setups_evaluated")
            if evaluation.decision in {SignalDecision.LONG.value, SignalDecision.SHORT.value} or _candidate_setup_type(analysis, evaluation) is not None:
                increment_candidate_funnel(candidate_funnel, "candidates_created")
            risk_plan = None
            status = SignalStatus.REJECTED.value
            if evaluation.decision in {SignalDecision.LONG.value, SignalDecision.SHORT.value}:
                risk_plan = calculate_risk_plan(
                    risk_plan_id=f"risk_{uuid4().hex[:12]}",
                    evaluation_id=evaluation.id,
                    decision=evaluation.decision,
                    snapshot=analysis.entry_snapshot,
                    min_rr=settings.min_rr,
                    risk_per_trade=settings.risk_per_trade,
                    account_balance_reference=settings.account_balance_reference,
                    created_at=_now_iso(),
                )
                if risk_plan is not None:
                    scan_repo.save_risk_plan(risk_plan)
                    status = SignalStatus.VALID.value
                else:
                    evaluation.decision = SignalDecision.NO_TRADE.value
                    evaluation.rejection_reasons.append("risk_plan_failed")
                    evaluation.failed_filters.append("risk_plan_failed")
                    status = SignalStatus.REJECTED.value
            scan_repo.save_evaluation(evaluation)
            module_diagnostics = build_parallel_module_diagnostics(
                symbol=symbol,
                settings=settings,
                notifier=notifier,
                analysis=analysis,
                evaluation=evaluation,
                risk_plan=risk_plan,
            )
            logger = logging.getLogger("trading_signals")
            for module_name, module_result in module_diagnostics.items():
                log_module_diagnostic(
                    logger,
                    symbol=symbol,
                    module=module_name,
                    result=module_result,
                )
            current_signal_decision = build_signal_decision_from_strategy_evaluation(
                evaluation=evaluation,
                risk_plan=risk_plan,
                setup_type=_signal_setup_type(evaluation),
            )
            parallel_signal_decision = build_signal_decision_from_modules(
                symbol=symbol,
                module_results=module_diagnostics,
                entry_price=getattr(risk_plan, "entry", None),
                stop_loss=getattr(risk_plan, "stop_loss", None),
                take_profit=getattr(risk_plan, "take_profit", None),
            )
            selected_decision = select_signal_decision(
                use_modular_decision_engine=settings.use_modular_decision_engine,
                symbol=symbol,
                evaluation=evaluation,
                risk_plan=risk_plan,
                setup_type=_signal_setup_type(evaluation),
                module_diagnostics=module_diagnostics,
            )
            signal_decision = selected_decision.signal_decision
            _log_signal_decision(logger, "signal_decision_current", current_signal_decision)
            _log_signal_decision(logger, "signal_decision_operational", signal_decision)
            _log_signal_decision(logger, "signal_decision_parallel", parallel_signal_decision)
            log_json(
                logger,
                "decision_engine_selected",
                symbol=symbol,
                selected_engine=selected_decision.selected_engine,
                selected_decision=signal_decision.decision,
            )
            _log_signal_decision_comparison(
                logger,
                symbol=symbol,
                current=current_signal_decision,
                parallel=parallel_signal_decision,
                module_diagnostics=module_diagnostics,
            )
            experimental_signal_saved = False
            if experimental_signal_store is not None:
                experimental_row = build_experimental_signal_row(
                    timestamp=_now_iso(),
                    symbol=symbol,
                    snapshot=analysis.entry_snapshot,
                    module_diagnostics=module_diagnostics,
                )
                if experimental_row is not None:
                    experimental_signal_saved = experimental_signal_store.upsert_signal(experimental_row)
            shadow_signal_saved = False
            if shadow_signal_store is not None:
                shadow_row = build_shadow_signal_row(
                    timestamp=_now_iso(),
                    symbol=symbol,
                    snapshot=analysis.entry_snapshot,
                    current_decision=current_signal_decision,
                    module_diagnostics=module_diagnostics,
                )
                if shadow_row is not None:
                    shadow_signal_saved = shadow_signal_store.upsert_signal(shadow_row)
            modular_signal_saved = False
            if modular_signal_store is not None and signal_decision.source_engine == "modular_decision_engine":
                modular_row = build_modular_signal_row(
                    timestamp=_now_iso(),
                    symbol=symbol,
                    snapshot=analysis.entry_snapshot,
                    modular_decision=signal_decision,
                    legacy_decision=current_signal_decision,
                    module_diagnostics=module_diagnostics,
                )
                if modular_row is not None:
                    modular_signal_saved = modular_signal_store.upsert_signal(modular_row)

            signal_created_at = _now_iso()
            signal_accepted = evaluation.decision in {SignalDecision.LONG.value, SignalDecision.SHORT.value}
            signal_universe = TradeUniverse.ACCEPTED.value if signal_accepted else (
                TradeUniverse.SHADOW.value if experimental_signal_saved else TradeUniverse.REJECTED.value
            )
            signal_trace = metadata_from_identity(
                scan_runtime_identity,
                selected_engine=selected_decision.selected_engine,
                strategy_version=evaluation.strategy_version,
                experiment_id="none" if signal_accepted else ("shadow" if experimental_signal_saved else "unknown"),
            )
            signal = TradeSignal(
                id=f"sig_{uuid4().hex[:12]}",
                scan_run_id=scan_run.id,
                evaluation_id=evaluation.id,
                risk_plan_id=risk_plan.id if risk_plan else None,
                strategy_id=evaluation.strategy_id,
                strategy_version=evaluation.strategy_version,
                symbol=symbol,
                decision=evaluation.decision,
                status=status,
                dedupe_key=build_signal_dedupe_key(symbol, evaluation.decision, evaluation.strategy_id, evaluation.strategy_version, analysis.entry_snapshot),
                entry_timeframe=evaluation.entry_timeframe,
                higher_timeframe=evaluation.higher_timeframe,
                entry_snapshot_id=evaluation.entry_snapshot_id,
                higher_snapshot_id=evaluation.higher_snapshot_id,
                created_at=signal_created_at,
                accepted_at=signal_created_at if signal_accepted else None,
                universe=signal_universe,
                accepted=signal_accepted,
                git_commit_sha=str(signal_trace["git_commit_sha"]),
                config_hash=str(signal_trace["config_hash"]),
                runtime_flags=dict(signal_trace["runtime_flags"]),
                deployment_id=str(signal_trace["deployment_id"]),
                selected_engine=str(signal_trace["selected_engine"]),
                policy_version=str(signal_trace["policy_version"]),
                experiment_id=str(signal_trace["experiment_id"]),
            )
            signal_repo.save_signal(signal)
            deliveries = []
            relaxed_public_shadow = None
            public_published = False
            should_publish_decision = signal.decision in settings.publish_signal_decisions
            is_duplicate = signal_repo.has_published_dedupe_key(signal.dedupe_key)
            lifecycle = None
            setup_context = build_setup_context(
                snapshot=analysis.entry_snapshot,
                higher_trend=analysis.higher_snapshot.trend,
                risk_plan=risk_plan,
                direction=evaluation.decision if evaluation.decision != SignalDecision.NO_TRADE.value else _candidate_direction(analysis),
                max_distance_to_liquidity_atr=settings.max_distance_to_liquidity_atr,
                atr_min_threshold=settings.paper_trading_atr_min_threshold,
                max_spread_atr=settings.paper_trading_max_spread_atr,
            ).to_dict()
            setup_context.update(
                {
                    "liquidity_sweep": analysis.entry_snapshot.liquidity_sweep,
                    "market_structure": analysis.entry_snapshot.market_structure,
                    "penalties": _penalties_from_trace(evaluation),
                    "trend_entry": analysis.entry_snapshot.trend,
                    "trend_higher": analysis.higher_snapshot.trend,
                }
            )
            candidate_direction = (
                evaluation.decision if evaluation.decision != SignalDecision.NO_TRADE.value else _candidate_direction(analysis)
            )
            candidate_setup_type = (
                _signal_setup_type(evaluation)
                if evaluation.decision != SignalDecision.NO_TRADE.value
                else (_candidate_setup_type(analysis, evaluation) or _signal_setup_type(evaluation))
            )
            strategy_v2_1_htf_alignment_filter = None
            if settings.strategy_v2_1_htf_alignment_filter_enabled:
                status, strategy_v2_1_result = apply_strategy_v2_1_htf_alignment_filter(
                    evaluation=evaluation,
                    signal=signal,
                    status=status,
                    enabled=settings.strategy_v2_1_htf_alignment_filter_enabled,
                    mode=settings.strategy_v2_1_htf_alignment_filter_mode,
                    direction=candidate_direction,
                    higher_trend=analysis.higher_snapshot.trend,
                )
                strategy_v2_1_htf_alignment_filter = {
                    "strategy_v2_1_htf_alignment": strategy_v2_1_result.get("htf_alignment"),
                    "strategy_v2_1_would_block": strategy_v2_1_result.get("would_block"),
                    "strategy_v2_1_blocked": strategy_v2_1_result.get("blocked"),
                    "strategy_v2_1_mode": strategy_v2_1_result.get("mode"),
                    "strategy_v2_1_rejection_reason": strategy_v2_1_result.get("rejection_reason"),
                    **strategy_v2_1_result,
                }
                should_publish_decision = signal.decision in settings.publish_signal_decisions
                log_json(
                    logger,
                    "strategy_v2_1_htf_alignment_filter_evaluated",
                    symbol=symbol,
                    direction=candidate_direction,
                    setup_type=candidate_setup_type,
                    score=evaluation.setup_score,
                    htf_alignment=strategy_v2_1_result.get("htf_alignment"),
                    would_block=strategy_v2_1_result.get("would_block"),
                    blocked=strategy_v2_1_result.get("blocked"),
                    mode=strategy_v2_1_result.get("mode"),
                    reason=strategy_v2_1_result.get("reason"),
                )
                if strategy_v2_1_result.get("mode") == "shadow":
                    log_json(
                        logger,
                        "strategy_v2_1_htf_alignment_shadow",
                        symbol=symbol,
                        direction=candidate_direction,
                        setup_type=candidate_setup_type,
                        score=evaluation.setup_score,
                        htf_alignment=strategy_v2_1_result.get("htf_alignment"),
                        would_block=strategy_v2_1_result.get("would_block"),
                        reason=strategy_v2_1_result.get("reason"),
                    )
                if strategy_v2_1_result.get("blocked"):
                    log_json(
                        logger,
                        "strategy_v2_1_htf_alignment_blocked",
                        symbol=symbol,
                        direction=candidate_direction,
                        setup_type=candidate_setup_type,
                        score=evaluation.setup_score,
                        htf_alignment=strategy_v2_1_result.get("htf_alignment"),
                        reason=strategy_v2_1_result.get("reason"),
                    )
                    scan_repo.save_evaluation(evaluation)
                    signal_repo.save_signal(signal)
            elite_subprofile = apply_elite_subprofile_dev_tag(
                evaluation,
                setup_type=candidate_setup_type,
                direction=candidate_direction,
                higher_trend=analysis.higher_snapshot.trend,
                session=setup_context.get("session"),
                market_regime=setup_context.get("market_regime"),
                trade_location=setup_context.get("trade_location"),
            )
            if elite_subprofile.matched:
                log_json(
                    logger,
                    "elite_subprofile_dev_tag",
                    symbol=symbol,
                    profiles=list(elite_subprofile.matched_profiles),
                    direction=elite_subprofile.direction,
                    setup_type=elite_subprofile.setup_type,
                    score=evaluation.setup_score,
                    score_bucket=elite_subprofile.score_bucket,
                    htf_alignment=elite_subprofile.htf_alignment,
                    session=elite_subprofile.session,
                    market_regime=elite_subprofile.market_regime,
                    trade_location=elite_subprofile.trade_location,
                    dev_note_enabled=settings.elite_subprofile_dev_note_enabled,
                )
                if settings.elite_subprofile_dev_note_enabled:
                    send_dev_message(
                        notifier,
                        format_elite_subprofile_dev_note(
                            symbol=symbol,
                            profiles=elite_subprofile.matched_profiles,
                            direction=elite_subprofile.direction,
                            score=evaluation.setup_score,
                            session=elite_subprofile.session,
                            market_regime=elite_subprofile.market_regime,
                            trade_location=elite_subprofile.trade_location,
                            setup_type=elite_subprofile.setup_type,
                        ),
                        dry_run=dry_run,
                    )
            edge_knowledge_shadow = evaluate_edge_knowledge_shadow_v1(
                symbol=symbol,
                analysis=analysis,
                evaluation=evaluation,
                risk_plan=risk_plan,
                setup_context=setup_context,
                signal_decision=signal_decision,
                setup_type=candidate_setup_type,
                direction=candidate_direction,
            )
            log_json(
                logger,
                "edge_knowledge_shadow_analysis",
                symbol=symbol,
                direction=candidate_direction,
                setup_type=candidate_setup_type,
                current_decision=edge_knowledge_shadow.current_decision,
                current_score=edge_knowledge_shadow.current_score,
                ekb_bonus=edge_knowledge_shadow.ekb_bonus,
                ekb_confidence=edge_knowledge_shadow.ekb_confidence,
                context=edge_knowledge_shadow.context,
                matched_edges_count=edge_knowledge_shadow.matched_edges_count,
                top_matched_edges=edge_knowledge_shadow.top_matched_edges,
                hypothetical_score=edge_knowledge_shadow.hypothetical_score,
                hypothetical_bias=edge_knowledge_shadow.hypothetical_bias,
            )
            log_json(
                logger,
                "edge_knowledge_shadow_decision",
                symbol=symbol,
                direction=candidate_direction,
                setup_type=candidate_setup_type,
                current_decision=edge_knowledge_shadow.current_decision,
                current_score=edge_knowledge_shadow.current_score,
                ekb_bonus=edge_knowledge_shadow.ekb_bonus,
                ekb_confidence=edge_knowledge_shadow.ekb_confidence,
                matched_edges_count=edge_knowledge_shadow.matched_edges_count,
                top_matched_edges=edge_knowledge_shadow.top_matched_edges,
                hypothetical_score=edge_knowledge_shadow.hypothetical_score,
                hypothetical_bias=edge_knowledge_shadow.hypothetical_bias,
                rejection_reasons=list(evaluation.rejection_reasons),
                final_decision=signal_decision.decision,
            )
            if settings.edge_knowledge_shadow_dev_note_enabled:
                send_dev_message(
                    notifier,
                    format_edge_knowledge_shadow_dev_note(edge_knowledge_shadow),
                    dry_run=dry_run,
                )
            edge_optimizer_shadow = evaluate_edge_optimizer_shadow_v1(
                symbol=symbol,
                analysis=analysis,
                evaluation=evaluation,
                risk_plan=risk_plan,
                setup_context=setup_context,
                signal_decision=signal_decision,
                setup_type=candidate_setup_type,
                direction=candidate_direction,
            )
            log_json(
                logger,
                "edge_optimizer_shadow_analysis",
                symbol=symbol,
                direction=candidate_direction,
                setup_type=candidate_setup_type,
                current_decision=edge_optimizer_shadow.current_decision,
                current_score=edge_optimizer_shadow.current_score,
                optimizer_adjustment=edge_optimizer_shadow.optimizer_adjustment,
                optimizer_confidence=edge_optimizer_shadow.optimizer_confidence,
                context=edge_optimizer_shadow.context,
                matched_edges_count=edge_optimizer_shadow.matched_edges_count,
                matched_positive_edges=edge_optimizer_shadow.matched_positive_edges,
                matched_negative_edges=edge_optimizer_shadow.matched_negative_edges,
                top_edges=edge_optimizer_shadow.top_edges,
                hypothetical_score=edge_optimizer_shadow.hypothetical_score,
                hypothetical_bias=edge_optimizer_shadow.hypothetical_bias,
                conflict_reduced=edge_optimizer_shadow.conflict_reduced,
                caps_applied=edge_optimizer_shadow.caps_applied,
            )
            log_json(
                logger,
                "edge_optimizer_shadow_decision",
                symbol=symbol,
                direction=candidate_direction,
                setup_type=candidate_setup_type,
                current_decision=edge_optimizer_shadow.current_decision,
                current_score=edge_optimizer_shadow.current_score,
                optimizer_adjustment=edge_optimizer_shadow.optimizer_adjustment,
                optimizer_confidence=edge_optimizer_shadow.optimizer_confidence,
                matched_edges_count=edge_optimizer_shadow.matched_edges_count,
                matched_positive_edges=edge_optimizer_shadow.matched_positive_edges,
                matched_negative_edges=edge_optimizer_shadow.matched_negative_edges,
                top_edges=edge_optimizer_shadow.top_edges,
                hypothetical_score=edge_optimizer_shadow.hypothetical_score,
                hypothetical_bias=edge_optimizer_shadow.hypothetical_bias,
                rejection_reasons=list(evaluation.rejection_reasons),
                final_decision=signal_decision.decision,
                conflict_reduced=edge_optimizer_shadow.conflict_reduced,
                caps_applied=edge_optimizer_shadow.caps_applied,
            )
            edge_optimizer_active = apply_edge_optimizer_active_v1(
                evaluation=evaluation,
                signal_decision=signal_decision,
                edge_optimizer_shadow=edge_optimizer_shadow,
                enabled=settings.edge_optimizer_active_enabled,
                max_adjustment=settings.edge_optimizer_active_max_adjustment,
                min_confidence=settings.edge_optimizer_active_min_confidence,
            )
            if settings.edge_optimizer_active_enabled:
                log_json(
                    logger,
                    "edge_optimizer_active_applied",
                    symbol=symbol,
                    direction=candidate_direction,
                    setup_type=candidate_setup_type,
                    applied=edge_optimizer_active.applied,
                    original_score=edge_optimizer_active.original_score,
                    active_adjustment=edge_optimizer_active.active_adjustment,
                    adjusted_score=edge_optimizer_active.adjusted_score,
                    confidence=edge_optimizer_active.confidence,
                    min_confidence=edge_optimizer_active.min_confidence,
                    matched_edges_count=edge_optimizer_active.matched_edges_count,
                    reasons=edge_optimizer_active.reasons,
                )
            current_public_policy = evaluate_public_safety_policy(
                signal=signal,
                evaluation_or_decision=signal_decision,
                setup_context=setup_context,
                public_short_canary_config=_public_short_canary_config(settings),
            )
            public_route_reason = public_routing_rejection_reason(signal, signal_decision, setup_context)
            evaluation.decision_trace.extend(
                [
                    f"public_block_against_htf={str(public_route_reason == 'public_block_against_htf').lower()}",
                    f"public_block_bad_breakout_context={str(public_route_reason == 'public_block_bad_breakout_context').lower()}",
                ]
            )
            scan_repo.save_evaluation(evaluation)
            kill_switch_status = evaluate_kill_switch(
                settings.data_storage_path,
                enabled=settings.kill_switch_enabled,
                max_daily_loss_r=settings.max_daily_loss_r,
                max_consecutive_losses=settings.max_consecutive_losses,
                max_weekly_drawdown_r=settings.max_weekly_drawdown_r,
                cooldown_hours=settings.kill_switch_cooldown_hours,
                consecutive_loss_reset_hours=settings.consecutive_loss_reset_hours,
            )
            # Manual-latch pause (scripts/run_kill_switch_monitor.py + resume_trading.py):
            # unlike kill_switch_status above (which self-resumes once its rolling loss
            # window ages out), this only clears when a human runs resume_trading.py.
            trading_paused_state = is_trading_paused(settings.data_storage_path / "runtime" / "trading_paused.json")
            pattern_memory = None
            performance_gate = None
            pattern_record = None
            pattern_risk_plan = None
            if pattern_memory_store is not None:
                pattern_history = pattern_memory_store.list_records(limit=1000)
                pattern_risk_plan = risk_plan
                pattern_record = build_pattern_record(
                    timestamp=_now_iso(),
                    symbol=symbol,
                    direction=evaluation.decision if evaluation.decision != SignalDecision.NO_TRADE.value else _candidate_direction(analysis),
                    setup_type=_signal_setup_type(evaluation) if evaluation.decision != SignalDecision.NO_TRADE.value else (_candidate_setup_type(analysis, evaluation) or "NO_SIGNAL"),
                    score=float(evaluation.setup_score),
                    setup_context=setup_context,
                    htf_trend=analysis.higher_snapshot.trend,
                    ltf_trend=analysis.entry_snapshot.trend,
                    timeframe_alignment=analysis.entry_snapshot.trend == analysis.higher_snapshot.trend,
                    penalties=_penalties_from_trace(evaluation),
                    blocking_reasons=list(evaluation.rejection_reasons),
                    risk_plan=pattern_risk_plan,
                    final_status="pending",
                    outcome=None,
                    r_result=None,
                )
                pattern_memory = _build_performance_intelligence_with_optional_edge_memory(
                    pattern_record=pattern_record,
                    pattern_history=pattern_history,
                    edge_memory_data_path=settings.data_storage_path,
                )
                performance_gate = evaluate_performance_gate(pattern_memory)
                pattern_memory["performance_gate"] = performance_gate
                pattern_memory["edge_knowledge_shadow"] = edge_knowledge_shadow.to_dict()
                pattern_memory["edge_optimizer_shadow"] = edge_optimizer_shadow.to_dict()
                pattern_memory["edge_optimizer_active"] = edge_optimizer_active.to_dict()
                pattern_memory["strategy_v2_1_htf_alignment_filter"] = strategy_v2_1_htf_alignment_filter
                log_performance_intelligence(
                    logger,
                    symbol=symbol,
                    pattern_record=pattern_record,
                    performance_intelligence=pattern_memory,
                )
                log_json(
                    logger,
                    "performance_gate_soft",
                    symbol=symbol,
                    direction=pattern_record.get("direction"),
                    setup_type=pattern_record.get("setup_type"),
                    action=performance_gate["action"],
                    would_block=performance_gate["would_block"],
                    would_prioritize=performance_gate["would_prioritize"],
                    confidence=performance_gate["confidence"],
                    reasons=performance_gate["reasons"],
                    risks=performance_gate["risks"],
                    scores=performance_gate["scores"],
                )
            relaxation_shadow_v1 = None
            if (
                status == SignalStatus.VALID.value
                and risk_plan is not None
                and relaxation_shadow_store is not None
                and not bool(current_public_policy.get("public_allowed"))
            ):
                relaxation_shadow_v1 = _observe_relaxation_shadow_v1(
                    logger=logger,
                    notifier=notifier,
                    signal=signal,
                    evaluation=signal_decision,
                    risk_plan=risk_plan,
                    analysis=analysis,
                    setup_context=setup_context,
                    current_policy=current_public_policy,
                    store=relaxation_shadow_store,
                    expires_after_candles=settings.paper_trading_timeout_candles,
                    dry_run=dry_run,
                    stage="pre_publish_policy",
                )
                record_relaxation_shadow_observation(candidate_funnel, relaxation_shadow_v1)
            publish_filter_reason = None
            if status == SignalStatus.VALID.value and should_publish_decision:
                publish_filter_reason = publish_filter_rejection_reason(
                    settings=settings,
                    symbol=symbol,
                    direction=evaluation.decision,
                    setup_context=setup_context,
                    opened_at=signal.created_at,
                    evaluation_or_decision=signal_decision,
                )
                if publish_filter_reason is not None:
                    if publish_filter_reason == "bullish_sweep_blocked":
                        evaluation.decision_trace.append("bullish_sweep_blocked=true")
                        log_json(
                            logger,
                            "bullish_sweep_blocked",
                            symbol=symbol,
                            direction=evaluation.decision,
                            setup_context=setup_context,
                        )
                    if publish_filter_reason == "against_htf_breakout_blocked":
                        evaluation.decision_trace.append("against_htf_breakout_blocked=true")
                        log_json(
                            logger,
                            "against_htf_breakout_blocked",
                            symbol=symbol,
                            direction=evaluation.decision,
                            setup_context=setup_context,
                        )
                    log_json(
                        logger,
                        "publish_signal_blocked",
                        symbol=symbol,
                        direction=evaluation.decision,
                        reason=publish_filter_reason,
                        setup_context=setup_context,
                    )
            should_publish_after_filters = should_publish_decision and publish_filter_reason is None
            public_meta_filter_reason = None
            public_block_reason = None
            if status == SignalStatus.VALID.value and should_publish_after_filters:
                if bool(kill_switch_status.get("kill_switch_active")):
                    kill_reason = str(kill_switch_status.get("kill_switch_reason") or "kill_switch_active")
                    public_block_reason = f"kill_switch:{kill_reason}"
                    log_json(
                        logger,
                        "kill_switch_blocked_public_signal",
                        symbol=symbol,
                        direction=evaluation.decision,
                        reason=kill_reason,
                        daily_realized_r=kill_switch_status.get("daily_realized_r"),
                        weekly_realized_r=kill_switch_status.get("weekly_realized_r"),
                        consecutive_losses=kill_switch_status.get("consecutive_losses"),
                        cooldown_until=kill_switch_status.get("cooldown_until"),
                    )
                else:
                    public_meta_filter_reason = meta_decision_public_filter_reason(settings, pattern_memory)
                    public_block_reason = public_meta_filter_reason
            if public_meta_filter_reason is not None:
                log_json(
                    logger,
                    "meta_decision_filter_blocked",
                    symbol=symbol,
                        direction=evaluation.decision,
                        reason=public_meta_filter_reason,
                        meta_decision=(pattern_memory or {}).get("meta_decision") if isinstance(pattern_memory, dict) else None,
                        trade_quality=(pattern_memory or {}).get("trade_quality") if isinstance(pattern_memory, dict) else None,
                    )
            if status == SignalStatus.VALID.value and should_publish_after_filters and not is_duplicate:
                lifecycle = classify_signal_lifecycle(
                    signal_repo=signal_repo,
                    symbol=symbol,
                    direction=evaluation.decision,
                    entry_snapshot=analysis.entry_snapshot,
                    evaluation=evaluation,
                )
                signal.signal_type = lifecycle.signal_type
                signal.lifecycle_reason = lifecycle.reason
                signal_repo.save_signal(signal)
            signal_update_v1 = None
            if status == SignalStatus.VALID.value:
                signal_update_v1 = _observe_signal_update_v1(
                    logger=logger,
                    notifier=notifier,
                    settings=settings,
                    signal_repo=signal_repo,
                    signal=signal,
                    evaluation=evaluation,
                    risk_plan=risk_plan,
                    entry_snapshot=analysis.entry_snapshot,
                    setup_context=setup_context,
                    is_duplicate=is_duplicate,
                    lifecycle=lifecycle,
                    dry_run=dry_run,
                )
                _observe_active_signal_cleanup_shadow_v1(
                    logger=logger,
                    signal_repo=signal_repo,
                    signal=signal,
                    is_duplicate=is_duplicate,
                    lifecycle=lifecycle,
                )
            if (
                relaxation_shadow_v1 is None
                and status == SignalStatus.VALID.value
                and risk_plan is not None
                and relaxation_shadow_store is not None
                and not (
                    should_publish_after_filters
                    and not is_duplicate
                    and lifecycle is not None
                    and lifecycle.should_publish
                )
            ):
                post_policy_reasons = _pre_publishability_block_reasons(
                    should_publish_decision=should_publish_decision,
                    publish_filter_reason=publish_filter_reason,
                    is_duplicate=is_duplicate,
                    lifecycle=lifecycle,
                    current_public_policy=current_public_policy,
                )
                if post_policy_reasons:
                    relaxation_shadow_v1 = _observe_relaxation_shadow_v1(
                        logger=logger,
                        notifier=notifier,
                        signal=signal,
                        evaluation=signal_decision,
                        risk_plan=risk_plan,
                        analysis=analysis,
                        setup_context=setup_context,
                        current_policy={**current_public_policy, "block_reasons": post_policy_reasons},
                        store=relaxation_shadow_store,
                        expires_after_candles=settings.paper_trading_timeout_candles,
                        dry_run=dry_run,
                        stage="pre_publishability_gate",
                    )
                    record_relaxation_shadow_observation(candidate_funnel, relaxation_shadow_v1)
            protection_engine = evaluate_protection_engine(
                data_path=settings.data_storage_path,
                symbol=symbol,
                direction=evaluation.decision if evaluation.decision != SignalDecision.NO_TRADE.value else _candidate_direction(analysis),
                setup_type=_signal_setup_type(evaluation) if evaluation.decision != SignalDecision.NO_TRADE.value else (_candidate_setup_type(analysis, evaluation) or "NO_SIGNAL"),
                setup_context=setup_context,
                config=_protection_engine_config(settings),
            )
            _log_protection_diagnostics(logger, symbol=symbol, protection=protection_engine)
            public_canary = evaluate_public_short_canary(
                signal=signal,
                evaluation_or_decision=signal_decision,
                setup_context=setup_context,
                config=_public_short_canary_config(settings),
            )
            signal_publishable = (
                status == SignalStatus.VALID.value
                and should_publish_after_filters
                and not is_duplicate
                and lifecycle
                and lifecycle.should_publish
            )
            if signal_publishable and trading_paused_state.get("paused"):
                increment_candidate_funnel(
                    candidate_funnel,
                    "rejected_by_trading_paused",
                    reason="trading_paused",
                    reason_stage="publishing",
                )
                evaluation.rejection_reasons.append("trading_paused_no_publish")
            elif signal_publishable:
                increment_candidate_funnel(candidate_funnel, "candidates_reaching_publish_signal")
                deliveries = publish_signal(
                    signal_repo,
                    notifier,
                    signal,
                    analysis.entry_snapshot,
                    analysis.higher_snapshot,
                    signal_decision,
                    risk_plan,
                    dry_run=dry_run,
                    signal_type=lifecycle.signal_type,
                    setup_context=setup_context,
                    public_block_reason=public_block_reason,
                    public_short_canary_config=_public_short_canary_config(settings),
                    relaxation_shadow_store=relaxation_shadow_store if relaxation_shadow_v1 is None else None,
                    relaxation_shadow_expires_after_candles=settings.paper_trading_timeout_candles,
                )
                relaxed_public_shadow = _relaxed_public_shadow_from_deliveries(deliveries)
                if any(item.status == "sent" for item in deliveries):
                    increment_candidate_funnel(candidate_funnel, "published_signals")
                    public_published = any(item.channel == "telegram_public" and item.status == "sent" for item in deliveries)
                    signal.public_published = public_published
                    signal.public_published_at = _now_iso() if public_published else None
                    signal.status = SignalStatus.PUBLISHED.value
                    signal.published_at = _now_iso()
                    signal.updated_at = signal.published_at
                    apply_active_signal_expiration_v1(
                        signal,
                        enabled=settings.active_signal_expiration_enabled,
                        default_expiration_hours=settings.active_signal_default_expiration_hours,
                    )
                    signal_repo.save_signal(signal)
                    if settings.live_trade_tracking_enabled and live_trading_store is not None and risk_plan is not None:
                        live_candidate = build_live_candidate_from_decision(
                            signal=signal,
                            setup_type=_signal_setup_type(evaluation),
                            evaluation_or_decision=signal_decision,
                            risk_plan=risk_plan,
                            setup_context=setup_context,
                            public_published=public_published,
                        )
                        live_trading_store.upsert_candidate(live_candidate)
                    scan_run.signals_emitted += 1
                    metrics.increment("signals_emitted_total")
            elif status == SignalStatus.VALID.value:
                lifecycle_reason = _funnel_publishability_reason(
                    should_publish_decision=should_publish_decision,
                    publish_filter_reason=publish_filter_reason,
                    is_duplicate=is_duplicate,
                    lifecycle=lifecycle,
                    public_block_reason=public_block_reason,
                )
                if lifecycle_reason:
                    increment_candidate_funnel(
                        candidate_funnel,
                        "rejected_by_lifecycle_publishability",
                        reason=lifecycle_reason,
                        reason_stage="lifecycle_publishability",
                    )
                if not should_publish_decision:
                    evaluation.rejection_reasons.append("publish_decision_filtered")
                if publish_filter_reason is not None:
                    evaluation.rejection_reasons.append(publish_filter_reason)
                if is_duplicate:
                    evaluation.rejection_reasons.append("duplicate_signal_suppressed")
                if lifecycle is not None and not lifecycle.should_publish:
                    evaluation.rejection_reasons.append(lifecycle.reason)
            else:
                scan_run.signals_rejected += 1
                metrics.increment("signals_rejected_total")

            high_score_rejected = _high_score_rejected_payload(
                symbol=symbol,
                analysis=analysis,
                evaluation=evaluation,
                signal=signal,
                status=status,
                should_publish_decision=should_publish_decision,
                is_duplicate=is_duplicate,
                setup_context=setup_context,
                risk_plan=risk_plan,
                publish_filter_reason=publish_filter_reason,
                lifecycle=lifecycle,
            )
            _log_high_score_rejected(high_score_rejected)
            candidate_rejected = _candidate_rejected_payload(
                symbol=symbol,
                analysis=analysis,
                evaluation=evaluation,
            )
            if signal.decision == SignalDecision.NO_TRADE.value and candidate_rejected is not None:
                record_candidate_rejection(
                    candidate_funnel,
                    rejection_reasons=evaluation.rejection_reasons,
                    failed_filters=evaluation.failed_filters,
                    fallback_reason=str(candidate_rejected.get("rejection_reason", "unknown")),
                )
            paper_trade_created = False
            paper_candidate_detected = False
            paper_rejection = None
            if settings.paper_trading_enabled and paper_trading_store is not None and not trading_paused_state.get("paused"):
                paper_tradeable, paper_tradeable_reason = paper_market_is_tradeable(
                    analysis.entry_snapshot,
                    atr_min_threshold=settings.paper_trading_atr_min_threshold,
                    max_spread_atr=settings.paper_trading_max_spread_atr,
                )
                if risk_plan is not None and evaluation.decision in {SignalDecision.LONG.value, SignalDecision.SHORT.value}:
                    paper_candidate_detected = True
                    rr_tp1, rr_tp2 = _risk_reward_values(risk_plan)
                    paper_candidate = build_paper_candidate_from_decision(
                        symbol=symbol,
                        direction=evaluation.decision,
                        setup_type=_signal_setup_type(evaluation),
                        evaluation_or_decision=signal_decision,
                        risk_plan=risk_plan,
                        opened_at=_now_iso(),
                        source_key=signal.dedupe_key,
                        snapshot=analysis.entry_snapshot,
                        higher_trend=analysis.higher_snapshot.trend,
                        entry_or_rejection_reason=paper_tradeable_reason,
                        expires_after_candles=settings.paper_trading_timeout_candles,
                        setup_context=setup_context,
                        trace={
                            **metadata_from_identity(
                                scan_runtime_identity,
                                selected_engine=selected_decision.selected_engine,
                                strategy_version=evaluation.strategy_version,
                            ),
                            "public_published": public_published,
                            "published_at": _now_iso() if public_published else "",
                        },
                        universe=TradeUniverse.ACCEPTED,
                    )
                    if paper_tradeable and paper_candidate is not None and paper_candidate.risk_reward_tp2 >= settings.paper_trading_min_rr:
                        paper_trade_created = paper_trading_store.upsert_candidate(paper_candidate)
                        if paper_trade_created and paper_trace_service is not None:
                            _paper_trace_shadow_call(
                                paper_trace_service,
                                "observe_signal",
                                logger,
                                signal=signal,
                                risk_plan=risk_plan,
                                evaluation=evaluation,
                                entry_snapshot=analysis.entry_snapshot,
                                higher_snapshot=analysis.higher_snapshot,
                                setup_type=_signal_setup_type(evaluation),
                                settings=settings,
                                runtime_identity=scan_runtime_identity,
                                accepted=True,
                            )
                    if not paper_trade_created:
                        if paper_level_label(evaluation.setup_score) == "BELOW_LOW":
                            reason = "paper_rejected_below_low"
                        elif not paper_tradeable:
                            reason = paper_tradeable_reason
                        elif paper_candidate is None:
                            reason = "paper_rejected_invalid_candidate_or_rr"
                        elif not paper_trade_created:
                            reason = "paper_rejected_duplicate"
                        else:
                            reason = "paper_rejected_unknown"
                        paper_rejection = build_paper_rejection_diagnostic(
                            symbol=symbol,
                            score=evaluation.setup_score,
                            snapshot=analysis.entry_snapshot,
                            atr_min_threshold=settings.paper_trading_atr_min_threshold,
                            max_spread_atr=settings.paper_trading_max_spread_atr,
                            rr_tp1=rr_tp1,
                            rr_tp2=rr_tp2,
                            rejection_reason=reason,
                            setup_context=setup_context,
                        )
                elif candidate_rejected is not None:
                    paper_candidate_detected = True
                    candidate_score = float(candidate_rejected.get("setup_score_final", 0.0))
                    if candidate_score < settings.paper_trading_strong_candidate_min_score:
                        paper_rejection = build_paper_rejection_diagnostic(
                            symbol=symbol,
                            score=evaluation.setup_score,
                            snapshot=analysis.entry_snapshot,
                            atr_min_threshold=settings.paper_trading_atr_min_threshold,
                            max_spread_atr=settings.paper_trading_max_spread_atr,
                            rr_tp1=None,
                            rr_tp2=None,
                            rejection_reason="paper_rejected_below_low",
                            setup_context=setup_context,
                        )
                    else:
                        candidate_risk_plan = calculate_risk_plan(
                            risk_plan_id=f"paper_risk_{uuid4().hex[:12]}",
                            evaluation_id=evaluation.id,
                            decision=str(candidate_rejected["direction"]),
                            snapshot=analysis.entry_snapshot,
                            min_rr=settings.paper_trading_min_rr,
                            risk_per_trade=settings.risk_per_trade,
                            account_balance_reference=settings.account_balance_reference,
                            created_at=_now_iso(),
                        )
                        rr_tp1, rr_tp2 = _risk_reward_values(candidate_risk_plan)
                        candidate_setup_context = build_setup_context(
                            snapshot=analysis.entry_snapshot,
                            higher_trend=analysis.higher_snapshot.trend,
                            risk_plan=candidate_risk_plan,
                            direction=str(candidate_rejected["direction"]),
                            max_distance_to_liquidity_atr=settings.max_distance_to_liquidity_atr,
                            atr_min_threshold=settings.paper_trading_atr_min_threshold,
                            max_spread_atr=settings.paper_trading_max_spread_atr,
                        ).to_dict()
                        candidate_setup_context.update(
                            {
                                "liquidity_sweep": analysis.entry_snapshot.liquidity_sweep,
                                "market_structure": analysis.entry_snapshot.market_structure,
                                "penalties": _penalties_from_trace(evaluation),
                            }
                        )
                        if candidate_risk_plan is not None:
                            paper_candidate = build_paper_candidate_from_decision(
                                symbol=symbol,
                                direction=str(candidate_rejected["direction"]),
                                setup_type=str(candidate_rejected["setup_type"]),
                                evaluation_or_decision=signal_decision,
                                risk_plan=candidate_risk_plan,
                                opened_at=_now_iso(),
                                source_key=f"{signal.dedupe_key}|candidate",
                                snapshot=analysis.entry_snapshot,
                                higher_trend=analysis.higher_snapshot.trend,
                                entry_or_rejection_reason=str(candidate_rejected.get("rejection_reason", paper_tradeable_reason)),
                                expires_after_candles=settings.paper_trading_timeout_candles,
                                setup_context=candidate_setup_context,
                                trace={
                                    **metadata_from_identity(
                                        scan_runtime_identity,
                                        selected_engine=selected_decision.selected_engine,
                                        strategy_version=evaluation.strategy_version,
                                        experiment_id="rejected_candidate_counterfactual",
                                    ),
                                },
                                universe=TradeUniverse.REJECTED,
                            )
                            if paper_tradeable and paper_candidate is not None and paper_candidate.risk_reward_tp2 >= settings.paper_trading_min_rr:
                                paper_trade_created = paper_trading_store.upsert_candidate(paper_candidate)
                        if not paper_trade_created:
                            if candidate_risk_plan is None:
                                reason = "paper_rejected_risk_plan_failed"
                            elif not paper_tradeable:
                                reason = paper_tradeable_reason
                            elif paper_candidate is None:
                                reason = "paper_rejected_invalid_candidate_or_rr"
                            else:
                                reason = "paper_rejected_duplicate"
                            paper_rejection = build_paper_rejection_diagnostic(
                                symbol=symbol,
                                score=evaluation.setup_score,
                                snapshot=analysis.entry_snapshot,
                                atr_min_threshold=settings.paper_trading_atr_min_threshold,
                                max_spread_atr=settings.paper_trading_max_spread_atr,
                                rr_tp1=rr_tp1,
                                rr_tp2=rr_tp2,
                                rejection_reason=reason,
                                setup_context=candidate_setup_context,
                            )
            append_signal_log(
                _signal_activity_entry(
                    timestamp=_now_iso(),
                    symbol=symbol,
                    analysis=analysis,
                    evaluation=evaluation,
                    risk_plan=risk_plan,
                    signal=signal,
                    signal_decision=signal_decision,
                    selected_engine=selected_decision.selected_engine,
                    setup_context=setup_context,
                    module_diagnostics=module_diagnostics,
                    paper_trade_created=paper_trade_created,
                    experimental_signal_saved=experimental_signal_saved,
                    publish_filter_reason=publish_filter_reason,
                    paper_rejection=paper_rejection,
                    public_published=public_published,
                    public_block_reason=public_block_reason,
                    public_canary=public_canary,
                    relaxed_public_shadow=relaxed_public_shadow,
                    signal_update_v1=signal_update_v1,
                    edge_knowledge_shadow=edge_knowledge_shadow.to_dict(),
                    edge_optimizer_shadow=edge_optimizer_shadow.to_dict(),
                    edge_optimizer_active=edge_optimizer_active.to_dict(),
                    strategy_v2_1_htf_alignment_filter=strategy_v2_1_htf_alignment_filter,
                    runtime_metadata=metadata_from_identity(
                        scan_runtime_identity,
                        selected_engine=selected_decision.selected_engine,
                        strategy_version=evaluation.strategy_version,
                        experiment_id="none" if evaluation.decision in {SignalDecision.LONG.value, SignalDecision.SHORT.value} else "unknown",
                    ),
                )
            )
            multi_agent_shadow_decision = None
            if pattern_memory_store is not None:
                if pattern_risk_plan is None and candidate_rejected is not None:
                    pattern_direction = str(candidate_rejected.get("direction", _candidate_direction(analysis)))
                    pattern_risk_plan = calculate_risk_plan(
                        risk_plan_id=f"pattern_risk_{uuid4().hex[:12]}",
                        evaluation_id=evaluation.id,
                        decision=pattern_direction,
                        snapshot=analysis.entry_snapshot,
                        min_rr=settings.min_rr,
                        risk_per_trade=settings.risk_per_trade,
                        account_balance_reference=settings.account_balance_reference,
                        created_at=_now_iso(),
                    )
                if pattern_record is not None:
                    pattern_record["entry"] = getattr(pattern_risk_plan, "entry", None)
                    pattern_record["stop_loss"] = getattr(pattern_risk_plan, "stop_loss", None)
                    pattern_record["take_profit"] = getattr(pattern_risk_plan, "take_profit", None)
                    pattern_record["rr"] = getattr(pattern_risk_plan, "risk_reward", None)
                    pattern_record["final_status"] = _pattern_final_status(
                        signal=signal,
                        high_score_rejected=high_score_rejected,
                        paper_trade_created=paper_trade_created,
                    )
                    pattern_record["outcome"] = "open" if signal.status == SignalStatus.PUBLISHED.value or paper_trade_created else None
                multi_agent_shadow_decision = _multi_agent_shadow_decision(
                    setup_context=setup_context,
                    evaluation=evaluation,
                    analysis=analysis,
                    risk_plan=pattern_risk_plan,
                    performance_gate=performance_gate,
                )
                pattern_memory["multi_agent_shadow_decision"] = multi_agent_shadow_decision
                log_json(
                    logger,
                    "multi_agent_shadow_decision",
                    symbol=symbol,
                    direction=pattern_record.get("direction"),
                    setup_type=pattern_record.get("setup_type"),
                    consensus_action=multi_agent_shadow_decision["consensus_action"],
                    agreement_score=multi_agent_shadow_decision["agreement_score"],
                    average_score=multi_agent_shadow_decision.get("average_score"),
                    disagreements=multi_agent_shadow_decision["disagreements"],
                    votes=multi_agent_shadow_decision["votes"],
                )
                if pattern_record is not None:
                    pattern_memory_store.append(pattern_record)
            results.append(
                {
                    "symbol": symbol,
                    "signal": asdict(signal),
                    "evaluation": asdict(evaluation),
                    "risk_plan": asdict(risk_plan) if risk_plan else None,
                    "deliveries": [asdict(item) for item in deliveries],
                    "candidate_rejected": candidate_rejected,
                    "paper_candidate_detected": paper_candidate_detected,
                    "paper_trade_created": paper_trade_created,
                    "paper_trade_rejection": paper_rejection,
                    "paper_trade_updates": paper_updates,
                    "relaxation_shadow_updates": relaxation_shadow_updates,
                    "relaxation_shadow_v1": relaxation_shadow_v1,
                    "live_trade_updates": live_trade_updates,
                    "module_diagnostics": module_diagnostics,
                    "signal_decision": signal_decision.to_dict(),
                    "selected_decision_engine": selected_decision.selected_engine,
                    "current_signal_decision": current_signal_decision.to_dict(),
                    "parallel_signal_decision": parallel_signal_decision.to_dict(),
                    "experimental_signal_saved": experimental_signal_saved,
                    "shadow_signal_saved": shadow_signal_saved,
                    "modular_signal_saved": modular_signal_saved,
                    "setup_context": setup_context,
                    "high_score_rejected": high_score_rejected,
                    "pattern_memory": pattern_memory,
                    "performance_gate": performance_gate,
                    "multi_agent_shadow_decision": multi_agent_shadow_decision,
                    "kill_switch": kill_switch_status,
                    "protection_engine": protection_engine,
                    "public_canary": public_canary,
                    "signal_update_v1": signal_update_v1,
                    "edge_knowledge_shadow": edge_knowledge_shadow.to_dict(),
                    "edge_optimizer_shadow": edge_optimizer_shadow.to_dict(),
                    "edge_optimizer_active": edge_optimizer_active.to_dict(),
                }
            )
            _log_symbol_diagnostics(
                settings=settings,
                symbol=symbol,
                analysis=analysis,
                evaluation=evaluation,
                signal=signal,
                status=status,
                should_publish_decision=should_publish_decision,
                is_duplicate=is_duplicate,
                setup_context=setup_context,
            )
            _log_candidate_rejected(payload=candidate_rejected)
            _log_paper_candidate_rejected(payload=paper_rejection)
            if signal.decision == SignalDecision.NO_TRADE.value:
                diagnostics_store.append_csv_row(
                    category="no_trade_diagnostics",
                    date_key=started_at[:10],
                    row={
                        "timestamp": _now_iso(),
                        "scan_run_id": scan_run.id,
                        "symbol": symbol,
                        "decision": signal.decision,
                        "setup_score": evaluation.setup_score,
                        "trend_entry_timeframe": analysis.entry_snapshot.trend,
                        "trend_higher_timeframe": analysis.higher_snapshot.trend,
                        "market_structure": analysis.entry_snapshot.market_structure,
                        "liquidity_sweep": analysis.entry_snapshot.liquidity_sweep,
                        "atr": analysis.entry_snapshot.atr,
                        "rejection_reason": "|".join(evaluation.rejection_reasons) if evaluation.rejection_reasons else "",
                    },
                    fieldnames=[
                        "timestamp",
                        "scan_run_id",
                        "symbol",
                        "decision",
                        "setup_score",
                        "trend_entry_timeframe",
                        "trend_higher_timeframe",
                        "market_structure",
                        "liquidity_sweep",
                        "atr",
                        "rejection_reason",
                    ],
                )
            scan_run.symbols_processed += 1
        except Exception as exc:
            scan_run.symbols_processed += 1
            scan_run.errors_count += 1
            metrics.increment("market_data_errors_total")
            error = SystemError(
                id=f"err_{uuid4().hex[:12]}",
                scan_run_id=scan_run.id,
                symbol=symbol,
                stage="run_market_scan",
                error_type=type(exc).__name__,
                error_message=str(exc),
                payload={},
                created_at=_now_iso(),
            )
            scan_repo.save_error(error)
            results.append({"symbol": symbol, "error": str(exc)})

    scan_run.status = "completed"
    scan_run.finished_at = _now_iso()
    scan_run.updated_at = scan_run.finished_at
    scan_repo.save_scan_run(scan_run)
    metrics.increment("scan_runs_total")
    try:
        candidate_funnel_report = finalize_candidate_funnel_cycle(
            candidate_funnel,
            data_path=settings.data_storage_path,
        )
    except Exception as exc:
        log_json(
            logging.getLogger("trading_signals"),
            "candidate_funnel_audit_failed",
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
    return {
        "scan_run": asdict(scan_run),
        "results": results,
        "universe_validation": universe_validation,
        "pair_universe_filter": pair_universe_filter,
        "candidate_funnel": candidate_funnel_report,
    }
