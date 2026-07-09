from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from trading_signals.agents.committee import run_agent_committee
from trading_signals.agents.qic_autonomous_reports import write_autonomous_qic_reports
from trading_signals.agents.qic_event_detector import detect_qic_events
from trading_signals.agents.telegram_approval import resolve_qic_telegram_config
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
    events = detect_qic_events(trades_path=args.data_path / "paper_trading" / "trades.csv")
    qic_telegram = resolve_qic_telegram_config(settings)
    result = run_agent_committee(
        reports_root=args.reports_root,
        data_path=args.data_path,
        output_path=args.output_path,
        enabled=True,
        min_confidence=str(getattr(settings, "agent_committee_min_confidence", "MEDIUM")),
        telegram_enabled=bool(qic_telegram["enabled"]) and not args.dry_run,
        telegram_bot_token=str(qic_telegram["bot_token"]),
        telegram_chat_id=str(qic_telegram["chat_id"]),
        telegram_send_no_actionable=bool(qic_telegram["send_no_actionable"]),
        telegram_min_priority=str(qic_telegram["min_priority"]),
        dry_run=args.dry_run,
        force=True,
        revalidation_min_new_trades=int(getattr(settings, "qic_revalidation_min_new_trades", 50)),
        edge_confirmation_min_seen=int(getattr(settings, "qic_edge_confirmation_min_seen", 3)),
        edge_reproposal_cooldown_days=int(getattr(settings, "qic_edge_reproposal_cooldown_days", 14)),
        edge_degradation_pf_drop_pct=float(getattr(settings, "qic_edge_degradation_pf_drop_pct", 15)),
    )
    autonomous_reports = write_autonomous_qic_reports(
        output_path=args.output_path,
        knowledge_base_path=args.data_path / "qic" / "strategy_knowledge_base.json",
        research_memory_path=args.data_path / "qic" / "research_memory.json",
        decision_ledger_path=args.data_path / "qic" / "decision_ledger.jsonl",
        events=events.get("events", []),
        daily_enabled=bool(getattr(settings, "qic_daily_brief_enabled", True)),
        weekly_enabled=bool(getattr(settings, "qic_weekly_research_review_enabled", True)),
    )
    proposal = result.get("single_proposal") if isinstance(result, dict) else None
    return {
        "status": "ok",
        "dry_run": args.dry_run,
        "event_mode": "extraordinary" if events.get("critical") else "scheduled",
        "events": events.get("events", []),
        "proposal_count": result.get("proposal_count", 0) if isinstance(result, dict) else 0,
        "proposal_id": proposal.get("id") if isinstance(proposal, dict) else None,
        "telegram_enabled": bool(qic_telegram["enabled"]) and not args.dry_run,
        "trading_scheduler_touched": False,
        "daily_brief_generated": autonomous_reports.get("daily_brief") is not None,
        "weekly_research_review_generated": autonomous_reports.get("weekly_research_review") is not None,
    }


if __name__ == "__main__":
    raise SystemExit(main())
