from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.agents.qic_runtime import atomic_write_json, read_json_safe

# Separate from kill_switch.py's own cooldown (which self-resumes once the rolling loss
# window ages out): this is a persistent latch that only clears via resume_trading(), so a
# trip always requires a human to explicitly resume, never a timer. New candidates only —
# never touches trades that are already open.
DEFAULT_PAUSE_PATH = Path("data") / "runtime" / "trading_paused.json"


def is_trading_paused(path: Path = DEFAULT_PAUSE_PATH) -> dict[str, Any]:
    state = read_json_safe(path, {})
    if not isinstance(state, dict) or not state.get("paused"):
        return {"paused": False}
    return state


def pause_trading(
    *,
    reason: str,
    details: dict[str, Any] | None = None,
    path: Path = DEFAULT_PAUSE_PATH,
) -> dict[str, Any]:
    existing = read_json_safe(path, {})
    if isinstance(existing, dict) and existing.get("paused"):
        return existing
    state = {
        "paused": True,
        "reason": reason,
        "details": details or {},
        "paused_at": _now(),
        "resume_requires": "manual",
    }
    atomic_write_json(path, state)
    return state


def resume_trading(*, actor: str, path: Path = DEFAULT_PAUSE_PATH) -> dict[str, Any]:
    state = {"paused": False, "resumed_by": actor, "resumed_at": _now()}
    atomic_write_json(path, state)
    return state


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()
