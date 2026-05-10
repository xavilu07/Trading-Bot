from __future__ import annotations

import sys
from pathlib import Path

from trading_signals.application.use_cases.modular_paper import ModularSignalStore, format_modular_summary


def main(argv: list[str] | None = None) -> int:
    base_path = Path(argv[0]) if argv else Path("data")
    store = ModularSignalStore(base_path)
    print(format_modular_summary(store.build_summary()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
