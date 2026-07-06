from __future__ import annotations

from typing import Any


def test_director_review(plan: dict[str, Any]) -> dict[str, Any]:
    required_tests = [
        "flag false does not block",
        "enabled hard_block blocks htf_alignment=against",
        "aligned does not block",
        "unknown does not block",
        "rejection_reason recorded",
    ]
    validation_commands = [
        "python3 -m py_compile src/trading_signals/application/use_cases/strategy_v2_1_htf_alignment_filter.py",
        "MPLBACKEND=Agg .venv/bin/pytest -q tests/unit/test_strategy_v2_1_htf_alignment_filter.py",
        "MPLBACKEND=Agg .venv/bin/pytest -q",
        "PYTHONPATH=src .venv/bin/python scripts/run_strategy_simulator.py --mode shadow --min-trades 1",
        "PYTHONPATH=src .venv/bin/python scripts/run_agent_committee.py --force --dry-run --min-confidence LOW",
    ]
    blockers = []
    if not plan.get("files_to_touch"):
        blockers.append("no_testable_files_defined")
    return {
        "agent": "test_director",
        "decision": "PASS" if not blockers else "BLOCK",
        "allowed": not blockers,
        "required_tests": required_tests,
        "validation_commands": validation_commands,
        "blockers": blockers,
    }
