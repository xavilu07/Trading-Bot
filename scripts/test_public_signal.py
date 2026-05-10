from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from trading_signals.app.settings import load_settings
from trading_signals.application.use_cases.publish_signal import format_public_signal_message
from trading_signals.infrastructure.notifications.telegram_notifier import TelegramNotifier
from trading_signals.notifications.telegram import send_public_signal


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
    parser = argparse.ArgumentParser(prog="test-public-signal")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_dotenv(Path(args.env_file))
    settings = load_settings()
    notifier = TelegramNotifier(
        settings.telegram_bot_token,
        settings.telegram_chat_ids,
        settings.telegram_users_file,
        settings.telegram_state_file,
        public_chat_id=settings.telegram_public_chat_id,
        dev_chat_id=settings.telegram_dev_chat_id,
        dev_chat_ids=settings.telegram_dev_chat_ids,
    )
    risk_plan = SimpleNamespace(
        entry=68420,
        stop_loss=67890,
        take_profit=69050,
        take_profit_2=69480,
        take_profit_3=70120,
        risk_reward=2.0,
    )
    message = format_public_signal_message(
        "BTCUSDT",
        "long",
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        risk_plan,
    )
    results = send_public_signal(notifier, message, dry_run=args.dry_run)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    failed = [item for item in results if item.get("status") == "failed"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
