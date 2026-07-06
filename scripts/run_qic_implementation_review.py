from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from trading_signals.agents.implementation.implementation_review_council import run_implementation_review_for_proposal_id
from trading_signals.agents.implementation.patch_generator import generate_patch_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run QIC implementation review for an approved proposal.")
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--proposal-store", type=Path, default=Path("data") / "agent_proposals" / "proposals.jsonl")
    parser.add_argument("--output-path", type=Path, default=Path("reports") / "qic")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply-patch", action="store_true", default=False)
    parser.add_argument("--run-tests", action="store_true", default=False)
    args = parser.parse_args(argv)

    review = run_implementation_review_for_proposal_id(
        args.proposal_id,
        proposal_store_path=args.proposal_store,
        output_path=args.output_path,
    )
    patch = generate_patch_report(review, output_path=args.output_path, apply_patch=args.apply_patch)
    test_results = _run_tests(review, output_path=args.output_path) if args.run_tests else _write_test_results(
        {"status": "skipped", "reason": "run_tests_not_requested", "commands": review.get("validation_commands", [])},
        output_path=args.output_path,
    )
    result = {"review": review, "patch": patch, "test_results": test_results}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if review.get("decision") != "REJECT_IMPLEMENTATION" else 1


def _run_tests(review: dict[str, object], *, output_path: Path) -> dict[str, object]:
    commands = [command for command in review.get("validation_commands", []) if isinstance(command, str)]
    results = []
    for command in commands:
        completed = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
        results.append(
            {
                "command": command,
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-2000:],
                "stderr_tail": completed.stderr[-2000:],
            }
        )
        if completed.returncode != 0:
            break
    status = "passed" if results and all(item["returncode"] == 0 for item in results) else "failed"
    return _write_test_results({"status": status, "results": results}, output_path=output_path)


def _write_test_results(payload: dict[str, object], *, output_path: Path) -> dict[str, object]:
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "test_results.json"
    md_path = output_path / "test_results.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_test_results_markdown(payload), encoding="utf-8")
    return payload


def _test_results_markdown(payload: dict[str, object]) -> str:
    lines = ["# QIC Test Results", "", f"- status: {payload.get('status')}", f"- reason: {payload.get('reason', '')}", ""]
    for result in payload.get("results", []) if isinstance(payload.get("results"), list) else []:
        lines.append(f"- `{result.get('command')}` -> {result.get('returncode')}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
