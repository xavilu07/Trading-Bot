from __future__ import annotations

from collections import Counter

from trading_signals.agents.agent_models import AgentVote

ACTION_PRIORITY = {
    "WOULD_BLOCK": 4,
    "PRIORITIZE": 3,
    "CAUTION": 2,
    "ALLOW": 1,
}


def coordinate_votes(votes: list[AgentVote]) -> dict[str, object]:
    if not votes:
        return {
            "mode": "SHADOW",
            "consensus_action": "ALLOW",
            "agreement_score": 0.0,
            "disagreements": [],
            "votes": [],
        }

    action_counts = Counter(vote.action for vote in votes)
    consensus_action = _consensus_action(action_counts)
    agreement_score = round(action_counts[consensus_action] / len(votes), 4)
    disagreements = [
        {
            "agent_name": vote.agent_name,
            "action": vote.action,
            "consensus_action": consensus_action,
            "reasons": list(vote.reasons),
            "risks": list(vote.risks),
        }
        for vote in votes
        if vote.action != consensus_action
    ]
    average_score = round(sum(vote.score for vote in votes) / len(votes), 2)
    return {
        "mode": "SHADOW",
        "consensus_action": consensus_action,
        "agreement_score": agreement_score,
        "average_score": average_score,
        "disagreements": disagreements,
        "votes": [vote.to_dict() for vote in votes],
    }


def _consensus_action(action_counts: Counter[str]) -> str:
    max_count = max(action_counts.values())
    tied = [action for action, count in action_counts.items() if count == max_count]
    return max(tied, key=lambda action: ACTION_PRIORITY.get(action, 0))
