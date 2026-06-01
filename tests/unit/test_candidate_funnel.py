from __future__ import annotations

import json
from pathlib import Path

from trading_signals.application.use_cases.candidate_funnel import (
    build_candidate_funnel_report,
    finalize_candidate_funnel_cycle,
    increment_candidate_funnel,
    new_candidate_funnel_cycle,
    record_candidate_rejection,
    record_relaxation_shadow_observation,
)


def test_funnel_counter_increments() -> None:
    cycle = new_candidate_funnel_cycle(scan_run_id="run_1")

    increment_candidate_funnel(cycle, "raw_setups_evaluated")
    increment_candidate_funnel(cycle, "candidates_created", amount=2)

    assert cycle["counts"]["raw_setups_evaluated"] == 1
    assert cycle["counts"]["candidates_created"] == 2


def test_score_gate_bottleneck_classification() -> None:
    cycle = new_candidate_funnel_cycle(scan_run_id="run_score")
    increment_candidate_funnel(cycle, "raw_setups_evaluated", amount=5)
    increment_candidate_funnel(cycle, "candidates_created", amount=5)
    record_candidate_rejection(
        cycle,
        rejection_reasons=["quality_score_failed"],
        failed_filters=["setup_score_below_threshold"],
    )
    record_candidate_rejection(cycle, rejection_reasons=["quality_score_failed"], failed_filters=[])

    report = build_candidate_funnel_report([cycle])

    assert report["conclusion"] == "score_gate_bottleneck"
    assert report["rolling_last_5_counts"]["rejected_by_score"] == 2
    assert report["top_rejection_reasons_per_stage"]["score"][0]["reason"] == "quality_score_failed"


def test_quality_gate_bottleneck_classification() -> None:
    cycle = new_candidate_funnel_cycle(scan_run_id="run_quality")
    increment_candidate_funnel(cycle, "raw_setups_evaluated", amount=6)
    increment_candidate_funnel(cycle, "candidates_created", amount=4)
    record_candidate_rejection(
        cycle,
        rejection_reasons=["directional_confluence_failed"],
        failed_filters=["body_ratio_below_threshold"],
    )
    record_candidate_rejection(cycle, rejection_reasons=["distance_to_liquidity_extreme"], failed_filters=[])
    record_candidate_rejection(cycle, rejection_reasons=["market_structure_range_penalty"], failed_filters=[])

    report = build_candidate_funnel_report([cycle])

    assert report["conclusion"] == "quality_gate_bottleneck"
    assert report["rolling_last_5_counts"]["rejected_by_quality_gates"] == 3


def test_v1_observed_counter_tracks_trade_and_skip() -> None:
    cycle = new_candidate_funnel_cycle(scan_run_id="run_v1")

    record_relaxation_shadow_observation(cycle, {"trade_created": True})
    record_relaxation_shadow_observation(cycle, {"trade_created": False, "skip_reason": "unsafe_or_empty_filters"})

    assert cycle["counts"]["observed_by_relaxation_shadow_v1"] == 2
    assert cycle["counts"]["v1_trades_created"] == 1
    assert cycle["counts"]["v1_skips_created"] == 1
    assert cycle["rejection_reasons"]["relaxation_shadow_v1"]["unsafe_or_empty_filters"] == 1


def test_candidate_funnel_report_generation(tmp_path: Path) -> None:
    cycle = new_candidate_funnel_cycle(scan_run_id="run_report", started_at="2026-01-01T00:00:00+00:00")
    increment_candidate_funnel(cycle, "raw_setups_evaluated", amount=3)
    increment_candidate_funnel(cycle, "candidates_created", amount=1)
    increment_candidate_funnel(
        cycle,
        "rejected_by_lifecycle_publishability",
        reason="duplicate_signal_suppressed",
        reason_stage="lifecycle_publishability",
    )

    report = finalize_candidate_funnel_cycle(cycle, data_path=tmp_path / "data", reports_path=tmp_path / "reports")

    state_path = tmp_path / "data" / "runtime" / "candidate_funnel_state.json"
    audit_json = tmp_path / "reports" / "candidate_funnel_audit.json"
    audit_md = tmp_path / "reports" / "candidate_funnel_audit.md"

    assert state_path.exists()
    assert audit_json.exists()
    assert audit_md.exists()
    assert report["rolling_last_5_counts"]["rejected_by_lifecycle_publishability"] == 1
    assert json.loads(audit_json.read_text(encoding="utf-8"))["latest_cycle"]["scan_run_id"] == "run_report"
    assert "Candidate Funnel Audit" in audit_md.read_text(encoding="utf-8")
