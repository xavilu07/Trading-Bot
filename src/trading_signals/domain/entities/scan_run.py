from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ScanRun:
    id: str
    started_at: str
    status: str
    symbols_total: int
    symbols_processed: int
    signals_emitted: int
    signals_rejected: int
    errors_count: int
    config: dict[str, object] = field(default_factory=dict)
    finished_at: str | None = None
    created_at: str | None = None
    schema_version: str = "1.0"
    updated_at: str | None = None

