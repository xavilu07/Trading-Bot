from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_signals.agents.implementation.code_changes import CodeChangeManager
from trading_signals.agents.notification_center import QICNotificationCenter
from trading_signals.agents.telegram_approval import resolve_qic_telegram_config
from trading_signals.app.settings import load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect and safely manage QIC code changes.")
    parser.add_argument("action", choices=("list", "show", "apply", "rollback", "verify"))
    parser.add_argument("change_id", nargs="?")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--human-approved", action="store_true")
    args = parser.parse_args(argv)
    settings = load_settings()
    manager = CodeChangeManager(
        project_root=args.project_root,
        allowlist=list(getattr(settings, "qic_change_allowlist", [])),
        denylist=list(getattr(settings, "qic_change_denylist", [])),
    )
    if args.action == "list":
        result: object = manager.list_changes()
    elif not args.change_id:
        parser.error("change_id is required for this action")
    elif args.action == "show":
        result = manager.get(args.change_id)
    elif args.action == "verify":
        result = manager.verify(args.change_id)
    elif args.action == "rollback":
        result = manager.rollback(args.change_id, manual_approval=args.human_approved)
    else:
        result = manager.apply(
            args.change_id,
            auto=False,
            manual_approval=args.human_approved,
            live_trading_changes_allowed=bool(getattr(settings, "qic_live_trading_changes_allowed", False)),
        )
    _notify_change_result(args.action, result, settings=settings)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _notify_change_result(action: str, result: object, *, settings: object) -> None:
    if not isinstance(result, dict):
        return
    status = str(result.get("final_status") or result.get("status") or "")
    event_type = None
    if action == "apply" and status == "applied":
        event_type = "CODE_APPLIED"
    elif action == "rollback" and status == "rolled_back":
        event_type = "CODE_ROLLED_BACK"
    if not event_type:
        return
    config = resolve_qic_telegram_config(settings)
    center = QICNotificationCenter(
        bot_token=str(config.get("bot_token") or ""),
        chat_ids=list(config.get("chat_ids") or []),
        enabled=bool(getattr(settings, "qic_telegram_enabled", False)) and bool(config.get("configured")),
    )
    center.publish(
        event_type,
        title=f"QIC code change {status}",
        message=f"Change {result.get('change_id')} finished with status {status}.",
        priority="CRITICAL",
        context={"change_id": result.get("change_id"), "status": status, "approval_source": result.get("approval_source")},
        dedupe_key=f"{event_type}:{result.get('change_id')}:{status}",
    )


if __name__ == "__main__":
    raise SystemExit(main())
