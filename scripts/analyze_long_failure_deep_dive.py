from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.long_failure_deep_dive import (  # noqa: E402
    analyze_long_failure_deep_dive,
    write_long_failure_deep_dive_report,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="long-failure-deep-dive")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_long_failure_deep_dive(data_path=Path(args.data_path))
    report_path = write_long_failure_deep_dive_report(result, Path(args.reports_path))
    long_metrics = result["long_metrics"]
    short_metrics = result["short_metrics"]
    print("LONG_FAILURE_DEEP_DIVE")
    print(f"- LONG trades: {long_metrics['trades']} | WR: {long_metrics['winrate']}% | PF: {long_metrics['profit_factor']} | Total R: {long_metrics['total_r']}")
    print(f"- SHORT trades: {short_metrics['trades']} | WR: {short_metrics['winrate']}% | PF: {short_metrics['profit_factor']} | Total R: {short_metrics['total_r']}")
    print(f"- Classification: {result['classification']}")
    print(f"- Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
