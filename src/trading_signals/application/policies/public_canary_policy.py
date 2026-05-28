from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PublicShortCanaryConfig:
    enabled: bool = False
    session: str = "LONDON"
    direction: str = "SHORT"
    entry_context: str = "PULLBACK"
    setup_type: str = "MAIN_SIGNAL"
    min_score: float = 70.0


def evaluate_public_short_canary(
    *,
    signal=None,
    evaluation_or_decision=None,
    setup_context: dict[str, Any] | None = None,
    config: PublicShortCanaryConfig | None = None,
) -> dict[str, Any]:
    cfg = config or PublicShortCanaryConfig()
    context = setup_context or {}
    direction = str(getattr(signal, "decision", context.get("direction", "")) or "").strip().upper()
    session = str(context.get("session", "") or "").strip().upper()
    entry_context = str(context.get("entry_context", "") or "").strip().upper()
    setup_type = str(context.get("setup_type") or getattr(evaluation_or_decision, "setup_type", "") or "").strip().upper()
    score = _score(evaluation_or_decision, context)
    checks = {
        "enabled": cfg.enabled,
        "direction": direction == cfg.direction.upper(),
        "session": session == cfg.session.upper(),
        "entry_context": entry_context == cfg.entry_context.upper(),
        "setup_type": setup_type == cfg.setup_type.upper(),
        "score": score >= cfg.min_score,
    }
    reasons = [f"canary_{name}_mismatch" for name, passed in checks.items() if name != "enabled" and not passed]
    if not cfg.enabled:
        reasons.insert(0, "canary_disabled")
    match = bool(cfg.enabled and all(checks.values()))
    return {
        "public_canary_decision": "allow" if match else "block",
        "public_canary_match": match,
        "public_canary_reason": "matched" if match else "|".join(reasons),
        "public_canary_enabled": cfg.enabled,
        "symbol": str(getattr(signal, "symbol", context.get("symbol", "")) or "").upper(),
        "direction": direction,
        "score": score,
        "session": session,
        "entry_context": entry_context,
        "setup_type": setup_type,
        "checks": checks,
    }


def _score(evaluation_or_decision, context: dict[str, Any]) -> float:
    for value in (
        context.get("score"),
        context.get("setup_score"),
        getattr(evaluation_or_decision, "setup_score", None),
        getattr(evaluation_or_decision, "total_score", None),
    ):
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0
