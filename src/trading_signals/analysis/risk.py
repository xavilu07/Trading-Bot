from __future__ import annotations

from trading_signals.domain.entities.risk_plan import RiskPlan


def calculate_risk_plan(
    *,
    risk_plan_id: str,
    evaluation_id: str,
    decision: str,
    snapshot,
    min_rr: float,
    risk_per_trade: float,
    account_balance_reference: float,
    created_at: str,
) -> RiskPlan | None:
    entry = snapshot.close
    atr_buffer = snapshot.atr * 0.2
    if decision == "long":
        stop_loss = snapshot.liquidity_low - atr_buffer
        risk = entry - stop_loss
        if risk <= 0:
            return None
        structural_target = max(snapshot.liquidity_high, entry)
        minimum_2r_target = entry + (risk * min_rr)
        take_profit = max(structural_target, minimum_2r_target)
    elif decision == "short":
        stop_loss = snapshot.liquidity_high + atr_buffer
        risk = stop_loss - entry
        if risk <= 0:
            return None
        structural_target = min(snapshot.liquidity_low, entry)
        minimum_2r_target = entry - (risk * min_rr)
        take_profit = min(structural_target, minimum_2r_target)
    else:
        return None

    denominator = abs(entry - stop_loss)
    if denominator <= 0:
        return None
    risk_reward = round(abs(take_profit - entry) / denominator, 4)
    if risk_reward < min_rr:
        return None
    risk_amount = round(account_balance_reference * risk_per_trade, 2)
    position_size = round(risk_amount / denominator, 8)
    if position_size <= 0:
        return None
    return RiskPlan(
        id=risk_plan_id,
        evaluation_id=evaluation_id,
        entry=round(entry, 6),
        stop_loss=round(stop_loss, 6),
        take_profit=round(take_profit, 6),
        risk_reward=risk_reward,
        risk_amount=risk_amount,
        position_size=position_size,
        sl_method="liquidity_plus_atr_buffer",
        tp_method="max_structural_or_min_rr" if decision == "long" else "min_structural_or_min_rr",
        created_at=created_at,
    )


def rr_is_valid(risk_plan, *, min_rr: float = 1.5) -> bool:
    return bool(risk_plan and risk_plan.risk_reward >= min_rr)


def distance_to_sl_atr(snapshot, risk_plan) -> float | None:
    if risk_plan is None or snapshot.atr <= 0:
        return None
    return round(abs(risk_plan.entry - risk_plan.stop_loss) / snapshot.atr, 4)


def distance_to_tp_atr(snapshot, risk_plan) -> float | None:
    if risk_plan is None or snapshot.atr <= 0:
        return None
    return round(abs(risk_plan.take_profit - risk_plan.entry) / snapshot.atr, 4)


def late_entry_from_bos(snapshot) -> bool:
    bos = str(snapshot.metadata.get("break_of_structure", "none"))
    if bos == "none" or snapshot.atr <= 0:
        return False
    if bos == "bullish_bos":
        reference = float(snapshot.metadata.get("recent_close_high_before_bos", snapshot.open))
        return (snapshot.close - reference) / snapshot.atr > 1.5
    if bos == "bearish_bos":
        reference = float(snapshot.metadata.get("recent_close_low_before_bos", snapshot.open))
        return (reference - snapshot.close) / snapshot.atr > 1.5
    return False


def avoidance_warnings(
    *,
    snapshot,
    higher_trend: str,
    direction: str,
    max_distance_to_liquidity_atr: float,
    atr_min_threshold: float,
    max_spread_atr: float,
) -> list[str]:
    warnings: list[str] = []
    volume_ratio = float(snapshot.metadata.get("volume_ratio_vs_average_20", 0.0))
    atr_ratio = snapshot.atr / snapshot.close if snapshot.close else 0.0
    spread_atr = abs(snapshot.close - snapshot.open) / snapshot.atr if snapshot.atr > 0 else 999.0
    if snapshot.body_ratio >= 0.75 and snapshot.distance_to_liquidity_atr > max_distance_to_liquidity_atr:
        warnings.append("explosive_candle_without_pullback")
    if volume_ratio < 0.8:
        warnings.append("low_volume")
    if snapshot.market_structure == "range" and volume_ratio < 1.0:
        warnings.append("dirty_sideways_market")
    if (direction == "long" and higher_trend == "bearish") or (direction == "short" and higher_trend == "bullish"):
        warnings.append("against_htf")
    if snapshot.distance_to_liquidity_atr > max_distance_to_liquidity_atr * 2:
        warnings.append("price_far_from_liquidity")
    if spread_atr > max_spread_atr:
        warnings.append("high_spread")
    if atr_ratio < atr_min_threshold:
        warnings.append("low_atr")
    return warnings


def analyze_risk(risk_plan, *, min_rr: float) -> dict[str, object]:
    if risk_plan is None:
        return {
            "ok": False,
            "score": 0.0,
            "reason": "risk_plan_missing",
            "details": {"min_rr": min_rr},
        }
    ok = risk_plan.risk_reward >= min_rr
    return {
        "ok": ok,
        "score": 100.0 if ok else 30.0,
        "reason": "risk_reward_valid" if ok else "risk_reward_below_minimum",
        "details": {
            "entry": risk_plan.entry,
            "stop_loss": risk_plan.stop_loss,
            "take_profit": risk_plan.take_profit,
            "risk_reward": risk_plan.risk_reward,
            "min_rr": min_rr,
            "position_size": risk_plan.position_size,
            "risk_amount": risk_plan.risk_amount,
        },
    }
