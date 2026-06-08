from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.bullish_sweep_subgroup_decomposition import (  # noqa: E402
    analyze_bullish_sweep_subgroup_decomposition,
    write_bullish_sweep_subgroup_decomposition_report,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="bullish-sweep-subgroup-decomposition")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze_bullish_sweep_subgroup_decomposition(data_path=Path(args.data_path))
    report_path = write_bullish_sweep_subgroup_decomposition_report(result, Path(args.reports_path))
    metrics = result["metrics"]
    print("BULLISH_SWEEP_SUBGROUP_DECOMPOSITION")
    print(f"- Trades: {metrics['trades']}")
    print(f"- WR: {metrics['winrate']}%")
    print(f"- PF: {metrics['profit_factor']}")
    print(f"- Total R: {metrics['total_r']}")
    print(f"- Classification: {result['classification']}")
    print(f"- Toxic subgroups: {len(result['toxic_subgroups'])}")
    print(f"- Profitable survivors: {len(result['profitable_survivors'])}")
    print(f"- Recommended action: {result['recommended_action']}")
    print(f"- Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
