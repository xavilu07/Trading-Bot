from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.agents.proposal_store import DEFAULT_PROPOSALS_PATH, load_proposals
from trading_signals.agents.research_memory import load_research_memory
from trading_signals.agents.strategy_knowledge_base import load_strategy_knowledge_base


def detect_qic_events(
    *,
    trades_path: Path = Path("data") / "paper_trading" / "trades.csv",
    proposal_store_path: Path = DEFAULT_PROPOSALS_PATH,
    strategy_knowledge_base_path: Path = Path("data") / "qic" / "strategy_knowledge_base.json",
    research_memory_path: Path = Path("data") / "qic" / "research_memory.json",
    code_engineer_report_path: Path = Path("reports") / "qic" / "code_engineer.json",
    pf_threshold: float = 1.0,
    losing_streak_threshold: int = 5,
    stale_proposal_hours: int = 48,
) -> dict[str, Any]:
    trades = _load_closed_trades(trades_path)
    events = []
    pf = _profit_factor(trades)
    if trades and pf < pf_threshold:
        events.append({"type": "pf_degradation", "severity": "critical", "profit_factor": pf})
    streak = _current_losing_streak(trades)
    if streak >= losing_streak_threshold:
        events.append({"type": "losing_streak", "severity": "critical", "count": streak})
    pending = [
        item
        for item in load_proposals(proposal_store_path)
        if str(item.get("status")) == "approved_for_implementation_review"
    ]
    if pending:
        events.append({"type": "approved_proposal_pending_implementation", "severity": "high", "count": len(pending)})
    structural = [
        item
        for item in load_proposals(proposal_store_path)
        if item.get("edge_type") == "STRUCTURAL_EDGE" and str(item.get("status") or "pending") == "pending"
    ]
    if structural:
        events.append({"type": "new_structural_edge", "severity": "high", "count": len(structural)})
    kb = load_strategy_knowledge_base(strategy_knowledge_base_path)
    memory = load_research_memory(research_memory_path)
    degraded = [item for item in (memory.get("experiments") or {}).values() if item.get("current_status") == "degraded"]
    if degraded:
        events.append({"type": "known_edge_degraded", "severity": "critical", "count": len(degraded)})
    invalidated = [item for item in (memory.get("experiments") or {}).values() if item.get("current_status") in {"retired", "invalidated"}]
    if invalidated:
        events.append({"type": "confirmed_edge_invalidated", "severity": "critical", "count": len(invalidated)})
    stale = [item for item in pending if _age_hours(item.get("reviewed_at") or item.get("created_at")) >= stale_proposal_hours]
    if stale:
        events.append({"type": "pending_proposal_stale", "severity": "high", "count": len(stale)})
    if pending:
        events.append({"type": "approved_proposal_waiting_implementation", "severity": "high", "count": len(pending)})
    blocked_items = [item for item in (kb.get("items") or {}).values() if item.get("implementation_status") == "blocked_preconditions"]
    code_engineer = _load_json(code_engineer_report_path)
    if blocked_items or code_engineer.get("status") == "failed_preconditions":
        events.append({"type": "code_engineer_blocked", "severity": "high", "count": len(blocked_items) or 1})
    shadow_required = [item for item in (kb.get("items") or {}).values() if item.get("implementation_status") == "patch_applied_shadow"]
    if shadow_required:
        events.append({"type": "shadow_monitoring_required", "severity": "medium", "count": len(shadow_required)})
    rolled_back = [item for item in (kb.get("items") or {}).values() if item.get("rollback_history")]
    if rolled_back:
        events.append({"type": "rollback_triggered", "severity": "critical", "count": len(rolled_back)})
    conflicts = _research_memory_conflicts(memory)
    if conflicts:
        events.append({"type": "research_memory_conflict", "severity": "medium", "count": len(conflicts)})
    return {
        "events": events,
        "critical": any(item.get("severity") == "critical" for item in events),
        "profit_factor": pf,
        "current_losing_streak": streak,
    }


def _load_closed_trades(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    closed_statuses = {"expired", "sl_hit", "tp1_hit", "tp2_hit", "closed", "win", "loss"}
    return [row for row in rows if str(row.get("status") or row.get("outcome") or "").lower() in closed_statuses]


def _r(row: dict[str, Any]) -> float:
    for key in ("result_r", "r_result", "realized_r"):
        try:
            return float(row.get(key) or 0)
        except (TypeError, ValueError):
            continue
    return 0.0


def _profit_factor(rows: list[dict[str, Any]]) -> float:
    wins = sum(_r(row) for row in rows if _r(row) > 0)
    losses = abs(sum(_r(row) for row in rows if _r(row) < 0))
    if losses == 0:
        return 999.0 if wins > 0 else 0.0
    return round(wins / losses, 4)


def _current_losing_streak(rows: list[dict[str, Any]]) -> int:
    streak = 0
    for row in reversed(rows):
        if _r(row) < 0:
            streak += 1
            continue
        break
    return streak


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _age_hours(value: Any) -> float:
    try:
        if not value:
            return 0.0
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        parsed = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        return (datetime.now(tz=UTC) - parsed).total_seconds() / 3600
    except ValueError:
        return 0.0


def _research_memory_conflicts(memory: dict[str, Any]) -> list[dict[str, Any]]:
    conflicts = []
    for item in (memory.get("experiments") or {}).values():
        if item.get("current_status") == "confirmed" and (item.get("last_revalidation_result") or {}).get("result") in {"edge_degraded", "edge_invalidated"}:
            conflicts.append(item)
    return conflicts
