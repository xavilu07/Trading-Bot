from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.winner_dna_2_super_survivor_analysis import (  # noqa: E402
    analyze_winner_dna_2_super_survivor,
    write_winner_dna_2_super_survivor_reports,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="winner-dna-2-super-survivor-analysis")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    parser.add_argument("--min-trades", type=int, default=10)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_winner_dna_2_super_survivor(data_path=Path(args.data_path), min_trades=args.min_trades)
    paths = write_winner_dna_2_super_survivor_reports(result, Path(args.reports_path))
    baseline = result["baseline_after_production_blocks"]
    answers = result["answers"]
    print("WINNER_DNA_2_0_SUPER_SURVIVOR_ANALYSIS")
    print(f"- Baseline after blocks: trades={baseline['trades']} | WR={baseline['winrate']}% | PF={baseline['profit_factor']} | TotalR={baseline['total_r']}")
    print(f"- Super survivors: {len(result['super_survivors'])}")
    print(f"- Multi-factor DNA candidates: {len(result['multi_factor_dna_top_20'])}")
    print(f"- Strongest DNA: {answers['strongest_trading_dna']}")
    print(f"- Recommended action: {result['recommended_action']}")
    print(f"- Markdown: {paths['markdown']}")
    print(f"- JSON: {paths['json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
