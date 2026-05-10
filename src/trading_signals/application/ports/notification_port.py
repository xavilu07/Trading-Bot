from __future__ import annotations

from typing import Protocol


class NotificationPort(Protocol):
    def publish(self, message: str, dry_run: bool = False) -> list[dict[str, object]]:
        ...

