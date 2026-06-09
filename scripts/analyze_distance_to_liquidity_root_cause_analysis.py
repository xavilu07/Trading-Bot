from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.distance_to_liquidity_root_cause_analysis import (  # noqa: E402
    analyze_distance_to_liquidity_root_cause,
    write_distance_to_liquidity_root_cause_reports,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="distance-to-liquidity-root-cause-analysis")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_distance_to_liquidity_root_cause(data_path=Path(args.data_path))
    paths = write_distance_to_liquidity_root_cause_reports(result, Path(args.reports_path))
    metrics = result["distance_to_liquidity_penalty_metrics"]
    post_blocks = result["distance_to_liquidity_penalty_after_existing_blocks_metrics"]
    answers = result["answers"]
    print("DISTANCE_TO_LIQUIDITY_ROOT_CAUSE_ANALYSIS")
    print(f"- distance_to_liquidity_penalty: trades={metrics['trades']} | WR={metrics['winrate']}% | PF={metrics['profit_factor']} | TotalR={metrics['total_r']}")
    print(f"- After existing blocks: trades={post_blocks['trades']} | PF={post_blocks['profit_factor']} | TotalR={post_blocks['total_r']}")
    print(f"- Classification: {result['classification']}")
    print(f"- Root cause or correlated: {answers['root_cause_or_correlated']}")
    print(f"- Recommended action: {result['recommended_action']}")
    print(f"- Markdown: {paths['markdown']}")
    print(f"- JSON: {paths['json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
