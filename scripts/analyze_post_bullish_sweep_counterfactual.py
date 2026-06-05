from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.post_bullish_sweep_counterfactual import (  # noqa: E402
    analyze_post_bullish_sweep_counterfactual,
    write_post_bullish_sweep_counterfactual_report,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="post-bullish-sweep-counterfactual")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_post_bullish_sweep_counterfactual(data_path=Path(args.data_path))
    report_path = write_post_bullish_sweep_counterfactual_report(result, Path(args.reports_path))
    current = result["current_metrics"]
    post = result["post_bullish_sweep_metrics"]
    answers = result["answers"]
    print("POST_BULLISH_SWEEP_COUNTERFACTUAL_ANALYSIS")
    print(f"- Current PF: {current['profit_factor']}")
    print(f"- Current Total R: {current['total_r']}")
    print(f"- PF without bullish_sweep: {post['profit_factor']}")
    print(f"- Total R without bullish_sweep: {post['total_r']}")
    print(f"- System profitable after removal: {answers['system_profitable_after_removal']}")
    print(f"- Largest loss contributor: {answers['largest_loss_contributor']}")
    print(f"- Next investigation: {answers['next_investigation_recommendation']}")
    print(f"- Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
