from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.secondary_failed_short_edge_tracker import (  # noqa: E402
    analyze_secondary_failed_short_edge_tracker,
    write_secondary_failed_short_edge_tracker_reports,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="secondary-failed-short-edge-tracker")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_secondary_failed_short_edge_tracker(data_path=Path(args.data_path))
    paths = write_secondary_failed_short_edge_tracker_reports(result, Path(args.reports_path))
    print("SECONDARY_FAILED_SHORT_EDGE_TRACKER")
    for profile in result["profiles"]:
        metrics = profile["metrics"]
        print(
            f"- {profile['profile']}: trades={metrics['trades']} | closed={metrics['closed_trades']} | "
            f"WR={metrics['winrate']}% | PF={metrics['profit_factor']} | TotalR={metrics['total_r']} | "
            f"AvgR={metrics['avg_r']} | recommendation={profile['recommendation']}"
        )
    print(f"- Recommendation summary: {result['recommendation_summary']}")
    print(f"- Markdown: {paths['markdown']}")
    print(f"- JSON: {paths['json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
