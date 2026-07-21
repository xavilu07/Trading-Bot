from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from trading_signals.agents.autonomous_orchestrator import PHASES, AutonomousQICOrchestrator
from trading_signals.app.settings import load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the autonomous Quantum Investment Council safely.")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Disable external notifications and code apply.")
    parser.add_argument("--force", action="store_true", help="Bypass input idempotency for research.")
    parser.add_argument("--phase", action="append", choices=PHASES)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--notify", action="store_true", help="Publish eligible health transitions through the guarded notification center.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--data-path", type=Path, default=Path("data"))
    parser.add_argument("--reports-root", type=Path, default=Path("reports"))
    parser.add_argument("--output-path", type=Path, default=Path("reports") / "qic")
    parser.add_argument("--logs-path", type=Path, default=Path("logs"))
    args = parser.parse_args(argv)
    _load_dotenv(args.env_file)
    settings = load_settings()
    orchestrator = AutonomousQICOrchestrator(
        settings=settings,
        data_path=args.data_path,
        reports_root=args.reports_root,
        output_path=args.output_path,
        logs_path=args.logs_path,
    )
    if args.status:
        print(json.dumps(orchestrator.status(), ensure_ascii=False, indent=2))
        return 0
    if args.health:
        health = orchestrator.health()
        if args.notify:
            health["notification_result"] = orchestrator.notify_health(health)
        print(json.dumps(health, ensure_ascii=False, indent=2))
        return 0
    if not args.once and not bool(getattr(settings, "qic_autonomous_enabled", False)):
        print(json.dumps({"status": "disabled", "reason": "QIC_AUTONOMOUS_ENABLED=false"}, indent=2))
        return 0
    dry_run = args.dry_run or bool(getattr(settings, "qic_autonomous_dry_run", True))
    interval = max(60.0, float(getattr(settings, "qic_scheduler_interval_hours", 6)) * 3600)
    while True:
        report = orchestrator.run(phases=args.phase, dry_run=dry_run, force=args.force)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if args.once:
            return 0 if report.get("status") not in {"failed"} else 1
        time.sleep(interval)


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value.strip().strip('"').strip("'")


if __name__ == "__main__":
    raise SystemExit(main())
