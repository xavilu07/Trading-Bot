from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TradeSignal:
    id: str
    scan_run_id: str
    evaluation_id: str
    risk_plan_id: str | None
    strategy_id: str
    strategy_version: str
    symbol: str
    decision: str
    status: str
    dedupe_key: str
    entry_timeframe: str
    higher_timeframe: str
    entry_snapshot_id: str
    higher_snapshot_id: str
    created_at: str
    published_at: str | None = None
    signal_type: str = "NEW"
    lifecycle_reason: str | None = None
    schema_version: str = "1.0"
    updated_at: str | None = None
