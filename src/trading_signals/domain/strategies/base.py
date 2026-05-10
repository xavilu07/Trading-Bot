from __future__ import annotations

from typing import Protocol

from trading_signals.application.dto.analysis_result import AnalysisResult
from trading_signals.domain.entities.strategy_evaluation import StrategyEvaluation


class Strategy(Protocol):
    strategy_id: str
    strategy_version: str

    def evaluate(self, analysis: AnalysisResult, evaluation_id: str, created_at: str) -> StrategyEvaluation:
        ...

