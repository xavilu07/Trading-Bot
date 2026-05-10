from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SystemError:
    id: str
    scan_run_id: str | None
    symbol: str | None
    stage: str
    error_type: str
    error_message: str
    payload: dict[str, object]
    created_at: str
    schema_version: str = "1.0"

