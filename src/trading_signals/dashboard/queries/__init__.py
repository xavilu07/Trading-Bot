"""Read-only dashboard queries backed only by the SQLite projection."""

from trading_signals.dashboard.queries.read_model import (
    build_freshness_from_read_model,
    build_system_from_read_model,
    read_model_evidence,
)

__all__ = [
    "build_freshness_from_read_model",
    "build_system_from_read_model",
    "read_model_evidence",
]
