from __future__ import annotations

from typing import Any


POLICY_VERSION = "v1"
DANGEROUS_CLASSIFICATIONS = {"DANGEROUS", "AVOID_PUBLIC"}


def evaluate_public_safety_policy(
    *,
    signal=None,
    evaluation_or_decision=None,
    setup_context: dict[str, Any] | None = None,
    public_block_reason: str | None = None,
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

    block_reasons = _dedupe(block_reasons)
    return {
        "public_allowed": not block_reasons,
        "block_reasons": block_reasons,
        "warnings": _dedupe(warnings_out),
        "policy_version": POLICY_VERSION,
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
