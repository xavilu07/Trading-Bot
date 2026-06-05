from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.against_htf_partial_block_design import (  # noqa: E402
    analyze_against_htf_partial_block_design,
    write_against_htf_partial_block_design_report,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="against-htf-partial-block-design")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_against_htf_partial_block_design(data_path=Path(args.data_path))
    report_path = write_against_htf_partial_block_design_report(result, Path(args.reports_path))
    answers = result["answers"]
    print("AGAINST_HTF_PARTIAL_BLOCK_DESIGN")
    print(f"- Baseline: {result['baseline_metrics']}")
    print(f"- Best candidate: {answers['best_candidate']}")
    print(f"- Safest candidate: {answers['safest_candidate']}")
    print(f"- Recommended shadow filter: {answers['recommended_shadow_filter']}")
    print(f"- Next action: {result['recommended_next_action']}")
    print(f"- Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
