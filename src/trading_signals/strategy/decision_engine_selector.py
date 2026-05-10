from __future__ import annotations

from dataclasses import dataclass

from trading_signals.domain.entities.signal_decision import SignalDecision
from trading_signals.strategy.signal_decision_adapter import (
    clean_modular_signal_decision,
    signal_decision_from_strategy_evaluation,
)


@dataclass(slots=True)
class DecisionEngineSelection:
    selected_engine: str
    signal_decision: SignalDecision


def select_signal_decision(
    *,
    use_modular_decision_engine: bool,
    symbol: str,
    evaluation,
    risk_plan,
    setup_type: str,
    module_diagnostics: dict[str, dict[str, object]],
) -> DecisionEngineSelection:
    if use_modular_decision_engine:
        return DecisionEngineSelection(
            selected_engine="modular",
            signal_decision=clean_modular_signal_decision(
                symbol=symbol,
                module_results=module_diagnostics,
                entry_price=getattr(risk_plan, "entry", None),
                stop_loss=getattr(risk_plan, "stop_loss", None),
                take_profit=getattr(risk_plan, "take_profit", None),
                source_engine="modular_decision_engine",
            ),
        )
    return DecisionEngineSelection(
        selected_engine="legacy",
        signal_decision=signal_decision_from_strategy_evaluation(
            evaluation=evaluation,
            risk_plan=risk_plan,
            setup_type=setup_type,
            source_engine="liquidity_sweep_mtf_v1",
        ),
    )
