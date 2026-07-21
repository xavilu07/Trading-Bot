from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from trading_signals.agents.autonomous_orchestrator import AutonomousQICOrchestrator
from trading_signals.app.settings import load_settings


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value.strip().strip('"').strip("'")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run independent QIC scheduler.")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--reports-root", type=Path, default=Path("reports"))
    parser.add_argument("--data-path", type=Path, default=Path("data"))
    parser.add_argument("--output-path", type=Path, default=Path("reports") / "qic")
    args = parser.parse_args(argv)

    load_dotenv(args.env_file)
    settings = load_settings()
    if not bool(getattr(settings, "qic_scheduler_enabled", False)) and not args.force and not args.once:
        print(json.dumps({"status": "disabled", "reason": "QIC_SCHEDULER_ENABLED=false"}, indent=2))
        return 0
    interval = float(getattr(settings, "qic_scheduler_interval_hours", 6) or 6) * 3600
    while True:
        result = run_qic_scheduler_cycle(settings=settings, args=args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.once:
            return 0
        time.sleep(max(interval, 60))


def run_qic_scheduler_cycle(*, settings: object, args: argparse.Namespace) -> dict[str, object]:
    orchestrator = AutonomousQICOrchestrator(
        settings=settings,
        data_path=args.data_path,
        reports_root=args.reports_root,
        output_path=args.output_path,
        logs_path=args.output_path.parent / "logs",
    )
    report = orchestrator.run(dry_run=bool(args.dry_run), force=True)
    event_result = _phase_payload(report, "events")
    research_result = _phase_payload(report, "research")
    reports_result = _phase_payload(report, "reports")
    proposal = research_result.get("single_proposal") if isinstance(research_result, dict) else None
    autonomous_reports = reports_result.get("autonomous_reports") if isinstance(reports_result, dict) else {}
    return {
        "status": report.get("status", "failed"),
        "run_id": report.get("run_id"),
        "dry_run": args.dry_run,
        "event_mode": "extraordinary" if event_result.get("critical") else "scheduled",
        "events": event_result.get("events", []),
        "proposal_count": research_result.get("proposal_count", 0),
        "proposal_id": proposal.get("id") if isinstance(proposal, dict) else None,
        "telegram_enabled": bool(orchestrator.notifications.enabled) and not args.dry_run,
        "trading_scheduler_touched": False,
        "daily_brief_generated": isinstance(autonomous_reports, dict) and autonomous_reports.get("daily_brief") is not None,
        "weekly_research_review_generated": isinstance(autonomous_reports, dict) and autonomous_reports.get("weekly_research_review") is not None,
    }


def _phase_payload(report: dict[str, object], phase: str) -> dict[str, object]:
    phases = report.get("phase_results") if isinstance(report.get("phase_results"), dict) else {}
    phase_result = phases.get(phase) if isinstance(phases, dict) else {}
    payload = phase_result.get("result") if isinstance(phase_result, dict) else {}
    return payload if isinstance(payload, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
