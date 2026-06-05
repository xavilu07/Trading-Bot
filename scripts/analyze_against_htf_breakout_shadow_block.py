from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.against_htf_breakout_shadow_block import generate_against_htf_breakout_shadow_block  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="against-htf-breakout-shadow-block")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = generate_against_htf_breakout_shadow_block(data_path=Path(args.data_path), reports_path=Path(args.reports_path))
    metrics = result["blocked_group_metrics"]
    print("AGAINST_HTF_BREAKOUT_SHADOW_BLOCK")
    print(f"- Total tracked: {result['records_total']}")
    print(f"- Closed/evaluable: {result['closed_records']}")
    print(f"- PF blocked group: {metrics['profit_factor']}")
    print(f"- Total R blocked group: {metrics['total_r']}")
    print(f"- Hypothetical R avoided: {result['hypothetical_r_avoided']}")
    print(f"- Recommendation: {result['recommendation']}")
    print(f"- Shadow CSV: {result['shadow_csv_path']}")
    print(f"- Report: {result['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
