from __future__ import annotations

import argparse
import os
from pathlib import Path

from trading_signals.research import run_quant_research


def main() -> int:
    root = Path(os.getenv("BOT_DATA_DIR", "."))
    parser = argparse.ArgumentParser(description="Generate Quant Research Engine V1 reports.")
    parser.add_argument("--data-path", type=Path, default=root / "data")
    parser.add_argument("--reports-path", type=Path, default=root / "reports" / "quant_research")
    parser.add_argument("--min-evidence", type=int, default=10)
    parser.add_argument("--edge-min-evidence", type=int, default=20)
    args = parser.parse_args()

    result = run_quant_research(
        data_path=args.data_path,
        reports_path=args.reports_path,
        min_evidence=args.min_evidence,
        edge_min_evidence=args.edge_min_evidence,
    )
    metrics = result["overview"]["metrics"]
    print("Quant Research Engine V1")
    print(f"Reports: {result['reports_path']}")
    print(f"Trades: {metrics['trades']}")
    print(f"Closed: {metrics['closed']}")
    print(f"Winrate: {metrics['winrate']:.2f}%")
    print(f"PF: {metrics['profit_factor']:.4f}")
    print(f"Total R: {metrics['total_r']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
