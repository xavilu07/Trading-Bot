from __future__ import annotations


def build_signal_diagnostic(symbol: str, evaluation, risk_plan, *, setup_type: str) -> dict[str, object]:
    is_signal = evaluation.decision in {"long", "short"} and risk_plan is not None
    return {
        "ok": is_signal,
        "score": float(evaluation.setup_score),
        "reason": "signal_candidate_ready" if is_signal else "signal_not_ready",
        "details": {
            "symbol": symbol,
            "direction": evaluation.decision,
            "setup_type": setup_type,
            "passed_filters": list(evaluation.passed_filters),
            "failed_filters": list(evaluation.failed_filters),
            "risk_plan_id": getattr(risk_plan, "id", None),
        },
    }

