from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.winner_dna_analysis import analyze_winner_dna, write_winner_dna_report  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="winner-dna-analysis")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    parser.add_argument("--min-trades", type=int, default=5)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_winner_dna(data_path=Path(args.data_path), min_trades=args.min_trades)
    report_path = write_winner_dna_report(result, Path(args.reports_path))
    baseline = result["baseline_metrics"]
    print("WINNER_DNA_ANALYSIS")
    print(f"- Trades: {baseline['trades']}")
    print(f"- WR: {baseline['winrate']}%")
    print(f"- PF: {baseline['profit_factor']}")
    print(f"- Total R: {baseline['total_r']}")
    print(f"- Positive predictors: {len(result['top_positive_predictors'])}")
    print(f"- Negative predictors: {len(result['top_negative_predictors'])}")
    print(f"- Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
