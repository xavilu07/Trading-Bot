from __future__ import annotations

from typing import Protocol

from trading_signals.domain.entities.market_snapshot import MarketSnapshot
from trading_signals.domain.entities.risk_plan import RiskPlan
from trading_signals.domain.entities.scan_run import ScanRun
from trading_signals.domain.entities.strategy_evaluation import StrategyEvaluation
from trading_signals.domain.entities.system_error import SystemError


class ScanRunRepositoryPort(Protocol):
    def save_scan_run(self, run: ScanRun) -> None:
        ...

    def save_snapshot(self, snapshot: MarketSnapshot) -> None:
        ...

    def save_evaluation(self, evaluation: StrategyEvaluation) -> None:
        ...

    def save_risk_plan(self, risk_plan: RiskPlan) -> None:
        ...

    def save_error(self, error: SystemError) -> None:
        ...

