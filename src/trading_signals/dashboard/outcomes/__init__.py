"""Pure and finite outcome evaluation for the dashboard read model."""

from trading_signals.dashboard.outcomes.engine import (
    MarketCandle,
    OutcomeEngineError,
    OutcomeSignal,
    evaluate_signal_outcome,
)

__all__ = [
    "MarketCandle",
    "OutcomeEngineError",
    "OutcomeSignal",
    "evaluate_signal_outcome",
]
