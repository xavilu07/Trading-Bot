from __future__ import annotations


def compute_setup_score(
    trend: str,
    structure: str,
    sweep: str,
    body_ratio_value: float,
    distance_to_liquidity_atr: float,
    atr_ratio: float,
) -> float:
    score = 0.0
    if trend in {"bullish", "bearish"}:
        score += 20
    if structure in {"bullish", "bearish"}:
        score += 20
    if sweep in {"bullish_sweep", "bearish_sweep"}:
        score += 20
    if body_ratio_value >= 0.35:
        score += 15
    if distance_to_liquidity_atr <= 2.5:
        score += 15
    if atr_ratio >= 0.002:
        score += 10
    return round(min(score, 100.0), 2)
