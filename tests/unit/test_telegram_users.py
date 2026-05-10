from __future__ import annotations

import json
from pathlib import Path

from trading_signals.infrastructure.notifications.telegram_notifier import TelegramNotifier


class StubTelegramNotifier(TelegramNotifier):
    def __init__(self, users_file: Path, updates: dict[str, object]) -> None:
        super().__init__("token", ["static-chat"], users_file, users_file.parent / "telegram_state.json")
        self._updates = updates
        self.sent_messages: list[tuple[str, str]] = []

    def fetch_updates(self, offset: int | None = None) -> dict[str, object]:
        return self._updates

    def _send_message(self, chat_id: str, message: str) -> dict[str, object]:
        self.sent_messages.append((chat_id, message))
        return {
            "recipient": chat_id,
            "status": "sent",
            "provider_message_id": f"msg-{len(self.sent_messages)}",
        }


def test_start_saves_new_user_and_sends_welcome_once(tmp_path: Path) -> None:
    users_file = tmp_path / "telegram_users.json"
    notifier = StubTelegramNotifier(
        users_file,
        {
            "result": [
                {
                    "message": {
                        "text": "/start",
                        "chat": {"id": 12345},
                    }
                }
            ]
        },
    )

    first = notifier.sync_start_users("Bienvenido")
    second = notifier.sync_start_users("Bienvenido")

    assert first == [
        {
            "recipient": "12345",
            "status": "welcome_sent",
            "provider_message_id": "msg-1",
        }
    ]
    assert second == [
        {
            "recipient": "12345",
            "status": "known_user",
            "provider_message_id": None,
        }
    ]
    assert notifier.sent_messages == [("12345", "Bienvenido")]
    assert json.loads(users_file.read_text(encoding="utf-8")) == ["12345"]


def test_publish_keeps_signals_separate_from_welcome_flow(tmp_path: Path) -> None:
    users_file = tmp_path / "telegram_users.json"
    users_file.write_text(json.dumps(["12345"]), encoding="utf-8")
    notifier = StubTelegramNotifier(users_file, {"result": []})

    result = notifier.publish("LONG BTCUSDT")

    assert result == [
        {
            "recipient": "12345",
            "status": "sent",
            "provider_message_id": "msg-1",
        },
        {
            "recipient": "static-chat",
            "status": "sent",
            "provider_message_id": "msg-2",
        },
    ]
    assert notifier.sent_messages == [
        ("12345", "LONG BTCUSDT"),
        ("static-chat", "LONG BTCUSDT"),
    ]


def test_public_and_dev_routing_use_dedicated_chat_ids(tmp_path: Path) -> None:
    users_file = tmp_path / "telegram_users.json"
    notifier = StubTelegramNotifier(users_file, {"result": []})
    notifier.public_chat_id = "public-chat"
    notifier.dev_chat_id = "dev-chat"

    public_result = notifier.send_public_signal("PUBLIC SIGNAL")
    dev_result = notifier.send_dev_message("DEV SUMMARY")

    assert public_result[0]["recipient"] == "public-chat"
    assert dev_result[0]["recipient"] == "dev-chat"
    assert notifier.sent_messages == [
        ("public-chat", "PUBLIC SIGNAL"),
        ("dev-chat", "DEV SUMMARY"),
    ]


def test_process_updates_deduplicates_and_replies_to_normal_messages(tmp_path: Path) -> None:
    users_file = tmp_path / "telegram_users.json"
    notifier = StubTelegramNotifier(
        users_file,
        {
            "result": [
                {
                    "update_id": 100,
                    "message": {
                        "text": "/start",
                        "chat": {"id": 12345},
                    },
                },
                {
                    "update_id": 101,
                    "message": {
                        "text": "hola",
                        "chat": {"id": 12345},
                    },
                },
            ]
        },
    )

    first = notifier.process_updates("Bienvenido", "Respuesta automática")
    second = notifier.process_updates("Bienvenido", "Respuesta automática")

    assert first == [
        {
            "recipient": "12345",
            "status": "welcome_sent",
            "provider_message_id": "msg-1",
            "update_id": 100,
        },
        {
            "recipient": "12345",
            "status": "auto_reply_sent",
            "provider_message_id": "msg-2",
            "update_id": 101,
        },
    ]
    assert second == []
    assert notifier.sent_messages == [
        ("12345", "Bienvenido"),
        ("12345", "Respuesta automática"),
    ]
    assert json.loads((tmp_path / "telegram_state.json").read_text(encoding="utf-8")) == {
        "last_update_id": 101
    }
