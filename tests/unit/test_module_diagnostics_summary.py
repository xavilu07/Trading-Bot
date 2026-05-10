from __future__ import annotations

import json

from scripts.module_diagnostics_summary import build_summary, format_summary, parse_log_lines


def event(symbol: str, module: str, ok: bool, score: float, reason: str, details: dict[str, object] | None = None) -> str:
    return json.dumps(
        {
            "event": "module_diagnostic",
            "symbol": symbol,
            "module": module,
            "ok": ok,
            "score": score,
            "reason": reason,
            "details": details or {},
        }
    )


def signal_decision_event(
    *,
    event_name: str,
    symbol: str,
    decision: str,
    direction: str,
    total_score: float,
    source_engine: str,
    rejection_reasons: list[str],
) -> str:
    return json.dumps(
        {
            "event": event_name,
            "symbol": symbol,
            "decision": decision,
            "direction": direction,
            "total_score": total_score,
            "source_engine": source_engine,
            "rejection_reasons": rejection_reasons,
        }
    )


def test_module_diagnostics_summary_groups_by_module_reason_score_and_symbol() -> None:
    rows = parse_log_lines(
        [
            signal_decision_event(
                event_name="signal_decision_current",
                symbol="BTCUSDT",
                decision="REJECT",
                direction="no_trade",
                total_score=35,
                source_engine="liquidity_sweep_mtf_v1",
                rejection_reasons=["body_ratio_below_threshold"],
            ),
            signal_decision_event(
                event_name="signal_decision_parallel",
                symbol="BTCUSDT",
                decision="PAPER_ONLY",
                direction="long",
                total_score=60,
                source_engine="parallel_decision_engine",
                rejection_reasons=["body_ratio_below_threshold"],
            ),
            event("BTCUSDT", "momentum", False, 35.0, "body_ratio_below_threshold"),
            event("ETHUSDT", "momentum", True, 80.0, "momentum_confirmed"),
            event(
                "NEARUSDT",
                "momentum",
                True,
                75.0,
                "momentum_confirmed",
                {"body_ratio": 0.31, "volume_ratio": 1.4, "rsi": 58.0, "direction": "long"},
            ),
            event(
                "NEARUSDT",
                "signal_builder",
                False,
                70.0,
                "signal_not_ready",
                {"direction": "long", "setup_type": "SECONDARY_SIGNAL"},
            ),
            event(
                "NEARUSDT",
                "strategy_gate",
                False,
                70.0,
                "strategy_gate_blocked",
                {
                    "setup_detected": "SECONDARY_SIGNAL",
                    "condition_failed": "long_secondary_bos",
                    "value": "none",
                    "required": "bullish_bos",
                    "reason_final": "secondary_setup_requirements_failed",
                },
            ),
            event(
                "NEARUSDT",
                "decision_engine",
                False,
                70.0,
                "parallel_decision_diagnostic",
                {"total_score": 70.0, "decision": "PAPER_ONLY", "rejection_reasons": ["signal_not_ready"]},
            ),
            event(
                "TAOUSDT",
                "momentum",
                True,
                100.0,
                "momentum_confirmed",
                {"body_ratio": 0.4, "volume_ratio": 2.0, "rsi": 61.0, "direction": "long"},
            ),
            event(
                "TAOUSDT",
                "signal_builder",
                True,
                90.0,
                "signal_candidate_ready",
                {"direction": "long", "setup_type": "SECONDARY_SIGNAL"},
            ),
            event(
                "TAOUSDT",
                "decision_engine",
                True,
                90.0,
                "parallel_decision_diagnostic",
                {"total_score": 90.0, "decision": "SEND", "rejection_reasons": []},
            ),
            event(
                "WIFUSDT",
                "experimental_decision_engine",
                True,
                82.0,
                "experimental_accepts_without_primary_sweep",
                {
                    "would_send_signal": True,
                    "direction": "short",
                    "score": 82.0,
                    "original_blocking_filter": "short_primary_sweep",
                    "experimental_reason": "experimental_accepts_short_only_without_primary_sweep",
                },
            ),
            event("BTCUSDT", "liquidity", False, 20.0, "liquidity_too_far"),
            event(
                "BTCUSDT",
                "decision_engine",
                False,
                55.0,
                "parallel_decision_diagnostic",
                {"rejection_reasons": ["body_ratio_below_threshold", "liquidity_too_far"]},
            ),
            "not-json",
            json.dumps({"event": "other_event"}),
        ]
    )

    summary = build_summary(rows)

    assert summary["total_module_diagnostics"] == 12
    momentum = next(item for item in summary["modules"] if item["module"] == "momentum")
    assert momentum["ok_true"] == 3
    assert momentum["ok_false"] == 1
    assert momentum["average_score"] == 72.5
    assert {"reason": "body_ratio_below_threshold", "count": 1} in momentum["top_reasons"]
    assert {"symbol": "BTCUSDT", "count": 1} in momentum["top_symbols"]
    assert {
        item["reason"]: item["count"]
        for item in summary["decision_engine_top_rejection_reasons"]
    } == {
        "body_ratio_below_threshold": 1,
        "liquidity_too_far": 1,
        "signal_not_ready": 1,
    }
    assert summary["near_miss_candidates"][0]["symbol"] == "NEARUSDT"
    assert summary["near_miss_candidates"][0]["principal_rejection_reason"] == "signal_not_ready"
    assert summary["near_miss_candidates"][0]["condition_failed"] == "long_secondary_bos"
    assert summary["valid_dry_run_signals"][0]["symbol"] == "TAOUSDT"
    assert summary["experimental_signals"][0]["symbol"] == "WIFUSDT"
    assert summary["signal_decision_comparison"]["matches"] == 0
    assert summary["signal_decision_comparison"]["differs"] == 1
    assert summary["signal_decision_comparison"]["current_reject_parallel_send_or_paper"][0]["symbol"] == "BTCUSDT"

    formatted = format_summary(summary)
    assert "Resumen de module_diagnostic" in formatted
    assert "momentum: ok=3 | fail=1" in formatted
    assert "body_ratio_below_threshold: 1" in formatted
    assert "near_miss_candidates" in formatted
    assert "valid_dry_run_signals" in formatted
    assert "experimental_signals" in formatted
