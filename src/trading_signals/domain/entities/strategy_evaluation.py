from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class StrategyEvaluation:
    id: str
    scan_run_id: str
    strategy_id: str
    strategy_version: str
    symbol: str
    entry_timeframe: str
    higher_timeframe: str
    entry_snapshot_id: str
    higher_snapshot_id: str
    decision: str
    decision_trace: list[str]
    rejection_reasons: list[str]
    passed_filters: list[str]
    failed_filters: list[str]
    setup_score: float
    confidence: float
    created_at: str
    schema_version: str = "1.0"
    updated_at: str | None = None

