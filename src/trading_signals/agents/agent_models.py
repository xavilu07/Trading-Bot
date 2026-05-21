from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

AgentAction = Literal["ALLOW", "CAUTION", "WOULD_BLOCK", "PRIORITIZE"]
AgentConfidence = Literal["LOW", "MEDIUM", "HIGH"]

VALID_ACTIONS = {"ALLOW", "CAUTION", "WOULD_BLOCK", "PRIORITIZE"}
VALID_CONFIDENCES = {"LOW", "MEDIUM", "HIGH"}


@dataclass(frozen=True)
class AgentVote:
    agent_name: str
    action: AgentAction
    confidence: AgentConfidence
    score: float
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        action = self.action.upper()
        confidence = self.confidence.upper()
        if action not in VALID_ACTIONS:
            raise ValueError(f"invalid agent action: {self.action}")
        if confidence not in VALID_CONFIDENCES:
            raise ValueError(f"invalid agent confidence: {self.confidence}")
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "score", max(0.0, min(float(self.score), 100.0)))

    def to_dict(self) -> dict[str, object]:
        return {
            "agent_name": self.agent_name,
            "action": self.action,
            "confidence": self.confidence,
            "score": self.score,
            "reasons": list(self.reasons),
            "risks": list(self.risks),
        }
