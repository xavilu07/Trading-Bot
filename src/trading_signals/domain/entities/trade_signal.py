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
    accepted_at: str | None = None
    public_published_at: str | None = None
    universe: str = "unknown"
    accepted: bool = False
    public_published: bool = False
    git_commit_sha: str = "unknown"
    config_hash: str = "unknown"
    runtime_flags: dict[str, object] | None = None
    deployment_id: str = "unknown"
    selected_engine: str = "unknown"
    policy_version: str = "unknown"
    experiment_id: str = "unknown"
    signal_type: str = "NEW"
    lifecycle_reason: str | None = None
    lifecycle_status: str | None = None
    expires_at: str | None = None
    close_reason: str | None = None
    closed_at: str | None = None
    schema_version: str = "1.0"
    updated_at: str | None = None
