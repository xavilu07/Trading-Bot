from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_signals.risk.trading_pause import DEFAULT_PAUSE_PATH, resume_trading


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manually resume new-trade creation after a kill-switch pause.")
    parser.add_argument("--actor", default="xavi_manual")
    parser.add_argument("--pause-path", type=Path, default=DEFAULT_PAUSE_PATH)
    args = parser.parse_args(argv)

    state = resume_trading(actor=args.actor, path=args.pause_path)
    print(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
