from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ELITE_PROFILE_C_HISTORICAL_PF = 2.64


@dataclass(frozen=True)
class EliteProfileCTagResult:
    matched: bool
    score_bucket: str
    htf_alignment: str
    setup_type: str
    trace_token: str = "elite_profile_c=true"


def matches_elite_profile_c(
    *,
    setup_type: str,
    score: object,
    direction: str,
    higher_trend: object = "",
    htf_alignment: object = "",
) -> bool:
    return (
        str(setup_type or "").strip().upper() == "SECONDARY_SIGNAL"
        and score_bucket(score) == "90+"
        and resolve_htf_alignment(direction=direction, higher_trend=higher_trend, explicit=htf_alignment) == "aligned_with_htf"
    )


def apply_elite_profile_c_dev_tag(
    evaluation: Any,
    *,
    setup_type: str,
    direction: str,
    higher_trend: object = "",
    htf_alignment: object = "",
) -> EliteProfileCTagResult:
    score = getattr(evaluation, "setup_score", None)
    resolved_score_bucket = score_bucket(score)
    resolved_htf_alignment = resolve_htf_alignment(direction=direction, higher_trend=higher_trend, explicit=htf_alignment)
    normalized_setup_type = str(setup_type or "").strip().upper()
    matched = normalized_setup_type == "SECONDARY_SIGNAL" and resolved_score_bucket == "90+" and resolved_htf_alignment == "aligned_with_htf"
    result = EliteProfileCTagResult(
        matched=matched,
        score_bucket=resolved_score_bucket,
        htf_alignment=resolved_htf_alignment,
        setup_type=normalized_setup_type,
    )
    if matched:
        trace = getattr(evaluation, "decision_trace", None)
        if isinstance(trace, list) and result.trace_token not in trace:
            trace.append(result.trace_token)
    return result


def format_elite_profile_c_dev_note(*, symbol: str, direction: str, score: object) -> str:
    return (
        "🔥 ELITE PROFILE C\n"
        f"{str(symbol or 'UNKNOWN').upper()} {str(direction or 'unknown').upper()}\n"
        f"Score {score_bucket(score)}\n"
        "SECONDARY_SIGNAL\n"
        "Aligned HTF\n"
        f"Historical PF: {ELITE_PROFILE_C_HISTORICAL_PF:.2f}"
    )


def score_bucket(value: object) -> str:
    number = _float(value)
    if number is None:
        return "UNKNOWN"
    if number < 60:
        return "<60"
    if number < 70:
        return "60-69"
    if number < 80:
        return "70-79"
    if number < 90:
        return "80-89"
    return "90+"


def resolve_htf_alignment(*, direction: str, higher_trend: object = "", explicit: object = "") -> str:
    explicit_text = str(explicit or "").strip().lower()
    if explicit_text:
        return explicit_text
    direction_text = str(direction or "unknown").strip().lower()
    higher = str(higher_trend or "").strip().lower()
    if not direction_text or not higher:
        return "UNKNOWN"
    if direction_text == "long" and higher == "bullish":
        return "aligned_with_htf"
    if direction_text == "short" and higher == "bearish":
        return "aligned_with_htf"
    if direction_text == "long" and higher == "bearish":
        return "against_htf"
    if direction_text == "short" and higher == "bullish":
        return "against_htf"
    return f"htf_{higher}" if higher else "UNKNOWN"


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
