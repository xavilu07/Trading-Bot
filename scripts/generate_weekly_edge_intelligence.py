from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.weekly_edge_intelligence import generate_weekly_edge_intelligence  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="weekly-edge-intelligence")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = generate_weekly_edge_intelligence(data_path=Path(args.data_path), reports_path=Path(args.reports_path))
    print("WEEKLY_EDGE_INTELLIGENCE")
    for profile in result["profiles"]:
        metrics = profile["metrics"]
        print(
            f"- {profile['profile']}: trades={metrics['trades']} | closed={metrics['closed_trades']} | "
            f"WR={metrics['winrate']}% | PF={metrics['profit_factor']} | TotalR={metrics['total_r']} | "
            f"AvgR={metrics['avg_r']} | new_7d={profile['new_trades_last_7d']} | recommendation={profile['recommendation']}"
        )
    print(f"- PROMOTE_TO_PRIORITY: {', '.join(result['summary']['PROMOTE_TO_PRIORITY']) or 'none'}")
    print(f"- KEEP_SHADOW: {', '.join(result['summary']['KEEP_SHADOW']) or 'none'}")
    print(f"- REJECT_PROFILE: {', '.join(result['summary']['REJECT_PROFILE']) or 'none'}")
    print(f"- Markdown: {result['markdown_path']}")
    print(f"- JSON: {result['json_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
