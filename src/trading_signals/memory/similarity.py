from __future__ import annotations


SCALAR_FIELDS = (
    "direction",
    "setup_type",
    "market_regime",
    "entry_context",
    "trade_location",
    "htf_trend",
    "ltf_trend",
)
SET_FIELDS = ("warnings", "penalties")


def compare_with_history(candidate: dict[str, object], history: list[dict[str, object]]) -> dict[str, object]:
    similar = [record for record in history if _is_similar(candidate, record)]
    r_values = [_to_float(record.get("r_result")) for record in similar if _to_float(record.get("r_result")) is not None]
    closed = [record for record in similar if str(record.get("outcome", "")).lower() in {"win", "loss", "timeout"}]
    wins = [record for record in closed if str(record.get("outcome", "")).lower() == "win"]
    similar_count = len(similar)
    return {
        "similar_count": similar_count,
        "historical_winrate": round((len(wins) / len(closed) * 100), 2) if closed else None,
        "historical_avg_r": round(sum(r_values) / len(r_values), 4) if r_values else None,
        "repeated_warnings": _repeated_tokens(candidate, similar, "warnings"),
        "repeated_penalties": _repeated_tokens(candidate, similar, "penalties"),
        "confidence_level": confidence_level(similar_count),
    }


def confidence_level(similar_count: int) -> str:
    if similar_count < 5:
        return "LOW"
    if similar_count <= 15:
        return "MEDIUM"
    return "HIGH"


def _is_similar(candidate: dict[str, object], record: dict[str, object]) -> bool:
    if str(candidate.get("direction", "")).lower() != str(record.get("direction", "")).lower():
        return False
    matches = 0
    for field in SCALAR_FIELDS[1:]:
        if _norm(candidate.get(field)) and _norm(candidate.get(field)) == _norm(record.get(field)):
            matches += 1
    for field in SET_FIELDS:
        if _tokens(candidate.get(field)) & _tokens(record.get(field)):
            matches += 1
    return matches >= 3


def _repeated_tokens(candidate: dict[str, object], similar: list[dict[str, object]], field: str) -> list[str]:
    candidate_tokens = _tokens(candidate.get(field))
    repeated: set[str] = set()
    for record in similar:
        repeated |= candidate_tokens & _tokens(record.get(field))
    return sorted(repeated)


def _tokens(value: object) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        raw_values = value.replace("|", ",").split(",")
    elif isinstance(value, list):
        raw_values = value
    else:
        raw_values = [value]
    return {str(item).strip() for item in raw_values if str(item).strip()}


def _norm(value: object) -> str:
    return str(value or "").strip().lower()


def _to_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
