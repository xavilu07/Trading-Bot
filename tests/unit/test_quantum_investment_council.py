from __future__ import annotations

import json
from pathlib import Path

from trading_signals.agents.agent_memory import load_agent_memory, update_agent_memory
from trading_signals.agents.cio import build_cio_consensus
from trading_signals.agents.committee import run_quantum_investment_council_v2
from trading_signals.agents.debate_engine import run_debate_engine
from trading_signals.agents.telegram_approval import send_cio_proposal_for_approval


def test_debate_engine_runs_full_pipeline(tmp_path: Path) -> None:
    _write_qic_reports(tmp_path)

    debate = run_debate_engine(reports_root=tmp_path / "reports")

    assert debate["pipeline"] == ["Research", "Strategy", "Risk", "Simulation", "Research", "CIO"]
    assert [item["stage"] for item in debate["interventions"]] == [
        "research",
        "strategy",
        "risk",
        "simulation",
        "research_response",
    ]


def test_agent_memory_tracks_interventions_and_status(tmp_path: Path) -> None:
    path = tmp_path / "agent_memory.json"
    interventions = [{"agent": "research_director", "content": "hypothesis"}]
    proposal = {"status": "approved"}

    memory = update_agent_memory(interventions, proposal, path=path)

    assert memory["agents"]["research_director"]["proposals_accepted"] == 1
    assert load_agent_memory(path)["agents"]["research_director"]["historical_precision"] == 1.0


def test_cio_generates_single_proposal_from_consensus(tmp_path: Path) -> None:
    _write_qic_reports(tmp_path)
    debate = run_debate_engine(reports_root=tmp_path / "reports")

    consensus = build_cio_consensus(debate, min_confidence="LOW")

    assert consensus["single_proposal"] is not None
    assert consensus["single_proposal"]["id"].startswith("cio_")
    assert isinstance(consensus["single_proposal"]["agent_votes"], list)
    assert consensus["single_proposal"]["action"] == "IMPLEMENTATION_CANDIDATE"
    assert consensus["single_proposal"]["baseline_trades"] == 1148
    assert consensus["single_proposal"]["trade_reduction_pct"] < 25


def test_cio_discards_weak_proposal_when_confidence_too_low(tmp_path: Path) -> None:
    _write_qic_reports(tmp_path, confidence="LOW")
    debate = run_debate_engine(reports_root=tmp_path / "reports")

    consensus = build_cio_consensus(debate, min_confidence="HIGH")

    assert consensus["single_proposal"] is None
    assert "below_min_confidence" in consensus["discard_reasons"]


def test_cio_marks_extreme_reduction_as_variant_search(tmp_path: Path) -> None:
    _write_qic_reports(
        tmp_path,
        trades_eliminated=864,
        remaining_closed=284,
        profit_factor=1.6693,
        total_r=43.8517,
        delta_total_r=43.8517,
    )
    debate = run_debate_engine(reports_root=tmp_path / "reports")

    consensus = build_cio_consensus(debate, min_confidence="LOW")

    proposal = consensus["single_proposal"]
    assert proposal is not None
    assert proposal["risk_level"] == "EXTREME"
    assert proposal["action"] == "REQUIRES_VARIANT_SEARCH"
    assert proposal["baseline_trades"] == 1148
    assert proposal["trade_reduction_pct"] == 75.2613
    assert "extreme_trade_reduction" in proposal["risk_objections"]


def test_qic_report_includes_risk_objections_for_extreme_reduction(tmp_path: Path) -> None:
    _write_qic_reports(tmp_path, trades_eliminated=864, remaining_closed=284, profit_factor=1.6693, total_r=43.8517)

    result = run_quantum_investment_council_v2(
        reports_root=tmp_path / "reports",
        data_path=tmp_path / "data",
        output_path=tmp_path / "reports" / "qic",
        min_confidence="LOW",
        telegram_enabled=False,
    )

    proposal = result["single_proposal"]
    assert proposal["action"] == "REQUIRES_MANUAL_RESEARCH"
    assert "extreme_trade_reduction" in proposal["risk_objections"]
    assert "no_profitable_variant_found" in proposal["risk_objections"]
    report = json.loads((tmp_path / "reports" / "qic" / "proposal.json").read_text())
    assert "extreme_trade_reduction" in report["risk_objections"]
    assert "no_profitable_variant_found" in report["risk_objections"]
    assert "risk_objections" in (tmp_path / "reports" / "qic" / "proposal.md").read_text()


def test_qic_persists_reports_and_only_one_proposal(tmp_path: Path) -> None:
    _write_qic_reports(tmp_path)

    result = run_quantum_investment_council_v2(
        reports_root=tmp_path / "reports",
        data_path=tmp_path / "data",
        output_path=tmp_path / "reports" / "qic",
        min_confidence="LOW",
        telegram_enabled=False,
    )

    assert result["proposal_count"] in {0, 1}
    assert len(result["proposals"]) <= 1
    for name in ("debate", "consensus", "proposal", "agent_memory"):
        assert (tmp_path / "reports" / "qic" / f"{name}.json").exists()
        assert (tmp_path / "reports" / "qic" / f"{name}.md").exists()
        json.loads((tmp_path / "reports" / "qic" / f"{name}.json").read_text())
    if result["proposal_count"]:
        rows = [line for line in (tmp_path / "data" / "agent_proposals" / "proposals.jsonl").read_text().splitlines() if line.strip()]
        assert len(rows) == 1


def test_telegram_sends_only_cio_proposal_payload_in_dry_run() -> None:
    proposal = {
        "id": "cio_1",
        "title": "CIO proposal",
        "hypothesis": "Test",
        "expected_pf": 1.2,
        "expected_total_r": 10,
        "trades_lost": 20,
        "confidence": "MEDIUM",
        "risk_level": "LOW",
        "evidence": 100,
    }

    result = send_cio_proposal_for_approval(proposal, bot_token="token", chat_id="chat", dry_run=True)

    assert len(result) == 1
    assert result[0]["status"] == "dry_run"
    buttons = result[0]["payload"]["reply_markup"]["inline_keyboard"][0]
    assert [button["text"] for button in buttons] == ["APPROVE", "REJECT", "DETAILS"]


def _write_qic_reports(
    tmp_path: Path,
    *,
    confidence: str = "MEDIUM",
    trades_eliminated: int = 100,
    remaining_closed: int = 586,
    profit_factor: float = 1.113,
    total_r: float = 21.1506,
    delta_total_r: float = 75.3217,
) -> None:
    simulator = tmp_path / "reports" / "strategy_simulator"
    simulator.mkdir(parents=True)
    simulation = {
        "simulation_type": "exclude",
        "conditions": ["exclude htf_alignment=against"],
        "condition_details": [{"feature": "htf_alignment", "operator": "==", "value": "against"}],
        "trades_eliminated": trades_eliminated,
        "remaining_closed": remaining_closed,
        "winrate": 45.0,
        "profit_factor": profit_factor,
        "total_r": total_r,
        "delta_total_r": delta_total_r,
        "confidence": confidence,
    }
    (simulator / "single_filters.json").write_text(json.dumps({"simulations": [simulation]}), encoding="utf-8")
    (simulator / "double_filters.json").write_text(json.dumps({"simulations": []}), encoding="utf-8")
    (simulator / "triple_filters.json").write_text(json.dumps({"simulations": []}), encoding="utf-8")
    (simulator / "best_configs.json").write_text(json.dumps({"configs": [simulation]}), encoding="utf-8")
    (simulator / "overview.json").write_text(json.dumps({"baseline": {"closed": 1148}}), encoding="utf-8")
    historical = tmp_path / "reports" / "historical_intelligence"
    historical.mkdir(parents=True)
    (historical / "negative_edges.json").write_text(
        json.dumps({"edges": [{"label": "htf against", "closed": 562, "profit_factor": 0.6, "total_r": -75, "confidence": confidence}]}),
        encoding="utf-8",
    )
    (historical / "positive_edges.json").write_text(json.dumps({"edges": []}), encoding="utf-8")
    quant = tmp_path / "reports" / "quant_research"
    quant.mkdir(parents=True)
    (quant / "feature_importance.json").write_text(
        json.dumps({"features": [{"feature": "htf_alignment", "importance_score": 10, "closed": 1148}]}),
        encoding="utf-8",
    )
