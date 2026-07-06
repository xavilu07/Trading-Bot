from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from trading_signals.agents.proposal_store import DEFAULT_PROPOSALS_PATH, load_proposals


def detect_qic_events(
    *,
    trades_path: Path = Path("data") / "paper_trading" / "trades.csv",
    proposal_store_path: Path = DEFAULT_PROPOSALS_PATH,
    pf_threshold: float = 1.0,
    losing_streak_threshold: int = 5,
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
