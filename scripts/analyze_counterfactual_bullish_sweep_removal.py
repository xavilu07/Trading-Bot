from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.counterfactual_bullish_sweep_removal import (  # noqa: E402
    analyze_counterfactual_bullish_sweep_removal,
    write_counterfactual_bullish_sweep_removal_report,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="counterfactual-bullish-sweep-removal")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_counterfactual_bullish_sweep_removal(data_path=Path(args.data_path))
    report_path = write_counterfactual_bullish_sweep_removal_report(result, Path(args.reports_path))
    current = result["current"]
    without = result["without_bullish_sweep"]
    deltas = result["deltas"]
    print("COUNTERFACTUAL_BULLISH_SWEEP_REMOVAL")
    print(f"- PF global actual: {current['profit_factor']}")
    print(f"- PF global sin bullish_sweep: {without['profit_factor']}")
    print(f"- Total R actual: {current['total_r']}")
    print(f"- Total R sin bullish_sweep: {without['total_r']}")
    print(f"- Winrate actual: {current['winrate']}%")
    print(f"- Winrate sin bullish_sweep: {without['winrate']}%")
    print(f"- PF delta: {deltas['pf_delta']}")
    print(f"- Total R delta: {deltas['total_r_delta']}")
    print(f"- Winrate delta: {deltas['winrate_delta']}")
    print(f"- Trades removed: {deltas['trades_removed']}")
    print(f"- Answer: {result['answer']}")
    print(f"- Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
