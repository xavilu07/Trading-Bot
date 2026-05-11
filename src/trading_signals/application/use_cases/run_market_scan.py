from __future__ import annotations

import logging
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from uuid import uuid4

from trading_signals.app.settings import Settings
from trading_signals.analysis.liquidity import analyze_liquidity
from trading_signals.analysis.market_regime import analyze_market_regime
from trading_signals.analysis.momentum import analyze_momentum
from trading_signals.analysis.risk import analyze_risk
from trading_signals.analysis.trend import analyze_trend
from trading_signals.application.use_cases.analyze_symbol import analyze_symbol
from trading_signals.application.use_cases.paper_trading import (
    build_paper_candidate_from_decision,
    build_paper_rejection_diagnostic,
    paper_level_label,
    paper_market_is_tradeable,
)
from trading_signals.application.use_cases.live_trading import (
    build_live_candidate_from_decision,
    format_public_live_trade_event_for_telegram,
    format_live_trade_event_for_telegram,
)
from trading_signals.notifications.telegram import send_public_signal
from trading_signals.application.use_cases.modular_paper import build_modular_signal_row
from trading_signals.application.use_cases.experimental_paper import build_experimental_signal_row
from trading_signals.application.use_cases.shadow_paper import build_shadow_signal_row
from trading_signals.application.use_cases.publish_signal import publish_signal
from trading_signals.application.use_cases.publish_signal import publish_filter_rejection_reason
from trading_signals.application.use_cases.setup_context import build_setup_context
from trading_signals.application.use_cases.signal_lifecycle import classify_signal_lifecycle
from trading_signals.data.market_data import market_data_status
from trading_signals.diagnostics.logger import log_module_diagnostic
from trading_signals.domain.entities.scan_run import ScanRun
from trading_signals.domain.entities.system_error import SystemError
from trading_signals.domain.entities.trade_signal import TradeSignal
from trading_signals.domain.services.risk_service import calculate_risk_plan
from trading_signals.domain.strategies.liquidity_sweep_mtf_v1 import LiquiditySweepMTFV1
from trading_signals.domain.value_objects.enums import SignalDecision, SignalStatus
from trading_signals.infrastructure.logging.logger import log_json
from trading_signals.memory.insights import build_pattern_memory_insights
from trading_signals.memory.pattern_memory import build_pattern_record, evaluate_pattern_memory
from trading_signals.notifications.telegram import telegram_status
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
    experimental_signal_store=None,
    shadow_signal_store=None,
    modular_signal_store=None,
    live_trading_store=None,
    pattern_memory_store=None,
    symbols: list[str] | None = None,
    dry_run: bool = False,
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
    for skipped in universe_validation["skipped_symbols"]:
        if isinstance(skipped, dict):
            log_json(
                logger,
                "symbol_skipped",
                symbol=skipped.get("symbol"),
                reason=skipped.get("reason"),
                provider=skipped.get("provider"),
            )
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

    for symbol in valid_symbols:
        try:
            analysis = analyze_symbol(market_data=market_data, settings=settings, scan_run_id=scan_run.id, symbol=symbol)
            paper_updates = []
            if settings.paper_trading_enabled and paper_trading_store is not None:
                paper_updates = paper_trading_store.update_open_trades_for_snapshot(
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
                created_at=_now_iso(),
            )
            signal_repo.save_signal(signal)
            deliveries = []
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
                }
            )
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
                    log_json(
                        logger,
                        "publish_signal_blocked",
                        symbol=symbol,
                        direction=evaluation.decision,
                        reason=publish_filter_reason,
                        setup_context=setup_context,
                    )
            should_publish_after_filters = should_publish_decision and publish_filter_reason is None
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
            if status == SignalStatus.VALID.value and should_publish_after_filters and not is_duplicate and lifecycle and lifecycle.should_publish:
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
                )
                if any(item.status == "sent" for item in deliveries):
                    public_published = any(item.channel == "telegram_public" and item.status == "sent" for item in deliveries)
                    signal.status = SignalStatus.PUBLISHED.value
                    signal.published_at = _now_iso()
                    signal.updated_at = signal.published_at
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
            paper_trade_created = False
            paper_candidate_detected = False
            paper_rejection = None
            if settings.paper_trading_enabled and paper_trading_store is not None:
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
                    )
                    if paper_tradeable and paper_candidate is not None and paper_candidate.risk_reward_tp2 >= settings.paper_trading_min_rr:
                        paper_trade_created = paper_trading_store.upsert_candidate(paper_candidate)
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
            pattern_memory = None
            if pattern_memory_store is not None:
                pattern_history = pattern_memory_store.list_records(limit=1000)
                pattern_risk_plan = risk_plan
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
                    final_status=_pattern_final_status(
                        signal=signal,
                        high_score_rejected=high_score_rejected,
                        paper_trade_created=paper_trade_created,
                    ),
                    outcome="open" if signal.status == SignalStatus.PUBLISHED.value or paper_trade_created else None,
                    r_result=None,
                )
                pattern_memory = evaluate_pattern_memory(pattern_record, pattern_history[-500:])
                pattern_memory["insights"] = build_pattern_memory_insights(pattern_history)
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
    return {"scan_run": asdict(scan_run), "results": results, "universe_validation": universe_validation}
