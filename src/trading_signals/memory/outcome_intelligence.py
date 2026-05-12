from __future__ import annotations

from datetime import datetime


def analyze_trade_outcome(trade: dict[str, object]) -> dict[str, object]:
    result_r = _float_or_none(trade.get("result_r") or trade.get("r_result"))
    mfe_r = _float_or_none(trade.get("mfe_r") or trade.get("max_favorable_move_r") or trade.get("max_favorable_move"))
    mae_r = _float_or_none(trade.get("mae_r") or trade.get("max_adverse_move_r") or trade.get("max_adverse_move"))
    bars = _int_or_none(trade.get("bars_held") or trade.get("candles_held") or trade.get("candles_elapsed"))
    exit_reason = str(trade.get("exit_reason") or trade.get("status") or trade.get("outcome") or "").lower()
    time_to_resolution = bars if bars is not None else _hours_between(trade.get("entry_time") or trade.get("created_at"), trade.get("exit_time") or trade.get("closed_at"))
    reasons: list[str] = []
    risks: list[str] = []
    outcome_type = _outcome_type(result_r=result_r, mfe_r=mfe_r, mae_r=mae_r, bars=time_to_resolution, exit_reason=exit_reason, reasons=reasons, risks=risks)
    score = _score(outcome_type=outcome_type, result_r=result_r, mfe_r=mfe_r, mae_r=mae_r, bars=time_to_resolution, reasons=reasons, risks=risks)
    return {
        "outcome_quality_score": score,
        "outcome_grade": _grade(score),
        "outcome_type": outcome_type,
        "post_entry_behavior": _post_entry_behavior(outcome_type, result_r=result_r, mfe_r=mfe_r, mae_r=mae_r, bars=time_to_resolution),
        "mfe_efficiency": _mfe_efficiency(result_r, mfe_r),
        "mae_pressure": _mae_pressure(mae_r),
        "time_to_resolution": time_to_resolution,
        "outcome_reasons": reasons,
        "outcome_risks": risks,
    }


def _outcome_type(
    *,
    result_r: float | None,
    mfe_r: float | None,
    mae_r: float | None,
    bars: int | None,
    exit_reason: str,
    reasons: list[str],
    risks: list[str],
) -> str:
    if "timeout" in exit_reason or "expired" in exit_reason:
        reasons.append("salida por timeout/expired")
        return "TIMEOUT"
    if result_r is None:
        risks.append("resultado R no disponible")
        return "UNKNOWN"
    fast = bars is not None and bars <= 6
    slow = bars is not None and bars >= 24
    low_mae = mae_r is None or mae_r >= -0.5
    high_mae = mae_r is not None and mae_r <= -1.0
    good_mfe = mfe_r is not None and mfe_r >= max(1.0, result_r)
    if result_r > 0:
        reasons.append("resultado positivo")
        if low_mae and (good_mfe or mfe_r is None) and not slow:
            reasons.append("win limpio: MAE bajo y resolución eficiente")
            return "CLEAN_WIN"
        risks.append("win con presión o resolución lenta")
        return "DIRTY_WIN"
    if result_r < 0:
        risks.append("resultado negativo")
        if high_mae or fast:
            risks.append("loss agresivo: MAE alto o SL rápido")
            return "BAD_LOSS"
        reasons.append("loss controlado")
        return "CLEAN_LOSS"
    if slow:
        risks.append("sin avance claro durante demasiadas velas")
        return "TIMEOUT"
    return "UNKNOWN"


def _score(
    *,
    outcome_type: str,
    result_r: float | None,
    mfe_r: float | None,
    mae_r: float | None,
    bars: int | None,
    reasons: list[str],
    risks: list[str],
) -> float:
    base = {
        "CLEAN_WIN": 85.0,
        "DIRTY_WIN": 65.0,
        "CLEAN_LOSS": 45.0,
        "BAD_LOSS": 20.0,
        "TIMEOUT": 35.0,
        "UNKNOWN": 50.0,
    }[outcome_type]
    if result_r is not None:
        base += max(-10.0, min(10.0, result_r * 4.0))
    if mfe_r is not None and mfe_r >= 1.5:
        base += 5
        reasons.append("MFE favorable")
    if mae_r is not None and mae_r <= -1.0:
        base -= 8
        risks.append("MAE elevado")
    if bars is not None and bars <= 6 and result_r is not None and result_r > 0:
        base += 4
        reasons.append("resolución rápida favorable")
    if bars is not None and bars >= 24:
        base -= 6
        risks.append("tiempo en mercado elevado")
    return round(max(0.0, min(100.0, base)), 2)


def _post_entry_behavior(outcome_type: str, *, result_r: float | None, mfe_r: float | None, mae_r: float | None, bars: int | None) -> str:
    if outcome_type == "UNKNOWN":
        return "UNKNOWN"
    if result_r is not None and result_r > 0 and (mae_r is None or mae_r >= -0.5) and (bars is None or bars <= 12):
        return "STRONG_CONTINUATION"
    if result_r is not None and result_r > 0 and mae_r is not None and mae_r < -0.75:
        return "CHOPPY_RECOVERY"
    if outcome_type == "BAD_LOSS":
        return "FAST_REVERSAL"
    if bars is not None and bars >= 18:
        return "SLOW_GRIND"
    return "UNKNOWN"


def _mfe_efficiency(result_r: float | None, mfe_r: float | None) -> float | None:
    if result_r is None or mfe_r is None or mfe_r == 0:
        return None
    return round(result_r / mfe_r, 4)


def _mae_pressure(mae_r: float | None) -> float | None:
    if mae_r is None:
        return None
    return round(abs(mae_r), 4)


def _grade(score: float) -> str:
    if score >= 90:
        return "A+"
    if score >= 75:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    return "TRASH"


def _hours_between(start: object, end: object) -> int | None:
    if not start or not end:
        return None
    try:
        start_dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, int((end_dt - start_dt).total_seconds() // 3600))


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None

