from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from trading_signals.agents.telegram_approval import (
    poll_approval_callbacks,
    resolve_qic_telegram_config,
    send_cio_proposal_for_approval,
    send_qic_test_message,
)
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
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Test QIC Telegram DEV communication.")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--proposal-path", type=Path, default=Path("reports") / "qic" / "proposal.json")
    parser.add_argument("--proposal", action="store_true", help="Send latest QIC proposal with inline buttons.")
    parser.add_argument("--poll-once", action="store_true", help="Process pending Telegram approval callbacks once.")
    parser.add_argument("--poll", action="store_true", help="Continuously process Telegram approval callbacks.")
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    load_dotenv(args.env_file)
    settings = load_settings()
    config = resolve_qic_telegram_config(settings)
    if not config["configured"]:
        print(
            json.dumps(
                {
                    "status": "skipped",
                    "reason": "qic_telegram_not_configured",
                    "required": ["QIC_TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN", "QIC_TELEGRAM_CHAT_ID or TELEGRAM_DEV_CHAT_ID"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    if args.poll or args.poll_once:
        return _run_polling(config, args)

    results = [send_qic_test_message(bot_token=config["bot_token"], chat_id=config["chat_id"], dry_run=args.dry_run)]
    if args.proposal:
        proposal = _load_proposal(args.proposal_path)
        results.extend(
            send_cio_proposal_for_approval(
                proposal,
                bot_token=config["bot_token"],
                chat_id=config["chat_id"],
                dry_run=args.dry_run,
            )
        )
    print(json.dumps({"status": "ok", "results": results}, ensure_ascii=False, indent=2))
    return 0 if all(item.get("status") in {"sent", "dry_run"} for item in results) else 1


def _run_polling(config: dict[str, Any], args: argparse.Namespace) -> int:
    while True:
        result = poll_approval_callbacks(
            bot_token=str(config["bot_token"]),
            limit=args.limit,
            timeout=args.timeout,
            dry_run=args.dry_run,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.poll_once:
            return 0 if result.get("status") in {"ok", "dry_run"} else 1
        time.sleep(max(args.poll_interval, 1.0))


def _load_proposal(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return raw if isinstance(raw, dict) and raw.get("id") else None


if __name__ == "__main__":
    raise SystemExit(main())
