from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from trading_signals.app.settings import load_settings
from trading_signals.application.use_cases.daily_dev_report import send_daily_dev_report
from trading_signals.infrastructure.notifications.telegram_notifier import TelegramNotifier


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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="send-daily-dev-report")
    parser.add_argument("--data-path", default="")
    parser.add_argument("--logs-path", default="logs")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_dotenv(Path(args.env_file))
    settings = load_settings()
    data_path = Path(args.data_path) if args.data_path else settings.data_storage_path
    notifier = TelegramNotifier(
        settings.telegram_bot_token,
        settings.telegram_chat_ids,
        settings.telegram_users_file,
        settings.telegram_state_file,
        public_chat_id=settings.telegram_public_chat_id,
        dev_chat_id=settings.telegram_dev_chat_id,
        dev_chat_ids=settings.telegram_dev_chat_ids,
        allowed_private_chat_ids=settings.telegram_allowed_private_chat_ids,
    )
    results = send_daily_dev_report(
        notifier,
        data_path,
        logs_path=Path(args.logs_path),
        dry_run=args.dry_run,
        settings=settings,
    )
    if not args.dry_run:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    failed = [item for item in results if item.get("status") == "failed"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

