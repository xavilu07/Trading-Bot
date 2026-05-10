from __future__ import annotations

import sys
from pathlib import Path

from trading_signals.application.use_cases.experimental_paper import ExperimentalSignalStore, format_experimental_summary


def main(argv: list[str] | None = None) -> int:
    base_path = Path(argv[0]) if argv else Path("data")
    store = ExperimentalSignalStore(base_path)
    print(format_experimental_summary(store.build_summary()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
