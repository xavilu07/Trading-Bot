"""Read-only dashboard domain.

This package is deliberately independent from the operational application
container. Importing it must not initialize exchanges, notifiers, agents, or
runtime writers.
"""

from trading_signals.dashboard.contracts import CONTRACT_VERSION

__all__ = ["CONTRACT_VERSION"]
