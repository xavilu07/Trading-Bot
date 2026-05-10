from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class SignalDecision:
    symbol: str
    direction: str
    decision: str
    setup_type: str
    entry_price: float | None
    stop_loss: float | None
    take_profit: float | None
    total_score: float
    module_scores: dict[str, float] = field(default_factory=dict)
    rejection_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    passed_filters: list[str] = field(default_factory=list)
    failed_filters: list[str] = field(default_factory=list)
    decision_trace: list[str] = field(default_factory=list)
    source_engine: str = "unknown"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @property
    def is_send(self) -> bool:
        return self.decision == "SEND"

    @property
    def is_rejected(self) -> bool:
        return self.decision == "REJECT"

    @property
    def is_paper_only(self) -> bool:
        return self.decision == "PAPER_ONLY"
