from __future__ import annotations

import math
from collections import Counter


MATCH_FIELDS = (
    "direction",
    "setup_type",
    "market_regime",
    "session",
    "entry_context",
    "trade_location",
    "liquidity_sweep",
    "market_structure",
)
TOKEN_FIELDS = ("warnings", "penalties")


def calculate_historical_edge_score(candidate: dict[str, object], history: list[dict[str, object]]) -> dict[str, object]:
    matches = [record for record in history if _is_similar(candidate, record) and _to_float(record.get("r_result")) is not None]
    count = len(matches)
    if count == 0:
        return {
            "historical_edge_score": 50,
            "historical_confidence": "LOW",
            "matched_patterns_count": 0,
            "matched_winrate": 0.0,
            "matched_avg_r": 0.0,
            "matched_profit_factor": 0.0,
            "positive_edge_reasons": [],
            "negative_edge_reasons": ["historial_insuficiente"],
        }

    r_values = [float(record["r_result"]) for record in matches if _to_float(record.get("r_result")) is not None]
    wins = [value for value in r_values if value > 0]
    losses = [value for value in r_values if value < 0]
    winrate = round(len(wins) / len(r_values) * 100, 2) if r_values else 0.0
    avg_r = round(sum(r_values) / len(r_values), 4) if r_values else 0.0
    gross_profit = sum(max(0.0, value) for value in r_values)
    gross_loss = abs(sum(min(0.0, value) for value in r_values))
    profit_factor = round(gross_profit / gross_loss, 4) if gross_loss > 0 else (round(gross_profit, 4) if gross_profit > 0 else 0.0)
    positives, negatives = _edge_reasons(avg_r=avg_r, profit_factor=profit_factor, winrate=winrate, matched=matches)
    return {
        "historical_edge_score": _score(avg_r=avg_r, profit_factor=profit_factor, winrate=winrate),
        "historical_confidence": _confidence(count),
        "matched_patterns_count": count,
        "matched_winrate": winrate,
        "matched_avg_r": avg_r,
        "matched_profit_factor": profit_factor,
        "positive_edge_reasons": positives,
        "negative_edge_reasons": negatives,
    }


def _is_similar(candidate: dict[str, object], record: dict[str, object]) -> bool:
    exact_matches = 0
    for field in MATCH_FIELDS:
        candidate_value = _normalize(candidate.get(field))
        record_value = _normalize(record.get(field))
        if candidate_value and record_value and candidate_value == record_value:
            exact_matches += 1
    token_overlap = 0
    for field in TOKEN_FIELDS:
        if set(_tokens(candidate.get(field))) & set(_tokens(record.get(field))):
            token_overlap += 1
    return exact_matches >= 4 or (exact_matches >= 3 and token_overlap >= 1)


def _score(*, avg_r: float, profit_factor: float, winrate: float) -> int:
    score = 50.0
    if avg_r > 0:
        score += min(20.0, avg_r * 20.0)
    elif avg_r < 0:
        score += max(-20.0, avg_r * 20.0)
    if profit_factor > 1.2:
        score += min(20.0, (profit_factor - 1.2) * 10.0)
    elif profit_factor < 1.0:
        score -= min(20.0, (1.0 - profit_factor) * 20.0)
    if winrate > 50:
        score += min(10.0, (winrate - 50.0) / 5.0)
    elif winrate < 40:
        score -= min(10.0, (40.0 - winrate) / 4.0)
    return int(max(0, min(100, round(score))))


def _confidence(count: int) -> str:
    if count >= 30:
        return "HIGH"
    if count >= 10:
        return "MEDIUM"
    return "LOW"


def _edge_reasons(*, avg_r: float, profit_factor: float, winrate: float, matched: list[dict[str, object]]) -> tuple[list[str], list[str]]:
    positives = []
    negatives = []
    if avg_r > 0:
        positives.append(f"avgR positivo ({avg_r})")
    if profit_factor > 1.2:
        positives.append(f"profit factor fuerte ({profit_factor})")
    if winrate > 50:
        positives.append(f"winrate favorable ({winrate}%)")
    if avg_r < 0:
        negatives.append(f"avgR negativo ({avg_r})")
    if profit_factor < 1.0:
        negatives.append(f"profit factor débil ({profit_factor})")
    if winrate < 40:
        negatives.append(f"winrate bajo ({winrate}%)")
    repeated_warnings = _common_tokens(matched, "warnings")
    repeated_penalties = _common_tokens(matched, "penalties")
    if repeated_warnings:
        negatives.append(f"warnings repetidos: {', '.join(repeated_warnings[:3])}")
    if repeated_penalties:
        negatives.append(f"penalties repetidas: {', '.join(repeated_penalties[:3])}")
    return positives, negatives


def _common_tokens(records: list[dict[str, object]], field: str) -> list[str]:
    counter: Counter[str] = Counter()
    for record in records:
        counter.update(_tokens(record.get(field)))
    min_count = max(2, math.ceil(len(records) * 0.3))
    return [token for token, count in counter.most_common(5) if count >= min_count]


def _normalize(value: object) -> str:
    text = str(value or "").strip().lower()
    return "" if text in {"", "unknown", "none"} else text


def _tokens(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip().lower() for item in value if str(item).strip()]
    return [item.strip().lower() for item in str(value).replace("|", ",").split(",") if item.strip()]


def _to_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

