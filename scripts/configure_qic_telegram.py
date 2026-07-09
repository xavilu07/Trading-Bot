from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from getpass import getpass
from pathlib import Path
from typing import Any

from trading_signals.agents.qic_telegram_config import DEFAULT_QIC_TELEGRAM_CONFIG_PATH, mask_token


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Configure persistent QIC Telegram DEV credentials.")
    parser.add_argument("--config-path", type=Path, default=DEFAULT_QIC_TELEGRAM_CONFIG_PATH)
    parser.add_argument("--bot-token", default="")
    parser.add_argument("--chat-id", action="append", default=[])
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    bot_token = args.bot_token or getpass("Bot Token: ").strip()
    chat_ids = args.chat_id or [input("Chat ID: ").strip()]
    chat_ids = [str(item).strip() for item in chat_ids if str(item).strip()]
    if not bot_token or not chat_ids:
        print(json.dumps({"status": "failed", "reason": "missing_bot_token_or_chat_id"}, indent=2))
        return 1

    validation = {"get_me": {"status": "skipped"}, "send_message": {"status": "skipped"}}
    if not args.skip_validation:
        validation = validate_telegram_config(bot_token=bot_token, chat_id=chat_ids[0])
        if validation["get_me"]["status"] != "ok" or validation["send_message"]["status"] != "ok":
            print(
                json.dumps(
                    {
                        "status": "failed",
                        "reason": "telegram_validation_failed",
                        "bot_token": mask_token(bot_token),
                        "chat_ids": chat_ids,
                        "validation": validation,
                    },
                    indent=2,
                )
            )
            return 1

    payload = {"bot_token": bot_token, "chat_ids": chat_ids}
    if not args.dry_run:
        write_config(payload, args.config_path)
    print(
        json.dumps(
            {
                "status": "configured" if not args.dry_run else "dry_run",
                "config_path": str(args.config_path),
                "bot_token": mask_token(bot_token),
                "chat_ids": chat_ids,
                "validation": validation,
            },
            indent=2,
        )
    )
    return 0


def validate_telegram_config(*, bot_token: str, chat_id: str) -> dict[str, Any]:
    get_me = _telegram_request(bot_token, "getMe", {})
    send_message = _telegram_request(
        bot_token,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": (
                "🤖 Quantum Investment Council\n\n"
                "Telegram DEV correctamente configurado.\n\n"
                "Si recibes este mensaje significa que el canal de comunicación está listo."
            ),
        },
    )
    return {"get_me": get_me, "send_message": send_message}


def write_config(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.chmod(path, 0o600)


def _telegram_request(bot_token: str, method: str, params: dict[str, Any]) -> dict[str, Any]:
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(f"https://api.telegram.org/bot{bot_token}/{method}", data=data if params else None, method="POST" if params else "GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:  # pragma: no cover - network path
            body = json.loads(response.read().decode("utf-8"))
        return {"status": "ok" if body.get("ok") else "failed", "ok": bool(body.get("ok"))}
    except Exception as exc:  # pragma: no cover - network path
        return {"status": "failed", "error": str(exc)}


if __name__ == "__main__":
    raise SystemExit(main())
