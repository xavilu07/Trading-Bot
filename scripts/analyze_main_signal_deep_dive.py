from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.main_signal_deep_dive import (  # noqa: E402
    analyze_main_signal_deep_dive,
    write_main_signal_deep_dive_report,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="main-signal-deep-dive")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_main_signal_deep_dive(data_path=Path(args.data_path))
    report_path = write_main_signal_deep_dive_report(result, Path(args.reports_path))
    main_metrics = result["main_signal_metrics"]
    secondary_metrics = result["secondary_signal_metrics"]
    counterfactual = result["counterfactual_removal"]
    print("MAIN_SIGNAL_DEEP_DIVE")
    print(f"- MAIN_SIGNAL trades: {main_metrics['trades']} | WR: {main_metrics['winrate']}% | PF: {main_metrics['profit_factor']} | Total R: {main_metrics['total_r']}")
    print(f"- SECONDARY_SIGNAL trades: {secondary_metrics['trades']} | WR: {secondary_metrics['winrate']}% | PF: {secondary_metrics['profit_factor']} | Total R: {secondary_metrics['total_r']}")
    print(f"- Classification: {result['classification']}")
    print(f"- PF without MAIN_SIGNAL: {counterfactual['without_main_signal_metrics']['profit_factor']}")
    print(f"- Recommended action: {result['recommended_action']}")
    print(f"- Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
