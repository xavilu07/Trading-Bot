from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trading_signals.application.use_cases.elite_profile_c_dev_tag import resolve_htf_alignment, score_bucket


@dataclass(frozen=True)
class EliteSubprofileTagResult:
    matched_profiles: tuple[str, ...]
    score_bucket: str
    htf_alignment: str
    setup_type: str
    direction: str
    session: str
    market_regime: str
    trade_location: str

    @property
    def matched(self) -> bool:
        return bool(self.matched_profiles)


def matches_elite_subprofile_g(
    *,
    setup_type: str,
    score: object,
    direction: str,
    higher_trend: object = "",
    htf_alignment: object = "",
    session: object = "",
    trade_location: object = "",
) -> bool:
    return (
        _matches_elite_c_base(
            setup_type=setup_type,
            score=score,
            direction=direction,
            higher_trend=higher_trend,
            htf_alignment=htf_alignment,
        )
        and _direction(direction) == "long"
        and _upper(session) == "OVERLAP"
        and _location(trade_location) == "near_resistance"
    )


def matches_elite_subprofile_h(
    *,
    setup_type: str,
    score: object,
    direction: str,
    higher_trend: object = "",
    htf_alignment: object = "",
    market_regime: object = "",
) -> bool:
    return (
        _matches_elite_c_base(
            setup_type=setup_type,
            score=score,
            direction=direction,
            higher_trend=higher_trend,
            htf_alignment=htf_alignment,
        )
        and _direction(direction) == "long"
        and _upper(market_regime) == "HIGH_VOLATILITY"
    )


def apply_elite_subprofile_dev_tag(
    evaluation: Any,
    *,
    setup_type: str,
    direction: str,
    higher_trend: object = "",
    htf_alignment: object = "",
    session: object = "",
    market_regime: object = "",
    trade_location: object = "",
) -> EliteSubprofileTagResult:
    score = getattr(evaluation, "setup_score", None)
    normalized_setup_type = str(setup_type or "").strip().upper()
    normalized_direction = _direction(direction)
    normalized_session = _upper(session)
    normalized_regime = _upper(market_regime)
    normalized_location = _location(trade_location)
    resolved_score_bucket = score_bucket(score)
    resolved_htf_alignment = resolve_htf_alignment(
        direction=normalized_direction,
        higher_trend=higher_trend,
        explicit=htf_alignment,
    )
    matched_profiles: list[str] = []
    if matches_elite_subprofile_g(
        setup_type=normalized_setup_type,
        score=score,
        direction=normalized_direction,
        higher_trend=higher_trend,
        htf_alignment=resolved_htf_alignment,
        session=normalized_session,
        trade_location=normalized_location,
    ):
        matched_profiles.append("G")
    if matches_elite_subprofile_h(
        setup_type=normalized_setup_type,
        score=score,
        direction=normalized_direction,
        higher_trend=higher_trend,
        htf_alignment=resolved_htf_alignment,
        market_regime=normalized_regime,
    ):
        matched_profiles.append("H")

    trace = getattr(evaluation, "decision_trace", None)
    if isinstance(trace, list):
        if "G" in matched_profiles and "elite_subprofile_g=true" not in trace:
            trace.append("elite_subprofile_g=true")
        if "H" in matched_profiles and "elite_subprofile_h=true" not in trace:
            trace.append("elite_subprofile_h=true")

    return EliteSubprofileTagResult(
        matched_profiles=tuple(matched_profiles),
        score_bucket=resolved_score_bucket,
        htf_alignment=resolved_htf_alignment,
        setup_type=normalized_setup_type,
        direction=normalized_direction,
        session=normalized_session,
        market_regime=normalized_regime,
        trade_location=normalized_location,
    )


def format_elite_subprofile_dev_note(
    *,
    symbol: str,
    profiles: tuple[str, ...],
    direction: str,
    score: object,
    session: object,
    market_regime: object,
    trade_location: object,
    setup_type: object,
) -> str:
    profile_label = "/".join(profiles) if profiles else "UNKNOWN"
    return (
        f"🔥 ELITE SUBPROFILE {profile_label}\n"
        f"{str(symbol or 'UNKNOWN').upper()} {str(direction or 'unknown').upper()}\n"
        f"Score: {score_bucket(score)}\n"
        f"Session: {_upper(session)}\n"
        f"Regime: {_upper(market_regime)}\n"
        f"Location: {_location(trade_location)}\n"
        f"Setup: {str(setup_type or 'UNKNOWN').strip().upper()}"
    )


def _matches_elite_c_base(
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


def _direction(value: object) -> str:
    return str(value or "unknown").strip().lower()


def _upper(value: object) -> str:
    text = str(value or "").strip()
    return text.upper() if text else "UNKNOWN"


def _location(value: object) -> str:
    return str(value or "UNKNOWN").strip() or "UNKNOWN"
