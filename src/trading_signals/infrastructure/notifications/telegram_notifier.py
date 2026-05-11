from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from pathlib import Path

from trading_signals.application.ports.notification_port import NotificationPort


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value).strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


class TelegramNotifier(NotificationPort):
    def __init__(
        self,
        bot_token: str,
        chat_ids: list[str],
        users_file: Path,
        state_file: Path,
        *,
        public_chat_id: str = "",
        dev_chat_id: str = "",
        dev_chat_ids: list[str] | None = None,
        allowed_private_chat_ids: list[str] | None = None,
    ) -> None:
        self.bot_token = bot_token
        self.chat_ids = chat_ids
        self.users_file = users_file
        self.state_file = state_file
        self.public_chat_id = public_chat_id.strip()
        self.dev_chat_id = dev_chat_id.strip()
        self.dev_chat_ids = _dedupe([*(dev_chat_ids or []), *self.dev_chat_id.split(",")])
        self.allowed_private_chat_ids = _dedupe(allowed_private_chat_ids or self.dev_chat_ids)

    def _load_user_ids(self) -> list[str]:
        if not self.users_file.exists():
            return []
        raw = json.loads(self.users_file.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return []
        return [str(item) for item in raw if str(item).strip()]

    def _save_user_ids(self, user_ids: list[str]) -> None:
        self.users_file.parent.mkdir(parents=True, exist_ok=True)
        self.users_file.write_text(
            json.dumps(sorted(set(user_ids)), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _all_recipients(self) -> list[str]:
        return sorted(set(self.chat_ids) | set(self._load_user_ids()))

    def _public_recipients(self) -> list[str]:
        if self.public_chat_id:
            return [self.public_chat_id]
        return self._all_recipients()

    def _dev_recipients(self) -> list[str]:
        if self.dev_chat_ids:
            return self.dev_chat_ids
        if self.dev_chat_id:
            return _dedupe(self.dev_chat_id.split(","))
        return self._all_recipients()

    def is_private_chat_allowed(self, chat_id: str) -> bool:
        if not self.allowed_private_chat_ids:
            return True
        return str(chat_id).strip() in set(self.allowed_private_chat_ids)

    def _unauthorized_private_chat_result(self, chat_id: str, update_id: int | None = None, dry_run: bool = False) -> dict[str, object]:
        logging.getLogger("trading_signals").info(
            "unauthorized_private_chat_ignored",
            extra={"chat_id": chat_id, "update_id": update_id},
        )
        if dry_run:
            result = {
                "recipient": chat_id,
                "status": "unauthorized_private_chat_ignored",
                "provider_message_id": "dry_run",
                "error_message": "unauthorized_private_chat",
            }
        else:
            try:
                result = self._send_message(chat_id, "⛔ Acceso no autorizado.")
                result["status"] = "unauthorized_private_chat_ignored"
                result["error_message"] = "unauthorized_private_chat"
            except Exception as exc:  # pragma: no cover - network path
                result = {
                    "recipient": chat_id,
                    "status": "unauthorized_private_chat_ignored",
                    "provider_message_id": None,
                    "error_message": str(exc),
                }
        if update_id is not None:
            result["update_id"] = update_id
        return result

    def _publish_to_recipients(self, message: str, recipients: list[str], dry_run: bool = False) -> list[dict[str, object]]:
        if dry_run:
            dry_recipients = recipients or ["dry_run"]
            return [{"recipient": chat_id, "status": "sent", "provider_message_id": "dry_run"} for chat_id in dry_recipients]
        if not self.bot_token or not recipients:
            return [
                {
                    "recipient": "unconfigured",
                    "status": "failed",
                    "provider_message_id": None,
                    "error_message": "telegram_not_configured",
                }
            ]
        results: list[dict[str, object]] = []
        for chat_id in recipients:
            try:
                results.append(self._send_message(chat_id, message))
            except Exception as exc:  # pragma: no cover - network path
                results.append({"recipient": chat_id, "status": "failed", "provider_message_id": None, "error_message": str(exc)})
        return results

    def _load_last_update_id(self) -> int | None:
        if not self.state_file.exists():
            return None
        raw = json.loads(self.state_file.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None
        update_id = raw.get("last_update_id")
        return int(update_id) if update_id is not None else None

    def _save_last_update_id(self, update_id: int) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps({"last_update_id": update_id}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _send_message(self, chat_id: str, message: str) -> dict[str, object]:
        payload = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
            data=payload,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            body = json.loads(response.read().decode("utf-8"))
        return {
            "recipient": chat_id,
            "status": "sent",
            "provider_message_id": str(body.get("result", {}).get("message_id", "")),
        }

    def fetch_updates(self, offset: int | None = None) -> dict[str, object]:
        query = ""
        if offset is not None:
            query = f"?offset={offset}"
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{self.bot_token}/getUpdates{query}",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    def sync_start_users(
        self,
        welcome_message: str,
        dry_run: bool = False,
    ) -> list[dict[str, object]]:
        if not self.bot_token:
            return [
                {
                    "recipient": "unconfigured",
                    "status": "failed",
                    "provider_message_id": None,
                    "error_message": "telegram_not_configured",
                }
            ]

        known_users = set(self._load_user_ids())
        try:
            updates = self.fetch_updates()
        except Exception as exc:  # pragma: no cover - network path
            return [
                {
                    "recipient": "updates",
                    "status": "failed",
                    "provider_message_id": None,
                    "error_message": str(exc),
                }
            ]

        results: list[dict[str, object]] = []
        for update in updates.get("result", []):
            message = update.get("message", {})
            if message.get("text") != "/start":
                continue
            chat_id = str(message.get("chat", {}).get("id", "")).strip()
            if not chat_id:
                continue
            if not self.is_private_chat_allowed(chat_id):
                results.append(self._unauthorized_private_chat_result(chat_id, dry_run=dry_run))
                continue
            if chat_id in known_users:
                results.append(
                    {
                        "recipient": chat_id,
                        "status": "known_user",
                        "provider_message_id": None,
                    }
                )
                continue

            known_users.add(chat_id)
            self._save_user_ids(list(known_users))
            if dry_run:
                results.append(
                    {
                        "recipient": chat_id,
                        "status": "welcome_sent",
                        "provider_message_id": "dry_run",
                    }
                )
                continue
            try:
                response = self._send_message(chat_id, welcome_message)
                response["status"] = "welcome_sent"
                results.append(response)
            except Exception as exc:  # pragma: no cover - network path
                results.append(
                    {
                        "recipient": chat_id,
                        "status": "failed",
                        "provider_message_id": None,
                        "error_message": str(exc),
                    }
                )
        return results

    def process_updates(
        self,
        welcome_message: str,
        default_message: str,
        dry_run: bool = False,
    ) -> list[dict[str, object]]:
        if not self.bot_token:
            return [
                {
                    "recipient": "unconfigured",
                    "status": "failed",
                    "provider_message_id": None,
                    "error_message": "telegram_not_configured",
                }
            ]

        known_users = set(self._load_user_ids())
        last_update_id = self._load_last_update_id()
        updates = self.fetch_updates(offset=(last_update_id + 1) if last_update_id is not None else None)
        results: list[dict[str, object]] = []

        for update in updates.get("result", []):
            update_id = int(update.get("update_id", 0))
            if last_update_id is not None and update_id <= last_update_id:
                continue

            message = update.get("message", {})
            chat_id = str(message.get("chat", {}).get("id", "")).strip()
            text = str(message.get("text", "")).strip()

            if not chat_id or not text:
                self._save_last_update_id(update_id)
                last_update_id = update_id
                continue

            if not self.is_private_chat_allowed(chat_id):
                results.append(self._unauthorized_private_chat_result(chat_id, update_id=update_id, dry_run=dry_run))
                self._save_last_update_id(update_id)
                last_update_id = update_id
                continue

            if text == "/start":
                if chat_id in known_users:
                    results.append(
                        {
                            "recipient": chat_id,
                            "status": "known_user",
                            "provider_message_id": None,
                            "update_id": update_id,
                        }
                    )
                else:
                    known_users.add(chat_id)
                    self._save_user_ids(list(known_users))
                    if dry_run:
                        results.append(
                            {
                                "recipient": chat_id,
                                "status": "welcome_sent",
                                "provider_message_id": "dry_run",
                                "update_id": update_id,
                            }
                        )
                    else:
                        response = self._send_message(chat_id, welcome_message)
                        response["status"] = "welcome_sent"
                        response["update_id"] = update_id
                        results.append(response)
            else:
                if dry_run:
                    results.append(
                        {
                            "recipient": chat_id,
                            "status": "auto_reply_sent",
                            "provider_message_id": "dry_run",
                            "update_id": update_id,
                        }
                    )
                else:
                    response = self._send_message(chat_id, default_message)
                    response["status"] = "auto_reply_sent"
                    response["update_id"] = update_id
                    results.append(response)

            self._save_last_update_id(update_id)
            last_update_id = update_id

        return results

    def publish(self, message: str, dry_run: bool = False) -> list[dict[str, object]]:
        return self.send_dev_message(message, dry_run=dry_run)

    def send_public_signal(self, message: str, dry_run: bool = False) -> list[dict[str, object]]:
        return self._publish_to_recipients(message, self._public_recipients(), dry_run=dry_run)

    def send_dev_message(self, message: str, dry_run: bool = False) -> list[dict[str, object]]:
        return self._publish_to_recipients(message, self._dev_recipients(), dry_run=dry_run)

    def send_dev_signal_detail(self, message: str, dry_run: bool = False) -> list[dict[str, object]]:
        return self.send_dev_message(message, dry_run=dry_run)
