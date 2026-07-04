from __future__ import annotations

import argparse
import os
from pathlib import Path

from trading_signals.intelligence.historical_intelligence import generate_historical_intelligence


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate historical intelligence reports from paper trades.")
    root = Path(os.getenv("BOT_DATA_DIR", "."))
    parser.add_argument("--data-path", type=Path, default=root / "data")
    parser.add_argument("--reports-path", type=Path, default=root / "reports" / "historical_intelligence")
    args = parser.parse_args()

    result = generate_historical_intelligence(data_path=args.data_path, reports_path=args.reports_path)
    overview = result["overview"]
    print("Historical Intelligence Engine V1")
    print(f"Source: {result['source']}")
    print(f"Reports: {result['reports_path']}")
    print(f"Trades: {overview['trades']}")
    print(f"Closed: {overview['closed']}")
    print(f"Open: {overview['open']}")
    print(f"Winrate: {overview['winrate']:.2f}%")
    print(f"PF: {overview['profit_factor']:.4f}")
    print(f"Total R: {overview['total_r']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
