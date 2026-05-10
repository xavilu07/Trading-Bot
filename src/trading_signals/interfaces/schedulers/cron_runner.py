from __future__ import annotations

from trading_signals.app.cli import main


def run() -> int:
    return main(["scheduler"])
