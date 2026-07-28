"""Isolated read-only FastAPI surface for the dashboard."""

from trading_signals.interfaces.dashboard_api.main import create_app

__all__ = ["create_app"]
