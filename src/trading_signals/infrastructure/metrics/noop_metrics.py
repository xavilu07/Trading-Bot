from __future__ import annotations


class NoopMetrics:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    def increment(self, key: str, value: int = 1) -> None:
        self.counters[key] = self.counters.get(key, 0) + value

