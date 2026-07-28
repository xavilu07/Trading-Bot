"""Read-only dashboard queries."""

from trading_signals.dashboard.queries.system import build_freshness, build_system_status

__all__ = ["build_freshness", "build_system_status"]
