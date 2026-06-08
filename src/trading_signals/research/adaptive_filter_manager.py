from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from trading_signals.data.canonical_trade_source import load_canonical_closed_trades, tokens


CONTEXTS = (
    "bullish_sweep",
    "against_htf_breakout",
    "bullish_sweep_ranging",
    "bullish_sweep_high_volatility",
    "new_york_ranging",
    "low_volume",
    "dirty_sideways_market",
    "choppy_range",
    "short_only",
    "secondary_signal",
    "directional_confluence_failed",
    "score_bucket_lt_60",
    "score_bucket_60_69",
    "score_bucket_80_89",
    "score_bucket_90_plus",
)
ALLOWED_MODES = {"observe", "shadow", "auto_safe"}
STATE_MAX_AGE_HOURS = 24


@dataclass(frozen=True, slots=True)
class AdaptiveFilterConfig:
    enabled: bool = False
    mode: str = "observe"
    min_closed: int = 30
    block_pf_threshold: float = 0.75
    block_total_r_threshold: float = -5.0
    unblock_pf_threshold: float = 1.20
    unblock_total_r_threshold: float = 5.0
    allowed_contexts: tuple[str, ...] = ("bullish_sweep", "against_htf_breakout")
    require_human_approval: bool = True
    current_blocks: tuple[str, ...] = ()


def config_from_settings(settings: object) -> AdaptiveFilterConfig:
    return AdaptiveFilterConfig(
        enabled=bool(getattr(settings, "adaptive_filter_enabled", False)),
        mode=str(getattr(settings, "adaptive_filter_mode", "observe") or "observe"),
        min_closed=int(getattr(settings, "adaptive_filter_min_closed", 30)),
        block_pf_threshold=float(getattr(settings, "adaptive_filter_block_pf_threshold", 0.75)),
        block_total_r_threshold=float(getattr(settings, "adaptive_filter_block_total_r_threshold", -5.0)),
        unblock_pf_threshold=float(getattr(settings, "adaptive_filter_unblock_pf_threshold", 1.20)),
        unblock_total_r_threshold=float(getattr(settings, "adaptive_filter_unblock_total_r_threshold", 5.0)),
        allowed_contexts=tuple(_normalize_contexts(getattr(settings, "adaptive_filter_allowed_contexts", ("bullish_sweep", "against_htf_breakout")))),
        require_human_approval=bool(getattr(settings, "adaptive_filter_require_human_approval", True)),
        current_blocks=tuple(_current_blocks_from_settings(settings)),
    )


def generate_adaptive_filter_manager_report(
    *,
    data_path: Path,
    reports_path: Path,
    runtime_path: Path,
    config: AdaptiveFilterConfig,
    now: datetime | None = None,
) -> dict[str, Any]:
    result = analyze_adaptive_filter_manager(data_path=data_path, config=config, now=now)
    reports_path.mkdir(parents=True, exist_ok=True)
    markdown_path = reports_path / "adaptive_filter_manager.md"
    json_path = reports_path / "adaptive_filter_manager.json"
    markdown_path.write_text(format_adaptive_filter_manager_markdown(result), encoding="utf-8")
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    state_path = runtime_path / "adaptive_filter_state.json"
    if config.mode in {"shadow", "auto_safe"}:
        write_adaptive_filter_state(result["adaptive_state"], state_path)
    return {**result, "report_path": str(markdown_path), "json_report_path": str(json_path), "state_path": str(state_path)}


def analyze_adaptive_filter_manager(
    *,
    data_path: Path,
    config: AdaptiveFilterConfig,
    now: datetime | None = None,
) -> dict[str, Any]:
    now_dt = _aware(now or datetime.now(tz=UTC))
    mode = _safe_mode(config.mode)
    trades = load_canonical_closed_trades(data_path)
    contexts = {context: _context_payload(context, trades, config=config, now=now_dt) for context in CONTEXTS}
    proposed_blocks = [name for name, payload in contexts.items() if payload["recommendation"] == "PROMOTE_TO_BLOCK"]
    proposed_unblocks = [name for name, payload in contexts.items() if payload["recommendation"] == "UNBLOCK_CANDIDATE"]
    active_blocks = _active_blocks_for_mode(config=config, mode=mode, proposed_blocks=proposed_blocks, proposed_unblocks=proposed_unblocks)
    production_block_status = _production_block_status(config)
    safety_warnings = _safety_warnings(config=config, mode=mode, proposed_blocks=proposed_blocks, contexts=contexts)
    state = {
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "mode": mode,
        "enabled": bool(config.enabled),
        "active_blocks": active_blocks,
        "proposed_blocks": proposed_blocks,
        "proposed_unblocks": proposed_unblocks,
        "contexts": contexts,
        "safety_warnings": safety_warnings,
        "human_approval_required": bool(config.require_human_approval),
        "production_block_status": production_block_status,
    }
    return {
        "scope": "ADAPTIVE_FILTER_MANAGER",
        "generated_at": now_dt.isoformat(timespec="seconds"),
        "data_path": str(data_path),
        "config": {
            "enabled": config.enabled,
            "mode": mode,
            "min_closed": config.min_closed,
            "block_pf_threshold": config.block_pf_threshold,
            "block_total_r_threshold": config.block_total_r_threshold,
            "unblock_pf_threshold": config.unblock_pf_threshold,
            "unblock_total_r_threshold": config.unblock_total_r_threshold,
            "allowed_contexts": list(config.allowed_contexts),
            "require_human_approval": config.require_human_approval,
            "current_blocks": list(config.current_blocks),
        },
        "production_block_status": production_block_status,
        "contexts": contexts,
        "adaptive_state": state,
    }


def write_adaptive_filter_state(state: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    return path


def should_block_by_adaptive_filter(
    evaluation: object,
    settings: object,
    *,
    state_path: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not bool(getattr(settings, "adaptive_filter_enabled", False)):
        return _block_result(False)
    mode = str(getattr(settings, "adaptive_filter_mode", "observe") or "observe")
    if mode != "auto_safe":
        return _block_result(False)
    if bool(getattr(settings, "adaptive_filter_require_human_approval", True)):
        return _block_result(False)
    path = state_path or Path(getattr(settings, "data_storage_path", "./data")) / "runtime" / "adaptive_filter_state.json"
    state = _load_state_fail_open(path)
    if not state:
        return _block_result(False)
    if not _state_is_fresh(state, now=_aware(now or datetime.now(tz=UTC))):
        return _block_result(False)
    if not bool(state.get("enabled")) or state.get("mode") != "auto_safe" or bool(state.get("human_approval_required")):
        return _block_result(False)
    allowed_contexts = set(_normalize_contexts(getattr(settings, "adaptive_filter_allowed_contexts", ())))
    active_blocks = set(_normalize_contexts(state.get("active_blocks", [])))
    for context in sorted(active_blocks):
        if context not in allowed_contexts:
            continue
        if context_matches(evaluation, context):
            return _block_result(True, reason=f"adaptive_filter:{context}", context=context)
    return _block_result(False)


def context_matches(row: object, context: str) -> bool:
    payload = _as_mapping(row)
    context = _normalize_context(context)
    if context == "bullish_sweep":
        return _is_bullish_sweep(payload)
    if context == "against_htf_breakout":
        return _is_against_htf_breakout(payload)
    if context == "bullish_sweep_ranging":
        return _is_bullish_sweep(payload) and _market_regime(payload) == "RANGING"
    if context == "bullish_sweep_high_volatility":
        return _is_bullish_sweep(payload) and _market_regime(payload) == "HIGH_VOLATILITY"
    if context == "new_york_ranging":
        return _session(payload) == "NEW_YORK" and _market_regime(payload) == "RANGING"
    if context == "low_volume":
        return "low_volume" in _all_tokens(payload)
    if context == "dirty_sideways_market":
        return "dirty_sideways_market" in _all_tokens(payload)
    if context == "choppy_range":
        return _entry_context(payload) == "CHOPPY_RANGE"
    if context == "short_only":
        return _direction(payload) == "short"
    if context == "secondary_signal":
        return _setup_type(payload) == "SECONDARY_SIGNAL"
    if context == "directional_confluence_failed":
        return "directional_confluence_failed" in _all_tokens(payload)
    if context == "score_bucket_lt_60":
        return _score_bucket(payload.get("score")) == "<60"
    if context == "score_bucket_60_69":
        return _score_bucket(payload.get("score")) == "60-69"
    if context == "score_bucket_80_89":
        return _score_bucket(payload.get("score")) == "80-89"
    if context == "score_bucket_90_plus":
        return _score_bucket(payload.get("score")) == "90+"
    return False


def format_adaptive_filter_manager_markdown(result: dict[str, Any]) -> str:
    state = result.get("adaptive_state", {})
    lines = [
        "# ADAPTIVE_FILTER_MANAGER",
        "",
        f"Generated at: {result.get('generated_at')}",
        f"Data path: {result.get('data_path')}",
        "Default posture: disabled/safe. This report is statistical observability and does not imply profitability.",
        "",
        "## State",
        "",
        f"- Enabled: {state.get('enabled', False)}",
        f"- Mode: {state.get('mode', 'observe')}",
        f"- Human approval required: {state.get('human_approval_required', True)}",
        f"- Active blocks: {', '.join(state.get('active_blocks', [])) or 'none'}",
        f"- Proposed blocks: {', '.join(state.get('proposed_blocks', [])) or 'none'}",
        f"- Proposed unblocks: {', '.join(state.get('proposed_unblocks', [])) or 'none'}",
        "",
        "## Production Block Status",
        "",
    ]
    production_status = result.get("production_block_status", {})
    for context in ("bullish_sweep", "against_htf_breakout"):
        lines.append(f"- {context}: {production_status.get(context, 'disabled')}")
    lines.extend(
        [
            "",
        "## Safety Warnings",
        "",
        ]
    )
    warnings = state.get("safety_warnings", [])
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Context Recommendations",
            "",
            "| Context | State | Closed | WR | PF | Total R | 7d PF | 30d PF | Recommendation | Survivor |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|---|",
        ]
    )
    for name, payload in result.get("contexts", {}).items():
        full = payload.get("full", {})
        last_7d = payload.get("last_7d", {})
        last_30d = payload.get("last_30d", {})
        lines.append(
            f"| {name} | {payload.get('current_state', 'unknown')} | {full.get('closed', 0)} | "
            f"{full.get('winrate', 0)}% | {full.get('profit_factor', 0)} | {full.get('total_r', 0)} | "
            f"{last_7d.get('profit_factor', 0)} | {last_30d.get('profit_factor', 0)} | "
            f"{payload.get('recommendation', 'WATCH')} | {payload.get('survivor_subgroup', {}).get('exists', False)} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def _context_payload(context: str, trades: list[dict[str, Any]], *, config: AdaptiveFilterConfig, now: datetime) -> dict[str, Any]:
    rows = [row for row in trades if context_matches(row, context)]
    survivor = _survivor_subgroup(rows)
    full = _metrics(rows)
    last_7d = _metrics(_since(rows, now - timedelta(days=7)))
    last_30d = _metrics(_since(rows, now - timedelta(days=30)))
    current_state = _current_state(context, config)
    recommendation = _recommendation(
        full=full,
        last_7d=last_7d,
        last_30d=last_30d,
        survivor=survivor,
        current_state=current_state,
        config=config,
    )
    return {
        "closed": full["closed"],
        "wins": full["wins"],
        "losses": full["losses"],
        "winrate": full["winrate"],
        "profit_factor": full["profit_factor"],
        "total_r": full["total_r"],
        "avg_r": full["avg_r"],
        "last_7d": last_7d,
        "last_30d": last_30d,
        "full": full,
        "current_state": current_state,
        "recommendation": recommendation,
        "survivor_subgroup": survivor,
    }


def _recommendation(
    *,
    full: dict[str, Any],
    last_7d: dict[str, Any],
    last_30d: dict[str, Any],
    survivor: dict[str, Any],
    current_state: str,
    config: AdaptiveFilterConfig,
) -> str:
    closed = int(full.get("closed", 0) or 0)
    pf = _pf_float(full.get("profit_factor"))
    total_r = float(full.get("total_r", 0.0) or 0.0)
    last_7d_pf = _pf_float(last_7d.get("profit_factor"))
    last_30d_pf = _pf_float(last_30d.get("profit_factor"))
    currently_blocked = current_state in {"blocked", "shadow_blocked"}
    if (
        currently_blocked
        and closed >= config.min_closed
        and pf >= config.unblock_pf_threshold
        and total_r >= config.unblock_total_r_threshold
        and (last_7d_pf >= 1.0 or last_30d_pf >= 1.0)
    ):
        return "UNBLOCK_CANDIDATE"
    if currently_blocked and (pf < 1.0 or total_r < 0):
        return "KEEP_BLOCKED"
    if (
        not currently_blocked
        and
        closed >= config.min_closed
        and pf <= config.block_pf_threshold
        and total_r <= config.block_total_r_threshold
        and (last_7d_pf <= 0.90 or last_30d_pf <= 0.90)
        and not bool(survivor.get("exists"))
    ):
        return "PROMOTE_TO_BLOCK"
    if closed >= config.min_closed and pf >= 1.10 and total_r > 0:
        return "KEEP_ALLOWED"
    return "WATCH"


def _active_blocks_for_mode(
    *,
    config: AdaptiveFilterConfig,
    mode: str,
    proposed_blocks: list[str],
    proposed_unblocks: list[str],
) -> list[str]:
    current = set(_normalize_contexts(config.current_blocks))
    if mode != "auto_safe" or not config.enabled or config.require_human_approval:
        return sorted(current)
    allowed = set(_normalize_contexts(config.allowed_contexts))
    active = set(current)
    active |= {context for context in proposed_blocks if context in allowed}
    active -= {context for context in proposed_unblocks if context in allowed}
    return sorted(active)


def _safety_warnings(
    *,
    config: AdaptiveFilterConfig,
    mode: str,
    proposed_blocks: list[str],
    contexts: dict[str, dict[str, Any]],
) -> list[str]:
    warnings = []
    if not config.enabled:
        warnings.append("adaptive_filter_disabled")
    if mode == "auto_safe" and config.require_human_approval:
        warnings.append("auto_safe_blocked_by_human_approval_requirement")
    disallowed = sorted(set(_normalize_contexts(proposed_blocks)) - set(_normalize_contexts(config.allowed_contexts)))
    if disallowed:
        warnings.append(f"proposals_outside_allowed_contexts:{','.join(disallowed)}")
    if mode not in ALLOWED_MODES:
        warnings.append("invalid_mode_fell_back_to_observe")
    for context in ("short_only", "secondary_signal", "directional_confluence_failed"):
        if contexts.get(context, {}).get("recommendation") == "KEEP_ALLOWED":
            warnings.append(f"context_regime_shift_detected:{context}")
    return warnings


def _production_block_status(config: AdaptiveFilterConfig) -> dict[str, str]:
    current = set(_normalize_contexts(config.current_blocks))
    return {
        "bullish_sweep": "enabled" if "bullish_sweep" in current else "disabled",
        "against_htf_breakout": "enabled" if "against_htf_breakout" in current else "disabled",
    }


def _survivor_subgroup(rows: list[dict[str, Any]]) -> dict[str, Any]:
    best: dict[str, Any] | None = None
    for dimension in ("symbol", "session", "direction", "setup_type", "market_regime", "entry_context"):
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            groups[_field_value(row, dimension)].append(row)
        for value, group_rows in groups.items():
            metrics = _metrics(group_rows)
            if int(metrics.get("closed", 0) or 0) >= 20 and _pf_float(metrics.get("profit_factor")) > 1.25:
                candidate = {"exists": True, "dimension": dimension, "value": value, "metrics": metrics}
                if best is None or float(metrics.get("total_r", 0.0) or 0.0) > float(best["metrics"].get("total_r", 0.0) or 0.0):
                    best = candidate
    return best or {"exists": False}


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [_float(row.get("result_r")) for row in rows]
    values = [value for value in values if value is not None]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "closed": len(values),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": _round(len(wins) / len(values) * 100) if values else 0.0,
        "profit_factor": _profit_factor(gross_profit, gross_loss),
        "total_r": _round(sum(values)),
        "avg_r": _round(sum(values) / len(values)) if values else 0.0,
    }


def _since(rows: list[dict[str, Any]], start: datetime) -> list[dict[str, Any]]:
    return [row for row in rows if (timestamp := _timestamp(row)) is not None and timestamp >= start]


def _current_state(context: str, config: AdaptiveFilterConfig) -> str:
    normalized = _normalize_context(context)
    if normalized in set(_normalize_contexts(config.current_blocks)):
        return "blocked"
    return "allowed"


def _current_blocks_from_settings(settings: object) -> list[str]:
    blocks = []
    if bool(getattr(settings, "bullish_sweep_block_enabled", False)):
        blocks.append("bullish_sweep")
    if bool(getattr(settings, "against_htf_breakout_block_enabled", False)):
        blocks.append("against_htf_breakout")
    return blocks


def _load_state_fail_open(path: Path) -> dict[str, Any] | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _state_is_fresh(state: dict[str, Any], *, now: datetime) -> bool:
    generated_at = str(state.get("generated_at") or "").strip()
    if not generated_at:
        return False
    try:
        parsed = _aware(datetime.fromisoformat(generated_at.replace("Z", "+00:00")))
    except ValueError:
        return False
    return now - parsed <= timedelta(hours=STATE_MAX_AGE_HOURS)


def _block_result(blocked: bool, reason: str | None = None, context: str | None = None) -> dict[str, Any]:
    return {"blocked": blocked, "reason": reason, "context": context}


def _safe_mode(mode: str) -> str:
    normalized = str(mode or "observe").strip().lower()
    return normalized if normalized in ALLOWED_MODES else "observe"


def _normalize_contexts(value: object) -> list[str]:
    if isinstance(value, str):
        raw = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = []
    return [_normalize_context(item) for item in raw if _normalize_context(item)]


def _normalize_context(value: object) -> str:
    return str(value or "").strip().lower()


def _as_mapping(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    result: dict[str, Any] = {}
    for name in (
        "symbol",
        "direction",
        "score",
        "setup_type",
        "market_regime",
        "session",
        "entry_context",
        "liquidity_context",
        "liquidity_sweep",
        "warnings",
        "avoidance_warnings",
        "penalties",
        "rejection_reasons",
        "conditions_failed",
        "reasons",
        "htf_alignment",
        "trend_higher",
        "trend_higher_timeframe",
        "trend_4h",
    ):
        if hasattr(value, name):
            result[name] = getattr(value, name)
    details = getattr(value, "details", None)
    if isinstance(details, dict):
        result.update(details)
    return result


def _all_tokens(row: dict[str, Any]) -> set[str]:
    return (
        tokens(row.get("warnings"))
        | tokens(row.get("avoidance_warnings"))
        | tokens(row.get("rejection_reasons"))
        | tokens(row.get("conditions_failed"))
        | tokens(row.get("penalties"))
        | tokens(row.get("reasons"))
    )


def _field_value(row: dict[str, Any], field: str) -> str:
    if field == "direction":
        return _direction(row)
    if field == "setup_type":
        return _setup_type(row)
    if field == "market_regime":
        return _market_regime(row)
    if field == "session":
        return _session(row)
    if field == "entry_context":
        return _entry_context(row)
    return str(row.get(field) or "UNKNOWN")


def _is_bullish_sweep(row: dict[str, Any]) -> bool:
    return _liquidity_context(row) == "sweep:bullish_sweep"


def _is_against_htf_breakout(row: dict[str, Any]) -> bool:
    return _entry_context(row) == "BREAKOUT" and _is_against_htf(row)


def _is_against_htf(row: dict[str, Any]) -> bool:
    return "against_htf" in _all_tokens(row) or _htf_alignment(row) == "against_htf"


def _liquidity_context(row: dict[str, Any]) -> str:
    explicit = str(row.get("liquidity_context") or "").strip()
    if explicit:
        return explicit
    sweep = str(row.get("liquidity_sweep") or "").strip()
    if sweep:
        return f"sweep:{sweep}"
    location = str(row.get("trade_location") or "").strip()
    if location and location.upper() != "UNKNOWN":
        return f"location:{location}"
    return "UNKNOWN"


def _htf_alignment(row: dict[str, Any]) -> str:
    explicit = str(row.get("htf_alignment") or "").strip().lower()
    if explicit:
        return explicit
    direction = _direction(row)
    higher = str(row.get("trend_higher") or row.get("trend_4h") or row.get("trend_higher_timeframe") or "").strip().lower()
    if not direction or not higher:
        return "UNKNOWN"
    if direction == "long" and higher == "bearish":
        return "against_htf"
    if direction == "short" and higher == "bullish":
        return "against_htf"
    if direction == "long" and higher == "bullish":
        return "aligned_with_htf"
    if direction == "short" and higher == "bearish":
        return "aligned_with_htf"
    return f"htf_{higher}"


def _direction(row: dict[str, Any]) -> str:
    return str(row.get("direction") or "unknown").strip().lower()


def _setup_type(row: dict[str, Any]) -> str:
    return str(row.get("setup_type") or "UNKNOWN").strip().upper()


def _market_regime(row: dict[str, Any]) -> str:
    return str(row.get("market_regime") or "UNKNOWN").strip().upper()


def _session(row: dict[str, Any]) -> str:
    return str(row.get("session") or "UNKNOWN").strip().upper()


def _entry_context(row: dict[str, Any]) -> str:
    return str(row.get("entry_context") or "UNKNOWN").strip().upper()


def _score_bucket(value: object) -> str:
    score = _float(value)
    if score is None:
        return "UNKNOWN"
    if score < 60:
        return "<60"
    if score < 70:
        return "60-69"
    if score < 80:
        return "70-79"
    if score < 90:
        return "80-89"
    return "90+"


def _timestamp(row: dict[str, Any]) -> datetime | None:
    raw = str(row.get("timestamp") or row.get("closed_at") or row.get("opened_at") or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _aware(parsed)


def _profit_factor(gross_profit: float, gross_loss: float) -> float | str:
    if gross_loss > 0:
        return _round(gross_profit / gross_loss)
    if gross_profit > 0:
        return "inf"
    return 0.0


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float) -> float:
    rounded = round(value, 4)
    return 0.0 if rounded == 0 else rounded


def _pf_float(value: object) -> float:
    if value == "inf":
        return 999.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
