from __future__ import annotations

import logging
import os
from collections import deque
from datetime import UTC, datetime
from uuid import uuid4

from trading_signals.application.policies.public_canary_policy import PublicShortCanaryConfig
from trading_signals.application.policies.public_safety_policy import evaluate_public_safety_policy
from trading_signals.application.policies.relaxed_public_safety_v2 import evaluate_relaxed_public_safety_v2
from trading_signals.application.use_cases.relaxation_shadow_v1 import (
    build_relaxation_shadow_candidate,
    format_relaxation_shadow_v1_message,
    safe_relaxation_filter_result,
)
from trading_signals.domain.entities.signal_delivery import SignalDelivery
from trading_signals.notifications.telegram import send_dev_signal_detail, send_public_signal


HARMFUL_PUBLISH_FILTERS = {
    "distance_to_liquidity_penalty",
    "directional_confluence_failed",
}
NEGATIVE_EDGE_PUBLIC_ROUTE_REASON = "negative_historical_edge"
RELAXED_SHADOW_DEDUPE_MAX = 500
_RELAXED_SHADOW_DEDUPE_KEYS: deque[str] = deque(maxlen=RELAXED_SHADOW_DEDUPE_MAX)


def signal_message_context(evaluation_or_decision) -> dict[str, object]:
    return {
        "setup_score": float(getattr(evaluation_or_decision, "setup_score", getattr(evaluation_or_decision, "total_score", 0.0))),
        "passed_filters": list(getattr(evaluation_or_decision, "passed_filters", [])),
        "failed_filters": list(getattr(evaluation_or_decision, "failed_filters", [])),
        "rejection_reasons": list(getattr(evaluation_or_decision, "rejection_reasons", [])),
        "setup_type": str(getattr(evaluation_or_decision, "setup_type", "")),
    }


def public_routing_rejection_reason(signal, evaluation_or_decision, setup_context: dict[str, object] | None = None) -> str | None:
    policy = evaluate_public_safety_policy(
        signal=signal,
        evaluation_or_decision=evaluation_or_decision,
        setup_context=setup_context,
    )
    reasons = list(policy.get("block_reasons", []))
    return _legacy_public_block_reason(reasons)


def _legacy_public_block_reason(reasons: list[str]) -> str | None:
    mapping = {
        "against_htf": "public_block_against_htf",
        "market_regime_ranging": "public_block_market_regime_ranging",
        "market_regime_not_trending": "public_block_market_regime_not_trending",
        "entry_context_choppy_range": "public_block_choppy_range",
        "trade_location_premium_zone": "public_block_trade_location_premium_zone",
        "short_shadow_mode": "short_shadow_mode",
        "setup_type_secondary_signal": NEGATIVE_EDGE_PUBLIC_ROUTE_REASON,
        "short_without_high_historical_edge": NEGATIVE_EDGE_PUBLIC_ROUTE_REASON,
        "low_volume": "public_block_low_volume",
        "dirty_sideways_market": "public_block_dirty_sideways_market",
        "bad_breakout_context": "public_block_bad_breakout_context",
        "breakout_bad_location": "public_block_breakout_bad_location",
        "breakout_against_htf": "public_block_breakout_against_htf",
    }
    for reason in reasons:
        if reason in mapping:
            return mapping[reason]
    return reasons[0] if reasons else None


def _htf_contradicts(direction: str, trend_higher: str) -> bool:
    return (direction == "long" and trend_higher == "bearish") or (direction == "short" and trend_higher == "bullish")


def _normalized_items(values) -> set[str]:
    items: set[str] = set()
    if values is None:
        return items
    if isinstance(values, str):
        values = [values]
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        for part in text.replace("|", ",").split(","):
            item = part.strip()
            if not item:
                continue
            items.add(item)
            if ":" in item:
                items.add(item.split(":", 1)[0].strip())
            if "=" in item:
                right_side = item.split("=", 1)[1].strip()
                items.add(right_side)
                if ":" in right_side:
                    items.add(right_side.split(":", 1)[0].strip())
    return items


def _trace_penalty_tokens(trace_values) -> set[str]:
    tokens: set[str] = set()
    for item in trace_values or []:
        text = str(item)
        if not text.startswith("penalties="):
            continue
        tokens |= _normalized_items(text.split("=", 1)[1])
    return tokens


def _infer_setup_type(evaluation_or_decision) -> str:
    passed_filters = list(getattr(evaluation_or_decision, "passed_filters", []))
    return "SECONDARY_SIGNAL" if "secondary_setup" in passed_filters else "MAIN_SIGNAL"


def score_stars(score: float) -> str:
    if score >= 80:
        return "⭐⭐⭐⭐"
    if score >= 60:
        return "⭐⭐⭐"
    if score >= 40:
        return "⭐⭐"
    return "⭐"


def summarize_reason(passed_filters: list[str]) -> str:
    labels = []
    mapping = (
        ("timeframe_alignment", "tendencia alineada"),
        ("secondary_trend_alignment", "tendencia"),
        ("primary_sweep_setup", "sweep de liquidez"),
        ("secondary_break_of_structure", "BOS"),
        ("secondary_volume_confirmation", "volumen"),
        ("secondary_rsi_alignment", "RSI"),
        ("secondary_nearest_liquidity", "liquidez cercana"),
        ("distance_to_liquidity", "zona de liquidez"),
        ("candle_confirmation", "vela confirmada"),
        ("quality_score", "score válido"),
        ("volatility", "volatilidad suficiente"),
    )
    for key, label in mapping:
        if key in passed_filters and label not in labels:
            labels.append(label)
    return " + ".join(labels[:6]) if labels else "setup válido según filtros principales"


def summarize_risks(evaluation, entry_snapshot, higher_snapshot) -> str:
    risks = []
    context = signal_message_context(evaluation)
    failed = set(context["failed_filters"])
    if "distance_to_liquidity_penalty" in failed:
        risks.append("distancia a liquidez con penalización")
    if "timeframe_alignment_penalty" in failed:
        risks.append("timeframes no perfectamente alineados")
    if entry_snapshot.trend != higher_snapshot.trend:
        risks.append("HTF no alineado")
    if entry_snapshot.market_structure == "range":
        risks.append("estructura en rango")
    if not risks:
        risks.append("sin alertas críticas")
    return "\n".join(f"- {item}" for item in risks[:4])


def summarize_public_warnings(evaluation, entry_snapshot, higher_snapshot) -> list[str]:
    risk_lines = summarize_risks(evaluation, entry_snapshot, higher_snapshot).splitlines()
    warnings = [line.removeprefix("- ").strip() for line in risk_lines if line.removeprefix("- ").strip()]
    return [warning for warning in warnings if warning != "sin alertas críticas"][:2]


def publish_filter_rejection_reason(
    *,
    settings,
    symbol: str,
    direction: str,
    setup_context: dict[str, object],
    opened_at: str,
    evaluation_or_decision=None,
) -> str | None:
    direction_allowed = _allowed(settings.publish_allowed_directions, direction.upper())
    session_allowed = _allowed(settings.publish_allowed_sessions, str(setup_context.get("session", "")).upper())
    hour_allowed = _allowed(settings.publish_allowed_hours_utc, str(_hour_utc(opened_at)))
    symbol_allowed = _allowed(settings.publish_symbol_whitelist, symbol.upper())
    if not direction_allowed:
        return "publish_filter_direction"
    if not session_allowed:
        return "publish_filter_session"
    if not hour_allowed:
        return "publish_filter_hour_utc"
    if not symbol_allowed:
        return "publish_filter_symbol_whitelist"
    filter_tokens = _publish_filter_tokens(setup_context=setup_context, evaluation_or_decision=evaluation_or_decision)
    blocked_warning = _first_configured_match(settings.publish_blocked_warnings, filter_tokens)
    if blocked_warning is not None:
        return f"publish_filter_blocked_warning:{blocked_warning}"
    blocked_reason = _first_configured_match(settings.publish_blocked_reasons, filter_tokens)
    if blocked_reason is not None:
        return f"publish_filter_blocked_reason:{blocked_reason}"
    if settings.publish_require_no_harmful_filters:
        harmful_filter = _first_configured_match(list(HARMFUL_PUBLISH_FILTERS), filter_tokens)
        if harmful_filter is not None:
            return f"publish_filter_harmful_filter:{harmful_filter}"
    return None


def meta_decision_public_filter_reason(settings, pattern_memory: dict[str, object] | None) -> str | None:
    if not getattr(settings, "meta_decision_filter_enabled", False):
        return None
    if not isinstance(pattern_memory, dict):
        return None
    meta_decision = pattern_memory.get("meta_decision")
    if not isinstance(meta_decision, dict):
        meta_decision = {}
    trade_quality = pattern_memory.get("trade_quality")
    if not isinstance(trade_quality, dict):
        trade_quality = {}
    if str(meta_decision.get("meta_decision", "")).upper() == "REJECT":
        return "meta_decision_reject"
    if bool(meta_decision.get("capital_preservation_mode")):
        return "capital_preservation_mode"
    if str(trade_quality.get("trade_quality_grade", "")).upper() == "TRASH":
        return "trade_quality_trash"
    return None


def _publish_filter_tokens(*, setup_context: dict[str, object], evaluation_or_decision) -> set[str]:
    tokens: set[str] = set()
    _extend_tokens(tokens, setup_context.get("avoidance_warnings", []))
    _extend_tokens(tokens, setup_context.get("warnings", []))
    if evaluation_or_decision is not None:
        _extend_tokens(tokens, getattr(evaluation_or_decision, "warnings", []))
        _extend_tokens(tokens, getattr(evaluation_or_decision, "failed_filters", []))
        _extend_tokens(tokens, getattr(evaluation_or_decision, "rejection_reasons", []))
        _extend_tokens(tokens, getattr(evaluation_or_decision, "decision_trace", []))
    return tokens


def _extend_tokens(tokens: set[str], values) -> None:
    if values is None:
        return
    if isinstance(values, str):
        values = [values]
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        tokens.add(text)
        for part in text.replace("|", ",").split(","):
            item = part.strip()
            if not item:
                continue
            tokens.add(item)
            if ":" in item:
                tokens.add(item.split(":", 1)[0].strip())
            if "=" in item:
                right_side = item.split("=", 1)[1].strip()
                tokens.add(right_side)
                if ":" in right_side:
                    tokens.add(right_side.split(":", 1)[0].strip())


def _first_configured_match(configured: list[str], tokens: set[str]) -> str | None:
    normalized_tokens = {token.strip().lower(): token for token in tokens if token.strip()}
    for item in configured:
        key = str(item).strip().lower()
        if key and key in normalized_tokens:
            return normalized_tokens[key]
    return None


def _allowed(configured: list[str], value: str) -> bool:
    if not configured:
        return True
    allowed = {str(item).strip().upper() for item in configured if str(item).strip()}
    return value.strip().upper() in allowed


def _hour_utc(timestamp: str) -> int:
    try:
        return datetime.fromisoformat(timestamp).astimezone(UTC).hour
    except ValueError:
        return datetime.now(tz=UTC).hour


def format_telegram_message(symbol: str, decision: str, entry_snapshot, higher_snapshot, evaluation, risk_plan, signal_type: str = "NEW") -> str:
    context = signal_message_context(evaluation)
    setup_score = float(context["setup_score"])
    passed_filters = list(context["passed_filters"])
    rejection_reasons = list(context["rejection_reasons"])
    if decision == "no_trade":
        return (
            f"Signal: NO_TRADE\n"
            f"Symbol: {symbol}\n"
            f"Timeframes: {entry_snapshot.timeframe.upper()} / {higher_snapshot.timeframe.upper()}\n"
            f"Setup Score: {setup_score}\n"
            f"Reasons: {', '.join(rejection_reasons) or 'none'}"
        )
    setup_type = str(context["setup_type"])
    if not setup_type:
        setup_type = _infer_setup_type(evaluation)
    setup_label = "⚠️ setup sin sweep\n" if setup_type == "SECONDARY_SIGNAL" or "secondary_setup" in passed_filters else ""
    direction = decision.upper()
    reason = summarize_reason(passed_filters)
    risks = summarize_risks(evaluation, entry_snapshot, higher_snapshot)
    return (
        setup_label +
        f"🚨 Señal {symbol} {direction}\n"
        f"Signal: {direction}\n"
        f"Direction: {direction}\n\n"
        f"📊 Setup\n"
        f"- Tipo: {setup_type}\n"
        f"- SIGNAL_TYPE: {signal_type}\n"
        f"- Score: {setup_score} {score_stars(setup_score)}\n\n"
        f"📉 Contexto\n"
        f"- Timeframes: {entry_snapshot.timeframe.upper()} / {higher_snapshot.timeframe.upper()}\n"
        f"- Tendencia: {entry_snapshot.trend} / {higher_snapshot.trend}\n"
        f"- Estructura: {entry_snapshot.market_structure}\n"
        f"- Liquidity sweep: {entry_snapshot.liquidity_sweep}\n"
        f"- ATR: {entry_snapshot.atr}\n\n"
        f"💰 Trade\n"
        f"- Entry: {risk_plan.entry}\n"
        f"- Stop Loss: {risk_plan.stop_loss}\n"
        f"- Take Profit: {risk_plan.take_profit}\n"
        f"- Risk/Reward: {risk_plan.risk_reward}\n\n"
        f"⚠️ Riesgos\n"
        f"{risks}\n\n"
        f"🧠 Motivo\n"
        f"{reason}"
    )


def format_public_signal_message(symbol: str, decision: str, entry_snapshot, higher_snapshot, evaluation, risk_plan) -> str:
    direction = decision.upper()
    direction_emoji = "🟢" if direction == "LONG" else "🔴"
    take_profit_1 = getattr(risk_plan, "take_profit_1", None) or getattr(risk_plan, "take_profit", None)
    take_profit_2 = getattr(risk_plan, "take_profit_2", None)
    take_profit_3 = getattr(risk_plan, "take_profit_3", None)
    tp_lines = []
    if take_profit_1 is not None:
        tp_lines.append(f"🎯 TP1: {take_profit_1}")
    if take_profit_2 is not None:
        tp_lines.append(f"🎯 TP2: {take_profit_2}")
    if take_profit_3 is not None:
        tp_lines.append(f"🎯 TP3: {take_profit_3}")
    message = (
        "🚨 NUEVA OPERACIÓN 🚨\n\n"
        f"{direction_emoji} {symbol}\n"
        f"📍 Entry: {risk_plan.entry}\n\n"
        f"{chr(10).join(tp_lines)}\n\n"
        f"🛑 SL: {risk_plan.stop_loss}\n\n"
        "🛡️ Gestiona tu capital con\n"
        "responsabilidad\n\n"
        "🔥 Recomendado:\n"
        "Cerrar parcial en TP1\n"
        "SL break even en TP2"
    )
    return message


def clear_relaxed_public_shadow_dedupe() -> None:
    _RELAXED_SHADOW_DEDUPE_KEYS.clear()


def publish_signal(
    signal_repo,
    notifier,
    signal,
    entry_snapshot,
    higher_snapshot,
    evaluation,
    risk_plan,
    dry_run: bool = False,
    signal_type: str = "NEW",
    setup_context: dict[str, object] | None = None,
    public_block_reason: str | None = None,
    public_short_canary_config: PublicShortCanaryConfig | None = None,
    relaxation_shadow_store=None,
    relaxation_shadow_expires_after_candles: int = 24,
) -> list[SignalDelivery]:
    public_message = format_public_signal_message(signal.symbol, signal.decision, entry_snapshot, higher_snapshot, evaluation, risk_plan)
    dev_message = format_telegram_message(signal.symbol, signal.decision, entry_snapshot, higher_snapshot, evaluation, risk_plan, signal_type=signal_type)
    routed_results = []
    policy = evaluate_public_safety_policy(
        signal=signal,
        evaluation_or_decision=evaluation,
        setup_context=setup_context,
        public_block_reason=public_block_reason,
        public_short_canary_config=public_short_canary_config,
    )
    logger = logging.getLogger("trading_signals")
    canary = policy.get("public_canary", {})
    if isinstance(canary, dict) and canary.get("public_canary_enabled") and signal.decision == "short":
        logger.info(
            "public_canary_evaluated",
            extra={
                "event": "public_canary_evaluated",
                "symbol": signal.symbol,
                "reason": canary.get("public_canary_reason"),
                "score": canary.get("score"),
                "session": canary.get("session"),
                "entry_context": canary.get("entry_context"),
                "setup_type": canary.get("setup_type"),
                "public_canary_match": canary.get("public_canary_match"),
            },
        )
    if not bool(policy.get("public_allowed")):
        logger.info(
            "public_safety_policy_blocked",
            extra={
                "event": "public_safety_policy_blocked",
                "symbol": signal.symbol,
                "direction": signal.decision,
                "block_reasons": policy.get("block_reasons", []),
                "warnings": policy.get("warnings", []),
                "policy_version": policy.get("policy_version", ""),
                "edge_activation_mode": policy.get("edge_activation_mode", False),
                "edge_activation_allowed": policy.get("edge_activation_allowed", True),
                "edge_activation_reasons": policy.get("edge_activation_reasons", []),
            },
        )
        if bool(policy.get("edge_activation_mode")) and not bool(policy.get("edge_activation_allowed")):
            logger.info(
                "edge_activation_blocked",
                extra={
                    "event": "edge_activation_blocked",
                    "symbol": signal.symbol,
                    "direction": signal.decision,
                    "edge_activation_reasons": policy.get("edge_activation_reasons", []),
                    "policy_version": policy.get("policy_version", ""),
                },
            )
        if bool(policy.get("short_shadow_mode")) and signal.decision == "short":
            logger.info(
                "short_shadow_signal",
                extra={
                    "event": "short_shadow_signal",
                    "symbol": signal.symbol,
                    "direction": signal.decision,
                    "public_allowed": False,
                    "block_reasons": policy.get("block_reasons", []),
                },
            )
        if isinstance(canary, dict) and canary.get("public_canary_enabled") and signal.decision == "short":
            logger.info(
                "public_canary_blocked",
                extra={
                    "event": "public_canary_blocked",
                    "symbol": signal.symbol,
                    "reason": canary.get("public_canary_reason"),
                    "score": canary.get("score"),
                    "session": canary.get("session"),
                    "entry_context": canary.get("entry_context"),
                    "setup_type": canary.get("setup_type"),
                },
            )
        relaxed_shadow = _evaluate_relaxed_public_shadow(
            signal=signal,
            evaluation=evaluation,
            risk_plan=risk_plan,
            setup_context=setup_context,
            current_policy=policy,
        )
        if relaxed_shadow["should_send_dev"]:
            relaxed_message = format_relaxed_public_shadow_message(
                signal=signal,
                evaluation=evaluation,
                risk_plan=risk_plan,
                setup_context=setup_context or {},
                relaxed_policy=relaxed_shadow["relaxed_policy"],
                current_policy=policy,
            )
            routed_results.append(
                (
                    "telegram_dev_relaxed_shadow",
                    relaxed_message,
                    send_dev_signal_detail(notifier, relaxed_message, dry_run=dry_run),
                )
            )
            logger.info(
                "relaxed_public_shadow_signal_sent_dev",
                extra={
                    "event": "relaxed_public_shadow_signal_sent_dev",
                    "symbol": signal.symbol,
                    "direction": signal.decision,
                    "relaxed_public_policy_decision": relaxed_shadow["relaxed_public_policy_decision"],
                    "relaxed_public_policy_vs_current": relaxed_shadow["relaxed_public_policy_vs_current"],
                    "current_block_reasons": policy.get("block_reasons", []),
                    "relaxed_warnings": relaxed_shadow["relaxed_policy"].get("warnings", []),
                },
            )
        else:
            logger.info(
                "relaxed_public_shadow_signal_skipped",
                extra={
                    "event": "relaxed_public_shadow_signal_skipped",
                    "symbol": signal.symbol,
                    "direction": signal.decision,
                    "reason": relaxed_shadow["skip_reason"],
                    "relaxed_public_policy_decision": relaxed_shadow["relaxed_public_policy_decision"],
                    "relaxed_public_policy_vs_current": relaxed_shadow["relaxed_public_policy_vs_current"],
                },
            )
        relaxation_shadow = _evaluate_relaxation_shadow_v1(
            signal=signal,
            evaluation=evaluation,
            risk_plan=risk_plan,
            entry_snapshot=entry_snapshot,
            higher_snapshot=higher_snapshot,
            setup_context=setup_context or {},
            current_policy=policy,
            store=relaxation_shadow_store,
            expires_after_candles=relaxation_shadow_expires_after_candles,
        )
        if relaxation_shadow["should_send_dev"]:
            candidate = relaxation_shadow["candidate"]
            relaxation_message = format_relaxation_shadow_v1_message(candidate)
            routed_results.append(
                (
                    "telegram_dev_relaxation_shadow_v1",
                    relaxation_message,
                    send_dev_signal_detail(notifier, relaxation_message, dry_run=dry_run),
                )
            )
            logger.info(
                "relaxation_shadow_v1_signal_sent_dev",
                extra={
                    "event": "relaxation_shadow_v1_signal_sent_dev",
                    "symbol": signal.symbol,
                    "direction": signal.decision,
                    "relaxed_filters": candidate.relaxed_filters,
                    "original_rejection_reasons": candidate.original_rejection_reasons,
                },
            )
        else:
            logger.info(
                "relaxation_shadow_v1_signal_skipped",
                extra={
                    "event": "relaxation_shadow_v1_signal_skipped",
                    "symbol": signal.symbol,
                    "direction": signal.decision,
                    "reason": relaxation_shadow["skip_reason"],
                    "safe_filters": relaxation_shadow["filter_result"].get("safe_filters", []),
                    "unsafe_filters": relaxation_shadow["filter_result"].get("unsafe_filters", []),
                },
            )
    else:
        if isinstance(canary, dict) and canary.get("public_canary_enabled") and signal.decision == "short":
            logger.info(
                "public_canary_allowed",
                extra={
                    "event": "public_canary_allowed",
                    "symbol": signal.symbol,
                    "reason": canary.get("public_canary_reason"),
                    "score": canary.get("score"),
                    "session": canary.get("session"),
                    "entry_context": canary.get("entry_context"),
                    "setup_type": canary.get("setup_type"),
                },
            )
        routed_results.append(("telegram_public", public_message, send_public_signal(notifier, public_message, dry_run=dry_run)))
    routed_results.append(("telegram_dev", dev_message, send_dev_signal_detail(notifier, dev_message, dry_run=dry_run)))
    deliveries: list[SignalDelivery] = []
    attempted_at = datetime.now(tz=UTC).isoformat()
    for channel, message, results in routed_results:
        for result in results:
            payload = {"message": message}
            if channel == "telegram_dev_relaxed_shadow":
                payload["relaxed_public_policy"] = {
                    "relaxed_public_policy_decision": "allow",
                    "relaxed_public_policy_vs_current": "relaxed_allow_current_block",
                    "relaxed_public_shadow_sent_dev": str(result["status"]) == "sent",
                    "current_public_policy_decision": "block",
                    "shadow_label": "RELAXED_SHADOW_SIGNAL",
                }
            if channel == "telegram_dev_relaxation_shadow_v1":
                payload["relaxation_shadow_v1"] = {
                    "shadow_label": "RELAXATION_SHADOW_V1",
                    "dev_only": True,
                    "public_published": False,
                }
            delivery = SignalDelivery(
                id=f"delivery_{uuid4().hex[:12]}",
                signal_id=signal.id,
                channel=channel,
                status=str(result["status"]),
                recipient=str(result["recipient"]),
                provider_message_id=result.get("provider_message_id"),
                payload=payload,
                error_message=result.get("error_message"),
                attempted_at=attempted_at,
            )
            signal_repo.save_delivery(delivery)
            deliveries.append(delivery)
    return deliveries


def format_relaxed_public_shadow_message(
    *,
    signal,
    evaluation,
    risk_plan,
    setup_context: dict[str, object],
    relaxed_policy: dict[str, object],
    current_policy: dict[str, object],
) -> str:
    reason = ", ".join(str(item) for item in current_policy.get("block_reasons", [])[:3]) or "public_safety_policy_blocked"
    return (
        "🧪 RELAXED SHADOW SIGNAL\n"
        "No publicada en canal público.\n\n"
        f"Símbolo: {signal.symbol}\n"
        f"Dirección: {str(signal.decision).upper()}\n"
        f"Entry: {getattr(risk_plan, 'entry', 'n/a')}\n"
        f"SL: {getattr(risk_plan, 'stop_loss', 'n/a')}\n"
        f"TP: {getattr(risk_plan, 'take_profit', 'n/a')}\n"
        f"Score: {getattr(evaluation, 'setup_score', getattr(evaluation, 'total_score', 'n/a'))}\n"
        f"Session: {setup_context.get('session', 'UNKNOWN')}\n"
        f"Setup type: {setup_context.get('setup_type') or getattr(evaluation, 'setup_type', 'UNKNOWN')}\n"
        f"Entry context: {setup_context.get('entry_context', 'UNKNOWN')}\n"
        f"Reason: relaxed allow; current block: {reason}\n"
        f"Relaxed warnings: {', '.join(str(item) for item in relaxed_policy.get('warnings', [])) or 'none'}"
    )


def _evaluate_relaxed_public_shadow(
    *,
    signal,
    evaluation,
    risk_plan,
    setup_context: dict[str, object] | None,
    current_policy: dict[str, object],
) -> dict[str, object]:
    runtime_shadow_enabled = _env_bool("RELAXED_PUBLIC_POLICY_RUNTIME_SHADOW", "true")
    send_dev_enabled = _env_bool("RELAXED_PUBLIC_POLICY_SEND_DEV", "true")
    if not runtime_shadow_enabled:
        return _relaxed_shadow_result("disabled", {}, "disabled", "not_evaluated")

    trade = _relaxed_runtime_trade(signal=signal, evaluation=evaluation, risk_plan=risk_plan, setup_context=setup_context or {})
    relaxed_policy = evaluate_relaxed_public_safety_v2(trade=trade, history=[])
    relaxed_allowed = bool(relaxed_policy.get("public_allowed"))
    current_allowed = bool(current_policy.get("public_allowed"))
    relaxed_decision = "allow" if relaxed_allowed else "block"
    comparison = f"relaxed_{relaxed_decision}_current_{'allow' if current_allowed else 'block'}"
    if not send_dev_enabled:
        return _relaxed_shadow_result("send_dev_disabled", relaxed_policy, relaxed_decision, comparison)
    if current_allowed or not relaxed_allowed:
        return _relaxed_shadow_result("no_policy_gap", relaxed_policy, relaxed_decision, comparison)

    dedupe_key = _relaxed_shadow_dedupe_key(trade)
    if dedupe_key in _RELAXED_SHADOW_DEDUPE_KEYS:
        return _relaxed_shadow_result("duplicate", relaxed_policy, relaxed_decision, comparison)
    _RELAXED_SHADOW_DEDUPE_KEYS.append(dedupe_key)
    return {
        "should_send_dev": True,
        "skip_reason": "",
        "relaxed_policy": relaxed_policy,
        "relaxed_public_policy_decision": relaxed_decision,
        "relaxed_public_policy_vs_current": comparison,
    }


def _evaluate_relaxation_shadow_v1(
    *,
    signal,
    evaluation,
    risk_plan,
    entry_snapshot,
    higher_snapshot,
    setup_context: dict[str, object],
    current_policy: dict[str, object],
    store,
    expires_after_candles: int,
) -> dict[str, object]:
    filter_result = safe_relaxation_filter_result(current_policy.get("block_reasons", []))
    if store is None:
        return {"should_send_dev": False, "skip_reason": "store_not_configured", "filter_result": filter_result}
    if not filter_result["eligible"]:
        return {"should_send_dev": False, "skip_reason": "unsafe_or_empty_filters", "filter_result": filter_result}
    candidate = build_relaxation_shadow_candidate(
        signal=signal,
        evaluation=evaluation,
        risk_plan=risk_plan,
        entry_snapshot=entry_snapshot,
        higher_snapshot=higher_snapshot,
        setup_context=setup_context,
        current_policy=current_policy,
        opened_at=datetime.now(tz=UTC).isoformat(),
        expires_after_candles=expires_after_candles,
    )
    if candidate is None:
        return {"should_send_dev": False, "skip_reason": "candidate_not_created", "filter_result": filter_result}
    created = store.upsert_candidate(candidate)
    if not created:
        return {"should_send_dev": False, "skip_reason": "duplicate", "filter_result": filter_result, "candidate": candidate}
    return {
        "should_send_dev": True,
        "skip_reason": "",
        "filter_result": filter_result,
        "candidate": candidate,
    }


def _relaxed_shadow_result(
    skip_reason: str,
    relaxed_policy: dict[str, object],
    relaxed_decision: str,
    comparison: str,
) -> dict[str, object]:
    return {
        "should_send_dev": False,
        "skip_reason": skip_reason,
        "relaxed_policy": relaxed_policy,
        "relaxed_public_policy_decision": relaxed_decision,
        "relaxed_public_policy_vs_current": comparison,
    }


def _relaxed_runtime_trade(*, signal, evaluation, risk_plan, setup_context: dict[str, object]) -> dict[str, object]:
    return {
        **setup_context,
        "symbol": signal.symbol,
        "direction": signal.decision,
        "setup_type": setup_context.get("setup_type") or getattr(evaluation, "setup_type", "") or _infer_setup_type(evaluation),
        "score": getattr(evaluation, "setup_score", getattr(evaluation, "total_score", None)),
        "entry": getattr(risk_plan, "entry", None),
        "stop_loss": getattr(risk_plan, "stop_loss", None),
        "take_profit": getattr(risk_plan, "take_profit", None),
        "risk_reward": getattr(risk_plan, "risk_reward", None),
        "warnings": setup_context.get("warnings", setup_context.get("avoidance_warnings", [])),
        "penalties": setup_context.get("penalties", []),
        "trend_higher_timeframe": setup_context.get("trend_higher_timeframe") or setup_context.get("trend_higher"),
        "risk_plan_valid": risk_plan is not None,
    }


def _relaxed_shadow_dedupe_key(trade: dict[str, object]) -> str:
    fields = [
        "symbol",
        "direction",
        "setup_type",
        "session",
        "entry_context",
        "entry",
        "stop_loss",
        "take_profit",
        "score",
    ]
    return "|".join(str(trade.get(field, "")).strip().lower() for field in fields)


def _env_bool(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}
