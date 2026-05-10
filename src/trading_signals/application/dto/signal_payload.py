from __future__ import annotations

from dataclasses import dataclass

from trading_signals.domain.entities.risk_plan import RiskPlan
from trading_signals.domain.entities.strategy_evaluation import StrategyEvaluation
from trading_signals.domain.entities.trade_signal import TradeSignal


@dataclass(slots=True)
class SignalPayload:
    signal: TradeSignal
    evaluation: StrategyEvaluation
    risk_plan: RiskPlan | None
    message: str

