from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.app.settings import load_settings  # noqa: E402
from trading_signals.research.adaptive_filter_manager import (  # noqa: E402
    config_from_settings,
    generate_adaptive_filter_manager_report,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="adaptive-filter-manager")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    parser.add_argument("--runtime-path", default=str(bot_data_dir / "data" / "runtime"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = load_settings()
    config = config_from_settings(settings)
    result = generate_adaptive_filter_manager_report(
        data_path=Path(args.data_path),
        reports_path=Path(args.reports_path),
        runtime_path=Path(args.runtime_path),
        config=config,
    )
    state = result["adaptive_state"]
    print("ADAPTIVE_FILTER_MANAGER")
    print(f"- Enabled: {state['enabled']}")
    print(f"- Mode: {state['mode']}")
    print(f"- Active blocks: {', '.join(state['active_blocks']) or 'none'}")
    print(f"- Proposed blocks: {', '.join(state['proposed_blocks']) or 'none'}")
    print(f"- Proposed unblocks: {', '.join(state['proposed_unblocks']) or 'none'}")
    print(f"- Report: {result['report_path']}")
    print(f"- JSON: {result['json_report_path']}")
    if state["mode"] in {"shadow", "auto_safe"}:
        print(f"- State: {result['state_path']}")
    else:
        print("- State: not written in observe mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
