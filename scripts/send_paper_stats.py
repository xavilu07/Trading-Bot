from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from trading_signals.app.settings import load_settings
from trading_signals.application.use_cases.paper_stats import send_paper_performance_summary
from trading_signals.infrastructure.notifications.telegram_notifier import TelegramNotifier


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="send-paper-stats")
    parser.add_argument("--data-path", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = load_settings()
    data_path = Path(args.data_path) if args.data_path else settings.data_storage_path
    notifier = TelegramNotifier(
        settings.telegram_bot_token,
        settings.telegram_chat_ids,
        settings.telegram_users_file,
        settings.telegram_state_file,
        public_chat_id=settings.telegram_public_chat_id,
        dev_chat_id=settings.telegram_dev_chat_id,
    )
    results = send_paper_performance_summary(notifier, data_path, dry_run=args.dry_run)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    failed = [item for item in results if item.get("status") == "failed"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
