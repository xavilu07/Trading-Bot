"""Prospective, simulated paper-trading evidence.

The package has no import-time I/O and does not depend on the operational
container, dashboard API, Telegram, or a network provider.
"""

from trading_signals.paper_trace.policy import (
    DEFAULT_EXPIRY_POLICY_ID,
    DEFAULT_FILL_POLICY_ID,
    TRACE_MODEL_VERSION,
    trace_policy_checksum,
)

__all__ = [
    "DEFAULT_EXPIRY_POLICY_ID",
    "DEFAULT_FILL_POLICY_ID",
    "TRACE_MODEL_VERSION",
    "trace_policy_checksum",
]
