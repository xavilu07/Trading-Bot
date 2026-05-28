from __future__ import annotations

import os
from typing import Any

from trading_signals.application.policies.public_canary_policy import PublicShortCanaryConfig, evaluate_public_short_canary


POLICY_VERSION = "v1"
DANGEROUS_CLASSIFICATIONS = {"DANGEROUS", "AVOID_PUBLIC"}


def evaluate_public_safety_policy(
    *,
    signal=None,
    evaluation_or_decision=None,
    setup_context: dict[str, Any] | None = None,
    public_block_reason: str | None = None,
    public_short_canary_config: PublicShortCanaryConfig | None = None,
) -> dict[str, Any]:
    context = setup_context or {}
    block_reasons: list[str] = []
    warnings_out: list[str] = []
    direction = str(getattr(signal, "decision", context.get("direction", "")) or "").strip().lower()
    setup_type = str(
        context.get("setup_type")
        or getattr(evaluation_or_decision, "setup_type", "")
        or _infer_setup_type(evaluation_or_decision)
    ).strip().upper()
    market_regime = str(context.get("market_regime", "") or "").strip().upper()
    entry_context = str(context.get("entry_context", "") or "").strip().upper()
    trade_location = str(context.get("trade_location", "") or "").strip()
    trend_higher = str(context.get("trend_higher") or context.get("trend_4h") or "").strip().lower()
    warnings = _normalized_items(context.get("avoidance_warnings", [])) | _normalized_items(context.get("warnings", []))
    penalties = _normalized_items(context.get("penalties", []))
    penalties |= _trace_penalty_tokens(getattr(evaluation_or_decision, "decision_trace", []))

    _add_external_block(block_reasons, public_block_reason)
    _add_kill_switch_blocks(block_reasons, context)
    _add_meta_blocks(block_reasons, context)

    if market_regime == "RANGING":
        block_reasons.append("market_regime_ranging")
    elif market_regime and market_regime != "TRENDING":
        block_reasons.append("market_regime_not_trending")
    if entry_context == "CHOPPY_RANGE":
        block_reasons.append("entry_context_choppy_range")
    if trade_location == "premium_zone":
        block_reasons.append("trade_location_premium_zone")
    if (
        entry_context == "BREAKOUT"
        and {"market_structure_range_penalty", "timeframe_alignment_penalty"}.issubset(penalties)
    ):
        block_reasons.append("bad_breakout_context")
    if entry_context == "BREAKOUT" and trade_location in {"near_support", "near_resistance"}:
        block_reasons.append("breakout_bad_location")
    if entry_context == "BREAKOUT" and _htf_contradicts(direction, trend_higher):
        block_reasons.append("breakout_against_htf")
    if setup_type == "SECONDARY_SIGNAL":
        block_reasons.append("setup_type_secondary_signal")
    short_shadow_mode = _short_shadow_enabled(context)
    if short_shadow_mode and direction == "short":
        block_reasons.append("short_shadow_mode")
    if direction == "short" and not _has_high_historical_edge(context):
        block_reasons.append("short_without_high_historical_edge")
    if "against_htf" in warnings:
        block_reasons.append("against_htf")
    if "low_volume" in warnings:
        block_reasons.append("low_volume")
    if "dirty_sideways_market" in warnings:
        block_reasons.append("dirty_sideways_market")

    dangerous_context_reason = _dangerous_context_reason(context)
    if dangerous_context_reason:
        block_reasons.append(dangerous_context_reason)

    if "market_structure_range_penalty" in penalties:
        warnings_out.append("market_structure_range_penalty")
    if "timeframe_alignment_penalty" in penalties:
        warnings_out.append("timeframe_alignment_penalty")
    if any(item.startswith("secondary_confluence_bonus") for item in penalties):
        warnings_out.append("secondary_confluence_bonus")

    edge_activation_mode = _edge_activation_enabled(context)
    edge_activation_reasons = _edge_activation_reasons(
        context=context,
        direction=direction,
        setup_type=setup_type,
        market_regime=market_regime,
        entry_context=entry_context,
        trade_location=trade_location,
        block_reasons=block_reasons,
    )
    edge_activation_allowed = not edge_activation_mode or not edge_activation_reasons
    if edge_activation_mode:
        block_reasons.extend(edge_activation_reasons)

    canary = evaluate_public_short_canary(
        signal=signal,
        evaluation_or_decision=evaluation_or_decision,
        setup_context=context,
        config=public_short_canary_config or _public_short_canary_config_from_env(),
    )
    if canary["public_canary_match"]:
        block_reasons = _remove_canary_overridden_short_blocks(block_reasons)
        edge_activation_reasons = _remove_canary_overridden_edge_reasons(edge_activation_reasons)
        edge_activation_allowed = not edge_activation_mode or not edge_activation_reasons

    block_reasons = _dedupe(block_reasons)
    return {
        "public_allowed": not block_reasons,
        "block_reasons": block_reasons,
        "warnings": _dedupe(warnings_out),
        "policy_version": POLICY_VERSION,
        "edge_activation_mode": edge_activation_mode,
        "edge_activation_allowed": edge_activation_allowed,
        "edge_activation_reasons": _dedupe(edge_activation_reasons),
        "short_shadow_mode": short_shadow_mode,
        "public_canary_decision": canary["public_canary_decision"],
        "public_canary_match": canary["public_canary_match"],
        "public_canary_reason": canary["public_canary_reason"],
        "public_canary": canary,
    }


def _add_external_block(block_reasons: list[str], public_block_reason: str | None) -> None:
    if not public_block_reason:
        return
    reason = str(public_block_reason)
    if reason.startswith("kill_switch"):
        block_reasons.append("kill_switch_active")
    elif reason == "meta_decision_reject":
        block_reasons.append("meta_decision_reject")
    elif reason == "capital_preservation_mode":
        block_reasons.append("capital_preservation_mode")
    elif reason == "trade_quality_trash":
        block_reasons.append("trade_quality_trash")
    else:
        block_reasons.append(reason)


def _add_kill_switch_blocks(block_reasons: list[str], context: dict[str, Any]) -> None:
    kill_switch = _dict(context.get("kill_switch"))
    active = context.get("kill_switch_active")
    if active is None:
        active = kill_switch.get("kill_switch_active")
    if _truthy(active):
        block_reasons.append("kill_switch_active")


def _add_meta_blocks(block_reasons: list[str], context: dict[str, Any]) -> None:
    pattern_memory = _dict(context.get("pattern_memory"))
    meta_decision = _dict(context.get("meta_decision")) or _dict(pattern_memory.get("meta_decision"))
    trade_quality = _dict(context.get("trade_quality")) or _dict(pattern_memory.get("trade_quality"))
    meta_value = context.get("meta_decision")
    if isinstance(meta_value, str) and meta_value.upper() == "REJECT":
        block_reasons.append("meta_decision_reject")
    if str(meta_decision.get("meta_decision", "")).upper() == "REJECT":
        block_reasons.append("meta_decision_reject")
    if _truthy(context.get("capital_preservation_mode")) or _truthy(meta_decision.get("capital_preservation_mode")):
        block_reasons.append("capital_preservation_mode")
    quality_value = context.get("trade_quality_grade")
    if isinstance(quality_value, str) and quality_value.upper() == "TRASH":
        block_reasons.append("trade_quality_trash")
    if str(trade_quality.get("trade_quality_grade", "")).upper() == "TRASH":
        block_reasons.append("trade_quality_trash")


def _dangerous_context_reason(context: dict[str, Any]) -> str:
    classification = str(
        context.get("strategy_opportunity_classification")
        or context.get("opportunity_classification")
        or ""
    ).upper()
    if classification in DANGEROUS_CLASSIFICATIONS:
        return f"strategy_opportunity_{classification.lower()}"
    dangerous = context.get("dangerous_contexts")
    if isinstance(dangerous, list):
        values = {str(item).strip() for item in dangerous}
        candidates = {
            str(context.get("market_regime", "")).strip(),
            str(context.get("entry_context", "")).strip(),
            str(context.get("trade_location", "")).strip(),
            str(context.get("setup_type", "")).strip(),
            str(context.get("direction", "")).strip(),
        }
        if values & candidates:
            return "strategy_opportunity_dangerous_context"
    return ""


def _has_high_historical_edge(context: dict[str, Any]) -> bool:
    candidates = [
        context,
        _dict(context.get("historical_edge")),
        _dict(context.get("edge_score")),
        _dict(context.get("pattern_memory")).get("historical_edge"),
        _dict(context.get("pattern_memory")).get("edge_score"),
    ]
    for item in candidates:
        data = _dict(item)
        if str(data.get("historical_confidence") or data.get("confidence_level") or "").upper() == "HIGH":
            return True
    return False


def _edge_activation_enabled(context: dict[str, Any]) -> bool:
    if "edge_activation_mode" in context:
        return _truthy(context.get("edge_activation_mode"))
    return _truthy(os.getenv("EDGE_ACTIVATION_MODE", "true"))


def _short_shadow_enabled(context: dict[str, Any]) -> bool:
    if "short_shadow_mode" in context:
        return _truthy(context.get("short_shadow_mode"))
    return _truthy(os.getenv("SHORT_SHADOW_MODE", "true"))


def _public_short_canary_config_from_env() -> PublicShortCanaryConfig:
    return PublicShortCanaryConfig(
        enabled=_truthy(os.getenv("PUBLIC_SHORT_CANARY_ENABLED", "false")),
        session=os.getenv("PUBLIC_SHORT_CANARY_SESSION", "LONDON"),
        direction=os.getenv("PUBLIC_SHORT_CANARY_DIRECTION", "SHORT"),
        entry_context=os.getenv("PUBLIC_SHORT_CANARY_ENTRY_CONTEXT", "PULLBACK"),
        setup_type=os.getenv("PUBLIC_SHORT_CANARY_SETUP_TYPE", "MAIN_SIGNAL"),
        min_score=float(os.getenv("PUBLIC_SHORT_CANARY_MIN_SCORE", "70")),
    )


def _remove_canary_overridden_short_blocks(block_reasons: list[str]) -> list[str]:
    allowed_overrides = {
        "short_shadow_mode",
        "short_without_high_historical_edge",
        "edge_activation_requires_long",
        "edge_activation_requires_overlap_session",
    }
    return [reason for reason in block_reasons if reason not in allowed_overrides]


def _remove_canary_overridden_edge_reasons(edge_reasons: list[str]) -> list[str]:
    allowed_overrides = {"edge_activation_requires_long", "edge_activation_requires_overlap_session"}
    return [reason for reason in edge_reasons if reason not in allowed_overrides]


def _edge_activation_reasons(
    *,
    context: dict[str, Any],
    direction: str,
    setup_type: str,
    market_regime: str,
    entry_context: str,
    trade_location: str,
    block_reasons: list[str],
) -> list[str]:
    reasons: list[str] = []
    if market_regime != "TRENDING":
        reasons.append("edge_activation_requires_trending")
    if str(context.get("session", "") or "").strip().upper() != "OVERLAP":
        reasons.append("edge_activation_requires_overlap_session")
    if direction != "long":
        reasons.append("edge_activation_requires_long")
    if entry_context == "CHOPPY_RANGE":
        reasons.append("edge_activation_choppy_range")
    if trade_location == "premium_zone":
        reasons.append("edge_activation_premium_zone")
    if setup_type == "SECONDARY_SIGNAL":
        reasons.append("edge_activation_secondary_signal")
    if "trade_quality_trash" in block_reasons:
        reasons.append("edge_activation_trade_quality_trash")
    if "meta_decision_reject" in block_reasons:
        reasons.append("edge_activation_meta_decision_reject")
    if "capital_preservation_mode" in block_reasons:
        reasons.append("edge_activation_capital_preservation_mode")
    if "kill_switch_active" in block_reasons:
        reasons.append("edge_activation_kill_switch_active")
    return _dedupe(reasons)


def _infer_setup_type(evaluation_or_decision) -> str:
    passed_filters = list(getattr(evaluation_or_decision, "passed_filters", []))
    return "SECONDARY_SIGNAL" if "secondary_setup" in passed_filters else "MAIN_SIGNAL"


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
        if text.startswith("penalties="):
            tokens |= _normalized_items(text.split("=", 1)[1])
    return tokens


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
