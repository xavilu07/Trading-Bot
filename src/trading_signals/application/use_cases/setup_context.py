from __future__ import annotations

from dataclasses import asdict, dataclass

from trading_signals.analysis.market_regime import (
    detect_entry_context,
    detect_market_regime,
    detect_session,
    detect_trade_location,
)
from trading_signals.analysis.risk import (
    avoidance_warnings,
    distance_to_sl_atr,
    distance_to_tp_atr,
    late_entry_from_bos,
    rr_is_valid,
)
from trading_signals.domain.entities.market_snapshot import MarketSnapshot
from trading_signals.domain.entities.risk_plan import RiskPlan


@dataclass(slots=True)
class SetupContext:
    market_regime: str
    session: str
    entry_context: str
    trade_location: str
    rr_valid: bool
    sl_distance_atr: float | None
    tp_distance_atr: float | None
    late_entry_from_bos: bool
    avoidance_warnings: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_setup_context(
    *,
    snapshot: MarketSnapshot,
    higher_trend: str,
    risk_plan: RiskPlan | None,
    direction: str,
    max_distance_to_liquidity_atr: float,
    atr_min_threshold: float,
    max_spread_atr: float,
) -> SetupContext:
    return SetupContext(
        market_regime=detect_market_regime(snapshot, atr_min_threshold=atr_min_threshold),
        session=detect_session(snapshot.timestamp),
        entry_context=detect_entry_context(snapshot),
        trade_location=detect_trade_location(snapshot),
        rr_valid=rr_is_valid(risk_plan),
        sl_distance_atr=distance_to_sl_atr(snapshot, risk_plan),
        tp_distance_atr=distance_to_tp_atr(snapshot, risk_plan),
        late_entry_from_bos=late_entry_from_bos(snapshot),
        avoidance_warnings=avoidance_warnings(
            snapshot=snapshot,
            higher_trend=higher_trend,
            direction=direction,
            max_distance_to_liquidity_atr=max_distance_to_liquidity_atr,
            atr_min_threshold=atr_min_threshold,
            max_spread_atr=max_spread_atr,
        ),
    )


__all__ = [
    "SetupContext",
    "avoidance_warnings",
    "build_setup_context",
    "detect_entry_context",
    "detect_market_regime",
    "detect_session",
    "detect_trade_location",
    "distance_to_sl_atr",
    "distance_to_tp_atr",
    "late_entry_from_bos",
    "rr_is_valid",
]
