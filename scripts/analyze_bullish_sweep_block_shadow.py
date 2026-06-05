from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading_signals.research.bullish_sweep_block_shadow import generate_bullish_sweep_block_shadow  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="bullish-sweep-block-shadow")
    bot_data_dir = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", default=str(bot_data_dir / "data"))
    parser.add_argument("--reports-path", default=str(bot_data_dir / "reports"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = generate_bullish_sweep_block_shadow(data_path=Path(args.data_path), reports_path=Path(args.reports_path))
    blocked = result["blocked_bullish_sweep"]
    comparison = result["comparison"]
    print("BULLISH_SWEEP_BLOCK_SHADOW")
    print(f"- Records tracked: {result['records_total']}")
    print(f"- Closed/evaluable: {result['closed_records']}")
    print(f"- Blocked PF: {blocked['profit_factor']}")
    print(f"- Blocked Total R: {blocked['total_r']}")
    print(f"- R avoided: {result['r_avoided']}")
    print(f"- Current global PF: {result['current_global']['profit_factor']}")
    print(f"- Without bullish_sweep PF: {result['without_bullish_sweep']['profit_factor']}")
    print(f"- PF delta: {comparison['pf_delta']}")
    print(f"- Total R delta: {comparison['total_r_delta']}")
    print(f"- Classification: {result['classification']}")
    print(f"- Shadow CSV: {result['shadow_csv_path']}")
    print(f"- Report: {result['report_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
