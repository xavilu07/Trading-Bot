from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class DebateIntervention:
    agent: str
    role: str
    stage: str
    content: str
    confidence: str = "LOW"
    evidence: int = 0
    risk_level: str = "MEDIUM"
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "role": self.role,
            "stage": self.stage,
            "content": self.content,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "risk_level": self.risk_level,
            "data": self.data,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class CIOProposal:
    id: str
    title: str
    hypothesis: str
    expected_pf: float | None
    expected_total_r: float | None
    trades_lost: int
    confidence: str
    risk_level: str
    evidence: int
    agent_votes: list[dict[str, Any]]
    action: str = "IMPLEMENTATION_CANDIDATE"
    baseline_trades: int = 0
    trade_reduction_pct: float = 0.0
    risk_objections: list[str] = field(default_factory=list)
    status: str = "pending"
    context: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "hypothesis": self.hypothesis,
            "expected_pf": self.expected_pf,
            "expected_total_r": self.expected_total_r,
            "trades_lost": self.trades_lost,
            "confidence": self.confidence,
            "risk_level": self.risk_level,
            "evidence": self.evidence,
            "agent_votes": self.agent_votes,
            "action": self.action,
            "baseline_trades": self.baseline_trades,
            "trade_reduction_pct": self.trade_reduction_pct,
            "risk_objections": self.risk_objections,
            "status": self.status,
            "context": self.context,
            "rationale": self.rationale,
            "created_at": self.created_at,
        }
