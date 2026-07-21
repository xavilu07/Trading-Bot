from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_signals.agents.implementation.approval_pipeline import (
    format_approval_pipeline_message,
    run_approved_proposal_pipeline,
    update_approval_job,
)
from trading_signals.agents.qic_telegram_config import load_qic_telegram_config
from trading_signals.agents.telegram_approval import send_qic_status_message


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one approved QIC proposal pipeline job.")
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--proposal-store", type=Path, required=True)
    parser.add_argument("--knowledge-base", type=Path, required=True)
    parser.add_argument("--reports-path", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--actor", default="telegram_dev")
    parser.add_argument("--chat-id", default="")
    parser.add_argument("--job-path", type=Path, required=True)
    args = parser.parse_args(argv)

    update_approval_job(args.job_path, status="running")
    try:
        report = run_approved_proposal_pipeline(
            proposal_id=args.proposal_id,
            proposal_store_path=args.proposal_store,
            knowledge_base_path=args.knowledge_base,
            reports_path=args.reports_path,
            actor=args.actor,
            project_root=args.project_root,
        )
    except Exception as exc:  # Last-resort worker boundary.
        report = {
            "proposal_id": args.proposal_id,
            "status": "internal_error",
            "stage": "worker",
            "blockers": [f"{type(exc).__name__}:{exc}"],
            "bot_operational": False,
        }
    update_approval_job(args.job_path, status=report.get("status"), result=report)
    _notify(report, chat_id=args.chat_id)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report.get("status") == "applied":
        return 0
    if report.get("status") == "internal_error":
        return 2
    return 1


def _notify(report: dict[str, object], *, chat_id: str) -> dict[str, object]:
    config = load_qic_telegram_config()
    authorized = {str(item) for item in config.get("chat_ids") or []}
    if not config.get("configured") or not chat_id or chat_id not in authorized:
        return {"status": "skipped", "reason": "qic_telegram_not_configured_or_unauthorized"}
    return send_qic_status_message(
        bot_token=str(config["bot_token"]),
        chat_id=chat_id,
        text=format_approval_pipeline_message(report),
        proposal_id=str(report.get("proposal_id") or "approval_pipeline"),
    )


if __name__ == "__main__":
    raise SystemExit(main())
