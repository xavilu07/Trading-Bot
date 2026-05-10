from __future__ import annotations

from dataclasses import dataclass

from trading_signals.domain.entities.market_snapshot import MarketSnapshot


@dataclass(slots=True)
class AnalysisResult:
    symbol: str
    entry_timeframe: str
    higher_timeframe: str
    entry_snapshot: MarketSnapshot
    higher_snapshot: MarketSnapshot

