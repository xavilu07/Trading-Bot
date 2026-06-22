from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.application.use_cases.signal_lifecycle import active_published_signals, has_reentry_confirmation


UPDATE_STRENGTHENED = "STRENGTHENED_SIGNAL"
UPDATE_REENTRY = "REENTRY_CANDIDATE"
UPDATE_INVALIDATION = "INVALIDATION_WARNING"
UPDATE_NONE = "NO_UPDATE"

ACTIVE_SIGNAL_REASONS = {
    "duplicate_signal_suppressed",
    "active_same_symbol_direction_without_reentry",
    "max_reentries_reached",
}


@dataclass(frozen=True)
class SignalUpdateV1Decision:
    detected: bool
    update_type: str
    symbol: str
    direction: str
    score: float | None
    active_score: float | None
    rr: float | None
    active_rr: float | None
    active_signal_id: str | None
    active_dedupe_key: str | None
    current_dedupe_key: str | None
    new_snapshot: bool
    reentry_confirmation: bool
    shadow_only: bool
    public_allowed: bool
    dev_note_enabled: bool
    reasons: list[str]
    risks: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_signal_update_v1(
    *,
    signal_repo,
    signal,
    evaluation,
    entry_snapshot,
    risk_plan=None,
    setup_context: dict[str, object] | None = None,
    is_duplicate: bool = False,
    lifecycle=None,
    dev_note_enabled: bool = False,
) -> SignalUpdateV1Decision | None:
    """Classify a valid signal blocked by active same-symbol/direction duplicate gates.

    This is intentionally shadow-only: the returned decision never grants publishability.
    """

    block_reasons = _active_signal_block_reasons(is_duplicate=is_duplicate, lifecycle=lifecycle)
    if not block_reasons:
        return None

    active = active_published_signals(signal_repo, symbol=signal.symbol, direction=signal.decision, limit=500)
    if not active:
        return None

    active_signal = _latest_active_signal(active)
    active_dedupe = _str_or_none(active_signal.get("dedupe_key"))
    current_dedupe = _str_or_none(getattr(signal, "dedupe_key", None))
    active_score = _extract_active_score(active_signal)
    current_score = _float(getattr(evaluation, "setup_score", None))
    active_rr = _extract_active_rr(active_signal)
    current_rr = _current_rr(risk_plan=risk_plan, setup_context=setup_context)
    new_snapshot = bool(active_dedupe and current_dedupe and active_dedupe != current_dedupe)
    reentry_confirmation = bool(has_reentry_confirmation(entry_snapshot, evaluation))

    risks = _context_risks(evaluation=evaluation, setup_context=setup_context, risk_plan=risk_plan)
    reasons: list[str] = list(block_reasons)
    update_type = UPDATE_NONE

    if risks:
        update_type = UPDATE_INVALIDATION
        reasons.append("context_worsened")
    elif active_score is not None and current_score is not None and current_score >= active_score:
        update_type = UPDATE_STRENGTHENED
        reasons.append("score_not_lower_than_active")
    elif active_rr is not None and current_rr is not None and current_rr > active_rr:
        update_type = UPDATE_STRENGTHENED
        reasons.append("rr_improved_vs_active")
    elif new_snapshot and reentry_confirmation:
        update_type = UPDATE_REENTRY
        reasons.append("new_snapshot_with_reentry_confirmation")
    else:
        reasons.append("no_material_update")

    return SignalUpdateV1Decision(
        detected=True,
        update_type=update_type,
        symbol=str(signal.symbol),
        direction=str(signal.decision),
        score=current_score,
        active_score=active_score,
        rr=current_rr,
        active_rr=active_rr,
        active_signal_id=_str_or_none(active_signal.get("id")),
        active_dedupe_key=active_dedupe,
        current_dedupe_key=current_dedupe,
        new_snapshot=new_snapshot,
        reentry_confirmation=reentry_confirmation,
        shadow_only=True,
        public_allowed=False,
        dev_note_enabled=bool(dev_note_enabled),
        reasons=list(dict.fromkeys(reasons)),
        risks=list(dict.fromkeys(risks)),
    )


def format_signal_update_v1_dev_message(update: SignalUpdateV1Decision) -> str:
    return (
        "🧪 SIGNAL UPDATE V1\n"
        "Shadow/dev only. No publicada como nueva señal.\n"
        f"{update.symbol} {update.direction.upper()}\n"
        f"Tipo: {update.update_type}\n"
        f"Score: {_format_number(update.score)} | RR: {_format_number(update.rr)}\n"
        f"Active score: {_format_number(update.active_score)} | Active RR: {_format_number(update.active_rr)}\n"
        f"Razones: {', '.join(update.reasons[:4]) or 'none'}"
    )


def write_signal_update_v1_shadow_report(
    *,
    reports_path: Path,
    update: SignalUpdateV1Decision | dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "signal_update_v1_shadow.json"
    existing = _read_existing_shadow(path)
    events = list(existing.get("events", []))
    if update is not None:
        payload = update.to_dict() if isinstance(update, SignalUpdateV1Decision) else dict(update)
        payload["recorded_at"] = generated_at or _now_iso()
        events.append(payload)
    events = events[-100:]
    summary = _summarize_events(events)
    path.write_text(
        json.dumps(
            {
                "generated_at": generated_at or _now_iso(),
                "mode": "shadow_dev_only",
                "public_behavior_changed": False,
                "duplicate_signal_suppressed_still_blocks": True,
                "summary": summary,
                "events": events,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def write_signal_update_v1_design_report(reports_path: Path) -> Path:
    reports_path.mkdir(parents=True, exist_ok=True)
    path = reports_path / "signal_update_v1_design.md"
    path.write_text(
        "\n".join(
            [
                "# SIGNAL_UPDATE_V1 Design",
                "",
                "Mode: shadow/dev only.",
                "",
                "## Objective",
                "Detect valid candidates blocked by `duplicate_signal_suppressed` or by active same symbol+direction lifecycle gates and classify whether they are useful updates to an already active signal.",
                "",
                "## Non-goals",
                "- No public Telegram publication.",
                "- No duplicate signal creation.",
                "- No strategy/filter changes.",
                "- No paper/live execution changes.",
                "",
                "## Detection",
                "A candidate is observed only when it remains `VALID` but is blocked by one of:",
                "- `duplicate_signal_suppressed`",
                "- `active_same_symbol_direction_without_reentry`",
                "- `max_reentries_reached`",
                "",
                "The active reference is the latest published signal with the same `symbol` and `direction`.",
                "",
                "## Classification",
                "- `STRENGTHENED_SIGNAL`: current score is not lower than active score, or RR improves.",
                "- `REENTRY_CANDIDATE`: new dedupe snapshot/candle plus existing reentry confirmation logic.",
                "- `INVALIDATION_WARNING`: context worsens through failed RR, choppy/ranging context, harmful warnings, or failed quality/confluence filters.",
                "- `NO_UPDATE`: duplicate remains informationally redundant.",
                "",
                "## Runtime events",
                "- `signal_update_v1_detected`",
                "- `signal_update_v1_classified`",
                "- `signal_update_v1_shadow_decision`",
                "",
                "## Safety",
                "The update always returns `public_allowed=false` and never changes the existing publishability branch. DEV notification is optional behind `SIGNAL_UPDATE_V1_DEV_NOTE_ENABLED=false` by default.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _active_signal_block_reasons(*, is_duplicate: bool, lifecycle) -> list[str]:
    reasons: list[str] = []
    if is_duplicate:
        reasons.append("duplicate_signal_suppressed")
    if lifecycle is not None and not bool(getattr(lifecycle, "should_publish", False)):
        reason = str(getattr(lifecycle, "reason", "") or "")
        if reason in ACTIVE_SIGNAL_REASONS:
            reasons.append(reason)
    return list(dict.fromkeys(reasons))


def _latest_active_signal(active: list[dict[str, object]]) -> dict[str, object]:
    return sorted(
        active,
        key=lambda item: str(item.get("published_at") or item.get("created_at") or ""),
        reverse=True,
    )[0]


def _extract_active_score(active_signal: dict[str, object]) -> float | None:
    for key in ("score", "setup_score", "total_score"):
        value = _float(active_signal.get(key))
        if value is not None:
            return value
    return None


def _extract_active_rr(active_signal: dict[str, object]) -> float | None:
    for key in ("rr", "risk_reward", "risk_reward_ratio"):
        value = _float(active_signal.get(key))
        if value is not None:
            return value
    risk_plan = active_signal.get("risk_plan")
    if isinstance(risk_plan, dict):
        return _float(risk_plan.get("risk_reward"))
    return None


def _current_rr(*, risk_plan, setup_context: dict[str, object] | None) -> float | None:
    value = _float(getattr(risk_plan, "risk_reward", None))
    if value is not None:
        return value
    context = setup_context or {}
    for key in ("rr", "risk_reward", "risk_reward_ratio"):
        value = _float(context.get(key))
        if value is not None:
            return value
    return None


def _context_risks(*, evaluation, setup_context: dict[str, object] | None, risk_plan) -> list[str]:
    risks: list[str] = []
    context = setup_context or {}
    failed = {str(item) for item in getattr(evaluation, "failed_filters", []) or []}
    rejected = {str(item) for item in getattr(evaluation, "rejection_reasons", []) or []}
    warnings = {str(item) for item in context.get("avoidance_warnings", []) or []}

    if risk_plan is None:
        risks.append("risk_plan_missing")
    if "directional_confluence_failed" in failed or "directional_confluence_failed" in rejected:
        risks.append("directional_confluence_failed")
    if "quality_score_failed" in rejected:
        risks.append("quality_score_failed")
    if "body_ratio_below_threshold" in failed:
        risks.append("body_ratio_below_threshold")
    if "against_htf" in warnings:
        risks.append("against_htf")
    if str(context.get("entry_context", "")).upper() == "CHOPPY_RANGE":
        risks.append("choppy_range")
    if str(context.get("market_regime", "")).upper() == "RANGING":
        risks.append("market_regime_ranging")
    return risks


def _read_existing_shadow(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for event in events:
        update_type = str(event.get("update_type") or "UNKNOWN")
        counts[update_type] = counts.get(update_type, 0) + 1
    return {
        "total_events": len(events),
        "by_update_type": counts,
        "latest_update_type": str(events[-1].get("update_type")) if events else None,
    }


def _format_number(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()
