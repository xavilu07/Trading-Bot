from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MarketSnapshot:
    id: str
    scan_run_id: str
    symbol: str
    timeframe: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    trend: str
    market_structure: str
    liquidity_high: float
    liquidity_low: float
    liquidity_sweep: str
    atr: float
    body_ratio: float
    distance_to_liquidity_atr: float
    setup_score: float
    created_at: str
    schema_version: str = "1.0"
    source: str = "binance"
    updated_at: str | None = None
    metadata: dict[str, float | str] = field(default_factory=dict)

