from __future__ import annotations

from pathlib import Path

from trading_signals.application.use_cases.candidate_funnel import (
    build_candidate_funnel_report,
    load_candidate_funnel_state,
    write_candidate_funnel_outputs,
)


def main() -> int:
    data_path = Path("data")
    reports_path = Path("reports")
    state = load_candidate_funnel_state(data_path)
    cycles = state.get("cycles", [])
    report = build_candidate_funnel_report(cycles if isinstance(cycles, list) else [])
    write_candidate_funnel_outputs(report, data_path=data_path, reports_path=reports_path, cycles=cycles if isinstance(cycles, list) else [])
    print("Candidate Funnel Audit")
    print(f"- cycles_total: {report['cycles_total']}")
    print(f"- conclusion: {report['conclusion']}")
    print(f"- top_disappearance_stage: {report['top_disappearance_stage']['stage']}")
    print(f"- audit_json: {reports_path / 'candidate_funnel_audit.json'}")
    print(f"- audit_md: {reports_path / 'candidate_funnel_audit.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
