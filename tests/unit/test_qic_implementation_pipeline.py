from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from trading_signals.agents.implementation.code_safety_director import code_safety_review
from trading_signals.agents.implementation.code_engineer import run_code_engineer
from trading_signals.agents.implementation.implementation_plan import build_implementation_plan
from trading_signals.agents.implementation.implementation_review_council import (
    run_implementation_review,
    run_implementation_review_for_proposal_id,
)
from trading_signals.agents.implementation.patch_generator import generate_patch_report
from trading_signals.agents.implementation.patch_generator import generate_patch_report
from trading_signals.agents.implementation.rollback_plan import build_rollback_plan
from trading_signals.agents.proposal_store import load_proposals, save_proposals
from trading_signals.agents.qic_event_detector import detect_qic_events
from trading_signals.agents.strategy_knowledge_base import upsert_knowledge_from_proposal
from trading_signals.agents.telegram_approval import handle_approval_callback
from scripts.run_qic_scheduler import run_qic_scheduler_cycle


def test_approve_moves_to_implementation_review_without_generating_patch(tmp_path: Path) -> None:
    proposal_store = tmp_path / "proposals.jsonl"
    kb_path = tmp_path / "strategy_knowledge_base.json"
    output_path = tmp_path / "reports" / "qic"
    proposal = _proposal()
    save_proposals([proposal], proposal_store)
    upsert_knowledge_from_proposal(proposal, path=kb_path)

    result = handle_approval_callback(
        f"agent:approve:{proposal['id']}",
        proposal_store_path=proposal_store,
        knowledge_base_path=kb_path,
        qic_output_path=output_path,
    )

    assert result["status"] == "approved_for_implementation_review"
    assert load_proposals(proposal_store)[0]["status"] == "approved_for_implementation_review"
    assert not (output_path / "generated_patch.json").exists()


def test_implementation_council_allows_valid_structural_htf_filter(tmp_path: Path) -> None:
    proposal = _proposal()

    review = run_implementation_review(proposal, output_path=tmp_path / "reports" / "qic", knowledge_base_path=tmp_path / "kb.json")

    assert review["decision"] == "IMPLEMENTATION_ALLOWED"
    assert review["allowed_to_generate_patch"] is True
    assert review["blockers"] == []
    # Flag/rejection-reason names are now derived from the proposal id (generalized
    # generator, no longer hardcoded to the single htf_alignment filter).
    assert review["required_feature_flags"][0]["name"] == "STRATEGY_V2_1_CONDITION_FILTER_CIO_HTF_AGAINST_ENABLED"
    assert "strategy_v2_1_condition_filter_cio_htf_against" in review["implementation_plan"]["required_rejection_reasons"]
    assert (tmp_path / "reports" / "qic" / "implementation_review.json").exists()
    assert (tmp_path / "reports" / "qic" / "rollback_plan.json").exists()


def test_implementation_council_blocks_trade_reduction_above_60(tmp_path: Path) -> None:
    proposal = _proposal(trade_reduction_pct=75.0)

    review = run_implementation_review(proposal, output_path=tmp_path / "reports" / "qic", knowledge_base_path=tmp_path / "kb.json")

    assert review["allowed_to_generate_patch"] is False
    assert "trade_reduction_above_60" in review["blockers"]


def test_code_safety_blocks_missing_rollback_and_default_true_flag() -> None:
    proposal = _proposal()
    plan = build_implementation_plan(proposal)
    plan["required_feature_flags"][0]["required_default"] = "true"

    result = code_safety_review(proposal, plan, rollback_plan={})

    assert result["allowed"] is False
    assert "feature_flag_default_true" in result["blockers"]
    assert "missing_rollback_plan" in result["blockers"]


def test_patch_generator_creates_report_but_does_not_apply_patch(tmp_path: Path) -> None:
    review = run_implementation_review(_proposal(), output_path=tmp_path / "reports" / "qic", knowledge_base_path=tmp_path / "kb.json")

    patch = generate_patch_report(review, output_path=tmp_path / "reports" / "qic")

    assert patch["status"] == "patch_report_generated"
    assert patch["patch_applied"] is False
    assert (tmp_path / "reports" / "qic" / "generated_patch.json").exists()
    assert "STRATEGY_V2_1_HTF_ALIGNMENT_FILTER_ENABLED=false" in (tmp_path / "reports" / "qic" / "generated_patch.md").read_text()


def test_telegram_implementation_review_button_generates_review(tmp_path: Path) -> None:
    proposal_store = tmp_path / "proposals.jsonl"
    kb_path = tmp_path / "strategy_knowledge_base.json"
    output_path = tmp_path / "reports" / "qic"
    proposal = _proposal()
    save_proposals([proposal], proposal_store)
    upsert_knowledge_from_proposal(proposal, path=kb_path)

    result = handle_approval_callback(
        f"agent:implementation_review:{proposal['id']}",
        proposal_store_path=proposal_store,
        knowledge_base_path=kb_path,
        qic_output_path=output_path,
    )

    assert result["handled"] is True
    assert result["status"] == "review_generated"
    assert result["implementation_review"]["decision"] == "IMPLEMENTATION_ALLOWED"


def test_telegram_generate_patch_only_after_allowed_review(tmp_path: Path) -> None:
    proposal_store = tmp_path / "proposals.jsonl"
    kb_path = tmp_path / "strategy_knowledge_base.json"
    output_path = tmp_path / "reports" / "qic"
    proposal = _proposal()
    save_proposals([proposal], proposal_store)
    upsert_knowledge_from_proposal(proposal, path=kb_path)

    result = handle_approval_callback(
        f"agent:generate_patch:{proposal['id']}",
        proposal_store_path=proposal_store,
        knowledge_base_path=kb_path,
        qic_output_path=output_path,
    )

    assert result["handled"] is True
    assert result["status"] == "patch_report_generated"
    assert json.loads((output_path / "generated_patch.json").read_text())["patch_applied"] is False


def test_code_engineer_dry_run_generates_plan_without_modifying_files(tmp_path: Path) -> None:
    proposal_store, reports_path, project_root = _prepare_code_engineer_fixture(tmp_path)

    report = run_code_engineer(
        proposal_id="cio_htf_against",
        project_root=project_root,
        proposal_store_path=proposal_store,
        reports_path=reports_path,
        dry_run=True,
    )

    assert report["status"] == "dry_run_generated"
    assert report["files_modified"] == []
    # Filenames are now derived from the proposal id (generalized generator, no longer
    # hardcoded to the single htf_alignment filter it originally shipped with).
    generated_module = "src/trading_signals/application/use_cases/strategy_v2_1_condition_filter_cio_htf_against.py"
    assert generated_module in report["files_planned"]
    assert not (project_root / generated_module).exists()


def test_code_engineer_blocks_missing_preconditions(tmp_path: Path) -> None:
    proposal_store = tmp_path / "proposals.jsonl"
    save_proposals([_proposal()], proposal_store)

    report = run_code_engineer(
        proposal_id="cio_htf_against",
        project_root=tmp_path / "project",
        proposal_store_path=proposal_store,
        reports_path=tmp_path / "reports" / "qic",
        dry_run=True,
    )

    assert report["status"] == "failed_preconditions"
    assert "implementation_review_missing" in report["blockers"]
    assert "generated_patch_missing" in report["blockers"]


def test_code_engineer_apply_requires_allow_apply(tmp_path: Path) -> None:
    proposal_store, reports_path, project_root = _prepare_code_engineer_fixture(tmp_path)

    report = run_code_engineer(
        proposal_id="cio_htf_against",
        project_root=project_root,
        proposal_store_path=proposal_store,
        reports_path=reports_path,
        dry_run=False,
        apply=True,
        allow_apply=False,
    )

    assert report["status"] == "failed_preconditions"
    assert "apply_not_allowed" in report["blockers"]


def test_code_engineer_apply_requires_tests_even_when_allowed(tmp_path: Path) -> None:
    proposal_store, reports_path, project_root = _prepare_code_engineer_fixture(tmp_path)

    report = run_code_engineer(
        proposal_id="cio_htf_against",
        project_root=project_root,
        proposal_store_path=proposal_store,
        reports_path=reports_path,
        dry_run=False,
        apply=True,
        allow_apply=True,
    )

    assert report["status"] == "failed_preconditions"
    assert "tests_required_before_apply" in report["blockers"]
    assert report["files_modified"] == []


def test_telegram_generate_code_callback_runs_dry_run(tmp_path: Path) -> None:
    proposal_store, reports_path, _project_root = _prepare_code_engineer_fixture(tmp_path)

    result = handle_approval_callback(
        "agent:generate_code:cio_htf_against",
        proposal_store_path=proposal_store,
        knowledge_base_path=tmp_path / "kb.json",
        qic_output_path=reports_path,
    )

    assert result["handled"] is True
    assert result["action"] == "generate_code"
    assert result["status"] == "dry_run_generated"


def test_telegram_apply_patch_blocked_by_default(tmp_path: Path) -> None:
    proposal_store, reports_path, _project_root = _prepare_code_engineer_fixture(tmp_path)

    result = handle_approval_callback(
        "agent:apply_patch:cio_htf_against",
        proposal_store_path=proposal_store,
        knowledge_base_path=tmp_path / "kb.json",
        qic_output_path=reports_path,
    )

    assert result["handled"] is True
    assert result["status"] == "blocked"
    assert result["reason"] == "qic_code_engineer_apply_disabled"


def test_event_detector_detects_losing_streak_and_pending_approved(tmp_path: Path) -> None:
    trades_path = tmp_path / "data" / "paper_trading" / "trades.csv"
    trades_path.parent.mkdir(parents=True)
    with trades_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["status", "result_r"])
        writer.writeheader()
        for _ in range(5):
            writer.writerow({"status": "sl_hit", "result_r": "-1"})
    proposal_store = tmp_path / "proposals.jsonl"
    proposal = _proposal()
    proposal["status"] = "approved_for_implementation_review"
    save_proposals([proposal], proposal_store)

    result = detect_qic_events(trades_path=trades_path, proposal_store_path=proposal_store)

    assert result["critical"] is True
    assert any(item["type"] == "losing_streak" for item in result["events"])
    assert any(item["type"] == "approved_proposal_pending_implementation" for item in result["events"])


def test_qic_scheduler_once_dry_run_does_not_touch_trading_scheduler(tmp_path: Path, monkeypatch) -> None:
    class Settings:
        agent_committee_min_confidence = "LOW"
        qic_telegram_enabled = False
        qic_telegram_bot_token = ""
        qic_telegram_chat_id = ""
        qic_telegram_send_no_actionable = True
        qic_telegram_min_priority = "LOW"

    calls = {}

    class FakeOrchestrator:
        def __init__(self, **kwargs: object) -> None:
            calls.update(kwargs)
            self.notifications = type("Notifications", (), {"enabled": False})()

        def run(self, **kwargs: object) -> dict[str, object]:
            calls.update(kwargs)
            return {
                "status": "completed",
                "run_id": "run_1",
                "phase_results": {
                    "events": {"result": {"critical": False, "events": []}},
                    "research": {"result": {"proposal_count": 0, "single_proposal": None}},
                    "reports": {"result": {"autonomous_reports": {"daily_brief": {}, "weekly_research_review": {}}}},
                },
            }

    monkeypatch.setattr("scripts.run_qic_scheduler.AutonomousQICOrchestrator", FakeOrchestrator)
    args = argparse.Namespace(
        data_path=tmp_path / "data",
        reports_root=tmp_path / "reports",
        output_path=tmp_path / "reports" / "qic",
        dry_run=True,
    )

    result = run_qic_scheduler_cycle(settings=Settings(), args=args)

    assert result["trading_scheduler_touched"] is False
    assert calls["dry_run"] is True
    assert result["telegram_enabled"] is False


def _proposal(*, trade_reduction_pct: float = 48.9547) -> dict[str, object]:
    return {
        "id": "cio_htf_against",
        "title": "CIO proposal: exclude htf_alignment=against",
        "action": "PROPOSE_IMPLEMENTATION",
        "conditions": ["exclude htf_alignment=against"],
        "expected_pf": 1.113,
        "expected_total_r": 21.1506,
        "baseline_pf": 0.8743,
        "baseline_total_r": -54.1711,
        "trades_lost": 562,
        "baseline_trades": 1148,
        "trade_reduction_pct": trade_reduction_pct,
        "confidence": "HIGH",
        "risk_level": "HIGH",
        "risk_objections": ["high_trade_reduction"],
        "evidence": 586,
        "knowledge_item_id": "edge_htf_against",
        "edge_type": "STRUCTURAL_EDGE",
        "implementation_priority": "HIGH",
        "context": {
            "conditions": ["exclude htf_alignment=against"],
            "normalized_conditions": ["exclude:htf_alignment=against"],
            "source": "single_filter",
            "complexity": 1,
            "baseline_pf": 0.8743,
            "baseline_total_r": -54.1711,
        },
    }


def _prepare_code_engineer_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    proposal_store = tmp_path / "data" / "agent_proposals" / "proposals.jsonl"
    reports_path = tmp_path / "reports" / "qic"
    project_root = tmp_path / "project"
    proposal = _proposal()
    proposal["status"] = "approved_for_implementation_review"
    save_proposals([proposal], proposal_store)
    review = run_implementation_review(proposal, output_path=reports_path, knowledge_base_path=tmp_path / "kb.json")
    patch = generate_patch_report(review, output_path=reports_path)
    assert review["decision"] == "IMPLEMENTATION_ALLOWED"
    assert patch["allowed_to_generate_patch"] is True
    return proposal_store, reports_path, project_root
