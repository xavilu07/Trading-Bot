from __future__ import annotations

from trading_signals.domain.value_objects.enums import SignalDecision


def analyze_strategy_gate(settings, analysis, evaluation) -> dict[str, object]:
    entry = analysis.entry_snapshot
    higher = analysis.higher_snapshot
    volume_ratio = float(entry.metadata.get("volume_ratio_vs_average_20", 0.0))
    rsi = float(entry.metadata.get("rsi", 50.0))
    bos = str(entry.metadata.get("break_of_structure", "none"))
    nearest_distance = float(entry.metadata.get("nearest_distance_to_liquidity_atr", entry.distance_to_liquidity_atr))
    secondary_direction = _secondary_direction(bos)
    suggested_direction = evaluation.decision if evaluation.decision in {"long", "short"} else secondary_direction
    if suggested_direction == SignalDecision.NO_TRADE.value:
        suggested_direction = SignalDecision.LONG.value if entry.trend == "bullish" else SignalDecision.SHORT.value

    checks = _base_checks(settings, evaluation, entry)
    if suggested_direction == SignalDecision.LONG.value:
        checks.extend(_long_checks(settings, evaluation, entry, higher, volume_ratio, rsi, bos, nearest_distance))
    elif suggested_direction == SignalDecision.SHORT.value:
        checks.extend(_short_checks(settings, evaluation, entry, higher, volume_ratio, rsi, bos, nearest_distance))

    failed = [item for item in checks if not item["passed"]]
    setup_detected = _setup_detected(entry, bos)
    return {
        "ok": evaluation.decision in {"long", "short"},
        "score": float(evaluation.setup_score),
        "reason": "strategy_gate_passed" if evaluation.decision in {"long", "short"} else "strategy_gate_blocked",
        "details": {
            "suggested_direction": suggested_direction,
            "setup_detected": setup_detected,
            "condition_failed": failed[0]["condition"] if failed else None,
            "value": failed[0]["value"] if failed else None,
            "required": failed[0]["required"] if failed else None,
            "reason_final": "|".join(evaluation.rejection_reasons) if evaluation.rejection_reasons else "none",
            "failed_conditions": failed,
        },
    }


def _base_checks(settings, evaluation, entry) -> list[dict[str, object]]:
    return [
        _check("volatility", (entry.atr / entry.close) if entry.close else 0.0, f">= {settings.atr_min_threshold}", (entry.atr / entry.close) >= settings.atr_min_threshold if entry.close else False),
        _check("body_ratio", entry.body_ratio, f">= {settings.min_body_ratio}", entry.body_ratio >= settings.min_body_ratio),
        _check("setup_score", float(evaluation.setup_score), f">= {settings.setup_score_threshold}", float(evaluation.setup_score) >= settings.setup_score_threshold),
    ]


def _long_checks(settings, evaluation, entry, higher, volume_ratio: float, rsi: float, bos: str, nearest_distance: float) -> list[dict[str, object]]:
    secondary_threshold = settings.setup_score_threshold + 15
    return [
        _check("long_primary_trend", entry.trend, "bullish", entry.trend == "bullish"),
        _check("long_primary_sweep", entry.liquidity_sweep, "bullish_sweep", entry.liquidity_sweep == "bullish_sweep"),
        _check("long_primary_structure", entry.market_structure, "bullish or allowed range", entry.market_structure in {"bullish", "range"}),
        _check("long_primary_htf", higher.trend, "not bearish", higher.trend != "bearish"),
        _check("long_primary_distance_not_extreme", entry.distance_to_liquidity_atr, f"<= {settings.max_distance_to_liquidity_atr * 2}", entry.distance_to_liquidity_atr <= settings.max_distance_to_liquidity_atr * 2),
        _check("long_secondary_trend_alignment", f"{entry.trend}/{higher.trend}", "bullish/bullish", entry.trend == higher.trend == "bullish"),
        _check("long_secondary_no_sweep", entry.liquidity_sweep, "none", entry.liquidity_sweep == "none"),
        _check("long_secondary_bos", bos, "bullish_bos", bos == "bullish_bos"),
        _check("long_secondary_volume", volume_ratio, ">= 1.2", volume_ratio >= 1.2),
        _check("long_secondary_rsi", rsi, ">= 50", rsi >= 50),
        _check("long_secondary_nearest_liquidity", nearest_distance, f"<= {settings.max_distance_to_liquidity_atr}", nearest_distance <= settings.max_distance_to_liquidity_atr),
        _check("long_secondary_structure", entry.market_structure, "not range or BOS present", entry.market_structure != "range" or bos in {"bullish_bos", "bearish_bos"}),
        _check("long_secondary_score", float(evaluation.setup_score), f">= {secondary_threshold}", float(evaluation.setup_score) >= secondary_threshold),
    ]


def _short_checks(settings, evaluation, entry, higher, volume_ratio: float, rsi: float, bos: str, nearest_distance: float) -> list[dict[str, object]]:
    secondary_threshold = settings.setup_score_threshold + 15
    return [
        _check("short_primary_trend", entry.trend, "bearish", entry.trend == "bearish"),
        _check("short_primary_sweep", entry.liquidity_sweep, "bearish_sweep", entry.liquidity_sweep == "bearish_sweep"),
        _check("short_primary_structure", entry.market_structure, "bearish or allowed range", entry.market_structure in {"bearish", "range"}),
        _check("short_primary_htf", higher.trend, "not bullish", higher.trend != "bullish"),
        _check("short_primary_distance_not_extreme", entry.distance_to_liquidity_atr, f"<= {settings.max_distance_to_liquidity_atr * 2}", entry.distance_to_liquidity_atr <= settings.max_distance_to_liquidity_atr * 2),
        _check("short_secondary_trend_alignment", f"{entry.trend}/{higher.trend}", "bearish/bearish", entry.trend == higher.trend == "bearish"),
        _check("short_secondary_no_sweep", entry.liquidity_sweep, "none", entry.liquidity_sweep == "none"),
        _check("short_secondary_bos", bos, "bearish_bos", bos == "bearish_bos"),
        _check("short_secondary_volume", volume_ratio, ">= 1.2", volume_ratio >= 1.2),
        _check("short_secondary_rsi", rsi, "<= 50", rsi <= 50),
        _check("short_secondary_nearest_liquidity", nearest_distance, f"<= {settings.max_distance_to_liquidity_atr}", nearest_distance <= settings.max_distance_to_liquidity_atr),
        _check("short_secondary_structure", entry.market_structure, "not range or BOS present", entry.market_structure != "range" or bos in {"bullish_bos", "bearish_bos"}),
        _check("short_secondary_score", float(evaluation.setup_score), f">= {secondary_threshold}", float(evaluation.setup_score) >= secondary_threshold),
    ]


def _check(condition: str, value: object, required: object, passed: bool) -> dict[str, object]:
    return {
        "condition": condition,
        "value": value,
        "required": required,
        "passed": passed,
    }


def _secondary_direction(bos: str) -> str:
    if bos == "bullish_bos":
        return SignalDecision.LONG.value
    if bos == "bearish_bos":
        return SignalDecision.SHORT.value
    return SignalDecision.NO_TRADE.value


def _setup_detected(entry, bos: str) -> str:
    if entry.liquidity_sweep in {"bullish_sweep", "bearish_sweep"}:
        return "MAIN_SIGNAL"
    if bos in {"bullish_bos", "bearish_bos"}:
        return "SECONDARY_SIGNAL"
    return "NO_SIGNAL"

