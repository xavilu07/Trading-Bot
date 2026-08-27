from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trading_signals.agents.decision_ledger import DEFAULT_DECISION_LEDGER_PATH, append_decision_ledger_entry
from trading_signals.agents.implementation.code_engineer import _parse_conditions
from trading_signals.agents.research_memory import (
    DEFAULT_RESEARCH_MEMORY_PATH,
    load_research_memory,
    save_research_memory,
)
from trading_signals.research.dataset import load_research_dataset
from trading_signals.research.simulator import matches_condition, simulate_exclusion
from trading_signals.research.statistics import compute_metrics

MIN_EVIDENCE_DEFAULT = 20


def reconcile_research_memory(
    *,
    data_path: Path = Path("data"),
    decision_ledger_path: Path = DEFAULT_DECISION_LEDGER_PATH,
    research_memory_path: Path = DEFAULT_RESEARCH_MEMORY_PATH,
    min_evidence: int = MIN_EVIDENCE_DEFAULT,
) -> dict[str, Any]:
    """Reconcile every QIC research-memory experiment against real closed trades.

    QIC proposals are backed by internal backtest/simulation "evidence" that is never
    checked against what actually happened afterward (decision_ledger.later_outcome was
    always left empty). This reuses the same condition-matching engine QIC's own strategy
    simulator uses (research.simulator) against the real canonical trade dataset, so future
    proposals can be judged against reality instead of only their own backtest claim.
    """
    dataset = load_research_dataset(data_path)
    rows = dataset["rows"]
    baseline = compute_metrics(rows)

    memory = load_research_memory(research_memory_path)
    experiments = memory.get("experiments") or {}
    results: list[dict[str, Any]] = []

    for item_id, experiment in experiments.items():
        if not isinstance(experiment, dict):
            continue
        normalized = experiment.get("normalized_conditions") or []
        parsed = _parse_conditions(normalized)
        if not parsed:
            results.append({"experiment_id": item_id, "status": "skipped_unsupported_conditions"})
            continue
        # simulate_exclusion (research.simulator) also expects a "label" per condition for
        # its own report formatting; matches_condition only reads feature/operator/value.
        for condition in parsed:
            op = "=" if condition["operator"] == "==" else condition["operator"]
            condition["label"] = f"exclude {condition['feature']}{op}{condition['value']}"

        # simulate_exclusion flattens the "kept" (remaining-after-exclusion) metrics onto the
        # top-level result and nests the excluded trades' own metrics under "removed_metrics".
        simulation = simulate_exclusion(rows, baseline, parsed)
        kept_metrics = {
            "profit_factor": simulation["profit_factor"],
            "total_r": simulation["total_r"],
            "winrate": simulation["winrate"],
            "closed": simulation["remaining_closed"],
        }
        matched_metrics = simulation["removed_metrics"]
        matched_rows = [row for row in rows if any(matches_condition(row, condition) for condition in parsed)]
        barrier_rows = [row for row in matched_rows if str(row.get("status") or "") != "expired"]
        expired_rows = [row for row in matched_rows if str(row.get("status") or "") == "expired"]

        if matched_metrics["closed"] < min_evidence:
            verdict = "insufficient_real_evidence"
        elif kept_metrics["profit_factor"] > baseline["profit_factor"] and kept_metrics["total_r"] > baseline["total_r"]:
            verdict = "reconciled_supported"
        else:
            verdict = "reconciled_underperforming"

        outcome = {
            "computed_at": _now(),
            "real_trades_evaluated": baseline["closed"],
            "baseline": _pick(baseline),
            "kept_if_excluded": _pick(kept_metrics),
            "matched_trades": _pick(matched_metrics),
            # The barrier-hit vs time-expired split matters more than the blended number:
            # trades that resolve by hitting SL/TP directly have historically performed very
            # differently from trades that time out without hitting either. Segmenting the
            # matched (would-be-excluded) trades this way lets future proposals reason about
            # *why* a filter helps or hurts, not just whether the blended R improved.
            "matched_by_exit_type": {
                "barrier_hit": _pick(compute_metrics(barrier_rows)),
                "time_expired": _pick(compute_metrics(expired_rows)),
            },
            "verdict": verdict,
        }

        experiment["reconciled_outcome"] = outcome
        if verdict != "insufficient_real_evidence":
            experiment["current_status"] = verdict
        experiments[item_id] = experiment

        history = experiment.get("decision_history") or []
        last_proposal_id = history[-1].get("proposal_id") if history else None
        append_decision_ledger_entry(
            {"id": last_proposal_id or item_id, "action": "RECONCILIATION", "context": {"conditions": normalized}},
            path=decision_ledger_path,
            final_decision="RECONCILED_OUTCOME",
            implementation_status=verdict,
            later_outcome=json.dumps(outcome, sort_keys=True),
            notes=(
                f"real_pf={outcome['kept_if_excluded']['pf']} real_total_r={outcome['kept_if_excluded']['total_r']} "
                f"vs baseline_pf={outcome['baseline']['pf']} baseline_total_r={outcome['baseline']['total_r']} "
                f"(n={matched_metrics['closed']})"
            ),
        )
        results.append({"experiment_id": item_id, "proposal_id": last_proposal_id, "verdict": verdict, "matched_closed": matched_metrics["closed"]})

    memory["experiments"] = experiments
    save_research_memory(memory, research_memory_path)
    return {"reconciled_at": _now(), "baseline": _pick(baseline), "experiments_checked": len(results), "results": results}


def _pick(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "pf": metrics.get("profit_factor"),
        "total_r": metrics.get("total_r"),
        "winrate": metrics.get("winrate"),
        "closed": metrics.get("closed"),
    }


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile QIC research memory against real closed trades.")
    parser.add_argument("--data-path", type=Path, default=Path("data"))
    parser.add_argument("--decision-ledger-path", type=Path, default=DEFAULT_DECISION_LEDGER_PATH)
    parser.add_argument("--research-memory-path", type=Path, default=DEFAULT_RESEARCH_MEMORY_PATH)
    parser.add_argument("--min-evidence", type=int, default=MIN_EVIDENCE_DEFAULT)
    args = parser.parse_args(argv)

    result = reconcile_research_memory(
        data_path=args.data_path,
        decision_ledger_path=args.decision_ledger_path,
        research_memory_path=args.research_memory_path,
        min_evidence=args.min_evidence,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
