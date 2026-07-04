from __future__ import annotations

import argparse
import os
from pathlib import Path

from trading_signals.research.simulator import run_strategy_simulator


def main() -> int:
    root = Path(os.getenv("BOT_DATA_DIR", "."))
    parser = argparse.ArgumentParser(description="Run offline Strategy Simulator V1.")
    parser.add_argument("--data-path", type=Path, default=root / "data")
    parser.add_argument("--reports-path", type=Path, default=root / "reports" / "strategy_simulator")
    parser.add_argument("--min-evidence", type=int, default=20)
    parser.add_argument(
        "--max-conditions",
        type=int,
        default=3,
        help="Maximum filter combination depth to test: 1, 2, or 3.",
    )
    args = parser.parse_args()

    result = run_strategy_simulator(
        data_path=args.data_path,
        reports_path=args.reports_path,
        min_evidence=args.min_evidence,
        max_conditions=args.max_conditions,
    )
    baseline = result["overview"]["baseline"]
    print("Strategy Simulator V1")
    print(f"Reports: {result['reports_path']}")
    print(f"Baseline trades: {baseline['trades']}")
    print(f"Baseline closed: {baseline['closed']}")
    print(f"Baseline winrate: {baseline['winrate']:.2f}%")
    print(f"Baseline PF: {baseline['profit_factor']:.4f}")
    print(f"Baseline Total R: {baseline['total_r']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
