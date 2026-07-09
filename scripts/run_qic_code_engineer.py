from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from trading_signals.agents.implementation.code_engineer import run_code_engineer
from trading_signals.app.settings import load_settings


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run QIC Code Engineer V1 safely.")
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--proposal-store", type=Path, default=Path("data") / "agent_proposals" / "proposals.jsonl")
    parser.add_argument("--reports-path", type=Path, default=Path("reports") / "qic")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true", default=False)
    parser.add_argument("--run-tests", action="store_true", default=False)
    args = parser.parse_args(argv)

    load_dotenv(args.env_file)
    settings = load_settings()
    allow_apply = bool(getattr(settings, "qic_code_engineer_enabled", False)) and bool(
        getattr(settings, "qic_code_engineer_allow_apply", False)
    )
    max_autofix = int(getattr(settings, "qic_code_engineer_max_autofix_attempts", 1) or 1)
    dry_run = not args.apply or args.dry_run
    if args.apply:
        dry_run = False
    report = run_code_engineer(
        proposal_id=args.proposal_id,
        project_root=args.project_root,
        proposal_store_path=args.proposal_store,
        reports_path=args.reports_path,
        dry_run=dry_run,
        apply=args.apply,
        run_tests=args.run_tests,
        allow_apply=allow_apply,
        max_autofix_attempts=max_autofix,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") not in {"failed_preconditions", "failed_tests"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
