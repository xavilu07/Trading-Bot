from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.main_signal_long_root_cause_analysis import (  # noqa: E402
    analyze_main_signal_long_root_cause,
    write_main_signal_long_root_cause_reports,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="main-signal-long-root-cause-analysis")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_main_signal_long_root_cause(data_path=Path(args.data_path))
    paths = write_main_signal_long_root_cause_reports(result, Path(args.reports_path))
    baseline = result["main_signal_long_baseline"]
    remaining = result["existing_production_blocks"]["remaining_after_existing_blocks"]
    answers = result["answers"]
    print("MAIN_SIGNAL_LONG_ROOT_CAUSE_ANALYSIS")
    print(f"- MAIN_SIGNAL LONG: trades={baseline['trades']} | WR={baseline['winrate']}% | PF={baseline['profit_factor']} | TotalR={baseline['total_r']}")
    print(f"- Remaining after existing blocks: trades={remaining['trades']} | PF={remaining['profit_factor']} | TotalR={remaining['total_r']}")
    print(f"- Classification: {result['classification']}")
    print(f"- Next non-overlapping root cause: {answers['next_best_non_overlapping_root_cause']}")
    print(f"- Recommended action: {result['recommended_action']}")
    print(f"- Markdown: {paths['markdown']}")
    print(f"- JSON: {paths['json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
