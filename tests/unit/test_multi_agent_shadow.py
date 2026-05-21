from __future__ import annotations

from dataclasses import dataclass

from trading_signals.agents.agent_models import AgentVote
from trading_signals.agents.coordinator import coordinate_votes
from trading_signals.agents.historical_agent import vote_historical
from trading_signals.agents.risk_agent import vote_risk
from trading_signals.agents.skeptic_agent import vote_skeptic
from trading_signals.agents.technical_agent import vote_technical


@dataclass
class DummyEvaluation:
    setup_score: float = 85.0
    passed_filters: list[str] | None = None
    failed_filters: list[str] | None = None
    rejection_reasons: list[str] | None = None
    decision_trace: list[str] | None = None


@dataclass
class DummyRiskPlan:
    risk_reward: float = 2.0
    stop_loss: float = 99.0
    take_profit: float = 104.0


def test_agent_vote_validates_and_serializes() -> None:
    vote = AgentVote("test", "allow", "medium", 150, ["ok"], ["risk"])

    assert vote.action == "ALLOW"
    assert vote.confidence == "MEDIUM"
    assert vote.score == 100.0
    assert vote.to_dict()["agent_name"] == "test"


def test_each_agent_returns_valid_vote() -> None:
    evaluation = DummyEvaluation(
        passed_filters=["primary_sweep_setup", "timeframe_alignment"],
        failed_filters=[],
        rejection_reasons=[],
        decision_trace=["penalties=none"],
    )
    setup_context = {
        "entry_context": "BREAKOUT",
        "rr_valid": True,
        "avoidance_warnings": [],
    }
    performance_gate = {
        "action": "ALLOW",
        "confidence": "MEDIUM",
        "scores": {"historical_edge_score": 60},
        "reasons": ["history acceptable"],
        "risks": [],
    }

    votes = [
        vote_technical(setup_context=setup_context, evaluation=evaluation),
        vote_risk(risk_plan=DummyRiskPlan(), setup_context=setup_context),
        vote_historical(performance_gate=performance_gate),
        vote_skeptic(evaluation=evaluation, setup_context=setup_context, performance_gate=performance_gate),
    ]

    assert {vote.agent_name for vote in votes} == {
        "technical_agent",
        "risk_agent",
        "historical_agent",
        "skeptic_agent",
    }
    assert all(vote.action in {"ALLOW", "CAUTION", "WOULD_BLOCK", "PRIORITIZE"} for vote in votes)
    assert all(vote.confidence in {"LOW", "MEDIUM", "HIGH"} for vote in votes)


def test_historical_agent_uses_performance_gate_would_block() -> None:
    vote = vote_historical(
        performance_gate={
            "action": "CAUTION",
            "would_block": True,
            "confidence": "HIGH",
            "scores": {"meta_decision_score": 20, "trade_quality_score": 30},
            "risks": ["negative historical edge"],
        }
    )

    assert vote.action == "WOULD_BLOCK"
    assert vote.confidence == "HIGH"
    assert "performance gate would block" in vote.risks


def test_coordinator_detects_consensus_and_disagreements() -> None:
    votes = [
        AgentVote("technical", "ALLOW", "MEDIUM", 70),
        AgentVote("risk", "ALLOW", "MEDIUM", 75),
        AgentVote("historical", "WOULD_BLOCK", "HIGH", 20, risks=["bad history"]),
    ]

    decision = coordinate_votes(votes)

    assert decision["mode"] == "SHADOW"
    assert decision["consensus_action"] == "ALLOW"
    assert decision["agreement_score"] == 0.6667
    assert decision["disagreements"][0]["agent_name"] == "historical"


def test_coordinator_tie_prefers_more_conservative_action() -> None:
    decision = coordinate_votes(
        [
            AgentVote("technical", "ALLOW", "MEDIUM", 70),
            AgentVote("skeptic", "WOULD_BLOCK", "HIGH", 20),
        ]
    )

    assert decision["consensus_action"] == "WOULD_BLOCK"
