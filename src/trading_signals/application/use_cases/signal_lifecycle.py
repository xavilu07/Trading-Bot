from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SignalLifecycleDecision:
    signal_type: str
    should_publish: bool
    reason: str
    active_entries_same_trend: int


def classify_signal_lifecycle(
    *,
    signal_repo,
    symbol: str,
    direction: str,
    entry_snapshot,
    evaluation,
    max_reentries: int = 2,
) -> SignalLifecycleDecision:
    active = active_published_signals(signal_repo, symbol=symbol, direction=direction, limit=500)
    if not active:
        return SignalLifecycleDecision("NEW", True, "new_signal", 0)

    if len(active) >= max_reentries + 1:
        return SignalLifecycleDecision("DUPLICATE", False, "max_reentries_reached", len(active))

    if has_reentry_confirmation(entry_snapshot, evaluation):
        return SignalLifecycleDecision("REENTRY", True, "pullback_and_confirmation", len(active))

    return SignalLifecycleDecision("DUPLICATE", False, "active_same_symbol_direction_without_reentry", len(active))


def active_published_signals(signal_repo, *, symbol: str, direction: str, limit: int) -> list[dict[str, object]]:
    items = signal_repo.list_latest_signals(limit=limit)
    active: list[dict[str, object]] = []
    for item in items:
        if item.get("symbol") != symbol:
            continue
        if item.get("decision") != direction:
            continue
        if not item.get("published_at"):
            continue
        active.append(item)
    return active


def has_reentry_confirmation(entry_snapshot, evaluation) -> bool:
    failed = set(evaluation.failed_filters)
    passed = set(evaluation.passed_filters)
    bos = str(entry_snapshot.metadata.get("break_of_structure", "none"))
    pullback_clear = (
        entry_snapshot.distance_to_liquidity_atr <= 2.5
        or float(entry_snapshot.metadata.get("nearest_distance_to_liquidity_atr", 999.0)) <= 1.25
        or "distance_to_liquidity" in passed
    )
    new_confirmation = (
        bos in {"bullish_bos", "bearish_bos"}
        or "secondary_break_of_structure" in passed
        or "candle_confirmation" in passed and "body_ratio_below_threshold" not in failed
    )
    return pullback_clear and new_confirmation
