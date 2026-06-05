from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.body_ratio_below_threshold_deep_dive import (  # noqa: E402
    analyze_body_ratio_below_threshold_deep_dive,
    write_body_ratio_below_threshold_deep_dive_report,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="body-ratio-below-threshold-deep-dive")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_body_ratio_below_threshold_deep_dive(data_path=Path(args.data_path))
    report_path = write_body_ratio_below_threshold_deep_dive_report(result, Path(args.reports_path))
    metrics = result["metrics"]
    counterfactual = result["counterfactual_removal"]
    print("BODY_RATIO_BELOW_THRESHOLD_DEEP_DIVE")
    print(f"- Trades: {metrics['trades']}")
    print(f"- WR: {metrics['winrate']}%")
    print(f"- PF: {metrics['profit_factor']}")
    print(f"- Total R: {metrics['total_r']}")
    print(f"- Classification: {result['classification']}")
    print(f"- PF without body_ratio_below_threshold: {counterfactual['without_body_ratio_metrics']['profit_factor']}")
    print(f"- Recommended action: {result['recommended_action']}")
    print(f"- Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
