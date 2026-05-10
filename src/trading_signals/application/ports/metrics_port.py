from __future__ import annotations

from typing import Protocol


class MetricsPort(Protocol):
    def increment(self, key: str, value: int = 1) -> None:
        ...

