from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RiskPlan:
    id: str
    evaluation_id: str
    entry: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    risk_amount: float
    position_size: float
    sl_method: str
    tp_method: str
    created_at: str
    schema_version: str = "1.0"
    updated_at: str | None = None

